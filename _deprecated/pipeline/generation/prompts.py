"""Plantillas de prompt para generación de preguntas, basadas en las reglas de redacción
de opción múltiple (Haladyna et al.) y las definiciones Bloom/DOK de
docs/estandares_y_mejores_practicas.md (secciones 6 y 8)."""

from __future__ import annotations

from pipeline.schemas import DifficultyProfile
from pipeline.standards.loader import TaggableStandard

SYSTEM_PROMPT = """Eres un asistente que genera preguntas de examen para escuela K-12 en Puerto Rico.

Reglas de redacción (basadas en Haladyna et al. 2002):
- Enunciado (stem) claro, sin negaciones ("NO es", "todas excepto").
- Si es opción múltiple: distractores plausibles (errores comunes de estudiantes, no absurdos),
  forma paralela, sin "todas/ninguna de las anteriores", una sola respuesta correcta defendible.
- Ancla cada pregunta en el contexto/material proporcionado — no inventes datos que no estén ahí
  ni en el conocimiento general del tema.

Para "bloom_level" elige EXACTAMENTE UNA de estas 6 palabras (nunca combines varias):
Recordar, Comprender, Aplicar, Analizar, Evaluar, Crear.
Para "dok_level" elige un solo número entero entre 1 y 4.
Para "part_type" elige EXACTAMENTE UNA de estas 6 palabras: pareo, verdadero_falso,
opcion_multiple, respuesta_corta, ensayo, completar. IMPORTANTE: nunca repitas el mismo
part_type en todas las preguntas — varía entre varios tipos distintos.
Si part_type es "opcion_multiple", agrega "options" (lista de 4 strings) y
"correct_option_index" (0-3). El "text" (enunciado) NUNCA debe mencionar ni insinuar cuál
opción es la correcta.

Debes responder ÚNICAMENTE con un JSON válido de la forma (este es solo un ejemplo del formato,
no copies estos valores). Usa EXACTAMENTE estos nombres de clave en inglés, sin traducirlos:
{"questions": [
  {"text": "¿Cuál fue la causa principal de...?", "bloom_level": "Comprender", "dok_level": 2, "part_type": "opcion_multiple", "options": ["opción A", "opción B", "opción C", "opción D"], "correct_option_index": 1, "standard_codes": ["CC"]},
  {"text": "Explica por qué...", "bloom_level": "Analizar", "dok_level": 3, "part_type": "ensayo", "standard_codes": ["CC"]}
]}
Sin texto antes ni después del JSON."""


def build_user_prompt(
    subject: str,
    grade: int | None,
    context_chunks: list[str],
    standards: list[TaggableStandard],
    target_profile: DifficultyProfile,
    tema: str | None = None,
) -> str:
    """Prompt deliberadamente corto: con modelos locales pequeños (ej. llama3.1:8b), un
    prompt largo con estándares + contexto + perfil detallado hace que el modelo ignore el
    formato JSON pedido o se desvíe del tema (confirmado probando). Si hay tema, este manda
    y se omite el listado de estándares; si no, los estándares son el ancla temática."""
    context_text = "\n---\n".join(context_chunks) if context_chunks else "(sin contexto recuperado)"
    profile_lines = ", ".join(f"{count}x {key}" for key, count in target_profile.counts.items())
    tema_o_estandares = (
        f"Tema: {tema}."
        if tema
        else "Estándares: " + "; ".join(f"{s.code} ({s.name})" for s in standards)
    )

    return f"""Materia: {subject}, grado {grade}. {tema_o_estandares}

Contexto de referencia (úsalo como base factual, no inventes datos fuera de esto):
{context_text}

Genera exactamente {target_profile.total_questions} pregunta(s) nueva(s) sobre el tema de arriba,
con esta distribución de dificultad: {profile_lines}."""
