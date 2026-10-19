"""Convención de nombre/ubicación de archivo compartida por exámenes y (en el futuro) lecciones
generadas: carpeta plana, archivo `<Tema> - grado <N>.docx`, sin sobrescribir si ya existe."""

from __future__ import annotations

import re
from pathlib import Path

_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def clean_filename_part(text: str) -> str:
    text = _INVALID_FILENAME_CHARS.sub("", text).strip()
    return re.sub(r"\s+", " ", text)


def unique_path(path: Path) -> Path:
    """Si `path` ya existe, devuelve la misma ruta con sufijo _2, _3, ... en vez de sobrescribir."""
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_stem(f"{path.stem}_{counter}")
        if not candidate.exists():
            return candidate
        counter += 1


def build_output_path(base_dir: Path, tema: str, grade: int | None) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    tema_clean = clean_filename_part(tema) or "Sin titulo"
    filename = f"{tema_clean} - grado {grade}.docx"
    return unique_path(base_dir / filename)
