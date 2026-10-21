"""Interfaz común para cualquier backend de LLM generativo (mock, Ollama local, Anthropic, etc.)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system: str | None = None, max_tokens: int = 1536) -> str:
        """Devuelve la respuesta del modelo como texto (se espera JSON, ver generation/prompts.py)."""
        raise NotImplementedError
