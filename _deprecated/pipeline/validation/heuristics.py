"""Checklist de redacción (Haladyna et al.) y detección de duplicados, sin LLM."""

from __future__ import annotations

import re

import numpy as np

from pipeline.embeddings.store import embed_texts
from pipeline.schemas import Question, ValidationIssue

_NEGATIVE_PATTERNS = re.compile(r"\bNO\s+es\b|\bexcepto\b|\bNO\s+corresponde\b", re.IGNORECASE)
_ALL_NONE_PATTERNS = re.compile(r"todas\s+las\s+anteriores|ninguna\s+de\s+las\s+anteriores", re.IGNORECASE)
_MIN_TEXT_CHARS = 15
_DUPLICATE_SIMILARITY_THRESHOLD = 0.90


# Revisa una pregunta contra las reglas de redacción de Haladyna (sin negaciones, sin
# "todas/ninguna de las anteriores", texto no vacío).
def check_format(question: Question) -> list[ValidationIssue]:
    issues = []
    if len(question.text.strip()) < _MIN_TEXT_CHARS:
        issues.append(
            ValidationIssue(question_id=question.id, rule="longitud_minima", detail="El texto es demasiado corto o vacío.", severity="error")
        )
    if _NEGATIVE_PATTERNS.search(question.text):
        issues.append(
            ValidationIssue(
                question_id=question.id,
                rule="enunciado_negativo",
                detail="Evitar construcciones negativas tipo 'NO es' / 'excepto' (Haladyna).",
            )
        )
    if _ALL_NONE_PATTERNS.search(question.text):
        issues.append(
            ValidationIssue(
                question_id=question.id,
                rule="todas_ninguna_anteriores",
                detail="Evitar 'todas/ninguna de las anteriores' (Haladyna).",
            )
        )
    return issues


# Compara cada pregunta generada contra el banco histórico (por embeddings) y marca las
# que son casi idénticas a una pregunta que ya existía.
def check_duplicates(
    generated: list[Question], historical: list[Question], embedding_model: str
) -> list[ValidationIssue]:
    if not generated or not historical:
        return []

    gen_embeddings = embed_texts([q.text for q in generated], embedding_model)
    hist_embeddings = embed_texts([q.text for q in historical], embedding_model)
    similarities = gen_embeddings @ hist_embeddings.T

    issues = []
    for i, question in enumerate(generated):
        best_match_index = int(np.argmax(similarities[i]))
        best_similarity = float(similarities[i][best_match_index])
        if best_similarity >= _DUPLICATE_SIMILARITY_THRESHOLD:
            issues.append(
                ValidationIssue(
                    question_id=question.id,
                    rule="posible_duplicado",
                    detail=(
                        f"Similaridad {best_similarity:.2f} con pregunta histórica "
                        f"'{historical[best_match_index].text[:80]}...'"
                    ),
                    severity="error",
                )
            )
    return issues
