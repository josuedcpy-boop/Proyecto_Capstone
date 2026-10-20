from pipeline.ml import bloom_classifier as mod
from pipeline.ml.bloom_classifier import LabeledQuestion, build_dataset, evaluate_models, train_test_report
from pipeline.schemas import Document


def _fake_document(doc_id, subject, grade, text):
    return Document(id=doc_id, subject=subject, grade=grade, doc_type="exam", group="g", source_path=doc_id, text=text)


def test_build_dataset_groups_questions_by_document(monkeypatch):
    docs = [
        _fake_document("examA", "history", 7, "1. Explica por qué ocurrió el Grito de Lares.\n2. Define qué es un cabildo."),
        _fake_document("examB", "history", 7, "1. Compara las dos reformas."),
    ]
    monkeypatch.setattr(mod, "load_all_documents", lambda: docs)

    items = build_dataset(subjects=("history",))

    assert len(items) == 3
    assert {i.document_id for i in items} == {"examA", "examB"}
    assert all(isinstance(i, LabeledQuestion) for i in items)
    assert all(i.bloom_level for i in items)


def _synthetic_items(n_per_group=6, n_groups=6):
    """Dataset sintético balanceado entre 2 clases y varios 'exámenes' (grupos), suficiente
    para correr StratifiedGroupKFold sin depender de datos reales."""
    items = []
    for g in range(n_groups):
        for i in range(n_per_group):
            if i % 2 == 0:
                text = f"Explica con tus palabras el concepto {g}-{i}."
                label = "Comprender"
            else:
                text = f"Define el término {g}-{i}."
                label = "Recordar"
            items.append(
                LabeledQuestion(text=text, bloom_level=label, document_id=f"doc{g}", subject="history", grade=7)
            )
    return items


def test_train_test_split_has_no_group_overlap():
    items = _synthetic_items()
    comparison = evaluate_models(items)
    winner = comparison["ganador"]
    hyperparams = comparison["modelos"][winner]["mejores_hiperparametros"]

    report = train_test_report(items, winner, hyperparams)

    assert report["sin_fuga_confirmada"] is True
    assert report["examenes_train"] + report["examenes_test"] == len({i.document_id for i in items})


def test_evaluate_models_returns_all_five_and_a_winner():
    items = _synthetic_items()
    comparison = evaluate_models(items)

    expected_models = {
        "linea_base_clase_mayoritaria",
        "regresion_logistica",
        "arbol_de_decision",
        "random_forest",
        "boosting",
    }
    assert set(comparison["modelos"].keys()) == expected_models
    assert comparison["ganador"] in expected_models
