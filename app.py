"""Interfaz web simple (Streamlit) para el pipeline — generar/auditar exámenes y ver el
balance de temas desde el navegador, sin usar la terminal. Reutiliza exactamente las mismas
funciones que pipeline/cli.py y mcp_server.py; no duplica lógica.

Correr: streamlit run app.py
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from pipeline.analysis.topic_balance import balance_report, cluster_questions, collect_historical_questions
from pipeline.assemble.run import assemble_exam
from pipeline.audit.docx_parser import ExamParseError, parse_generated_exam
from pipeline.audit.exam_audit import audit_exam
from pipeline.audit.report import write_audit_report
from pipeline.cli import _resolve_subject
from pipeline.config import EXAMEN_GENERADO_DIR, RAW_DIR, get_settings
from pipeline.difficulty.run import profile_file
from pipeline.generation.run import generate_exam
from pipeline.ingest.extractors import extract_text
from pipeline.ingest.run import _detect_doc_type, _detect_grade, ingest_all
from pipeline.ml.bloom_classifier import run_full_report as run_ml_report
from pipeline.standards.loader import get_standards_for
from pipeline.tagging.run import tag_all
from pipeline.validation.run import validate_exam

st.set_page_config(page_title="Generador de Exámenes", page_icon="📝", layout="wide")
st.title("Generador y Auditor de Exámenes — Capstone MAI540")

_GRADOS = [5, 6, 7, 8]
_MATERIAS = ["historia", "tecnologia"]


# Busca en data/raw/ todos los exámenes que calcen con esa materia/grado, para que el
# usuario elija uno de una lista en vez de escribir la ruta a mano.
def _list_candidate_exams(subject: str, grado: int) -> list[Path]:
    subject_dir = RAW_DIR / subject
    if not subject_dir.exists():
        return []
    candidates = []
    for file_path in sorted(subject_dir.rglob("*")):
        if not file_path.is_file() or file_path.suffix.lower() not in (".docx", ".pdf", ".txt"):
            continue
        group = file_path.parent.name
        if _detect_doc_type(file_path.name, group) != "exam":
            continue
        if _detect_grade(file_path.name, group) == grado:
            candidates.append(file_path)
    return candidates


# Convierte la lista de criterios de auditoría al formato de filas que espera st.table.
def _audit_table(criterios) -> list[dict]:
    return [
        {"Estado": "OK" if c.aprobado else "FALLA", "Criterio": c.criterio, "Detalle": c.detalle}
        for c in criterios
    ]


tab_generar, tab_auditar, tab_balance, tab_ml, tab_mantenimiento = st.tabs(
    ["Generar examen", "Auditar examen", "Balance de temas", "Modelo de dificultad (ML)", "Mantenimiento"]
)

with tab_generar:
    st.subheader("Generar un examen nuevo")
    col1, col2 = st.columns(2)
    materia = col1.selectbox("Materia", _MATERIAS, key="gen_materia")
    grado = col2.selectbox("Grado", _GRADOS, key="gen_grado")
    tema = st.text_input("Tema (opcional — si no lo pones, se usa el nombre del examen de referencia)", key="gen_tema")

    subject_preview = _resolve_subject(materia)
    candidatos = _list_candidate_exams(subject_preview, grado)
    opciones = ["(automático — el primero que se encuentre)"] + [str(p) for p in candidatos]
    perfil_elegido = st.selectbox(f"Examen de referencia ({len(candidatos)} encontrados)", opciones, key="gen_perfil")

    if st.button("Generar examen", type="primary"):
        with st.spinner("Generando (puede tardar si el proveedor de LLM es local)..."):
            try:
                subject = _resolve_subject(materia)
                reference_path = (
                    Path(perfil_elegido) if perfil_elegido != opciones[0] else candidatos[0] if candidatos else None
                )
                if reference_path is None:
                    raise FileNotFoundError(f"No se encontró un examen de referencia para {subject}/{grado}.")

                target_profile, _hist = profile_file(reference_path, subject=subject, grade=grado)
                tema_resuelto = tema or reference_path.stem
                reference_text = extract_text(reference_path)

                exam = generate_exam(subject, grado, target_profile, tema=tema_resuelto, reference_text=reference_text)
                exam = validate_exam(exam)

                settings = get_settings()
                audit = audit_exam(exam, reference_text=reference_text, embedding_model=settings.embedding_model)
                out_path = assemble_exam(exam, tema=tema_resuelto, audit=audit, reference_path=str(reference_path))

                st.session_state["gen_resultado"] = {
                    "out_path": out_path,
                    "reference_path": reference_path,
                    "target_profile": target_profile,
                    "audit": audit,
                    "exam": exam,
                }
            except Exception as exc:  # noqa: BLE001
                st.session_state["gen_resultado"] = None
                st.error(f"No se pudo generar el examen: {exc}")

    resultado = st.session_state.get("gen_resultado")
    if resultado:
        st.success(f"Examen generado: {resultado['out_path']}")
        st.caption(f"Material de referencia usado: {resultado['reference_path']}")

        audit = resultado["audit"]
        st.markdown(f"**Auditoría: {'APROBADO' if audit.aprobado_general else 'NO APROBADO'}**")
        st.table(_audit_table(audit.criterios))

        with st.expander(f"Ver las {len(resultado['exam'].questions)} pregunta(s) generada(s)"):
            for n, q in enumerate(resultado["exam"].questions, start=1):
                st.markdown(f"**{n}.** ({q.bloom_level} / DOK{q.dok_level} / {q.part_type} / {q.points}pts)")
                st.write(q.text)
                if q.options:
                    for letter, option in zip("abcd", q.options):
                        st.write(f"   {letter}) {option}")

        docx_bytes = Path(resultado["out_path"]).read_bytes()
        st.download_button(
            "Descargar .docx",
            data=docx_bytes,
            file_name=Path(resultado["out_path"]).name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

with tab_auditar:
    st.subheader("Auditar un examen ya generado")
    existentes = sorted(EXAMEN_GENERADO_DIR.glob("*.docx")) if EXAMEN_GENERADO_DIR.exists() else []
    if not existentes:
        st.info("No hay archivos en Examen_generado/ todavía — genera uno primero en la otra pestaña.")
    else:
        archivo = st.selectbox("Archivo", [str(p) for p in existentes], key="audit_archivo")
        perfil_override = st.text_input(
            "Ruta al material de referencia (opcional — por defecto usa la guardada en el .docx)",
            key="audit_perfil",
        )

        if st.button("Auditar", type="primary"):
            try:
                exam, reference_path_in_doc, tema = parse_generated_exam(Path(archivo))
                reference_path_str = perfil_override or reference_path_in_doc
                reference_text = extract_text(Path(reference_path_str)) if reference_path_str else ""

                settings = get_settings()
                report = audit_exam(exam, reference_text=reference_text, embedding_model=settings.embedding_model)
                report_path = write_audit_report(
                    exam, report, tema=tema or Path(archivo).stem, reference_path=reference_path_str
                )
                st.session_state["audit_resultado"] = {
                    "report": report,
                    "reference_path_str": reference_path_str,
                    "exam": exam,
                    "report_path": report_path,
                }
            except ExamParseError as exc:
                st.session_state["audit_resultado"] = None
                st.error(str(exc))

        resultado_audit = st.session_state.get("audit_resultado")
        if resultado_audit:
            report = resultado_audit["report"]
            st.caption(f"Material de referencia: {resultado_audit['reference_path_str'] or '(ninguno)'}")
            st.success(f"Reporte de auditoría guardado en: {resultado_audit['report_path']}")
            st.markdown(f"**{'APROBADO' if report.aprobado_general else 'NO APROBADO'}**")
            st.table(_audit_table(report.criterios))

            if any(
                q.part_type == "opcion_multiple" and q.correct_option_index is None
                for q in resultado_audit["exam"].questions
            ):
                st.warning(
                    "Este .docx no guarda cuál opción es la correcta (por diseño) — 'sin fuga "
                    "de respuesta' no se pudo confirmar para sus preguntas de opción múltiple."
                )

with tab_balance:
    st.subheader("Balance de temas (k-means + PCA sobre el banco histórico)")
    col1, col2 = st.columns(2)
    materia_b = col1.selectbox("Materia", _MATERIAS, key="balance_materia")
    grado_b = col2.selectbox("Grado", _GRADOS, key="balance_grado")

    if st.button("Analizar balance de temas", type="primary"):
        with st.spinner("Agrupando preguntas históricas..."):
            subject = _resolve_subject(materia_b)
            settings = get_settings()
            questions = collect_historical_questions(subject, grado_b)
            standards = get_standards_for(subject, grado_b)
            cluster_result = cluster_questions(questions, settings.embedding_model, standards)
            st.session_state["balance_resultado"] = balance_report(cluster_result, standards)
            st.session_state["balance_n_preguntas"] = len(questions)

    resultado_balance = st.session_state.get("balance_resultado")
    if resultado_balance:
        st.caption(f"Preguntas históricas analizadas: {st.session_state.get('balance_n_preguntas', '?')}")
        if resultado_balance["estado"] != "ok":
            st.info(resultado_balance["detalle"])
        else:
            st.write(
                f"Grupos detectados: {resultado_balance['numero_de_grupos_detectados']} "
                f"(promedio {resultado_balance['promedio_preguntas_por_grupo']} preguntas/grupo)"
            )
            filas = [
                {
                    "Grupo": grupo_id,
                    "Estado": info["estado"],
                    "Estándar más cercano": f"{info['estándar_más_cercano']} ({info['estándar']})",
                    "Preguntas en el grupo": info["preguntas_en_cluster"],
                }
                for grupo_id, info in resultado_balance["por_grupo"].items()
            ]
            st.table(filas)

            if resultado_balance["estandares_sin_grupo_cercano"]:
                st.warning(
                    "Estándares sin ningún grupo cercano (posible vacío de contenido): "
                    + ", ".join(resultado_balance["estandares_sin_grupo_cercano"])
                )

with tab_ml:
    st.subheader("Clasificador supervisado (entregable del rúbrico de ML)")

    objetivo_label = st.radio("Objetivo a predecir", ["Dificultad (nivel Bloom)", "Materia"], horizontal=True)
    label_attr = "bloom_level" if objetivo_label == "Dificultad (nivel Bloom)" else "subject"

    if label_attr == "bloom_level":
        st.warning(
            "Limitación honesta: las etiquetas de entrenamiento vienen de la heurística de reglas "
            "del propio proyecto (pipeline/difficulty/bloom_dok_rules.py), no de jueces humanos ni "
            "de datos reales de estudiantes. Este modelo mide si se puede *aprender* ese criterio "
            "desde el texto — no reemplaza las reglas en el pipeline de generación/auditoría."
        )
    else:
        st.warning(
            "Limitación honesta: solo hay 2 materias locales (history/technology) con vocabulario "
            "muy distinto, así que el accuracy global sale trivialmente alto (~98%). El F1-macro "
            "(la métrica real de selección de modelo) es más modesto porque las materias están "
            "muy desbalanceadas (87 preguntas de technology vs 603 de history) — no es un logro "
            "de ML, refleja el tamaño/balance actual del banco."
        )

    if st.button("Entrenar y evaluar", type="primary"):
        with st.spinner("Entrenando 5 modelos con validación cruzada agrupada por examen..."):
            st.session_state["ml_resultado"] = run_ml_report(label_attr=label_attr)
            st.session_state["ml_objetivo_label"] = objetivo_label

    resultado_ml = st.session_state.get("ml_resultado")
    if resultado_ml:
        if resultado_ml["estado"] != "ok":
            st.info(resultado_ml["detalle"])
        else:
            etiqueta_columna = "Por nivel Bloom" if st.session_state.get("ml_objetivo_label") == "Dificultad (nivel Bloom)" else "Por materia"
            st.caption(f"Preguntas históricas usadas: {resultado_ml['total_preguntas']}")
            col1, col2 = st.columns(2)
            col1.write(f"**{etiqueta_columna}**")
            col1.table(resultado_ml["conteos_por_etiqueta"])
            col2.write("**Por grado**")
            col2.table(resultado_ml["conteos_por_grado"])

            comparacion = resultado_ml["comparacion_de_modelos"]
            st.write(f"**Comparación de modelos** (F1-macro, CV agrupada por examen, {comparacion['n_splits_usados']} particiones)")
            filas_modelos = [
                {
                    "Modelo": nombre + (" (ganador)" if nombre == comparacion["ganador"] else ""),
                    "F1-macro (CV)": datos["f1_macro_cv"],
                    "Hiperparámetros": datos["mejores_hiperparametros"] or "—",
                }
                for nombre, datos in sorted(comparacion["modelos"].items(), key=lambda kv: -kv[1]["f1_macro_cv"])
            ]
            st.table(filas_modelos)

            test = resultado_ml["evaluacion_en_test"]
            st.write(f"**Evaluación de '{test['modelo_evaluado']}' en exámenes nunca vistos en entrenamiento**")
            st.write(
                f"Train: {test['preguntas_train']} preguntas de {test['examenes_train']} exámenes · "
                f"Test: {test['preguntas_test']} preguntas de {test['examenes_test']} exámenes"
            )
            if test["sin_fuga_confirmada"]:
                st.success("Sin fuga de datos confirmada: ningún examen quedó repartido entre train y test.")
            else:
                st.error("¡Fuga de datos detectada! Algún examen quedó repartido entre train y test.")

            st.write("Matriz de confusión (filas = clase real, columnas = clase predicha):")
            st.table(
                [
                    {"Clase real": clase, **dict(zip(test["clases"], fila))}
                    for clase, fila in zip(test["clases"], test["matriz_de_confusion"])
                ]
            )

            col3, col4 = st.columns(2)
            col3.write("**Accuracy por materia**")
            col3.table(
                [{"Materia": k, "Accuracy": v["accuracy"], "Preguntas": v["total"]} for k, v in test["accuracy_por_materia"].items()]
            )
            col4.write("**Accuracy por grado**")
            col4.table(
                [{"Grado": k, "Accuracy": v["accuracy"], "Preguntas": v["total"]} for k, v in test["accuracy_por_grado"].items()]
            )

with tab_mantenimiento:
    st.subheader("Ingesta y etiquetado")
    col1, col2 = st.columns(2)
    if col1.button("Ingerir materiales (data/raw/ -> data/processed/)"):
        with st.spinner("Ingiriendo..."):
            report = ingest_all()
        st.success(f"Documentos ingeridos: {report.ingested}")
        if report.skipped:
            with st.expander(f"{len(report.skipped)} archivo(s) omitido(s)"):
                for item in report.skipped:
                    st.write(f"- {item}")

    if col2.button("Etiquetar temas"):
        with st.spinner("Etiquetando..."):
            summary = tag_all()
        for grupo, counts in summary.items():
            st.write(f"**{grupo}**")
            st.table([{"Estándar": code, "Documentos": n} for code, n in sorted(counts.items(), key=lambda kv: -kv[1])])
