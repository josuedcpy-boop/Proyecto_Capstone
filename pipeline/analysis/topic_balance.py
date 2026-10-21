"""Agrupa preguntas históricas por similaridad semántica (k-means + PCA, sin estándares
predefinidos) para ver qué temas están sobre/sub-representados en el banco real — una vista
complementaria al etiquetado contra los 8 estándares conocidos (pipeline/tagging/)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

from pipeline.difficulty.splitter import split_questions
from pipeline.embeddings.store import cosine_similarity_matrix, embed_texts
from pipeline.ingest.run import load_all_documents
from pipeline.schemas import Question
from pipeline.standards.loader import TaggableStandard, get_standards_for

_K_MIN = 2
_K_MAX = 10
_PCA_MAX_COMPONENTS = 50
_UNDER_REPRESENTED_RATIO = 0.5
_OVER_REPRESENTED_RATIO = 1.5


# Junta todas las preguntas históricas (de exámenes/reviews ya ingeridos) de esa materia/grado.
def collect_historical_questions(subject: str, grade: int | None) -> list[Question]:
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


# Corre KMeans con cada k del rango y se queda con el que da mejor silhouette score
# (qué tan bien separados quedan los grupos) — así no hay que adivinar k a mano.
def auto_select_k(embeddings: np.ndarray, k_min: int = _K_MIN, k_max: int | None = None) -> int:
    """Prueba varios k y se queda con el de mayor silhouette score."""
    n_samples = embeddings.shape[0]
    k_max = min(k_max or _K_MAX, n_samples - 1)
    if k_max < k_min:
        return max(1, n_samples)

    best_k, best_score = k_min, -1.0
    for k in range(k_min, k_max + 1):
        labels = KMeans(n_clusters=k, random_state=0, n_init="auto").fit_predict(embeddings)
        if len(set(labels)) < 2:
            continue
        score = silhouette_score(embeddings, labels)
        if score > best_score:
            best_k, best_score = k, score
    return best_k


@dataclass
class ClusterInfo:
    cluster_id: int
    size: int
    sample_questions: list[str]
    closest_standard: TaggableStandard | None
    closest_standard_similarity: float


@dataclass
class ClusterReport:
    clusters: list[ClusterInfo] = field(default_factory=list)
    total_questions: int = 0
    k: int = 0


# Embebe las preguntas, reduce dimensiones con PCA, agrupa con KMeans (k automático), y
# etiqueta cada grupo con el estándar cuyo centroide quede más cerca.
def cluster_questions(questions: list[Question], embedding_model: str, standards: list[TaggableStandard]) -> ClusterReport:
    if len(questions) < _K_MIN:
        return ClusterReport(clusters=[], total_questions=len(questions), k=0)

    embeddings = embed_texts([q.text for q in questions], embedding_model)

    n_components = min(_PCA_MAX_COMPONENTS, embeddings.shape[0] - 1, embeddings.shape[1])
    reduced = PCA(n_components=n_components, random_state=0).fit_transform(embeddings) if n_components >= 2 else embeddings

    k = auto_select_k(reduced)
    kmeans = KMeans(n_clusters=k, random_state=0, n_init="auto").fit(reduced)
    labels = kmeans.labels_

    standard_embeddings = embed_texts([s.text for s in standards], embedding_model) if standards else None

    clusters = []
    for cluster_id in range(k):
        member_indices = [i for i, label in enumerate(labels) if label == cluster_id]
        if not member_indices:
            continue
        cluster_embeddings = embeddings[member_indices]
        centroid = cluster_embeddings.mean(axis=0, keepdims=True)
        centroid = centroid / (np.linalg.norm(centroid) + 1e-9)

        closest_standard, closest_similarity = None, 0.0
        if standard_embeddings is not None and len(standard_embeddings):
            similarities = cosine_similarity_matrix(centroid, standard_embeddings)[0]
            best_index = int(similarities.argmax())
            closest_standard = standards[best_index]
            closest_similarity = float(similarities[best_index])

        clusters.append(
            ClusterInfo(
                cluster_id=cluster_id,
                size=len(member_indices),
                sample_questions=[questions[i].text[:120] for i in member_indices[:3]],
                closest_standard=closest_standard,
                closest_standard_similarity=round(closest_similarity, 4),
            )
        )

    return ClusterReport(clusters=clusters, total_questions=len(questions), k=k)


def balance_report(report: ClusterReport, standards: list[TaggableStandard]) -> dict:
    """Cruza los clusters encontrados contra la lista completa de estándares del grado."""
    if not report.clusters:
        return {"estado": "sin_datos", "detalle": "No hay suficientes preguntas históricas para agrupar."}

    avg_size = report.total_questions / len(report.clusters)
    # Clave por cluster_id, no por código de estándar: varios clusters distintos pueden
    # caer más cerca del mismo estándar, y usar el código como clave perdía esos grupos
    # (el último sobreescribía a los anteriores).
    by_cluster: dict[str, dict] = {}

    for cluster in report.clusters:
        estado = "balanceado"
        if cluster.size < avg_size * _UNDER_REPRESENTED_RATIO:
            estado = "sub-representado"
        elif cluster.size > avg_size * _OVER_REPRESENTED_RATIO:
            estado = "sobre-representado"

        code = cluster.closest_standard.code if cluster.closest_standard else "(sin estándar cercano)"
        by_cluster[f"grupo_{cluster.cluster_id}"] = {
            "estándar_más_cercano": code,
            "estándar": cluster.closest_standard.name if cluster.closest_standard else None,
            "preguntas_en_cluster": cluster.size,
            "estado": estado,
            "similaridad_con_estandar": cluster.closest_standard_similarity,
            "ejemplos": cluster.sample_questions,
        }

    covered_codes = {c.closest_standard.code for c in report.clusters if c.closest_standard}
    sin_cobertura = [s.name for s in standards if s.code not in covered_codes]

    return {
        "estado": "ok",
        "total_preguntas_historicas": report.total_questions,
        "numero_de_grupos_detectados": report.k,
        "promedio_preguntas_por_grupo": round(avg_size, 1),
        "por_grupo": by_cluster,
        "estandares_sin_grupo_cercano": sin_cobertura,
    }
