import numpy as np

from pipeline.ml import standards_classifier as mod
from pipeline.ml.standards_classifier import (
    _iterative_multilabel_split,
    build_standards_dataset,
    evaluate_standards_model,
)
from pipeline.schemas import Document, StandardTag


def _fake_document(doc_id, text):
    return Document(id=doc_id, subject="history", grade=7, doc_type="exam", group="g", source_path=doc_id, text=text)


# Mapa determinista doc_id -> códigos de estándar "cubiertos", para simular lo que
# tag_document()+document_coverage() producirían en pipeline/tagging/run.py sin depender
# de embeddings reales.
def _fake_tags_by_doc():
    docs = []
    tags_by_id = {}
    for i in range(16):
        doc_id = f"doc{i}"
        codes = ["CC"] if i % 2 == 0 else ["PLA"]
        if i % 4 == 0:
            codes.append("IC")  # algunos documentos con más de un estándar (multi-etiqueta)
        docs.append(_fake_document(doc_id, f"Texto del examen de historia número {i} sobre el tema {i % 3}."))
        tags_by_id[doc_id] = [StandardTag(standard_code=c, standard_name=c, grade=7, similarity=0.5) for c in codes]
    return docs, tags_by_id


def test_build_standards_dataset_produces_multilabel_sets(monkeypatch):
    docs, tags_by_id = _fake_tags_by_doc()
    monkeypatch.setattr(mod, "load_all_documents", lambda: docs)
    monkeypatch.setattr(mod, "tag_document", lambda doc, _model: tags_by_id[doc.id])

    texts, document_ids, label_sets = build_standards_dataset("history")

    assert len(texts) == len(document_ids) == len(label_sets) == 16
    assert {"CC", "PLA", "IC"} >= set().union(*label_sets)
    assert label_sets[document_ids.index("doc0")] == {"CC", "IC"}
    assert label_sets[document_ids.index("doc1")] == {"PLA"}


def test_evaluate_standards_model_reports_support_and_metrics(monkeypatch):
    docs, tags_by_id = _fake_tags_by_doc()
    monkeypatch.setattr(mod, "load_all_documents", lambda: docs)
    monkeypatch.setattr(mod, "tag_document", lambda doc, _model: tags_by_id[doc.id])

    report = evaluate_standards_model("history")

    assert report["estado"] == "ok"
    assert report["total_documentos"] == 16
    assert set(report["codigos"]) == {"CC", "PLA", "IC"}
    assert report["soporte_por_codigo"]["CC"] == 8
    assert report["soporte_por_codigo"]["PLA"] == 8
    assert report["soporte_por_codigo"]["IC"] == 4
    assert 0.0 <= report["f1_micro"] <= 1.0
    assert 0.0 <= report["f1_macro"] <= 1.0


def test_evaluate_standards_model_reports_sin_datos_with_too_few_documents(monkeypatch):
    docs, tags_by_id = _fake_tags_by_doc()
    pocos = docs[:3]
    monkeypatch.setattr(mod, "load_all_documents", lambda: pocos)
    monkeypatch.setattr(mod, "tag_document", lambda doc, _model: tags_by_id[doc.id])

    report = evaluate_standards_model("history")

    assert report["estado"] == "sin_datos"


def test_iterative_multilabel_split_represents_codes_with_enough_support_in_both_sets():
    # CC y PLA tienen 8 documentos cada uno (suficiente para aparecer en ambos conjuntos);
    # IC tiene solo 1, así que no se le puede exigir presencia en los dos a la vez.
    y = np.zeros((16, 3), dtype=int)  # columnas: CC, PLA, IC
    for i in range(16):
        if i % 2 == 0:
            y[i, 0] = 1
        else:
            y[i, 1] = 1
    y[0, 2] = 1

    train_idx, test_idx = _iterative_multilabel_split(y, test_size=0.2, random_state=42)

    assert set(train_idx) | set(test_idx) == set(range(16))
    assert set(train_idx) & set(test_idx) == set()
    assert y[test_idx, 0].sum() >= 1  # CC presente en test
    assert y[test_idx, 1].sum() >= 1  # PLA presente en test
    assert 2 <= len(test_idx) <= 6  # cerca del 20% de 16, sin ser exacto por el redondeo por código


def test_iterative_multilabel_split_keeps_rare_code_out_of_test_without_crashing():
    # Un código con un solo documento positivo no puede repartirse entre train y test;
    # la función no debe fallar ni forzarlo, solo lo deja donde caiga por la proporción global.
    y = np.zeros((10, 2), dtype=int)
    y[:, 0] = 1  # CC en todos
    y[0, 1] = 1  # PLA solo en un documento

    train_idx, test_idx = _iterative_multilabel_split(y, test_size=0.2, random_state=42)

    assert len(train_idx) + len(test_idx) == 10
    assert len(test_idx) in (1, 2, 3)
