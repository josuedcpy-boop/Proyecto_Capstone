"""RAG (recuperación sobre el banco de materiales) + llamada al LLMProvider configurado
para generar preguntas nuevas que cumplan un perfil de dificultad/cobertura objetivo."""

from __future__ import annotations

import json
import re

from pipeline.config import CHROMA_DIR, get_settings
from pipeline.difficulty.bloom_dok_rules import classify_question
from pipeline.difficulty.part_type_rules import (
    VALID_PART_TYPES,
    detect_part_type,
    points_for,
    strip_option_prefix,
)
from pipeline.embeddings.chunking import chunk_document
from pipeline.embeddings.store import EmbeddingStore
from pipeline.generation.prompts import SYSTEM_PROMPT, build_user_prompt
from pipeline.ingest.run import load_all_documents
from pipeline.llm.factory import get_provider
from pipeline.schemas import DifficultyProfile, GeneratedExam, Question
from pipeline.standards.loader import get_standards_for

_CONTEXT_CHUNKS_PER_STANDARD = 2
_CONTEXT_CHUNKS_FOR_TEMA = 4
_MAX_CONTEXT_CHUNKS = 4  # prompts más largos hacen que modelos locales pequeños ignoren el formato pedido
_VALID_BLOOM_LEVELS = {"Recordar", "Comprender", "Aplicar", "Analizar", "Evaluar", "Crear"}
# Material de referencia/backmatter de libros de texto (glosarios, índices, atlas, lista de
# presidentes...) es puro ruido para RAG: es texto alfabético/tabular sin hilo narrativo que
# puede coincidir por palabras sueltas con casi cualquier tema y confundir al LLM (confirmado
# probando: un chunk de glosario coló "Pinckney's Treaty" en una pregunta sobre Colón).
_BACKMATTER_PATTERN = re.compile(r"reference_part|glossary|_toc\b|cover.*toc.*preface", re.IGNORECASE)


# True si el documento es material de referencia de libro de texto (glosario, índice, atlas...).
def _is_backmatter(document) -> bool:
    return document.doc_type == "textbook" and bool(_BACKMATTER_PATTERN.search(document.source_path))


def _normalize_bloom_dok(text: str, bloom_level, dok_level) -> tuple[str, int]:
    """Modelos locales/pequeños no siempre respetan el formato pedido (ej. devuelven
    'Recordar|Comprender|...' en vez de un solo valor). Si el valor no es válido, se
    recalcula con la misma heurística usada para exámenes históricos (sin LLM)."""
    if isinstance(bloom_level, str) and bloom_level in _VALID_BLOOM_LEVELS and isinstance(dok_level, int) and 1 <= dok_level <= 4:
        return bloom_level, dok_level
    return classify_question(text)


def _normalize_part_type_and_options(
    text: str, part_type, options, correct_option_index
) -> tuple[str, list[str] | None, int | None]:
    """Igual filosofía que _normalize_bloom_dok: si el modelo no da un part_type válido,
    se detecta con heurística. Si dice 'opcion_multiple' pero las opciones no son usables,
    se degrada a 'respuesta_corta' en vez de fallar."""
    if not isinstance(part_type, str) or part_type not in VALID_PART_TYPES:
        part_type = detect_part_type(text)

    if part_type == "opcion_multiple":
        valid_options = (
            isinstance(options, list) and len(options) >= 2 and all(isinstance(o, str) for o in options)
        )
        valid_index = isinstance(correct_option_index, int) and 0 <= correct_option_index < len(options or [])
        if valid_options and valid_index:
            return part_type, [strip_option_prefix(o) for o in options], correct_option_index
        return "respuesta_corta", None, None

    return part_type, None, None


# Construye (o actualiza) el índice de embeddings con todos los documentos de esa
# materia/grado, excluyendo el material de referencia/backmatter.
def _build_index(subject: str, grade: int | None, embedding_model: str) -> EmbeddingStore:
    store = EmbeddingStore(CHROMA_DIR, embedding_model)
    documents = [
        d
        for d in load_all_documents()
        if d.subject == subject and (grade is None or d.grade == grade) and not _is_backmatter(d)
    ]
    for document in documents:
        store.upsert_chunks(chunk_document(document))
    return store


_REFERENCE_TEXT_MAX_WORDS = 500


def _retrieve_context(
    store: EmbeddingStore,
    subject: str,
    grade: int | None,
    standards,
    tema: str | None,
    reference_text: str | None = None,
) -> list[str]:
    """Recupera pocos chunks y enfocados: prompts largos hacen que modelos locales pequeños
    (ej. llama3.1:8b) ignoren el formato pedido o se desvíen del tema (confirmado probando)."""
    seen_ids: set[str] = set()
    context: list[str] = []

    if reference_text:
        # Si el usuario apuntó a un examen de referencia concreto (--perfil-de), ese documento
        # ES el tema — se incluye directo en vez de confiar en que gane el ranking de
        # similaridad contra miles de chunks de todo el grado (confirmado probando: no siempre
        # ganaba, aunque fuera el más relevante).
        context.append(" ".join(reference_text.split()[:_REFERENCE_TEXT_MAX_WORDS]))

    def _add_matches(matches):
        for match in matches:
            if match["id"] not in seen_ids and len(context) < _MAX_CONTEXT_CHUNKS:
                seen_ids.add(match["id"])
                context.append(match["text"])

    remaining = _MAX_CONTEXT_CHUNKS - len(context)
    if remaining > 0:
        if tema:
            _add_matches(store.query(tema, n_results=min(_CONTEXT_CHUNKS_FOR_TEMA, remaining), subject=subject, grade=grade))
        else:
            for standard in standards[:2]:
                _add_matches(store.query(standard.text, n_results=_CONTEXT_CHUNKS_PER_STANDARD, subject=subject, grade=grade))
    return context


_QUESTIONS_KEY_ALIASES = ("questions", "preguntas")
_TEXT_KEY_ALIASES = ("text", "texto", "pregunta", "enunciado")
_BLOOM_KEY_ALIASES = ("bloom_level", "bloom", "nivel_bloom", "nivel")
_DOK_KEY_ALIASES = ("dok_level", "dok", "nivel_dok")
_STANDARDS_KEY_ALIASES = ("standard_codes", "estandares", "estándares")
_PART_TYPE_KEY_ALIASES = ("part_type", "tipo", "tipo_parte")
_OPTIONS_KEY_ALIASES = ("options", "opciones")
_CORRECT_INDEX_KEY_ALIASES = ("correct_option_index", "correct_index", "respuesta_correcta_index")


# Devuelve el valor de la primera clave de `keys` que exista en el diccionario `d`.
def _first_present(d: dict, keys: tuple[str, ...], default=None):
    for key in keys:
        if key in d:
            return d[key]
    return default


def _parse_llm_response(raw: str) -> list[dict]:
    """Modelos locales pequeños a veces traducen las claves del JSON al español pese a que
    se les pide no hacerlo — aceptamos ambos idiomas en vez de descartar la respuesta."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []

    raw_questions = _first_present(data, _QUESTIONS_KEY_ALIASES, [])
    if not isinstance(raw_questions, list):
        return []

    normalized = []
    for item in raw_questions:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "text": _first_present(item, _TEXT_KEY_ALIASES, ""),
                "bloom_level": _first_present(item, _BLOOM_KEY_ALIASES),
                "dok_level": _first_present(item, _DOK_KEY_ALIASES),
                "standard_codes": _first_present(item, _STANDARDS_KEY_ALIASES, []),
                "part_type": _first_present(item, _PART_TYPE_KEY_ALIASES),
                "options": _first_present(item, _OPTIONS_KEY_ALIASES),
                "correct_option_index": _first_present(item, _CORRECT_INDEX_KEY_ALIASES),
            }
        )
    return normalized


_RETRY_SUFFIX = (
    "\n\nTu respuesta anterior no fue un JSON válido o no siguió el formato pedido. "
    "Responde ÚNICAMENTE el JSON de la forma indicada arriba, sin explicaciones, sin texto "
    "antes ni después, y sin markdown."
)


# Función principal de esta etapa: recupera contexto relevante (RAG), le pide al
# LLMProvider configurado que genere preguntas nuevas con ese perfil de dificultad, y
# normaliza la respuesta a una lista de Question (con reintento si el formato sale mal).
def generate_exam(
    subject: str,
    grade: int | None,
    target_profile: DifficultyProfile,
    tema: str | None = None,
    reference_text: str | None = None,
) -> GeneratedExam:
    settings = get_settings()
    standards = get_standards_for(subject, grade)
    store = _build_index(subject, grade, settings.embedding_model)
    context_chunks = _retrieve_context(store, subject, grade, standards, tema, reference_text)

    provider = get_provider(settings)
    prompt = build_user_prompt(subject, grade, context_chunks, standards, target_profile, tema)

    raw_response = provider.generate(prompt, system=SYSTEM_PROMPT)
    raw_questions = [q for q in _parse_llm_response(raw_response) if q["text"].strip()]

    if not raw_questions:
        # los modelos locales pequeños a veces ignoran "responde solo JSON" — un reintento
        # con la corrección explícita suele bastar.
        raw_response = provider.generate(prompt + _RETRY_SUFFIX, system=SYSTEM_PROMPT)
        raw_questions = [q for q in _parse_llm_response(raw_response) if q["text"].strip()]

    if not raw_questions:
        raise RuntimeError(
            "El modelo no devolvió preguntas en el formato esperado (JSON) tras dos intentos. "
            f"Respuesta cruda del modelo:\n{raw_response[:500]}"
        )

    questions = []
    for i, q in enumerate(raw_questions):
        text = q.get("text", "")
        bloom_level, dok_level = _normalize_bloom_dok(text, q.get("bloom_level"), q.get("dok_level"))
        part_type, options, correct_option_index = _normalize_part_type_and_options(
            text, q.get("part_type"), q.get("options"), q.get("correct_option_index")
        )
        questions.append(
            Question(
                id=f"{subject}_{grade}_gen{i}",
                text=text,
                bloom_level=bloom_level,
                dok_level=dok_level,
                standard_codes=q.get("standard_codes", []),
                source="generated",
                part_type=part_type,
                points=points_for(dok_level),
                options=options,
                correct_option_index=correct_option_index,
            )
        )

    return GeneratedExam(subject=subject, grade=grade, questions=questions, target_profile=target_profile)
