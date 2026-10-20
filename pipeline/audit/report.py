"""Genera el reporte de auditoría como un .md guardado en Reportes_auditoria/, con el
título del examen y la fecha (abreviada) de la auditoría en el nombre del archivo."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pipeline.assemble.naming import clean_filename_part, unique_path
from pipeline.config import REPORTES_AUDITORIA_DIR
from pipeline.schemas import AuditReport, GeneratedExam

_MESES_ABREVIADOS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


# Día + mes abreviado en letras + año de 2 dígitos (ej. "20Oct26") — fácil de leer y no se
# confunde con el orden día/mes de un formato puramente numérico.
def fecha_abreviada(dt: datetime | None = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    return f"{dt.day:02d}{_MESES_ABREVIADOS[dt.month - 1]}{dt.year % 100:02d}"


# Construye el reporte de auditoría en Markdown (título del examen + fecha abreviada en el
# nombre del archivo) y lo guarda en Reportes_auditoria/, sin pisar un reporte anterior.
def write_audit_report(
    exam: GeneratedExam, report: AuditReport, tema: str, reference_path: str | None = None
) -> Path:
    REPORTES_AUDITORIA_DIR.mkdir(parents=True, exist_ok=True)
    tema_clean = clean_filename_part(tema) or "Examen"
    fecha = fecha_abreviada()
    report_path = unique_path(REPORTES_AUDITORIA_DIR / f"{tema_clean} - Auditoria - {fecha}.md")

    lines = [
        f"# Reporte de auditoría — {tema_clean}",
        "",
        f"**Fecha:** {fecha} ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')})",
        f"**Preguntas auditadas:** {len(exam.questions)}",
    ]
    if reference_path:
        lines.append(f"**Material de referencia:** {reference_path}")
    lines.append(f"\n**Resultado general: {'APROBADO' if report.aprobado_general else 'NO APROBADO'}**\n")

    for criterio in report.criterios:
        marca = "[OK]" if criterio.aprobado else "[FALLA]"
        lines.append(f"- {marca} **{criterio.criterio}**: {criterio.detalle}")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
