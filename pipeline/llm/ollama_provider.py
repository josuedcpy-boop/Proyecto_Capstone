"""Proveedor gratis y local: llama a un servidor Ollama corriendo en esta máquina.
Requiere instalar Ollama (https://ollama.com) y descargar un modelo, ej. `ollama pull llama3.1:8b`."""

from __future__ import annotations

import requests

from pipeline.llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    # Guarda el host/modelo a usar en cada llamada.
    def __init__(self, host: str, model: str):
        self._host = host.rstrip("/")
        self._model = model

    # Le manda el prompt a la API local de Ollama (/api/generate) y devuelve el texto de
    # respuesta; si Ollama no está corriendo, lanza un error claro explicando cómo arrancarlo.
    def generate(self, prompt: str, system: str | None = None, max_tokens: int = 1536) -> str:
        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": system or "",
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        try:
            response = requests.post(f"{self._host}/api/generate", json=payload, timeout=120)
            response.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"No se pudo conectar a Ollama en {self._host}. "
                "¿Está instalado y corriendo? (`ollama serve`, y `ollama pull "
                f"{self._model}` si no has descargado el modelo)"
            ) from exc
        return response.json()["response"]
