"""Construye el perfil de dificultad (tabla de especificaciones Bloom x DOK) de un examen."""

from __future__ import annotations

from pathlib import Path

from pipeline.config import RAW_DIR
from pipeline.difficulty.bloom_dok_rules import classify_question
from pipeline.difficulty.splitter import split_questions
from pipeline.ingest.extractors import extract_text
from pipeline.ingest.run import _detect_doc_type, _detect_grade
from pipeline.schemas import DifficultyProfile, Document, Question


# Separa el documento en preguntas, clasifica cada una (Bloom/DOK), y arma la tabla de
# especificaciones (cuántas preguntas hay de cada combinación Bloom|DOK).
def build_profile(document: Document) -> tuple[DifficultyProfile, list[Question]]:
    question_texts = split_questions(document.text)
    questions = []
    counts: dict[str, int] = {}

    for i, qtext in enumerate(question_texts):
        bloom, dok = classify_question(qtext)
        key = f"{bloom}|DOK{dok}"
        counts[key] = counts.get(key, 0) + 1
        questions.append(
            Question(
                id=f"{document.id}__q{i}",
                text=qtext,
                bloom_level=bloom,
                dok_level=dok,
                source="historical",
            )
        )

    profile = DifficultyProfile(
        subject=document.subject,
        grade=document.grade,
        source_exam=document.id,
        total_questions=len(questions),
        counts=counts,
    )
    return profile, questions


def profile_file(path: Path, subject: str | None = None, grade: int | None = None) -> tuple[DifficultyProfile, list[Question]]:
    """Perfila un archivo crudo directamente (no necesita haber sido ingerido antes)."""
    text = extract_text(path)
    group = path.parent.name
    if subject is None:
        # intenta inferir la materia desde la ruta: data/raw/<materia>/<grupo>/archivo
        try:
            subject = path.resolve().relative_to(RAW_DIR.resolve()).parts[0]
        except ValueError:
            subject = "unknown"
    if grade is None:
        grade = _detect_grade(path.name, group)

    document = Document(
        id=path.stem,
        subject=subject,
        grade=grade,
        doc_type=_detect_doc_type(path.name, group),
        group=group,
        source_path=str(path),
        text=text,
    )
    return build_profile(document)


# Imprime el perfil de dificultad en la consola, en formato legible.
def print_profile(profile: DifficultyProfile) -> None:
    print(f"Examen: {profile.source_exam} ({profile.subject}, grado {profile.grade})")
    print(f"Total de preguntas detectadas: {profile.total_questions}")
    for key, count in sorted(profile.counts.items()):
        print(f"  {key}: {count}")
