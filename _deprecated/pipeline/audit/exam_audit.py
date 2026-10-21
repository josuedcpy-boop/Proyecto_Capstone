"""Auditoría de un examen generado contra los 5 criterios de docs/criterios_auditoria.md.
Sin LLM — todo vía reglas y embeddings ya usados en el resto del pipeline."""

from __future__ import annotations

import numpy as np

from pipeline.embeddings.store import embed_texts
from pipeline.schemas import AuditCriterionResult, AuditReport, Document, GeneratedExam, Question
from pipeline.tagging.run import document_coverage, tag_document

_MIN_TOTAL_POINTS = 50
_MIN_DISTINCT_PARTS = 4
_MIN_COVERAGE_SIMILARITY = 0.5
_DUPLICATE_SIMILARITY_THRESHOLD = 0.90


_ALL_PART_TYPES = ("pareo", "verdadero_falso", "opcion_multiple", "respuesta_corta", "ensayo", "completar")


# Criterio 1: suma los puntos de todas las preguntas y chequea que pase de 50.
def _check_points(questions: list[Question]) -> AuditCriterionResult:
    total = sum(q.points or 0 for q in questions)
    aprobado = total > _MIN_TOTAL_POINTS
    explicacion = (
        ""
        if aprobado
        else f"Suma {total} punto(s), pero se requiere más de {_MIN_TOTAL_POINTS} — faltan al menos "
        f"{_MIN_TOTAL_POINTS + 1 - total} punto(s). Añade más preguntas o sube el valor de las existentes."
    )
    return AuditCriterionResult(
        criterio="Puntuación total > 50",
        aprobado=aprobado,
        detalle=f"Total: {total} puntos ({len(questions)} pregunta(s)).",
        explicacion=explicacion,
    )


# Criterio 2: cuenta cuántos part_type distintos hay y chequea que sean al menos 4.
def _check_parts(questions: list[Question]) -> AuditCriterionResult:
    distinct = {q.part_type for q in questions if q.part_type}
    aprobado = len(distinct) >= _MIN_DISTINCT_PARTS
    faltantes = [p for p in _ALL_PART_TYPES if p not in distinct]
    explicacion = (
        ""
        if aprobado
        else f"Solo hay {len(distinct)} tipo(s) de pregunta distinto(s); se requieren al menos "
        f"{_MIN_DISTINCT_PARTS}. Añade {_MIN_DISTINCT_PARTS - len(distinct)} tipo(s) más, por ejemplo: "
        f"{', '.join(faltantes[:_MIN_DISTINCT_PARTS - len(distinct)])}."
    )
    return AuditCriterionResult(
        criterio="Mínimo 4 partes distintas",
        aprobado=aprobado,
        detalle=f"Partes encontradas ({len(distinct)}): {', '.join(sorted(distinct)) or '(ninguna)'}.",
        explicacion=explicacion,
    )


# Simplifica el reporte de cobertura a solo {código_estándar: cantidad de chunks}.
def _coverage_vector(coverage: dict[str, dict]) -> dict[str, int]:
    return {code: entry["chunk_count"] for code, entry in coverage.items()}


# Similaridad coseno entre dos diccionarios {código: conteo}, tratando las claves ausentes como 0.
def _cosine_over_dicts(a: dict[str, int], b: dict[str, int]) -> float:
    codes = sorted(set(a) | set(b))
    if not codes:
        return 0.0
    va = np.array([a.get(c, 0) for c in codes], dtype=float)
    vb = np.array([b.get(c, 0) for c in codes], dtype=float)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(va @ vb / (na * nb))


# Criterio 3: etiqueta el material de referencia y las preguntas generadas contra los
# estándares, y compara ambas distribuciones por similaridad coseno.
def _check_coverage(
    questions: list[Question], reference_text: str, subject: str, grade: int | None, embedding_model: str
) -> AuditCriterionResult:
    if not reference_text or not questions:
        return AuditCriterionResult(
            criterio="Cobertura de temas comparable al material fuente",
            aprobado=False,
            detalle="Sin texto de referencia o sin preguntas generadas — no se puede comparar.",
            explicacion=(
                "No se puede evaluar cobertura sin material de referencia — vuelve a auditar pasando "
                "--perfil-de <ruta al examen/material original> si el .docx no lo guardó."
            ),
        )

    reference_doc = Document(
        id="audit_reference",
        subject=subject,
        grade=grade,
        doc_type="exam",
        group="audit",
        source_path="(auditoría)",
        text=reference_text,
    )
    generated_doc = Document(
        id="audit_generated",
        subject=subject,
        grade=grade,
        doc_type="exam",
        group="audit",
        source_path="(auditoría)",
        text="\n".join(q.text for q in questions),
    )

    reference_coverage = _coverage_vector(document_coverage(tag_document(reference_doc, embedding_model)))
    generated_coverage = _coverage_vector(document_coverage(tag_document(generated_doc, embedding_model)))
    similarity = _cosine_over_dicts(reference_coverage, generated_coverage)
    aprobado = similarity >= _MIN_COVERAGE_SIMILARITY

    explicacion = ""
    if not aprobado:
        faltantes = sorted(set(reference_coverage) - set(generated_coverage))
        extras = sorted(set(generated_coverage) - set(reference_coverage))
        partes = [
            f"La distribución de temas del examen generado no se parece a la del material fuente "
            f"(similaridad {similarity:.2f}, se requiere al menos {_MIN_COVERAGE_SIMILARITY})."
        ]
        if faltantes:
            partes.append(f"Estándares del material fuente que no aparecen en lo generado: {', '.join(faltantes)}.")
        if extras:
            partes.append(f"Estándares presentes en lo generado pero no en la fuente: {', '.join(extras)}.")
        partes.append("Revisa si el contexto RAG está anclado al tema correcto, o genera más preguntas de los estándares faltantes.")
        explicacion = " ".join(partes)

    return AuditCriterionResult(
        criterio="Cobertura de temas comparable al material fuente",
        aprobado=aprobado,
        detalle=(
            f"Similaridad coseno entre distribución de estándares: {similarity:.2f} "
            f"(umbral {_MIN_COVERAGE_SIMILARITY}). Fuente: {reference_coverage or '(sin estándares detectados)'}. "
            f"Generado: {generated_coverage or '(sin estándares detectados)'}."
        ),
        explicacion=explicacion,
    )


def _check_leakage(questions: list[Question]) -> AuditCriterionResult:
    """Solo aplica a preguntas de opción múltiple con opciones válidas — para otros tipos
    de pregunta no hay una noción clara de "respuesta correcta separada del enunciado"."""
    leaks = []
    checked = 0
    unchecked = 0
    for q in questions:
        if q.part_type != "opcion_multiple" or not q.options:
            continue
        if q.correct_option_index is None:
            # Puede pasar al re-auditar un .docx ya ensamblado: por diseño no se guarda ahí
            # cuál opción es la correcta (para no revelarla en el examen), así que no hay
            # forma de comparar el enunciado contra "la respuesta correcta".
            unchecked += 1
            continue
        checked += 1
        correct_text = q.options[q.correct_option_index].strip().lower()
        if correct_text and correct_text in q.text.lower():
            leaks.append(q.id)

    detalle_partes = []
    if checked:
        detalle_partes.append(
            f"{len(leaks)} de {checked} pregunta(s) de opción múltiple revisada(s) revelan la respuesta: {leaks}."
            if leaks
            else f"Ninguna de las {checked} pregunta(s) de opción múltiple revisada(s) revela la respuesta."
        )
    if unchecked:
        detalle_partes.append(
            f"{unchecked} pregunta(s) de opción múltiple no se pudieron revisar (sin clave de respuesta disponible)."
        )
    if not checked and not unchecked:
        detalle_partes.append("No hay preguntas de opción múltiple en este examen.")

    # Si hay preguntas sin revisar, no se puede declarar "aprobado" con certeza — se marca
    # como no aprobado para que quede visible que falta información, no para asumir que falló.
    aprobado = not leaks and not unchecked
    explicacion = ""
    if not aprobado:
        partes = []
        if leaks:
            partes.append(
                f"Las preguntas {leaks} repiten en su propio enunciado el texto de la opción correcta "
                "— un estudiante puede adivinar la respuesta sin saber el contenido. Reescribe el "
                "enunciado o la opción correcta para que no coincidan textualmente."
            )
        if unchecked:
            partes.append(
                f"{unchecked} pregunta(s) de opción múltiple no se pudieron revisar porque este .docx no "
                "guarda cuál opción es la correcta (por diseño, para no revelarla en el examen). Para "
                "confirmar este criterio con certeza, audita justo después de generar el examen (antes de "
                "ensamblarlo a .docx), por ejemplo vía `pipeline.cli generate` o la herramienta MCP "
                "`generar_examen`."
            )
        explicacion = " ".join(partes)
    return AuditCriterionResult(
        criterio="Sin fuga de respuesta", aprobado=aprobado, detalle=" ".join(detalle_partes), explicacion=explicacion
    )


# Criterio 5: compara cada pregunta generada contra las demás del mismo examen (no
# contra el banco histórico) y marca los pares demasiado parecidos entre sí.
def _check_internal_duplicates(questions: list[Question], embedding_model: str) -> AuditCriterionResult:
    if len(questions) < 2:
        return AuditCriterionResult(
            criterio="Sin preguntas casi duplicadas",
            aprobado=True,
            detalle="Menos de 2 preguntas generadas — no hay pares que comparar.",
        )

    embeddings = embed_texts([q.text for q in questions], embedding_model)
    similarities = embeddings @ embeddings.T

    duplicate_pairs = []
    for i in range(len(questions)):
        for j in range(i + 1, len(questions)):
            if similarities[i][j] >= _DUPLICATE_SIMILARITY_THRESHOLD:
                duplicate_pairs.append((questions[i].id, questions[j].id, round(float(similarities[i][j]), 2)))

    detalle = (
        f"Pares casi-duplicados encontrados: {duplicate_pairs}."
        if duplicate_pairs
        else "Ninguna pregunta generada se parece demasiado a otra del mismo examen."
    )
    explicacion = (
        f"Las preguntas de cada par listado son casi idénticas entre sí (similaridad semántica "
        f">= {_DUPLICATE_SIMILARITY_THRESHOLD}) — elimina o reescribe una de cada par para no repetir "
        "contenido dentro del mismo examen."
        if duplicate_pairs
        else ""
    )
    return AuditCriterionResult(
        criterio="Sin preguntas casi duplicadas",
        aprobado=not duplicate_pairs,
        detalle=detalle,
        explicacion=explicacion,
    )


# Punto de entrada: corre los 5 criterios sobre el examen y devuelve el reporte completo.
def audit_exam(exam: GeneratedExam, reference_text: str, embedding_model: str) -> AuditReport:
    criterios = [
        _check_points(exam.questions),
        _check_parts(exam.questions),
        _check_coverage(exam.questions, reference_text, exam.subject, exam.grade, embedding_model),
        _check_leakage(exam.questions),
        _check_internal_duplicates(exam.questions, embedding_model),
    ]
    return AuditReport(criterios=criterios, aprobado_general=all(c.aprobado for c in criterios))
