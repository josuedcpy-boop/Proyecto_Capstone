"""Carga pipeline/standards/*.yaml y los expone como objetos tipados para el etiquetador."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_STANDARDS_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class TaggableStandard:
    """Un estándar/concepto contra el cual se puede etiquetar un chunk de texto."""

    code: str
    name: str
    text: str  # descripción a embeber (específica de grado si existe, si no la general)


def _load_yaml(name: str) -> dict:
    path = _STANDARDS_DIR / name
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def get_history_standards_for_grade(grade: int | None) -> list[TaggableStandard]:
    data = _load_yaml("pr_estudios_sociales.yaml")
    result = []
    for std in data["standards"]:
        grade_detail = std.get("grade_detail") or {}
        text = grade_detail.get(grade, std["description"]) if grade is not None else std["description"]
        result.append(TaggableStandard(code=std["code"], name=std["name"], text=text.strip()))
    return result


def get_technology_standards() -> list[TaggableStandard]:
    """Los conceptos CSTA + estándares ISTE no varían por grado en este nivel de detalle."""
    data = _load_yaml("pr_tecnologia.yaml")
    result = []
    for concept in data["concepts"]:
        result.append(
            TaggableStandard(code=concept["code"], name=concept["name"], text=concept["description"].strip())
        )
    for iste in data["iste_standards"]:
        result.append(TaggableStandard(code=f"ISTE-{iste['code']}", name=iste["name"], text=iste["name"]))
    return result


def get_standards_for(subject: str, grade: int | None) -> list[TaggableStandard]:
    if subject == "history":
        return get_history_standards_for_grade(grade)
    if subject == "technology":
        return get_technology_standards()
    raise ValueError(f"Materia desconocida: {subject}")
