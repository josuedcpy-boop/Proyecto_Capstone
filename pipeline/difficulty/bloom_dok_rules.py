"""Heurística (sin LLM) para clasificar una pregunta en nivel Bloom + Webb's DOK,
basada en los verbos/patrones de docs/estandares_y_mejores_practicas.md sección 6.

Es una heurística de palabras clave: funciona razonablemente para preguntas que usan
un verbo explícito ("explica", "compara"), pero preguntas de opción múltiple sin verbo
("¿Cuál de los siguientes...?") caen al nivel por defecto (Recordar / DOK 1).
"""

from __future__ import annotations

import re

# Orden de prioridad: se revisa de mayor a menor nivel cognitivo, así una pregunta que
# combina verbos de varios niveles (ej. "describe y luego evalúa") se clasifica por el
# nivel más alto presente, que es el que realmente determina su dificultad.
_RULES: list[tuple[str, int, tuple[str, ...]]] = [
    ("Crear", 4, ("diseña", "diseñe", "construye", "elabora", "produce", "formula", "propone", "crea", "design", "create", "construct")),
    ("Evaluar", 3, ("evalúa", "evaluar", "justifica", "argumenta", "critica", "defiende", "juzga", "evaluate", "justify", "argue")),
    ("Analizar", 3, ("compara", "contrasta", "categoriza", "distingue", "organiza", "examina", "analiza", "compare", "contrast", "analyze")),
    ("Aplicar", 2, ("calcula", "resuelve", "demuestra", "utiliza", "aplica", "calculate", "solve", "apply", "demonstrate")),
    ("Comprender", 1, ("explica", "describe", "resume", "parafrasea", "clasifica", "explain", "describe", "summarize")),
    ("Recordar", 1, ("define", "identifica", "menciona", "enumera", "nombra", "lista", "recuerda", "copia", "define", "identify", "list")),
]

_DEFAULT_BLOOM = "Recordar"
_DEFAULT_DOK = 1


def classify_question(text: str) -> tuple[str, int]:
    lower = text.lower()
    for bloom, dok, keywords in _RULES:
        if any(re.search(rf"\b{re.escape(kw)}\w*", lower) for kw in keywords):
            return bloom, dok
    return _DEFAULT_BLOOM, _DEFAULT_DOK
