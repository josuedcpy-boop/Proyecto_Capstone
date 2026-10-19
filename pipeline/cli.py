"""CLI del pipeline. Uso: python -m pipeline.cli <comando> [opciones]."""

from __future__ import annotations

from pathlib import Path

import typer

from pipeline.assemble.run import assemble_exam
from pipeline.config import RAW_DIR
from pipeline.difficulty.run import print_profile, profile_file
from pipeline.generation.run import generate_exam
from pipeline.ingest.extractors import extract_text
from pipeline.ingest.run import _detect_doc_type, _detect_grade
from pipeline.ingest.run import ingest_all as _ingest_all
from pipeline.tagging.run import tag_all as _tag_all
from pipeline.validation.run import validate_exam

app = typer.Typer(help="Pipeline de generación de exámenes/lecciones")

_SUBJECT_MAP = {
    "historia": "history",
    "history": "history",
    "tecnologia": "technology",
    "tecnología": "technology",
    "technology": "technology",
}


def _resolve_subject(materia: str) -> str:
    key = materia.strip().lower()
    if key not in _SUBJECT_MAP:
        raise typer.BadParameter(f"Materia desconocida: {materia!r} (usa historia | tecnologia)")
    return _SUBJECT_MAP[key]


@app.command()
def ingest():
    """Extrae texto de data/raw/ y lo normaliza en data/processed/documents/."""
    report = _ingest_all()
    typer.echo(f"Documentos ingeridos: {report.ingested}")
    if report.skipped:
        typer.echo(f"Omitidos ({len(report.skipped)}):")
        for item in report.skipped:
            typer.echo(f"  - {item}")


@app.command()
def tag():
    """Etiqueta los documentos ingeridos contra los estándares curriculares."""
    summary = _tag_all()
    for group, counts in summary.items():
        typer.echo(f"\n{group}")
        for code, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            typer.echo(f"  {code}: cubierto en {n} documento(s)")


@app.command()
def profile(archivo: str):
    """Construye la tabla de especificaciones (Bloom x DOK) de un examen puntual."""
    exam_profile, _questions = profile_file(Path(archivo))
    print_profile(exam_profile)


def _pick_reference_exam(subject: str, grade: int) -> Path:
    subject_dir = RAW_DIR / subject
    for file_path in sorted(subject_dir.rglob("*")):
        if not file_path.is_file() or file_path.suffix.lower() not in (".docx", ".pdf", ".txt"):
            continue
        group = file_path.parent.name
        if _detect_doc_type(file_path.name, group) != "exam":
            continue
        if _detect_grade(file_path.name, group) == grade:
            return file_path
    raise FileNotFoundError(f"No se encontró un examen de referencia para materia={subject} grado={grade}")


@app.command()
def generate(
    materia: str = typer.Option(..., "--materia"),
    grado: int = typer.Option(..., "--grado"),
    tema: str | None = typer.Option(None, "--tema", help="Nombre del tema, usado en el nombre del archivo .docx (ej. 'Grito de Lares'). Si no se da, se toma del examen de referencia."),
    perfil_de: str | None = typer.Option(None, "--perfil-de", help="Ruta a un examen pasado del cual copiar el perfil de dificultad objetivo."),
):
    """Genera, valida y ensambla un examen nuevo para materia/grado dado un perfil objetivo."""
    subject = _resolve_subject(materia)
    reference_path = Path(perfil_de) if perfil_de else _pick_reference_exam(subject, grado)
    target_profile, _historical_questions = profile_file(reference_path, subject=subject, grade=grado)
    typer.echo(f"Perfil objetivo tomado de: {reference_path}")
    print_profile(target_profile)

    tema_resuelto = tema or reference_path.stem
    reference_text = extract_text(reference_path)
    try:
        exam = generate_exam(subject, grado, target_profile, tema=tema_resuelto, reference_text=reference_text)
    except RuntimeError as exc:
        typer.echo(f"\nERROR: {exc}")
        typer.echo("Prueba de nuevo (los modelos locales pequeños no siempre responden igual) o cambia de proveedor en .env.")
        raise typer.Exit(code=1)

    exam = validate_exam(exam)
    out_path = assemble_exam(exam, tema=tema_resuelto)
    typer.echo(f"\nExamen generado en: {out_path}")


@app.command(name="run-all")
def run_all(
    materia: str = typer.Option(..., "--materia"),
    grado: int = typer.Option(..., "--grado"),
    tema: str | None = typer.Option(None, "--tema"),
):
    """Corre ingesta -> etiquetado -> generación -> validación -> ensamblado para materia/grado."""
    ingest()
    tag()
    generate(materia=materia, grado=grado, tema=tema, perfil_de=None)


if __name__ == "__main__":
    app()
