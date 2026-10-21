from pipeline.ml import standards_classifier as mod
from pipeline.ml.standards_classifier import build_standards_dataset, evaluate_standards_model
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
