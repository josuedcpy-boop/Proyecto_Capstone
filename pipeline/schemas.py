"""Modelos de datos compartidos entre las etapas del pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Document(BaseModel):
    """Un archivo ingerido y normalizado a texto plano."""

    id: str
    subject: str  # "history" | "technology"
    grade: int | None = None
    doc_type: str  # "exam" | "material" | "review" | "textbook"
    group: str  # subcarpeta de origen dentro de data/raw/<subject>/
    source_path: str
    text: str


class Chunk(BaseModel):
    """Fragmento de un Document, usado para embeddings/RAG."""

    id: str
    document_id: str
    subject: str
    grade: int | None = None
    chunk_index: int
    text: str


class StandardTag(BaseModel):
    """Resultado de etiquetar un chunk/documento contra un estándar curricular."""

    standard_code: str
    standard_name: str
    grade: int | None = None
    similarity: float


class Question(BaseModel):
    """Una pregunta individual, histórica o generada."""

    id: str
    text: str
    bloom_level: str | None = None
    dok_level: int | None = None
    standard_codes: list[str] = Field(default_factory=list)
    source: str = "historical"  # "historical" | "generated"


class DifficultyProfile(BaseModel):
    """Tabla de especificaciones: conteo de preguntas por (Bloom, DOK)."""

    subject: str
    grade: int | None = None
    source_exam: str
    total_questions: int
    counts: dict[str, int] = Field(default_factory=dict)  # clave "Bloom|DOKn"


class ValidationIssue(BaseModel):
    question_id: str
    rule: str
    detail: str
    severity: str = "warning"  # "warning" | "error"


class GeneratedExam(BaseModel):
    subject: str
    grade: int | None = None
    questions: list[Question]
    target_profile: DifficultyProfile | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)
