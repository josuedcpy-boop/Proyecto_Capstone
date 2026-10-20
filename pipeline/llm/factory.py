"""Selecciona la implementación de LLMProvider según Settings.llm_provider."""

from __future__ import annotations

from pipeline.config import Settings
from pipeline.llm.base import LLMProvider


# Según LLM_PROVIDER en la configuración, construye y devuelve el proveedor correspondiente.
def get_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "mock":
        from pipeline.llm.mock_provider import MockProvider

        return MockProvider()

    if settings.llm_provider == "ollama":
        from pipeline.llm.ollama_provider import OllamaProvider

        return OllamaProvider(host=settings.ollama_host, model=settings.ollama_model)

    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("LLM_PROVIDER=anthropic pero ANTHROPIC_API_KEY no está configurada.")
        from pipeline.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(api_key=settings.anthropic_api_key, model=settings.anthropic_model)

    raise ValueError(f"LLM_PROVIDER desconocido: {settings.llm_provider!r} (usa mock | ollama | anthropic)")
