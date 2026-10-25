"""Clasificador supervisado multi-etiqueta (TF-IDF + OneVsRestClassifier) que predice qué
estándares curriculares cumple un examen completo, a partir de su texto.

LIMITACIÓN HONESTA (léase antes de usar los resultados): no existe ninguna verdad de terreno
humana sobre qué estándares cumple cada examen histórico. Las etiquetas de entrenamiento son
las PSEUDO-ETIQUETAS que ya produce pipeline/tagging/run.py (similaridad de embeddings por
fragmento contra la descripción de cada estándar, umbral 0.25, agregada por documento) — el
mismo tipo de limitación que ya se documenta para el clasificador de nivel Bloom en
pipeline/ml/bloom_classifier.py. Este modelo aprende a reproducir desde texto crudo (TF-IDF)
lo que esa heurística de embeddings ya decide; no es una validación independiente de qué
estándares cumple un examen, es una vía de inferencia más rápida (no hay que re-embeber ni
volver a calcular similaridad por fragmento en cada predicción nueva, una vez entrenado).

Con ~20 códigos de estándar repartidos entre ~130 documentos tipo examen/review (ver conteos
reales en evaluate_standards_model), muchos códigos tienen muy pocos documentos positivos —
por eso aquí se usa un solo modelo razonable (regresión logística multi-etiqueta) en vez de
la comparación de 5 modelos con búsqueda de hiperparámetros que sí tiene sentido para Bloom:
con tan poco soporte por etiqueta, esa comparación no sería estadísticamente significativa.
"""

from __future__ import annotations

import random
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MultiLabelBinarizer

from pipeline.config import get_settings
from pipeline.ingest.extractors import extract_text
from pipeline.ingest.run import load_all_documents
from pipeline.tagging.run import document_coverage, tag_document

_MIN_DOCS_FOR_EVAL = 10
_RANDOM_STATE = 42  # misma semilla que pipeline/ml/bloom_classifier.py, para reproducibilidad
_TEST_SIZE = 0.2  # 80/20 train/test a nivel de documento


# Para cada documento tipo examen/review de esa materia, corre el etiquetado por embeddings
# ya existente (pipeline/tagging/run.py) y usa el conjunto de códigos resultante como la
# etiqueta multi-label del documento completo.
def build_standards_dataset(subject: str) -> tuple[list[str], list[str], list[set[str]]]:
    settings = get_settings()
    docs = [d for d in load_all_documents() if d.subject == subject and d.doc_type in ("exam", "review")]

    texts, document_ids, label_sets = [], [], []
    for doc in docs:
        coverage = document_coverage(tag_document(doc, settings.embedding_model))
        texts.append(doc.text)
        document_ids.append(doc.id)
        label_sets.append(set(coverage.keys()))
    return texts, document_ids, label_sets


def _make_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(max_features=3000, ngram_range=(1, 2), min_df=1)),
        ("clf", OneVsRestClassifier(LogisticRegression(max_iter=1000))),
    ])


def _rarest_label_count(row, label_totals) -> float:
    activos = [label_totals[l] for l in range(len(row)) if row[l]]
    return min(activos) if activos else float("inf")


# Partición train/test consciente de las etiquetas multi-label (versión simplificada de la
# estratificación iterativa de Sechidis et al., 2011): procesa primero los documentos que
# cargan la etiqueta más rara, y decide cada documento según SOLO esa etiqueta más rara que
# carga (no la suma de todas sus etiquetas: sumar deja que un código muy común presente en el
# mismo documento, como CC con 66 de 96 documentos, arrastre a un código raro que coexiste con
# él siempre hacia train, porque el remanente de train para el código común es mucho mayor).
# Un código con menos de 2 documentos positivos no puede aparecer en ambos conjuntos a la vez;
# esos quedan sin representación en test (se ve reflejado en soporte_por_codigo, no se oculta).
def _iterative_multilabel_split(y, test_size: float, random_state: int) -> tuple[list[int], list[int]]:
    n_samples, n_labels = y.shape
    label_totals = y.sum(axis=0)
    deseado_test = [round(total * test_size) for total in label_totals]
    objetivo_test_total = round(n_samples * test_size)

    test_count = [0] * n_labels
    train_count = [0] * n_labels
    train_idx: list[int] = []
    test_idx: list[int] = []

    orden = list(range(n_samples))
    random.Random(random_state).shuffle(orden)
    orden.sort(key=lambda i: _rarest_label_count(y[i], label_totals))

    for i in orden:
        activos = [l for l in range(n_labels) if y[i][l]]
        if not activos:
            va_a_test = len(test_idx) < objetivo_test_total
        else:
            l_decisivo = min(activos, key=lambda l: label_totals[l])
            if deseado_test[l_decisivo] == 0:
                # Esta etiqueta es tan rara que su propia cuota de test redondea a 0: no hay
                # nada que "repartir" para ella, así que no debe decidir el documento. Sin este
                # caso, cuando TODOS los documentos caen en esta situación (ej. cada uno con una
                # etiqueta única propia), el documento siempre gana train de forma determinista
                # y test_idx termina vacío, lo cual rompe classification_report más adelante.
                va_a_test = len(test_idx) < objetivo_test_total
            else:
                restante_test = deseado_test[l_decisivo] - test_count[l_decisivo]
                restante_train = (label_totals[l_decisivo] - deseado_test[l_decisivo]) - train_count[l_decisivo]
                if restante_test == restante_train:
                    va_a_test = len(test_idx) < objetivo_test_total
                else:
                    va_a_test = restante_test > restante_train

        if va_a_test:
            test_idx.append(i)
            for l in activos:
                test_count[l] += 1
        else:
            train_idx.append(i)
            for l in activos:
                train_count[l] += 1

    return train_idx, test_idx


# Reporta soporte por código (cuántos documentos lo tienen — clave para leer el resto con
# cautela) más precision/recall/F1 por código y agregados micro/macro, sobre una partición
# train/test que intenta repartir cada código de estándar entre ambos conjuntos
# (_iterative_multilabel_split), no solo mantener la proporción global 80/20.
def evaluate_standards_model(subject: str) -> dict:
    texts, document_ids, label_sets = build_standards_dataset(subject)
    if len(texts) < _MIN_DOCS_FOR_EVAL:
        return {
            "estado": "sin_datos",
            "detalle": f"Solo {len(texts)} documento(s) tipo examen/review encontrados para '{subject}' — muy pocos para entrenar/evaluar con rigor.",
        }

    binarizer = MultiLabelBinarizer()
    y = binarizer.fit_transform(label_sets)
    codigos = list(binarizer.classes_)
    soporte = {codigo: int(y[:, i].sum()) for i, codigo in enumerate(codigos)}

    train_idx, test_idx = _iterative_multilabel_split(y, _TEST_SIZE, _RANDOM_STATE)
    train_texts = [texts[i] for i in train_idx]
    test_texts = [texts[i] for i in test_idx]

    pipeline = _make_pipeline()
    pipeline.fit(train_texts, y[train_idx])
    predictions = pipeline.predict(test_texts)

    reporte = classification_report(
        y[test_idx], predictions, target_names=codigos, output_dict=True, zero_division=0
    )

    return {
        "estado": "ok",
        "materia": subject,
        "total_documentos": len(texts),
        "documentos_train": len(train_idx),
        "documentos_test": len(test_idx),
        "codigos": codigos,
        "soporte_por_codigo": soporte,
        "reporte_por_codigo": reporte,
        "f1_micro": round(reporte["micro avg"]["f1-score"], 4),
        "f1_macro": round(reporte["macro avg"]["f1-score"], 4),
    }


# Entrena con TODOS los documentos de esa materia (sin holdout) — para inferencia real sobre
# un examen nuevo, no para medir qué tan bien le fue (para eso: evaluate_standards_model).
def train_final_standards_model(subject: str) -> tuple[Pipeline, MultiLabelBinarizer]:
    texts, _document_ids, label_sets = build_standards_dataset(subject)
    binarizer = MultiLabelBinarizer()
    y = binarizer.fit_transform(label_sets)

    pipeline = _make_pipeline()
    pipeline.fit(texts, y)
    return pipeline, binarizer


# Predice qué estándares cumple un examen nuevo: devuelve los códigos cuya probabilidad
# supera `threshold` (orden descendente), o lo dice explícitamente si ninguno lo supera en
# vez de forzar una respuesta.
def predict_exam_standards(path: Path, subject: str, threshold: float = 0.5) -> dict:
    pipeline, binarizer = train_final_standards_model(subject)

    texto = extract_text(path)
    probabilidades = pipeline.predict_proba([texto])[0]
    codigos = list(binarizer.classes_)

    predicciones = sorted(
        (
            {"estandar": codigo, "probabilidad": round(float(p), 4)}
            for codigo, p in zip(codigos, probabilidades)
            if p >= threshold
        ),
        key=lambda item: -item["probabilidad"],
    )

    return {
        "archivo": str(path),
        "materia": subject,
        "umbral": threshold,
        "estandares_predichos": predicciones,
        "aviso": None if predicciones else "Ningún estándar superó el umbral de confianza.",
    }
