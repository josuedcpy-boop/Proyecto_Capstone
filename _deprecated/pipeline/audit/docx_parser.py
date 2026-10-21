"""Lee un .docx ya ensamblado por pipeline/assemble/run.py y reconstruye el GeneratedExam
(más la ruta del material de referencia, si quedó guardada) para poder re-auditarlo sin
tener que volver a generarlo."""

from __future__ import annotations

import re
from pathlib import Path

import docx

from pipeline.assemble.run import _SUBJECT_LABELS
from pipeline.schemas import GeneratedExam, Question

_SUBJECT_LABELS_INVERSE = {v: k for k, v in _SUBJECT_LABELS.items()}

_HEADING_PATTERN = re.compile(r"^Examen generado — (.+) \((.+), grado (\S+)\)$")
_REFERENCE_PATTERN = re.compile(r"^Material de referencia:\s*(.+)$")
_QUESTION_META_PATTERN = re.compile(
    r"^(\d+)\.\s*\((?P<bloom>[^/]+?)\s*/\s*DOK(?P<dok>\S+)\s*/\s*(?P<part_type>\S+)\s*/\s*(?P<points>\d+)pts\)"
)
_OPTION_PATTERN = re.compile(r"^\s*([a-d])\)\s*(.+)$", re.IGNORECASE)
_SECTION_HEADERS = ("Reporte de validación", "Reporte de auditoría")


class ExamParseError(Exception):
    pass


# Recorre los párrafos del .docx como una máquina de estados simple: detecta el título
# (tema/materia/grado), la línea de referencia, y cada bloque de pregunta (línea de
# metadatos + enunciado + opciones si las hay), hasta llegar a las secciones de reportes.
def parse_generated_exam(path: Path) -> tuple[GeneratedExam, str | None, str | None]:
    document = docx.Document(str(path))
    paragraphs = [p.text for p in document.paragraphs]

    tema: str | None = None
    subject: str | None = None
    grade: int | None = None
    reference_path: str | None = None

    questions: list[Question] = []
    current_meta: dict | None = None
    current_text_lines: list[str] = []
    current_options: list[str] = []

    # Cierra la pregunta que se venía armando (si hay una) y la agrega a `questions`.
    def _flush_current():
        if current_meta is None:
            return
        dok_raw = current_meta["dok"]
        dok_level = int(dok_raw) if dok_raw.isdigit() else None
        questions.append(
            Question(
                id=f"parsed_{len(questions)}",
                text="\n".join(current_text_lines).strip(),
                bloom_level=current_meta["bloom"].strip() or None,
                dok_level=dok_level,
                part_type=current_meta["part_type"] if current_meta["part_type"] != "?" else None,
                points=int(current_meta["points"]),
                options=current_options or None,
                source="generated",
            )
        )

    in_question_section = False
    for raw_line in paragraphs:
        line = raw_line.strip()

        if tema is None:
            match = _HEADING_PATTERN.match(line)
            if match:
                tema, subject_label, grade_str = match.groups()
                subject = _SUBJECT_LABELS_INVERSE.get(subject_label, subject_label.lower())
                grade = int(grade_str) if grade_str.isdigit() else None
                in_question_section = True
            continue

        ref_match = _REFERENCE_PATTERN.match(line)
        if ref_match:
            reference_path = ref_match.group(1).strip()
            continue

        if any(line.startswith(header) for header in _SECTION_HEADERS):
            in_question_section = False
            _flush_current()
            current_meta = None
            continue

        if not in_question_section:
            continue

        meta_match = _QUESTION_META_PATTERN.match(line)
        if meta_match:
            _flush_current()
            current_meta = meta_match.groupdict()
            current_text_lines = []
            current_options = []
            continue

        if current_meta is None or not line:
            continue

        option_match = _OPTION_PATTERN.match(line)
        if option_match:
            current_options.append(option_match.group(2).strip())
        else:
            current_text_lines.append(line)

    _flush_current()

    if tema is None or not questions:
        raise ExamParseError(
            f"No se pudo leer '{path}' como un examen generado por este pipeline "
            "(¿es un .docx creado por `pipeline.cli generate`?)."
        )

    exam = GeneratedExam(subject=subject or "unknown", grade=grade, questions=questions)
    return exam, reference_path, tema
