"""Separa el texto de un examen en preguntas individuales (heurística por numeración).

Limitación conocida: asume que cada pregunta empieza una línea con "1.", "2)", etc.
Exámenes con otro formato (ej. preguntas sin numerar, tablas) no se separarán bien;
en ese caso el documento completo se trata como una sola "pregunta".
"""

from __future__ import annotations

import re

_QUESTION_START = re.compile(r"^\s*(\d{1,2})[.\)]\s+\S")
_MIN_QUESTION_CHARS = 8


def split_questions(text: str) -> list[str]:
    lines = text.splitlines()
    blocks: list[list[str]] = []

    for line in lines:
        if _QUESTION_START.match(line):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
        # líneas antes de la primera pregunta numerada (instrucciones) se descartan

    questions = ["\n".join(block).strip() for block in blocks]
    questions = [q for q in questions if len(q) >= _MIN_QUESTION_CHARS]

    if not questions and text.strip():
        # no se detectó numeración: devolver el texto completo como una sola unidad
        return [text.strip()]
    return questions
