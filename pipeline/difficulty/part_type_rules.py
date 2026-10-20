"""Puntos y tipo de parte por pregunta — heurística sin LLM, reutilizable para preguntas
históricas y como respaldo cuando la generación no asigna un valor válido."""

from __future__ import annotations

import re

_OPTION_PREFIX_PATTERN = re.compile(r"^\s*[a-dA-D][\).:]\s*")

VALID_PART_TYPES = {
    "pareo",
    "verdadero_falso",
    "opcion_multiple",
    "respuesta_corta",
    "ensayo",
    "completar",
}

_POINTS_BY_DOK = {1: 5, 2: 8, 3: 12, 4: 15}
_DEFAULT_POINTS = 5

_MULTIPLE_CHOICE_PATTERN = re.compile(r"\ba\)\s.*\bb\)\s", re.IGNORECASE | re.DOTALL)
_TRUE_FALSE_PATTERN = re.compile(r"\bverdadero\b|\bfalso\b|\bv\s+o\s+f\b", re.IGNORECASE)
_BLANK_PATTERN = re.compile(r"_{3,}")
_ESSAY_MIN_CHARS = 200


def points_for(dok_level: int | None) -> int:
    """Escala con dificultad, igual que los exámenes reales del banco (el ensayo final
    vale más que el pareo de vocabulario)."""
    if dok_level is None:
        return _DEFAULT_POINTS
    return _POINTS_BY_DOK.get(dok_level, _DEFAULT_POINTS)


def strip_option_prefix(option: str) -> str:
    """Algunos modelos devuelven las opciones ya con el prefijo 'a) '/'b. ' incluido — se
    quita para no duplicarlo cuando se vuelve a numerar al ensamblar el examen."""
    return _OPTION_PREFIX_PATTERN.sub("", option).strip()


# Adivina el tipo de pregunta por patrones en el texto (opciones a)/b).., "Verdadero/Falso",
# un blanco "____", o simplemente lo largo que es el texto para distinguir ensayo de respuesta corta.
def detect_part_type(text: str) -> str:
    if _MULTIPLE_CHOICE_PATTERN.search(text):
        return "opcion_multiple"
    if _TRUE_FALSE_PATTERN.search(text):
        return "verdadero_falso"
    if _BLANK_PATTERN.search(text):
        return "completar"
    if len(text) > _ESSAY_MIN_CHARS:
        return "ensayo"
    return "respuesta_corta"
