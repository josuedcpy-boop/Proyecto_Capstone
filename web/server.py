"""Servidor local (Flask) que sirve demo.html y expone identificar/auditar un examen que el
usuario suba desde su propio dispositivo — reutiliza exactamente las mismas funciones que
pipeline/cli.py, mcp_server.py y app.py (predict_exam_subject, predict_exam_standards,
review_exam); no duplica lógica.

Correr: python web/server.py
Abre:   http://localhost:8600 — no abras demo.html directamente con doble clic, porque sin
este servidor corriendo no hay nada que responda a las llamadas de identificar/auditar.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.datastructures import FileStorage

from pipeline.audit.exam_review import review_exam
from pipeline.ml.bloom_classifier import predict_exam_subject
from pipeline.ml.standards_classifier import predict_exam_standards

_WEB_DIR = Path(__file__).resolve().parent

app = Flask(__name__)


# Guarda el archivo subido a un temporal con la misma extensión, para que extract_text (que
# trabaja por sufijo de Path) lo pueda leer igual que un archivo del disco.
def _save_upload(file_storage: FileStorage) -> Path:
    suffix = Path(file_storage.filename or "").suffix
    fd, name = tempfile.mkstemp(suffix=suffix)
    os.close(fd)  # Windows no deja borrar un archivo mientras su descriptor sigue abierto
    path = Path(name)
    file_storage.save(path)
    return path


def _require_file() -> FileStorage:
    archivo = request.files.get("archivo")
    if archivo is None or not archivo.filename:
        raise ValueError("No se recibió ningún archivo.")
    return archivo


@app.get("/")
def index():
    return send_from_directory(_WEB_DIR, "demo.html")


@app.post("/api/identificar")
def identificar():
    try:
        archivo = _require_file()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    path = _save_upload(archivo)
    try:
        materia = predict_exam_subject(path)
        estandares = predict_exam_standards(path, subject=materia["materia_predicha"])
        return jsonify({"materia": materia, "estandares": estandares})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500
    finally:
        path.unlink(missing_ok=True)


@app.post("/api/auditar")
def auditar():
    try:
        archivo = _require_file()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    # Si el frontend ya corrió /api/identificar, manda la materia predicha aquí (campo de
    # formulario "materia") para que la auditoría no la reporte como "unknown" — un archivo
    # subido vive en un temporal fuera de data/raw/, así que profile_file no puede
    # inferirla por carpeta.
    materia_hint = request.form.get("materia") or None

    path = _save_upload(archivo)
    try:
        return jsonify(review_exam(path, subject=materia_hint))
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500
    finally:
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    print("Abre http://localhost:8600 en el navegador (no abras demo.html directamente).")
    app.run(port=8600, debug=False)
