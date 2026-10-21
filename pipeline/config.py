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
STANDARDS_DIR = Path(__file__).resolve().parent / "standards"
BANCO_EXAMENES_PATH = PROCESSED_DIR / "banco_examenes.jsonl"

load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    embedding_model: str


# Lee la configuración actual desde las variables de entorno (ya cargadas desde .env),
# con un valor por defecto si no está definida.
def get_settings() -> Settings:
    return Settings(
        embedding_model=os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        ),
    )
