"""Auditoría de forma/calidad de CUALQUIER examen que un usuario suba (no necesariamente
generado por este pipeline) — complementa a identificar_materia/identificar_estandares con
chequeos de estructura, reutilizando piezas que ya existen (perfil Bloom/DOK, detección de
tipo de parte, embeddings), sin volver a tocar nada de lo archivado en _deprecated/pipeline/audit/.

LIMITACIÓN HONESTA: el audit original (archivado) incluía un 5to criterio, "sin fuga de
respuesta", que solo tiene sentido para un examen GENERADO con su estructura de opción
múltiple + respuesta correcta ya conocida de antemano. Un examen real subido por un usuario
no trae eso estructurado (normalmente ni siquiera incluye la clave de respuesta), así que ese
criterio no aplica aquí y se omite — no se intenta adivinar la respuesta correcta desde texto
crudo, sería una heurística demasiado frágil para reportarse como un criterio de auditoría.
"""

from __future__ import annotations

from pathlib import Path

from pipeline.config import get_settings
from pipeline.difficulty.part_type_rules import detect_part_type, points_for
from pipeline.difficulty.run import profile_file
from pipeline.embeddings.store import embed_texts
from pipeline.schemas import Question

_MIN_TOTAL_POINTS = 50
_MIN_DISTINCT_PARTS = 4
_ALL_PART_TYPES = ("pareo", "verdadero_falso", "opcion_multiple", "respuesta_corta", "ensayo", "completar")
_DUPLICATE_SIMILARITY_THRESHOLD = 0.90


def _criterio(criterio: str, aprobado: bool, detalle: str, explicacion: str = "") -> dict:
    return {"criterio": criterio, "aprobado": aprobado, "detalle": detalle, "explicacion": explicacion}


# Criterio 1: suma los puntos heurísticos (por DOK, pipeline/difficulty/part_type_rules.py)
# de todas las preguntas y chequea que pase de 50 — mismo umbral que el audit archivado.
def _check_points(questions: list[Question]) -> dict:
    total = sum(q.points or 0 for q in questions)
    aprobado = total > _MIN_TOTAL_POINTS
    explicacion = (
        ""
        if aprobado
        else f"Suma {total} punto(s) (heurística por DOK), pero se esperan más de {_MIN_TOTAL_POINTS} — "
        "un examen corto puede ser perfectamente válido, esto solo marca que es breve."
    )
    return _criterio(
        "Puntuación total > 50 (heurística por DOK)",
        aprobado,
        f"Total: {total} puntos ({len(questions)} pregunta(s)).",
        explicacion,
    )


# Criterio 2: cuenta cuántos tipos de parte distintos hay (detectados por patrón de texto)
# y chequea que sean al menos 4 — mismo umbral que el audit archivado.
def _check_parts(questions: list[Question]) -> dict:
    distinct = {q.part_type for q in questions if q.part_type}
    aprobado = len(distinct) >= _MIN_DISTINCT_PARTS
    faltantes = [p for p in _ALL_PART_TYPES if p not in distinct]
    explicacion = (
        ""
        if aprobado
        else f"Solo se detectaron {len(distinct)} tipo(s) de pregunta distinto(s); un examen con "
        f"variedad suele tener al menos {_MIN_DISTINCT_PARTS} (ej. {', '.join(faltantes[:2])}). "
        "La detección es por patrón de texto (opción múltiple/verdadero-falso/blanco/largo), puede "
        "fallar en formatos poco comunes."
    )
    return _criterio(
        "Mínimo 4 tipos de parte distintos (detectados por patrón)",
        aprobado,
        f"Tipos encontrados ({len(distinct)}): {', '.join(sorted(distinct)) or '(ninguno)'}.",
        explicacion,
    )


# Criterio 3: compara cada pregunta del examen contra las demás del mismo examen (no contra
# el banco histórico) y marca los pares demasiado parecidos entre sí.
def _check_internal_duplicates(questions: list[Question], embedding_model: str) -> dict:
    if len(questions) < 2:
        return _criterio(
            "Sin preguntas casi duplicadas (dentro del mismo examen)",
            True,
            "Menos de 2 preguntas detectadas — no hay pares que comparar.",
        )

    embeddings = embed_texts([q.text for q in questions], embedding_model)
    similarities = embeddings @ embeddings.T

    pares = []
    for i in range(len(questions)):
        for j in range(i + 1, len(questions)):
            if similarities[i][j] >= _DUPLICATE_SIMILARITY_THRESHOLD:
                pares.append((questions[i].id, questions[j].id, round(float(similarities[i][j]), 2)))

    explicacion = (
        f"Las preguntas de cada par listado son casi idénticas entre sí (similaridad semántica "
        f">= {_DUPLICATE_SIMILARITY_THRESHOLD}) — puede ser redundancia involuntaria o repetición "
        "intencional (refuerzo); revisa si tiene sentido en este examen."
        if pares
        else ""
    )
    return _criterio(
        "Sin preguntas casi duplicadas (dentro del mismo examen)",
        not pares,
        f"Pares casi-duplicados: {pares}." if pares else "Ninguna pregunta se parece demasiado a otra.",
        explicacion,
    )


# Punto de entrada: perfila el archivo (reutiliza profile_file, que ya separa preguntas y
# clasifica Bloom/DOK), enriquece cada pregunta con tipo de parte/puntos, y corre los 3
# criterios de forma aplicables a un examen real (sin fuga de respuesta, ver docstring).
#
# `subject`/`grade` son opcionales: profile_file infiere la materia por la carpeta del
# archivo (data/raw/<materia>/...), lo cual no funciona para un archivo subido por un
# usuario (vive en un temporal fuera de data/raw/) — si el llamador ya corrió
# predict_exam_subject, puede pasar ese resultado aquí para que "materia" en la salida
# no quede en "unknown" sin necesidad de reentrenar el clasificador otra vez.
def review_exam(path: Path, subject: str | None = None, grade: int | None = None) -> dict:
    profile, questions = profile_file(path, subject=subject, grade=grade)
    for q in questions:
        q.part_type = detect_part_type(q.text)
        q.points = points_for(q.dok_level)

    settings = get_settings()
    criterios = [
        _check_points(questions),
        _check_parts(questions),
        _check_internal_duplicates(questions, settings.embedding_model),
    ]

    return {
        "archivo": str(path),
        "materia": profile.subject,
        "grado": profile.grade,
        "total_preguntas": profile.total_questions,
        "perfil_bloom_dok": profile.counts,
        "criterios": criterios,
        "aprobado_general": all(c["aprobado"] for c in criterios),
    }
