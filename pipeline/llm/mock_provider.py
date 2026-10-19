"""Proveedor sin red ni costo: devuelve preguntas de ejemplo fijas, claramente marcadas
como placeholder, para poder probar el flujo completo del pipeline sin ningún LLM real."""

from __future__ import annotations

import json

from pipeline.llm.base import LLMProvider

_PLACEHOLDER_QUESTIONS = [
    {
        "text": "[MOCK] Explica con tus propias palabras la idea principal del tema cubierto en este material.",
        "bloom_level": "Comprender",
        "dok_level": 2,
    },
    {
        "text": "[MOCK] ¿Cuál de los siguientes conceptos corresponde al tema estudiado? (pregunta de ejemplo, no generada por un LLM real)",
        "bloom_level": "Recordar",
        "dok_level": 1,
    },
]


class MockProvider(LLMProvider):
    def generate(self, prompt: str, system: str | None = None, max_tokens: int = 1536) -> str:
        return json.dumps({"questions": _PLACEHOLDER_QUESTIONS}, ensure_ascii=False)
