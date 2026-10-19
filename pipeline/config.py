"""Configuración centralizada del pipeline, cargada desde variables de entorno / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DOCUMENTS_DIR = PROCESSED_DIR / "documents"
CHROMA_DIR = PROCESSED_DIR / "chroma"
EXAMEN_GENERADO_DIR = PROJECT_ROOT / "Examen_generado"
LECCION_GENERADA_DIR = PROJECT_ROOT / "Leccion_generada"
STANDARDS_DIR = Path(__file__).resolve().parent / "standards"

load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    ollama_model: str
    ollama_host: str
    anthropic_api_key: str | None
    anthropic_model: str
    embedding_model: str


def get_settings() -> Settings:
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "mock").strip().lower(),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5"),
        embedding_model=os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        ),
    )
