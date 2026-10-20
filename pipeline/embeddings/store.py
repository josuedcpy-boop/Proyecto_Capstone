"""Wrapper delgado sobre sentence-transformers (embeddings locales, gratis) + Chroma (vector store local)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

from pipeline.schemas import Chunk


# Carga el modelo de embeddings una sola vez por nombre (descarga la primera vez, luego
# queda cacheado en memoria para el resto del proceso).
@lru_cache(maxsize=2)
def _get_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


# Convierte una lista de textos en sus vectores de embedding (normalizados, para que el
# producto punto entre dos vectores sea directamente su similaridad coseno).
def embed_texts(texts: list[str], model_name: str) -> np.ndarray:
    if not texts:
        return np.empty((0, 0))
    model = _get_model(model_name)
    return np.asarray(model.encode(texts, normalize_embeddings=True))


def cosine_similarity_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Asume que ambas matrices ya vienen normalizadas (ver embed_texts)."""
    return a @ b.T


class EmbeddingStore:
    """Persiste chunks + sus embeddings en una colección Chroma local, para RAG."""

    # Abre (o crea) la base Chroma persistida en `persist_dir`.
    def __init__(self, persist_dir: Path, model_name: str, collection_name: str = "chunks"):
        import chromadb

        self._model_name = model_name
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(collection_name)

    # Embebe cada chunk y lo guarda (o actualiza, si ya existía ese id) en la colección.
    def upsert_chunks(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        embeddings = embed_texts([c.text for c in chunks], self._model_name)
        self._collection.upsert(
            ids=[c.id for c in chunks],
            embeddings=embeddings.tolist(),
            documents=[c.text for c in chunks],
            metadatas=[
                {"document_id": c.document_id, "subject": c.subject, "grade": c.grade or -1}
                for c in chunks
            ],
        )

    # Busca los `n_results` chunks más parecidos a `text`, opcionalmente filtrando por
    # materia/grado.
    def query(
        self, text: str, n_results: int = 5, subject: str | None = None, grade: int | None = None
    ) -> list[dict]:
        clauses = []
        if subject is not None:
            clauses.append({"subject": {"$eq": subject}})
        if grade is not None:
            clauses.append({"grade": {"$eq": grade}})
        where = {"$and": clauses} if len(clauses) > 1 else (clauses[0] if clauses else None)

        query_embedding = embed_texts([text], self._model_name)[0].tolist()
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
        )
        matches = []
        for doc, meta, dist, doc_id in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0], result["ids"][0]
        ):
            matches.append({"id": doc_id, "text": doc, "metadata": meta, "distance": dist})
        return matches

    # Cuántos chunks hay guardados en la colección.
    def count(self) -> int:
        return self._collection.count()
