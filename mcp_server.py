"""Servidor MCP que expone el pipeline de identificación de materia y estándares de exámenes
como herramientas, para que una sesión de Claude pueda orquestarlo conversacionalmente.

Cada herramienta es una envoltura delgada sobre funciones que ya existen en pipeline/ —
no duplica lógica, reutiliza exactamente lo que usa pipeline/cli.py.

Correr localmente (stdio, lo que usa .mcp.json para conectarlo a Claude Code):
    python mcp_server.py

Correr como servidor web (HTTP), accesible por red en vez de solo desde esta terminal:
    python mcp_server.py --http [--host 0.0.0.0] [--port 8000]
    Las herramientas quedan disponibles en http://<host>:<port>/mcp (protocolo MCP sobre
    HTTP, no un sitio para abrir en el navegador — se conecta con un cliente MCP que hable
    ese protocolo, no con un navegador común).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from pipeline.analysis.topic_balance import balance_report, cluster_questions, collect_historical_questions
from pipeline.audit.exam_review import review_exam
from pipeline.cli import _resolve_subject
from pipeline.config import BANCO_EXAMENES_PATH, get_settings
from pipeline.difficulty.run import profile_file
from pipeline.ingest.run import ingest_all
from pipeline.ml.bloom_classifier import (
    build_dataset,
    build_document_dataset,
    predict_exam_file,
    predict_exam_subject,
    run_full_report,
    save_bank,
)
from pipeline.ml.standards_classifier import evaluate_standards_model, predict_exam_standards
from pipeline.standards.loader import get_standards_for
from pipeline.tagging.run import tag_all

mcp = MCPServer(name="capstone-pipeline")


@mcp.tool()
def ingerir_materiales() -> dict:
    """Extrae texto de data/raw/ (docx/pptx/xlsx/pdf/txt) y lo normaliza en data/processed/documents/."""
    report = ingest_all()
    return {"documentos_ingeridos": report.ingested, "omitidos": report.skipped}


@mcp.tool()
def etiquetar_temas() -> dict:
    """Etiqueta cada documento ingerido contra los estándares curriculares (sin LLM, solo embeddings)."""
    return tag_all()


@mcp.tool()
def verificar_cobertura_temas(materia: str, grado: int) -> dict:
    """Agrupa las preguntas históricas por similaridad (k-means + PCA, sin LLM) y marca qué
    estándares están sobre/sub-representados en el banco real de esa materia/grado."""
    try:
        subject = _resolve_subject(materia)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}

    settings = get_settings()
    questions = collect_historical_questions(subject, grado)
    standards = get_standards_for(subject, grado)
    cluster_result = cluster_questions(questions, settings.embedding_model, standards)
    return balance_report(cluster_result, standards)


@mcp.tool()
def clasificar_dificultad(ruta_archivo: str) -> dict:
    """Construye la tabla de especificaciones (Bloom x DOK) de un examen puntual (sin LLM)."""
    try:
        exam_profile, _questions = profile_file(Path(ruta_archivo))
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    return exam_profile.model_dump()


@mcp.tool()
def identificar_materia(ruta_archivo: str) -> dict:
    """Identifica la materia (historia/tecnología) de un examen completo nuevo, entrenando
    el clasificador con el banco actual (reentrena desde cero, ~1 min)."""
    try:
        return predict_exam_subject(Path(ruta_archivo))
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@mcp.tool()
def identificar_estandares(ruta_archivo: str, materia: str | None = None) -> dict:
    """Identifica qué estándares curriculares cumple un examen completo nuevo. Si no se da
    `materia`, primero se infiere con identificar_materia/predict_exam_subject. LIMITACIÓN
    HONESTA: las etiquetas de entrenamiento son pseudo-etiquetas del etiquetado por
    embeddings (pipeline/tagging/run.py), no juicio humano — ver pipeline/ml/standards_classifier.py."""
    try:
        subject = _resolve_subject(materia) if materia else predict_exam_subject(Path(ruta_archivo))["materia_predicha"]
        resultado = predict_exam_standards(Path(ruta_archivo), subject=subject)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    return resultado


@mcp.tool()
def entrenar_clasificador_estandares(materia: str) -> dict:
    """Entrena/evalúa el clasificador multi-etiqueta de estándares curriculares para una
    materia. Ver limitaciones en pipeline/ml/standards_classifier.py."""
    try:
        subject = _resolve_subject(materia)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    return evaluate_standards_model(subject)


@mcp.tool()
def auditar_examen(ruta_archivo: str) -> dict:
    """Audita la FORMA de cualquier examen (propio o subido por un usuario, no tiene que ser
    generado por este pipeline): puntuación total, variedad de tipos de pregunta, y
    duplicados internos. No chequea 'fuga de respuesta' — ver pipeline/audit/exam_review.py."""
    try:
        return review_exam(Path(ruta_archivo))
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@mcp.tool()
def construir_banco_examenes() -> dict:
    """Construye el banco de preguntas etiquetadas (materia + Bloom/DOK + tipo de parte) desde
    los exámenes/reviews ya ingeridos y lo guarda en data/processed/banco_examenes.jsonl."""
    items = build_dataset()
    save_bank(items, BANCO_EXAMENES_PATH)
    return {"preguntas_guardadas": len(items), "ruta": str(BANCO_EXAMENES_PATH)}


@mcp.tool()
def entrenar_clasificador_dificultad() -> dict:
    """Entrena/evalúa (CV agrupada por examen) un clasificador supervisado de nivel Bloom a
    partir del texto de la pregunta. Ver limitaciones en pipeline/ml/bloom_classifier.py."""
    return run_full_report()


@mcp.tool()
def predecir_dificultad(ruta_archivo: str) -> dict:
    """Predice el nivel Bloom/DOK de cada pregunta de un archivo nuevo (clasificador
    por-pregunta, ya que Bloom sí varía dentro de un mismo examen). Para materia o
    estándares a nivel de examen completo, usar identificar_materia/identificar_estandares."""
    try:
        return predict_exam_file(Path(ruta_archivo), label_attr="bloom_level")
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@mcp.tool()
def entrenar_clasificador_materia() -> dict:
    """Entrena/evalúa el clasificador supervisado de MATERIA a nivel de EXAMEN COMPLETO (una
    fila por documento, no por pregunta). A diferencia de Bloom, esta etiqueta sí es verdad
    de terreno real (viene de la carpeta de origen en data/raw/). LIMITACIÓN: con solo 2
    materias de vocabulario muy distinto y pocos documentos (96 historia / 34 tecnología
    tipo examen/review), el F1-macro es modesto por el desbalance y el tamaño chico del banco."""
    return run_full_report(label_attr="subject", items=build_document_dataset())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor MCP de identificación de materia/estándares de exámenes")
    parser.add_argument("--http", action="store_true", help="Correr sobre HTTP en vez de stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.http:
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run()
