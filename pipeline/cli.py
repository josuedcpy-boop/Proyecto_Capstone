"""CLI del pipeline. Uso: python -m pipeline.cli <comando> [opciones]."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from pipeline.analysis.topic_balance import balance_report, cluster_questions, collect_historical_questions
from pipeline.config import BANCO_EXAMENES_PATH, get_settings
from pipeline.difficulty.run import print_profile, profile_file
from pipeline.ingest.run import ingest_all as _ingest_all
from pipeline.ml.bloom_classifier import build_dataset as _build_bank_dataset
from pipeline.ml.bloom_classifier import build_document_dataset as _build_document_dataset
from pipeline.ml.bloom_classifier import predict_exam_file as _predict_exam_file
from pipeline.ml.bloom_classifier import predict_exam_subject as _predict_exam_subject
from pipeline.ml.bloom_classifier import run_full_report as _run_ml_report
from pipeline.ml.bloom_classifier import save_bank as _save_bank
from pipeline.ml.standards_classifier import evaluate_standards_model as _evaluate_standards_model
from pipeline.ml.standards_classifier import predict_exam_standards as _predict_exam_standards
from pipeline.standards.loader import get_standards_for
from pipeline.tagging.run import tag_all as _tag_all

app = typer.Typer(help="Pipeline de identificación de materia y estándares de exámenes")

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
    """Entrena/evalúa un clasificador de MATERIA (history/technology) a nivel de EXAMEN
    COMPLETO (una fila por documento, no por pregunta — materia no varía dentro de un mismo
    examen). A diferencia de Bloom, esta etiqueta sí es verdad de terreno real (viene de la
    carpeta de origen en data/raw/), no una pseudo-etiqueta. LIMITACIÓN: con solo 2 materias
    de vocabulario muy distinto y pocos documentos (96 historia / 34 tecnología tipo
    examen/review), el accuracy global sale trivialmente alto; el F1-macro es más modesto
    por el desbalance entre materias y el tamaño chico del banco."""
    report = _run_ml_report(label_attr="subject", items=_build_document_dataset())

    if report["estado"] != "ok":
        typer.echo(report["detalle"])
        return

    typer.echo(f"Exámenes históricos usados: {report['total_preguntas']}")
    typer.echo(f"Por materia: {report['conteos_por_etiqueta']}")
    typer.echo(f"Por grado: {report['conteos_por_grado']}\n")

    comparacion = report["comparacion_de_modelos"]
    typer.echo(f"Comparación de modelos (F1-macro, validación cruzada, {comparacion['n_splits_usados']} particiones):")
    for nombre, datos in sorted(comparacion["modelos"].items(), key=lambda kv: -kv[1]["f1_macro_cv"]):
        marca = " <- GANADOR" if nombre == comparacion["ganador"] else ""
        typer.echo(f"  {nombre}: {datos['f1_macro_cv']}{marca}")
        if datos["mejores_hiperparametros"]:
            typer.echo(f"      hiperparámetros: {datos['mejores_hiperparametros']}")

    test = report["evaluacion_en_test"]
    typer.echo(f"\nEvaluación del ganador ({test['modelo_evaluado']}) en exámenes nunca vistos en entrenamiento:")
    typer.echo(f"  Train: {test['examenes_train']} exámenes")
    typer.echo(f"  Test:  {test['examenes_test']} exámenes")
    typer.echo(f"  Sin fuga de datos confirmada: {test['sin_fuga_confirmada']}")
    typer.echo(f"  Clases: {test['clases']}")
    typer.echo(f"  Matriz de confusión: {test['matriz_de_confusion']}")
    typer.echo(f"  Accuracy por materia: {test['accuracy_por_materia']}")
    typer.echo(f"  Accuracy por grado: {test['accuracy_por_grado']}")


@app.command(name="ml-estandares-eval")
def ml_estandares_eval(materia: str = typer.Option(..., "--materia")):
    """Entrena/evalúa el clasificador multi-etiqueta de estándares curriculares para una
    materia. LIMITACIÓN HONESTA: las etiquetas son pseudo-etiquetas del etiquetado por
    embeddings (pipeline/tagging/run.py), no juicio humano — ver pipeline/ml/standards_classifier.py."""
    subject = _resolve_subject(materia)
    report = _evaluate_standards_model(subject)

    if report["estado"] != "ok":
        typer.echo(report["detalle"])
        return

    typer.echo(f"Documentos tipo examen/review usados: {report['total_documentos']} (train {report['documentos_train']} / test {report['documentos_test']})")
    typer.echo(f"Códigos de estándar: {report['codigos']}")
    typer.echo(f"Soporte por código (documentos positivos): {report['soporte_por_codigo']}\n")
    typer.echo(f"F1 micro: {report['f1_micro']}  F1 macro: {report['f1_macro']}")
    for codigo in report["codigos"]:
        metrica = report["reporte_por_codigo"][codigo]
        typer.echo(f"  {codigo}: precision={metrica['precision']:.2f} recall={metrica['recall']:.2f} f1={metrica['f1-score']:.2f} (soporte={int(metrica['support'])})")


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
    objetivo: str = typer.Option("materia", "--objetivo", help="'materia', 'estandares' o 'dificultad'"),
    materia: str | None = typer.Option(None, "--materia", help="Solo para --objetivo estandares: si no se da, se infiere automáticamente con el clasificador de materia."),
):
    """Identifica materia y/o estándares de un examen nuevo (o su perfil Bloom/DOK por
    pregunta), entrenando el clasificador correspondiente con el banco actual (reentrena
    desde cero cada vez, tarda ~1 min). Es inferencia real sobre un archivo — no una
    evaluación con train/test separado (para eso: ml-subject-eval / ml-estandares-eval /
    ml-bloom-eval)."""
    objetivo_normalizado = objetivo.strip().lower()

    if objetivo_normalizado in ("materia", "subject"):
        resultado = _predict_exam_subject(Path(ruta_archivo))
        typer.echo(f"Modelo usado: {resultado['modelo_usado']}")
        typer.echo(f"Materia predicha: {resultado['materia_predicha']} (confianza: {resultado['confianza']})")
        return

    if objetivo_normalizado in ("estandares", "estándares", "standards"):
        subject = _resolve_subject(materia) if materia else _predict_exam_subject(Path(ruta_archivo))["materia_predicha"]
        typer.echo(f"Materia usada para predecir estándares: {subject}")
        resultado = _predict_exam_standards(Path(ruta_archivo), subject=subject)
        if not resultado["estandares_predichos"]:
            typer.echo(resultado["aviso"])
            return
        for item in resultado["estandares_predichos"]:
            typer.echo(f"  {item['estandar']}: probabilidad {item['probabilidad']}")
        return

    resultado = _predict_exam_file(Path(ruta_archivo), label_attr="bloom_level")
    typer.echo(f"Modelo usado: {resultado['modelo_usado']} (objetivo: dificultad)")
    if not resultado["predicciones"]:
        typer.echo("No se detectaron preguntas numeradas en el archivo.")
        return
    for item in resultado["predicciones"]:
        pregunta_corta = item["pregunta"].replace("\n", " ")[:120]
        _echo_safe(f"\n[{item['prediccion']}] {pregunta_corta}")


if __name__ == "__main__":
    app()
