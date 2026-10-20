"""CLI del pipeline. Uso: python -m pipeline.cli <comando> [opciones]."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from pipeline.analysis.topic_balance import balance_report, cluster_questions, collect_historical_questions
from pipeline.assemble.run import assemble_exam
from pipeline.audit.docx_parser import ExamParseError, parse_generated_exam
from pipeline.audit.exam_audit import audit_exam
from pipeline.audit.report import write_audit_report
from pipeline.config import BANCO_EXAMENES_PATH, RAW_DIR, get_settings
from pipeline.difficulty.run import print_profile, profile_file
from pipeline.generation.run import generate_exam
from pipeline.ingest.extractors import extract_text
from pipeline.ingest.run import _detect_doc_type, _detect_grade
from pipeline.ingest.run import ingest_all as _ingest_all
from pipeline.ml.bloom_classifier import build_dataset as _build_bank_dataset
from pipeline.ml.bloom_classifier import predict_exam_file as _predict_exam_file
from pipeline.ml.bloom_classifier import run_full_report as _run_ml_report
from pipeline.ml.bloom_classifier import save_bank as _save_bank
from pipeline.standards.loader import get_standards_for
from pipeline.tagging.run import tag_all as _tag_all
from pipeline.validation.run import validate_exam

app = typer.Typer(help="Pipeline de generación de exámenes/lecciones")

_SUBJECT_MAP = {
    "historia": "history",
    "history": "history",
    "tecnologia": "technology",
    "tecnología": "technology",
    "technology": "technology",
}


# Traduce lo que escribió el usuario ("historia"/"tecnologia"/etc.) al nombre interno
# de la materia ("history"/"technology"); error claro si no reconoce la palabra.
def _resolve_subject(materia: str) -> str:
    key = materia.strip().lower()
    if key not in _SUBJECT_MAP:
        raise typer.BadParameter(f"Materia desconocida: {materia!r} (usa historia | tecnologia)")
    return _SUBJECT_MAP[key]


@app.command()
def ingest():
    """Extrae texto de data/raw/ y lo normaliza en data/processed/documents/."""
    report = _ingest_all()
    typer.echo(f"Documentos ingeridos: {report.ingested}")
    if report.skipped:
        typer.echo(f"Omitidos ({len(report.skipped)}):")
        for item in report.skipped:
            typer.echo(f"  - {item}")


@app.command()
def tag():
    """Etiqueta los documentos ingeridos contra los estándares curriculares."""
    summary = _tag_all()
    for group, counts in summary.items():
        typer.echo(f"\n{group}")
        for code, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            typer.echo(f"  {code}: cubierto en {n} documento(s)")


@app.command()
def profile(archivo: str):
    """Construye la tabla de especificaciones (Bloom x DOK) de un examen puntual."""
    exam_profile, _questions = profile_file(Path(archivo))
    print_profile(exam_profile)


# Cuando no se pasa --perfil-de, busca en data/raw/ el primer examen que calce con esa
# materia/grado, para usarlo como perfil de dificultad objetivo.
def _pick_reference_exam(subject: str, grade: int) -> Path:
    subject_dir = RAW_DIR / subject
    for file_path in sorted(subject_dir.rglob("*")):
        if not file_path.is_file() or file_path.suffix.lower() not in (".docx", ".pdf", ".txt"):
            continue
        group = file_path.parent.name
        if _detect_doc_type(file_path.name, group) != "exam":
            continue
        if _detect_grade(file_path.name, group) == grade:
            return file_path
    raise FileNotFoundError(f"No se encontró un examen de referencia para materia={subject} grado={grade}")


@app.command()
def generate(
    materia: str = typer.Option(..., "--materia"),
    grado: int = typer.Option(..., "--grado"),
    tema: str | None = typer.Option(None, "--tema", help="Nombre del tema, usado en el nombre del archivo .docx (ej. 'Grito de Lares'). Si no se da, se toma del examen de referencia."),
    perfil_de: str | None = typer.Option(None, "--perfil-de", help="Ruta a un examen pasado del cual copiar el perfil de dificultad objetivo."),
):
    """Genera, valida y ensambla un examen nuevo para materia/grado dado un perfil objetivo."""
    subject = _resolve_subject(materia)
    reference_path = Path(perfil_de) if perfil_de else _pick_reference_exam(subject, grado)
    target_profile, _historical_questions = profile_file(reference_path, subject=subject, grade=grado)
    typer.echo(f"Perfil objetivo tomado de: {reference_path}")
    print_profile(target_profile)

    tema_resuelto = tema or reference_path.stem
    reference_text = extract_text(reference_path)
    try:
        exam = generate_exam(subject, grado, target_profile, tema=tema_resuelto, reference_text=reference_text)
    except RuntimeError as exc:
        typer.echo(f"\nERROR: {exc}")
        typer.echo("Prueba de nuevo (los modelos locales pequeños no siempre responden igual) o cambia de proveedor en .env.")
        raise typer.Exit(code=1)

    exam = validate_exam(exam)

    settings = get_settings()
    audit = audit_exam(exam, reference_text=reference_text, embedding_model=settings.embedding_model)
    typer.echo("\nAuditoría:")
    for criterio in audit.criterios:
        marca = "[OK]" if criterio.aprobado else "[FALLA]"
        typer.echo(f"  {marca} {criterio.criterio}")
    typer.echo("APROBADO GENERAL" if audit.aprobado_general else "NO APROBADO (ver detalle en el .docx)")

    out_path = assemble_exam(exam, tema=tema_resuelto, audit=audit, reference_path=str(reference_path))
    typer.echo(f"\nExamen generado en: {out_path}")


@app.command()
def audit(
    archivo: str,
    perfil_de: str | None = typer.Option(
        None, "--perfil-de", help="Ruta al material de referencia, si no quedó guardada en el .docx."
    ),
):
    """Audita un examen .docx ya generado (sin volver a generarlo)."""
    path = Path(archivo)
    try:
        exam, reference_path_in_doc, tema = parse_generated_exam(path)
    except ExamParseError as exc:
        typer.echo(f"ERROR: {exc}")
        raise typer.Exit(code=1)

    reference_path_str = perfil_de or reference_path_in_doc
    if reference_path_str:
        typer.echo(f"Material de referencia: {reference_path_str}")
        reference_text = extract_text(Path(reference_path_str))
    else:
        reference_text = ""
        typer.echo(
            "Aviso: no se encontró la ruta del material de referencia (ni guardada en el "
            ".docx ni dada con --perfil-de) — el criterio de cobertura de temas no se puede evaluar."
        )

    settings = get_settings()
    report = audit_exam(exam, reference_text=reference_text, embedding_model=settings.embedding_model)

    typer.echo(f"\nAuditoría de: {archivo}")
    for criterio in report.criterios:
        marca = "[OK]" if criterio.aprobado else "[FALLA]"
        typer.echo(f"  {marca} {criterio.criterio}")
        typer.echo(f"      {criterio.detalle}")
    typer.echo("APROBADO GENERAL" if report.aprobado_general else "NO APROBADO")

    if any(q.part_type == "opcion_multiple" and q.correct_option_index is None for q in exam.questions):
        typer.echo(
            "\nAviso: este .docx no guarda cuál opción es la correcta (por diseño, para no "
            "revelarla en el examen) — 'Sin fuga de respuesta' no se pudo confirmar para sus "
            "preguntas de opción múltiple."
        )

    report_path = write_audit_report(exam, report, tema=tema or path.stem, reference_path=reference_path_str)
    typer.echo(f"\nReporte de auditoría guardado en: {report_path}")


@app.command(name="topic-balance")
def topic_balance(
    materia: str = typer.Option(..., "--materia"),
    grado: int = typer.Option(..., "--grado"),
):
    """Agrupa las preguntas históricas por similaridad (k-means + PCA) y marca qué
    estándares están sobre/sub-representados en el banco real."""
    subject = _resolve_subject(materia)
    settings = get_settings()

    questions = collect_historical_questions(subject, grado)
    typer.echo(f"Preguntas históricas encontradas: {len(questions)}")

    standards = get_standards_for(subject, grado)
    cluster_result = cluster_questions(questions, settings.embedding_model, standards)
    report = balance_report(cluster_result, standards)

    if report["estado"] != "ok":
        typer.echo(report["detalle"])
        return

    typer.echo(f"Grupos detectados: {report['numero_de_grupos_detectados']} (promedio {report['promedio_preguntas_por_grupo']} preguntas/grupo)\n")
    for grupo_id, info in report["por_grupo"].items():
        typer.echo(
            f"  [{info['estado']}] {grupo_id} -> más cercano a {info['estándar_más_cercano']} "
            f"({info['estándar']}): {info['preguntas_en_cluster']} pregunta(s)"
        )
        for ejemplo in info["ejemplos"]:
            typer.echo(f"      - {ejemplo}")

    if report["estandares_sin_grupo_cercano"]:
        typer.echo("\nEstándares sin ningún grupo cercano (posible vacío total de contenido):")
        for nombre in report["estandares_sin_grupo_cercano"]:
            typer.echo(f"  - {nombre}")


@app.command(name="ml-bloom-eval")
def ml_bloom_eval():
    """Entrena y evalúa (con rigor: CV agrupada por examen + búsqueda de hiperparámetros)
    un clasificador supervisado de nivel Bloom a partir del texto, comparado contra línea
    base y árbol/Random Forest/boosting. Ver limitaciones en pipeline/ml/bloom_classifier.py."""
    report = _run_ml_report()

    if report["estado"] != "ok":
        typer.echo(report["detalle"])
        return

    typer.echo(f"Preguntas históricas usadas: {report['total_preguntas']}")
    typer.echo(f"Por nivel Bloom: {report['conteos_por_etiqueta']}")
    typer.echo(f"Por grado: {report['conteos_por_grado']}\n")

    comparacion = report["comparacion_de_modelos"]
    typer.echo(f"Comparación de modelos (F1-macro, validación cruzada agrupada por examen, {comparacion['n_splits_usados']} particiones):")
    for nombre, datos in sorted(comparacion["modelos"].items(), key=lambda kv: -kv[1]["f1_macro_cv"]):
        marca = " <- GANADOR" if nombre == comparacion["ganador"] else ""
        typer.echo(f"  {nombre}: {datos['f1_macro_cv']}{marca}")
        if datos["mejores_hiperparametros"]:
            typer.echo(f"      hiperparámetros: {datos['mejores_hiperparametros']}")

    test = report["evaluacion_en_test"]
    typer.echo(f"\nEvaluación del ganador ({test['modelo_evaluado']}) en examenes nunca vistos en entrenamiento:")
    typer.echo(f"  Train: {test['preguntas_train']} preguntas de {test['examenes_train']} exámenes")
    typer.echo(f"  Test:  {test['preguntas_test']} preguntas de {test['examenes_test']} exámenes")
    typer.echo(f"  Sin fuga de datos confirmada: {test['sin_fuga_confirmada']}")
    typer.echo(f"  Clases: {test['clases']}")
    typer.echo(f"  Matriz de confusión: {test['matriz_de_confusion']}")
    typer.echo(f"  Accuracy por materia: {test['accuracy_por_materia']}")
    typer.echo(f"  Accuracy por grado: {test['accuracy_por_grado']}")


@app.command(name="banco-build")
def banco_build():
    """Construye el banco de preguntas etiquetadas (materia + Bloom/DOK + tipo de parte) a
    partir de los exámenes/reviews ya ingeridos, y lo guarda en data/processed/banco_examenes.jsonl."""
    items = _build_bank_dataset()
    _save_bank(items, BANCO_EXAMENES_PATH)

    por_materia = {s: sum(1 for i in items if i.subject == s) for s in sorted({i.subject for i in items})}
    por_bloom = {b: sum(1 for i in items if i.bloom_level == b) for b in sorted({i.bloom_level for i in items})}
    por_parte = {p: sum(1 for i in items if i.part_type == p) for p in sorted({i.part_type for i in items})}

    typer.echo(f"Banco guardado en {BANCO_EXAMENES_PATH} ({len(items)} preguntas)")
    typer.echo(f"Por materia: {por_materia}")
    typer.echo(f"Por nivel Bloom: {por_bloom}")
    typer.echo(f"Por tipo de parte: {por_parte}")


@app.command(name="ml-subject-eval")
def ml_subject_eval():
    """Igual que ml-bloom-eval pero entrena un clasificador de MATERIA (history/technology) en
    vez de nivel Bloom. LIMITACIÓN: con solo 2 materias de vocabulario muy distinto, el accuracy
    global sale trivialmente alto (~98%); el F1-macro (métrica real de selección de modelo) es
    más modesto porque las materias están muy desbalanceadas (87 preguntas de technology vs 603
    de history) — no es un logro de ML, refleja el tamaño/balance actual del banco."""
    report = _run_ml_report(label_attr="subject")

    if report["estado"] != "ok":
        typer.echo(report["detalle"])
        return

    typer.echo(f"Preguntas históricas usadas: {report['total_preguntas']}")
    typer.echo(f"Por materia: {report['conteos_por_etiqueta']}")
    typer.echo(f"Por grado: {report['conteos_por_grado']}\n")

    comparacion = report["comparacion_de_modelos"]
    typer.echo(f"Comparación de modelos (F1-macro, validación cruzada agrupada por examen, {comparacion['n_splits_usados']} particiones):")
    for nombre, datos in sorted(comparacion["modelos"].items(), key=lambda kv: -kv[1]["f1_macro_cv"]):
        marca = " <- GANADOR" if nombre == comparacion["ganador"] else ""
        typer.echo(f"  {nombre}: {datos['f1_macro_cv']}{marca}")
        if datos["mejores_hiperparametros"]:
            typer.echo(f"      hiperparámetros: {datos['mejores_hiperparametros']}")

    test = report["evaluacion_en_test"]
    typer.echo(f"\nEvaluación del ganador ({test['modelo_evaluado']}) en examenes nunca vistos en entrenamiento:")
    typer.echo(f"  Train: {test['preguntas_train']} preguntas de {test['examenes_train']} exámenes")
    typer.echo(f"  Test:  {test['preguntas_test']} preguntas de {test['examenes_test']} exámenes")
    typer.echo(f"  Sin fuga de datos confirmada: {test['sin_fuga_confirmada']}")
    typer.echo(f"  Clases: {test['clases']}")
    typer.echo(f"  Matriz de confusión: {test['matriz_de_confusion']}")
    typer.echo(f"  Accuracy por materia: {test['accuracy_por_materia']}")
    typer.echo(f"  Accuracy por grado: {test['accuracy_por_grado']}")


# El texto de un documento puede traer cualquier caracter Unicode (ej. emojis en un reporte
# de auditoría embebido en un .docx generado); la consola de Windows (cp1252) no puede
# codificarlos todos y typer.echo revienta en vez de solo mostrarlos mal — se reemplazan los
# que no entren en el encoding real de la consola para no tumbar el comando por eso.
def _echo_safe(text: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    typer.echo(text.encode(encoding, errors="replace").decode(encoding))


@app.command(name="predecir-examen")
def predecir_examen(
    ruta_archivo: str = typer.Argument(..., help="Archivo del examen a predecir (.docx/.pdf/.pptx/.xlsx/.txt)"),
    objetivo: str = typer.Option("dificultad", "--objetivo", help="'materia' o 'dificultad'"),
):
    """Entrena el clasificador ganador con el banco actual (reentrena desde cero, tarda ~1 min)
    y predice materia o dificultad para cada pregunta de un examen nuevo. Es inferencia real
    sobre un archivo — no una evaluación con train/test separado (para eso: ml-bloom-eval /
    ml-subject-eval)."""
    label_attr = "subject" if objetivo.strip().lower() in ("materia", "subject") else "bloom_level"
    resultado = _predict_exam_file(Path(ruta_archivo), label_attr=label_attr)

    typer.echo(f"Modelo usado: {resultado['modelo_usado']} (objetivo: {objetivo})")
    if not resultado["predicciones"]:
        typer.echo("No se detectaron preguntas numeradas en el archivo.")
        return

    for item in resultado["predicciones"]:
        pregunta_corta = item["pregunta"].replace("\n", " ")[:120]
        _echo_safe(f"\n[{item['prediccion']}] {pregunta_corta}")


@app.command(name="run-all")
def run_all(
    materia: str = typer.Option(..., "--materia"),
    grado: int = typer.Option(..., "--grado"),
    tema: str | None = typer.Option(None, "--tema"),
):
    """Corre ingesta -> etiquetado -> generación -> validación -> ensamblado para materia/grado."""
    ingest()
    tag()
    generate(materia=materia, grado=grado, tema=tema, perfil_de=None)


if __name__ == "__main__":
    app()
