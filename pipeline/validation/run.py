"""Corre las heurísticas de validación sobre un examen generado, y (si hay un LLM real
configurado, no el mock) añade una pasada de LLM-juez simple sobre los ítems marcados."""

from __future__ import annotations

from pipeline.config import get_settings
from pipeline.difficulty.splitter import split_questions
from pipeline.ingest.run import load_all_documents
from pipeline.llm.factory import get_provider
from pipeline.llm.mock_provider import MockProvider
from pipeline.schemas import GeneratedExam, Question
from pipeline.validation.heuristics import check_duplicates, check_format


def _historical_questions(subject: str, grade: int | None) -> list[Question]:
    docs = [
        d
        for d in load_all_documents()
        if d.subject == subject and d.doc_type in ("exam", "review") and (grade is None or d.grade == grade)
    ]
    questions = []
    for doc in docs:
        for i, text in enumerate(split_questions(doc.text)):
            questions.append(Question(id=f"{doc.id}__q{i}", text=text, source="historical"))
    return questions


def validate_exam(exam: GeneratedExam) -> GeneratedExam:
    settings = get_settings()
    issues = []

    for question in exam.questions:
        issues.extend(check_format(question))

    historical = _historical_questions(exam.subject, exam.grade)
    issues.extend(check_duplicates(exam.questions, historical, settings.embedding_model))

    provider = get_provider(settings)
    if not isinstance(provider, MockProvider):
        issues.extend(_llm_judge(exam, provider))

    exam.issues = issues
    return exam


def _llm_judge(exam: GeneratedExam, provider) -> list:
    """Pasada opcional de LLM-juez: solo corre si hay un proveedor real configurado.
    Mantenida simple a propósito; puede ampliarse con un prompt más detallado por ítem."""
    from pipeline.schemas import ValidationIssue

    issues = []
    for question in exam.questions:
        prompt = (
            f"Evalúa si esta pregunta de examen es clara, factualmente razonable y sin errores "
            f"evidentes. Responde solo 'OK' o una frase breve describiendo el problema.\n\n{question.text}"
        )
        verdict = provider.generate(prompt).strip()
        # algunos modelos devuelven "OK." o "OK, está clara." — comparamos solo el inicio.
        if not verdict.upper().startswith("OK"):
            issues.append(
                ValidationIssue(question_id=question.id, rule="llm_juez", detail=verdict, severity="warning")
            )
    return issues
