"""Servidor MCP que expone el pipeline de generación/auditoría de exámenes como herramientas,
para que una sesión de Claude pueda orquestar todo el proceso conversacionalmente.

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
from pipeline.assemble.run import assemble_exam
from pipeline.audit.docx_parser import ExamParseError, parse_generated_exam
from pipeline.audit.exam_audit import audit_exam
from pipeline.audit.report import write_audit_report
from pipeline.cli import _pick_reference_exam, _resolve_subject
from pipeline.config import get_settings
from pipeline.difficulty.run import profile_file
from pipeline.generation.run import generate_exam
from pipeline.ingest.extractors import extract_text
from pipeline.ingest.run import ingest_all
from pipeline.standards.loader import get_standards_for
from pipeline.tagging.run import tag_all
from pipeline.validation.run import validate_exam

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
def generar_examen(materia: str, grado: int, tema: str | None = None, perfil_de: str | None = None) -> dict:
    """Genera, valida, audita y ensambla un examen nuevo en Examen_generado/ (.docx) para
    materia/grado, usando un examen histórico como perfil de dificultad/tema objetivo.
    NOTA: genera un examen completo (varias preguntas con su perfil), no una sola pregunta suelta."""
    try:
        subject = _resolve_subject(materia)
        reference_path = Path(perfil_de) if perfil_de else _pick_reference_exam(subject, grado)
        target_profile, _historical_questions = profile_file(reference_path, subject=subject, grade=grado)
        tema_resuelto = tema or reference_path.stem
        reference_text = extract_text(reference_path)

        exam = generate_exam(subject, grado, target_profile, tema=tema_resuelto, reference_text=reference_text)
        exam = validate_exam(exam)

        settings = get_settings()
        audit = audit_exam(exam, reference_text=reference_text, embedding_model=settings.embedding_model)
        out_path = assemble_exam(exam, tema=tema_resuelto, audit=audit, reference_path=str(reference_path))
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}

    return {
        "archivo_generado": str(out_path),
        "material_de_referencia": str(reference_path),
        "perfil_objetivo": target_profile.model_dump(),
        "auditoria_aprobada": audit.aprobado_general,
        "auditoria": [c.model_dump() for c in audit.criterios],
        "preguntas": [q.model_dump() for q in exam.questions],
    }


@mcp.tool()
def auditar_examen(ruta_docx: str, perfil_de: str | None = None) -> dict:
    """Audita un examen .docx ya generado (sin volver a generarlo) contra los 5 criterios
    de docs/criterios_auditoria.md."""
    try:
        exam, reference_path_in_doc, tema = parse_generated_exam(Path(ruta_docx))
    except ExamParseError as exc:
        return {"error": str(exc)}

    reference_path_str = perfil_de or reference_path_in_doc
    reference_text = extract_text(Path(reference_path_str)) if reference_path_str else ""

    settings = get_settings()
    report = audit_exam(exam, reference_text=reference_text, embedding_model=settings.embedding_model)
    report_path = write_audit_report(exam, report, tema=tema or Path(ruta_docx).stem, reference_path=reference_path_str)

    sin_clave_de_respuesta = any(
        q.part_type == "opcion_multiple" and q.correct_option_index is None for q in exam.questions
    )

    return {
        "material_de_referencia": reference_path_str,
        "aprobado_general": report.aprobado_general,
        "criterios": [c.model_dump() for c in report.criterios],
        "reporte_guardado_en": str(report_path),
        "aviso_fuga_respuesta": (
            "Este .docx no guarda cuál opción es la correcta (por diseño) — 'sin fuga de "
            "respuesta' no se pudo confirmar para sus preguntas de opción múltiple."
            if sin_clave_de_respuesta
            else None
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor MCP del pipeline de exámenes")
    parser.add_argument("--http", action="store_true", help="Correr sobre HTTP en vez de stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.http:
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run()
