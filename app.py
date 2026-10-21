"""Interfaz web simple (Streamlit) para el pipeline — identificar materia/estándares de un
examen nuevo, ver el balance de temas y entrenar los clasificadores, desde el navegador sin
usar la terminal. Reutiliza exactamente las mismas funciones que pipeline/cli.py y
mcp_server.py; no duplica lógica.

Correr: streamlit run app.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from pipeline.analysis.topic_balance import balance_report, cluster_questions, collect_historical_questions
from pipeline.cli import _resolve_subject
from pipeline.config import get_settings
from pipeline.ingest.run import ingest_all
from pipeline.ml.bloom_classifier import build_document_dataset
from pipeline.ml.bloom_classifier import predict_exam_subject
from pipeline.ml.bloom_classifier import run_full_report as run_ml_report
from pipeline.ml.standards_classifier import evaluate_standards_model, predict_exam_standards
from pipeline.standards.loader import get_standards_for
from pipeline.tagging.run import tag_all

st.set_page_config(page_title="Identificador de Exámenes", page_icon="🔎", layout="wide")
st.title("Identificador de Materia y Estándares — Capstone MAI540")

_GRADOS = [5, 6, 7, 8]
_MATERIAS = ["historia", "tecnologia"]


# Guarda el archivo subido a un temporal con la misma extensión, para que extract_text
# (que trabaja por sufijo de Path) lo pueda leer igual que un archivo del disco.
def _save_uploaded_file(uploaded) -> Path:
    suffix = Path(uploaded.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getvalue())
        return Path(tmp.name)


tab_identificar, tab_balance, tab_ml, tab_mantenimiento = st.tabs(
    ["Identificar examen", "Balance de temas", "Modelos ML", "Mantenimiento"]
)

with tab_identificar:
    st.subheader("Identificar materia y estándares de un examen nuevo")
    st.caption(
        "Sube un examen (propio o de cualquier docente) y el sistema entrena los "
        "clasificadores con el banco histórico actual (~1 min) para identificar de qué "
        "materia es y qué estándares curriculares cumple."
    )
    archivo_subido = st.file_uploader("Examen (.docx/.pdf/.pptx/.xlsx/.txt)", key="id_archivo")

    if archivo_subido and st.button("Identificar", type="primary"):
        with st.spinner("Entrenando clasificadores y prediciendo..."):
            ruta_temporal = _save_uploaded_file(archivo_subido)
            try:
                materia_resultado = predict_exam_subject(ruta_temporal)
                estandares_resultado = predict_exam_standards(
                    ruta_temporal, subject=materia_resultado["materia_predicha"]
                )
                st.session_state["id_resultado"] = {
                    "materia": materia_resultado,
                    "estandares": estandares_resultado,
                }
            except Exception as exc:  # noqa: BLE001
                st.session_state["id_resultado"] = None
                st.error(f"No se pudo identificar el examen: {exc}")
            finally:
                ruta_temporal.unlink(missing_ok=True)

    resultado_id = st.session_state.get("id_resultado")
    if resultado_id:
        materia_resultado = resultado_id["materia"]
        st.success(
            f"Materia predicha: **{materia_resultado['materia_predicha']}** "
            f"(modelo: {materia_resultado['modelo_usado']}, confianza: {materia_resultado['confianza']})"
        )

        estandares_resultado = resultado_id["estandares"]
        if estandares_resultado["estandares_predichos"]:
            st.write("**Estándares predichos:**")
            st.table(
                [
                    {"Estándar": item["estandar"], "Probabilidad": item["probabilidad"]}
                    for item in estandares_resultado["estandares_predichos"]
                ]
            )
        else:
            st.info(estandares_resultado["aviso"])

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
    st.subheader("Clasificadores supervisados (entregable del rúbrico de ML)")

    objetivo_label = st.radio(
        "Objetivo a entrenar/evaluar", ["Dificultad (nivel Bloom)", "Materia", "Estándares"], horizontal=True
    )

    if objetivo_label == "Dificultad (nivel Bloom)":
        st.warning(
            "Limitación honesta: las etiquetas de entrenamiento vienen de la heurística de reglas "
            "del propio proyecto (pipeline/difficulty/bloom_dok_rules.py), no de jueces humanos ni "
            "de datos reales de estudiantes. Este modelo mide si se puede *aprender* ese criterio "
            "desde el texto."
        )
    elif objetivo_label == "Materia":
        st.warning(
            "Limitación honesta: solo hay 2 materias locales (history/technology) con vocabulario "
            "muy distinto y pocos documentos tipo examen/review (96 historia / 34 tecnología), así "
            "que el F1-macro (la métrica real de selección de modelo) es modesto por el desbalance "
            "y el tamaño chico del banco — a diferencia de Bloom, esta etiqueta sí es verdad de "
            "terreno real (viene de la carpeta de origen), no una pseudo-etiqueta."
        )
    else:
        st.warning(
            "Limitación honesta: las etiquetas de estándar son PSEUDO-ETIQUETAS producidas por el "
            "etiquetado por embeddings (pipeline/tagging/run.py), no juicio humano — este modelo "
            "aprende a reproducir esa heurística desde texto crudo. Con ~20 códigos repartidos en "
            "~130 documentos, muchos códigos tendrán muy poco soporte."
        )
        materia_estandares = st.selectbox("Materia", _MATERIAS, key="ml_estandares_materia")

    if st.button("Entrenar y evaluar", type="primary"):
        with st.spinner("Entrenando..."):
            if objetivo_label == "Dificultad (nivel Bloom)":
                st.session_state["ml_resultado"] = run_ml_report(label_attr="bloom_level")
            elif objetivo_label == "Materia":
                st.session_state["ml_resultado"] = run_ml_report(
                    label_attr="subject", items=build_document_dataset()
                )
            else:
                subject = _resolve_subject(materia_estandares)
                st.session_state["ml_resultado"] = evaluate_standards_model(subject)
            st.session_state["ml_objetivo_label"] = objetivo_label

    resultado_ml = st.session_state.get("ml_resultado")
    if resultado_ml:
        objetivo_actual = st.session_state.get("ml_objetivo_label")
        if resultado_ml["estado"] != "ok":
            st.info(resultado_ml["detalle"])
        elif objetivo_actual == "Estándares":
            st.caption(
                f"Documentos tipo examen/review: {resultado_ml['total_documentos']} "
                f"(train {resultado_ml['documentos_train']} / test {resultado_ml['documentos_test']})"
            )
            st.write(f"**F1 micro:** {resultado_ml['f1_micro']}  **F1 macro:** {resultado_ml['f1_macro']}")
            st.table(
                [
                    {
                        "Estándar": codigo,
                        "Soporte (docs)": resultado_ml["soporte_por_codigo"][codigo],
                        "Precision": round(resultado_ml["reporte_por_codigo"][codigo]["precision"], 2),
                        "Recall": round(resultado_ml["reporte_por_codigo"][codigo]["recall"], 2),
                        "F1": round(resultado_ml["reporte_por_codigo"][codigo]["f1-score"], 2),
                    }
                    for codigo in resultado_ml["codigos"]
                ]
            )
        else:
            etiqueta_columna = "Por nivel Bloom" if objetivo_actual == "Dificultad (nivel Bloom)" else "Por materia"
            st.caption(f"Documentos/preguntas históricas usadas: {resultado_ml['total_preguntas']}")
            col1, col2 = st.columns(2)
            col1.write(f"**{etiqueta_columna}**")
            col1.table(resultado_ml["conteos_por_etiqueta"])
            col2.write("**Por grado**")
            col2.table(resultado_ml["conteos_por_grado"])

            comparacion = resultado_ml["comparacion_de_modelos"]
            st.write(f"**Comparación de modelos** (F1-macro, CV, {comparacion['n_splits_usados']} particiones)")
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
            st.write(f"Train: {test['examenes_train']} exámenes · Test: {test['examenes_test']} exámenes")
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
