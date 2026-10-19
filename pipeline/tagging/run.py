"""Etiqueta cada documento ingerido con el(los) estándar(es) curricular(es) más cercano(s)
por similaridad de embeddings (sin LLM, sin API key)."""

from __future__ import annotations

import json
from collections import defaultdict

from pipeline.config import PROCESSED_DIR, get_settings
from pipeline.embeddings.chunking import chunk_document
from pipeline.embeddings.store import cosine_similarity_matrix, embed_texts
from pipeline.ingest.run import load_all_documents
from pipeline.schemas import Document, StandardTag
from pipeline.standards.loader import get_standards_for

TAGS_DIR = PROCESSED_DIR / "tags"

# Similaridad mínima para considerar que un chunk cubre un estándar; por debajo de esto
# se asume que el chunk no tiene suficiente relación temática con ningún estándar conocido.
_MIN_SIMILARITY = 0.25


def tag_document(document: Document, embedding_model: str) -> list[StandardTag]:
    chunks = chunk_document(document)
    if not chunks:
        return []

    standards = get_standards_for(document.subject, document.grade)
    if not standards:
        return []

    chunk_embeddings = embed_texts([c.text for c in chunks], embedding_model)
    standard_embeddings = embed_texts([s.text for s in standards], embedding_model)
    similarities = cosine_similarity_matrix(chunk_embeddings, standard_embeddings)

    tags = []
    for row in similarities:
        best_index = int(row.argmax())
        best_similarity = float(row[best_index])
        if best_similarity < _MIN_SIMILARITY:
            continue
        standard = standards[best_index]
        tags.append(
            StandardTag(
                standard_code=standard.code,
                standard_name=standard.name,
                grade=document.grade,
                similarity=round(best_similarity, 4),
            )
        )
    return tags


def document_coverage(tags: list[StandardTag]) -> dict[str, dict]:
    coverage: dict[str, dict] = {}
    for tag in tags:
        entry = coverage.setdefault(
            tag.standard_code, {"name": tag.standard_name, "chunk_count": 0, "similarities": []}
        )
        entry["chunk_count"] += 1
        entry["similarities"].append(tag.similarity)
    for entry in coverage.values():
        sims = entry.pop("similarities")
        entry["avg_similarity"] = round(sum(sims) / len(sims), 4)
    return coverage


def tag_all() -> dict:
    settings = get_settings()
    TAGS_DIR.mkdir(parents=True, exist_ok=True)
    documents = load_all_documents()

    group_summary: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for document in documents:
        tags = tag_document(document, settings.embedding_model)
        coverage = document_coverage(tags)
        out_path = TAGS_DIR / f"{document.id}.json"
        out_path.write_text(json.dumps(coverage, indent=2, ensure_ascii=False), encoding="utf-8")

        group_key = f"{document.subject}/grado {document.grade or '?'}"
        for code in coverage:
            group_summary[group_key][code] += 1

    return {k: dict(v) for k, v in group_summary.items()}


if __name__ == "__main__":
    summary = tag_all()
    for group, counts in summary.items():
        print(f"\n{group}")
        for code, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"  {code}: cubierto en {n} documento(s)")
