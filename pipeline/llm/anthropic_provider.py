"""Proveedor de bajo costo vía la API de Anthropic. Solo se activa si hay ANTHROPIC_API_KEY."""

from __future__ import annotations

from pipeline.llm.base import LLMProvider


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key)
        self._model = model

    def generate(self, prompt: str, system: str | None = None, max_tokens: int = 1536) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system or "",
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text")
