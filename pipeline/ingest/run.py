"""Recorre data/raw/<materia>/<grupo>/**, extrae texto y normaliza a data/processed/documents/*.json."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from pipeline.config import DOCUMENTS_DIR, RAW_DIR
from pipeline.ingest.extractors import UnsupportedFileError, extract_text
from pipeline.schemas import Document

_GRADE_PATTERNS = [
    re.compile(r"\b([5-9])(?:th|to|mo|vo)\b", re.IGNORECASE),
    re.compile(r"\b([5-9])°"),
    re.compile(r"\bgrado\s*([5-9])\b", re.IGNORECASE),
    re.compile(r"\bgrade([5-9])\b", re.IGNORECASE),
]

_EXAM_HINTS = ("test", "exam", "examen", "final", "quiz")
_REVIEW_HINTS = ("review", "repaso", "guide", "guía", "guia", "practice", "practica", "preguntas")
_TEXTBOOK_GROUP_HINT = "textbook"


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def _detect_grade(filename: str, group: str) -> int | None:
    haystacks = [filename, group]
    for haystack in haystacks:
        for pattern in _GRADE_PATTERNS:
            match = pattern.search(haystack)
            if match:
                return int(match.group(1))
    # grupos como "grade5_supplement" ya contienen el número
    match = re.search(r"grade([5-9])", group, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _detect_doc_type(filename: str, group: str) -> str:
    lower = filename.lower()
    if _TEXTBOOK_GROUP_HINT in group.lower():
        return "textbook"
    if any(hint in lower for hint in _EXAM_HINTS):
        return "exam"
    if any(hint in lower for hint in _REVIEW_HINTS):
        return "review"
    return "material"


@dataclass
class IngestReport:
    ingested: int = 0
    skipped: list[str] = field(default_factory=list)


def _iter_subject_groups():
    """Produce (subject, group, group_dir) para cada grupo bajo data/raw/.

    `textbook_text/<grade>` es un caso especial: no es una materia propia, es
    contenido de libro de texto de Historia ya extraído a .txt.
    """
    for subject_dir in sorted(p for p in RAW_DIR.iterdir() if p.is_dir()):
        if subject_dir.name == "textbook_text":
            for grade_dir in sorted(p for p in subject_dir.iterdir() if p.is_dir()):
                yield "history", f"{grade_dir.name}_textbook", grade_dir
        else:
            for group_dir in sorted(p for p in subject_dir.iterdir() if p.is_dir()):
                yield subject_dir.name, group_dir.name, group_dir


def ingest_all() -> IngestReport:
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    report = IngestReport()

    for subject, group, group_dir in _iter_subject_groups():
        for file_path in sorted(group_dir.rglob("*")):
            if not file_path.is_file():
                continue
            try:
                text = extract_text(file_path)
            except UnsupportedFileError as exc:
                report.skipped.append(f"{file_path}: {exc}")
                continue
            except Exception as exc:  # noqa: BLE001 - queremos seguir con el resto
                report.skipped.append(f"{file_path}: error de extracción ({exc})")
                continue

            if not text.strip():
                report.skipped.append(f"{file_path}: sin texto extraíble")
                continue

            grade = _detect_grade(file_path.name, group)
            doc_type = _detect_doc_type(file_path.name, group)
            doc_id = _slugify(f"{subject}_{group}_{file_path.stem}")

            document = Document(
                id=doc_id,
                subject=subject,
                grade=grade,
                doc_type=doc_type,
                group=group,
                source_path=str(file_path.relative_to(RAW_DIR.parent.parent)),
                text=text,
            )
            out_path = DOCUMENTS_DIR / f"{doc_id}.json"
            out_path.write_text(
                document.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8"
            )
            report.ingested += 1

    return report


def load_all_documents() -> list[Document]:
    docs = []
    for path in sorted(DOCUMENTS_DIR.glob("*.json")):
        docs.append(Document.model_validate_json(path.read_text(encoding="utf-8")))
    return docs


if __name__ == "__main__":
    result = ingest_all()
    print(f"Documentos ingeridos: {result.ingested}")
    if result.skipped:
        print(f"Omitidos ({len(result.skipped)}):")
        for item in result.skipped:
            print(f"  - {item}")
