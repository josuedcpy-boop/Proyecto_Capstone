"""Divide el texto de un Document en Chunks aptos para embeber (~ palabras por chunk)."""

from __future__ import annotations

from pipeline.schemas import Chunk, Document

_TARGET_WORDS = 120
_OVERLAP_WORDS = 20


# Parte el texto del documento en ventanas de ~120 palabras con 20 de traslape entre
# una y la siguiente, para no cortar una idea justo en el borde de un chunk.
def chunk_document(document: Document) -> list[Chunk]:
    words = document.text.split()
    if not words:
        return []

    chunks = []
    start = 0
    index = 0
    step = max(_TARGET_WORDS - _OVERLAP_WORDS, 1)
    while start < len(words):
        piece = words[start : start + _TARGET_WORDS]
        text = " ".join(piece)
        chunks.append(
            Chunk(
                id=f"{document.id}__chunk{index}",
                document_id=document.id,
                subject=document.subject,
                grade=document.grade,
                chunk_index=index,
                text=text,
            )
        )
        index += 1
        start += step
    return chunks
