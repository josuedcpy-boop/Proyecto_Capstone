"""Dos clasificadores supervisados (TF-IDF + modelos de scikit-learn) que comparten el mismo
motor genérico (evaluate_models/train_test_report/train_final_model, agnóstico al label_attr):

1. Nivel Bloom por pregunta — una versión APRENDIDA del clasificador de reglas que ya existe
   en pipeline/difficulty/bloom_dok_rules.py::classify_question.

   LIMITACIÓN HONESTA (léase antes de usar los resultados): las etiquetas de entrenamiento son
   la salida de esa misma heurística de reglas, no juicio humano independiente ni datos reales
   de estudiantes. Este experimento mide si un modelo de texto puede aprender a *reproducir*
   ese criterio con features de superficie (TF-IDF) — no se presenta como "mejor que las
   reglas". Sirve para el día que haya etiquetas independientes (jueces humanos, o p-values
   reales de estudiantes, ver docs/estandares_y_mejores_practicas.md sección 9).

2. Materia (history/technology) a nivel de EXAMEN COMPLETO (build_document_dataset) — esta
   etiqueta sí es verdad de terreno real (viene de la carpeta de origen en data/raw/), no una
   pseudo-etiqueta. Es el modelo central del propósito actual del proyecto: identificar de
   qué materia es un examen nuevo (ver predict_exam_subject).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import GridSearchCV, GroupShuffleSplit, StratifiedGroupKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier

from pipeline.difficulty.bloom_dok_rules import classify_question
from pipeline.difficulty.part_type_rules import detect_part_type
from pipeline.difficulty.splitter import split_questions
from pipeline.ingest.extractors import extract_text
from pipeline.ingest.run import load_all_documents

_SUBJECTS = ("history", "technology")
_MAX_CV_SPLITS = 5
_RANDOM_STATE = 42  # semilla fija para que el split y los modelos sean reproducibles
_TEST_SIZE = 0.2  # 80/20 train/test, agrupado por examen (ver train_test_report)


@dataclass
class LabeledQuestion:
    """Una pregunta histórica con su etiqueta Bloom/DOK/tipo-de-parte (de las heurísticas) y
    su examen/materia/grado de origen — una fila completa del banco de exámenes.

    También se reutiliza a nivel de EXAMEN COMPLETO (ver build_document_dataset): ahí
    `text` es el texto del documento entero, no de una pregunta, y `bloom_level` no aplica
    (queda en "") — materia no varía dentro de un mismo examen, así que clasificarla por
    examen completo es más natural que por pregunta suelta."""

    text: str
    document_id: str
    subject: str
    grade: int | None
    bloom_level: str = ""
    dok_level: int | None = None
    part_type: str | None = None


# Junta todas las preguntas históricas (de exámenes/reviews ya ingeridos), las etiqueta con
# la heurística existente, y guarda de qué examen/materia/grado viene cada una — necesario
# para partir por examen (no por pregunta) y para el desagregado por categoría después.
def build_dataset(subjects: tuple[str, ...] = _SUBJECTS) -> list[LabeledQuestion]:
    items: list[LabeledQuestion] = []
    for subject in subjects:
        docs = [d for d in load_all_documents() if d.subject == subject and d.doc_type in ("exam", "review")]
        for doc in docs:
            for text in split_questions(doc.text):
                bloom_level, dok_level = classify_question(text)
                part_type = detect_part_type(text)
                items.append(
                    LabeledQuestion(
                        text=text,
                        bloom_level=bloom_level,
                        document_id=doc.id,
                        subject=subject,
                        grade=doc.grade,
                        dok_level=dok_level,
                        part_type=part_type,
                    )
                )
    return items


# Igual que build_dataset, pero una fila POR DOCUMENTO COMPLETO (no por pregunta dividida)
# — natural para materia, que es la misma para todas las preguntas de un mismo examen (a
# diferencia de bloom_level, que sí varía pregunta a pregunta dentro de un examen).
def build_document_dataset(
    subjects: tuple[str, ...] = _SUBJECTS, doc_types: tuple[str, ...] = ("exam", "review")
) -> list[LabeledQuestion]:
    return [
        LabeledQuestion(text=doc.text, document_id=doc.id, subject=doc.subject, grade=doc.grade)
        for doc in load_all_documents()
        if doc.subject in subjects and doc.doc_type in doc_types
    ]


# Separa la lista de LabeledQuestion en los 3 arreglos paralelos que espera scikit-learn.
# label_attr elige qué campo de LabeledQuestion predecir ("bloom_level" por defecto, o
# "subject" para entrenar un clasificador de materia con el mismo motor).
def _unpack(items: list[LabeledQuestion], label_attr: str = "bloom_level") -> tuple[list[str], list[str], list[str]]:
    return [i.text for i in items], [getattr(i, label_attr) for i in items], [i.document_id for i in items]


def _make_pipeline(estimator) -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(max_features=3000, ngram_range=(1, 2), min_df=1)),
        ("clf", estimator),
    ])


# Número de particiones seguro para StratifiedGroupKFold: no puede pasar del tamaño de la
# clase (ni del número de grupos) más chica, o sklearn lanza error.
def _safe_n_splits(labels: list[str], groups: list[str]) -> int:
    counts = np.unique(labels, return_counts=True)[1]
    return max(2, min(_MAX_CV_SPLITS, int(counts.min()), len(set(groups))))


# Compara 5 modelos (2 líneas base + árbol + Random Forest + boosting) con validación
# cruzada agrupada por examen; a Random Forest y boosting se les hace además búsqueda de
# hiperparámetros. El ganador se elige por F1-macro (no accuracy, porque las clases Bloom
# están desbalanceadas) promedio en CV, no en una sola partición.
def evaluate_models(items: list[LabeledQuestion], label_attr: str = "bloom_level") -> dict:
    texts, labels, groups = _unpack(items, label_attr)
    n_splits = _safe_n_splits(labels, groups)
    cv = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=_RANDOM_STATE)

    results: dict[str, dict] = {}

    simple_models = {
        "linea_base_clase_mayoritaria": DummyClassifier(strategy="most_frequent"),
        "regresion_logistica": LogisticRegression(max_iter=1000),
        "arbol_de_decision": DecisionTreeClassifier(random_state=_RANDOM_STATE),
    }
    for name, estimator in simple_models.items():
        pipeline = _make_pipeline(estimator)
        scores = cross_val_score(pipeline, texts, labels, groups=groups, cv=cv, scoring="f1_macro")
        results[name] = {"f1_macro_cv": round(float(scores.mean()), 4), "f1_macro_std": round(float(scores.std()), 4), "mejores_hiperparametros": None}

    grid_models = {
        "random_forest": (
            RandomForestClassifier(random_state=_RANDOM_STATE),
            {"clf__n_estimators": [100, 200], "clf__max_depth": [None, 10, 20]},
        ),
        "boosting": (
            GradientBoostingClassifier(random_state=_RANDOM_STATE),
            {"clf__n_estimators": [100, 200], "clf__learning_rate": [0.05, 0.1], "clf__max_depth": [2, 3]},
        ),
    }
    for name, (estimator, param_grid) in grid_models.items():
        pipeline = _make_pipeline(estimator)
        search = GridSearchCV(pipeline, param_grid, cv=cv, scoring="f1_macro", n_jobs=-1)
        search.fit(texts, labels, groups=groups)
        results[name] = {
            "f1_macro_cv": round(float(search.best_score_), 4),
            "f1_macro_std": None,
            "mejores_hiperparametros": search.best_params_,
        }

    winner = max(results, key=lambda name: results[name]["f1_macro_cv"])
    return {"n_splits_usados": n_splits, "modelos": results, "ganador": winner}


def _build_winner_estimator(name: str, hyperparameters: dict | None):
    base = {
        "linea_base_clase_mayoritaria": DummyClassifier(strategy="most_frequent"),
        "regresion_logistica": LogisticRegression(max_iter=1000),
        "arbol_de_decision": DecisionTreeClassifier(random_state=_RANDOM_STATE),
        "random_forest": RandomForestClassifier(random_state=_RANDOM_STATE),
        "boosting": GradientBoostingClassifier(random_state=_RANDOM_STATE),
    }[name]
    pipeline = _make_pipeline(base)
    if hyperparameters:
        pipeline.set_params(**hyperparameters)
    return pipeline


# Parte el dataset en train/test POR EXAMEN (nunca por pregunta suelta, para no filtrar
# vocabulario del mismo examen entre train y test), entrena el modelo ganador, y evalúa en
# el test con matriz de confusión + desagregado por materia/grado — más la confirmación
# explícita de que ningún examen quedó repartido entre ambos lados.
def train_test_report(
    items: list[LabeledQuestion],
    winner_name: str,
    winner_hyperparameters: dict | None,
    label_attr: str = "bloom_level",
) -> dict:
    texts, labels, groups = _unpack(items, label_attr)
    splitter = GroupShuffleSplit(n_splits=1, test_size=_TEST_SIZE, random_state=_RANDOM_STATE)
    train_idx, test_idx = next(splitter.split(texts, labels, groups))

    train_groups = {groups[i] for i in train_idx}
    test_groups = {groups[i] for i in test_idx}
    sin_fuga_confirmada = train_groups.isdisjoint(test_groups)

    pipeline = _build_winner_estimator(winner_name, winner_hyperparameters)
    train_texts = [texts[i] for i in train_idx]
    train_labels = [labels[i] for i in train_idx]
    pipeline.fit(train_texts, train_labels)

    test_texts = [texts[i] for i in test_idx]
    test_labels = [labels[i] for i in test_idx]
    test_items = [items[i] for i in test_idx]
    predictions = pipeline.predict(test_texts)

    all_labels = sorted(set(labels))
    matrix = confusion_matrix(test_labels, predictions, labels=all_labels)
    report = classification_report(test_labels, predictions, labels=all_labels, output_dict=True, zero_division=0)

    por_materia: dict[str, dict] = {}
    por_grado: dict[str, dict] = {}
    for item, pred, real in zip(test_items, predictions, test_labels):
        for bucket, key in ((por_materia, item.subject), (por_grado, str(item.grade))):
            entry = bucket.setdefault(key, {"correctas": 0, "total": 0})
            entry["total"] += 1
            entry["correctas"] += int(pred == real)
    for bucket in (por_materia, por_grado):
        for entry in bucket.values():
            entry["accuracy"] = round(entry["correctas"] / entry["total"], 4) if entry["total"] else None

    return {
        "modelo_evaluado": winner_name,
        "preguntas_train": len(train_idx),
        "preguntas_test": len(test_idx),
        "examenes_train": len(train_groups),
        "examenes_test": len(test_groups),
        "sin_fuga_confirmada": sin_fuga_confirmada,
        "clases": all_labels,
        "matriz_de_confusion": matrix.tolist(),
        "reporte_por_clase": report,
        "accuracy_por_materia": por_materia,
        "accuracy_por_grado": por_grado,
    }


# Punto de entrada: compara modelos, evalúa al ganador en un test separado por examen, y
# agrega estadísticas del tamaño de cada subgrupo (para no interpretar un accuracy alto en
# un subgrupo con muy pocas preguntas como si fuera una conclusión sólida).
def run_full_report(
    subjects: tuple[str, ...] = _SUBJECTS,
    label_attr: str = "bloom_level",
    items: list[LabeledQuestion] | None = None,
) -> dict:
    items = items if items is not None else build_dataset(subjects)
    if len(items) < 20:
        return {
            "estado": "sin_datos",
            "detalle": f"Solo {len(items)} preguntas históricas encontradas — muy pocas para entrenar/evaluar con rigor.",
        }

    comparacion = evaluate_models(items, label_attr)
    ganador = comparacion["ganador"]
    detalle_test = train_test_report(items, ganador, comparacion["modelos"][ganador]["mejores_hiperparametros"], label_attr)

    etiquetas = [getattr(i, label_attr) for i in items]
    conteos_por_etiqueta = {label: etiquetas.count(label) for label in sorted(set(etiquetas))}
    conteos_por_grado = {str(g): sum(1 for i in items if i.grade == g) for g in sorted({i.grade for i in items}, key=lambda g: (g is None, g))}

    return {
        "estado": "ok",
        "total_preguntas": len(items),
        "conteos_por_etiqueta": conteos_por_etiqueta,
        "conteos_por_grado": conteos_por_grado,
        "comparacion_de_modelos": comparacion,
        "evaluacion_en_test": detalle_test,
    }


# Persiste el banco completo (una pregunta por línea JSON) para no tener que reconstruirlo
# desde los documentos crudos cada vez — mismo patrón que pipeline/ingest/run.py.
def save_bank(items: list[LabeledQuestion], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")


def load_bank(path: Path) -> list[LabeledQuestion]:
    items: list[LabeledQuestion] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(LabeledQuestion(**json.loads(line)))
    return items


# Entrena el modelo ganador (elegido por CV en evaluate_models) con TODO el banco — a
# diferencia de train_test_report, esto es para usar el modelo de verdad sobre preguntas
# nuevas, no para medir qué tan bien le fue (por eso no separa train/test aquí).
def train_final_model(items: list[LabeledQuestion], label_attr: str = "bloom_level") -> tuple[Pipeline, str]:
    comparacion = evaluate_models(items, label_attr)
    ganador = comparacion["ganador"]
    hiperparametros = comparacion["modelos"][ganador]["mejores_hiperparametros"]

    pipeline = _build_winner_estimator(ganador, hiperparametros)
    texts, labels, _groups = _unpack(items, label_attr)
    pipeline.fit(texts, labels)
    return pipeline, ganador


# Entrena con el banco actual (ingerido de data/raw/) y predice la etiqueta (bloom_level o
# subject) para cada pregunta de un examen NUEVO — cualquier archivo que extract_text soporte
# (.docx/.pdf/.pptx/.xlsx/.txt), ingerido o no. Reentrena desde cero cada llamada (sin caché de
# modelo, igual que el resto del módulo); tarda lo mismo que ml-bloom-eval/ml-subject-eval.
def predict_exam_file(path: Path, label_attr: str = "bloom_level", subjects: tuple[str, ...] = _SUBJECTS) -> dict:
    items = build_dataset(subjects)
    pipeline, modelo = train_final_model(items, label_attr)

    texto = extract_text(path)
    preguntas = split_questions(texto)
    predicciones = pipeline.predict(preguntas) if preguntas else []

    return {
        "modelo_usado": modelo,
        "archivo": str(path),
        "predicciones": [{"pregunta": q, "prediccion": p} for q, p in zip(preguntas, predicciones)],
    }


# Igual que predict_exam_file, pero para materia a nivel de EXAMEN COMPLETO: entrena con
# build_document_dataset (una fila por examen) y predice una sola etiqueta para todo el
# archivo, no una por pregunta — materia no varía dentro de un mismo examen.
def predict_exam_subject(path: Path, subjects: tuple[str, ...] = _SUBJECTS) -> dict:
    items = build_document_dataset(subjects)
    pipeline, modelo = train_final_model(items, label_attr="subject")

    texto = extract_text(path)
    prediccion = pipeline.predict([texto])[0]

    confianza = None
    if hasattr(pipeline, "predict_proba"):
        confianza = round(float(max(pipeline.predict_proba([texto])[0])), 4)

    return {
        "modelo_usado": modelo,
        "archivo": str(path),
        "materia_predicha": prediccion,
        "confianza": confianza,
    }
