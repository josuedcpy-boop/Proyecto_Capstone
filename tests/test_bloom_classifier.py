from pipeline.ml import bloom_classifier as mod
from pipeline.ml.bloom_classifier import (
    LabeledQuestion,
    build_dataset,
    build_document_dataset,
    evaluate_models,
    load_bank,
    run_full_report,
    save_bank,
    train_test_report,
)
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


def test_build_dataset_populates_dok_and_part_type(monkeypatch):
    docs = [_fake_document("examA", "history", 7, "1. Explica por qué ocurrió el Grito de Lares.")]
    monkeypatch.setattr(mod, "load_all_documents", lambda: docs)

    items = build_dataset(subjects=("history",))

    assert all(i.dok_level is not None for i in items)
    assert all(i.part_type for i in items)


def test_build_document_dataset_one_row_per_document(monkeypatch):
    docs = [
        _fake_document("examA", "history", 7, "1. Explica por qué ocurrió el Grito de Lares.\n2. Define qué es un cabildo."),
        _fake_document("examB", "technology", 6, "1. Explica qué es un algoritmo."),
    ]
    monkeypatch.setattr(mod, "load_all_documents", lambda: docs)

    items = build_document_dataset(subjects=("history", "technology"))

    assert len(items) == 2  # una fila por documento, no por pregunta dividida
    assert {i.document_id for i in items} == {"examA", "examB"}
    by_id = {i.document_id: i for i in items}
    assert by_id["examA"].subject == "history"
    assert by_id["examA"].grade == 7
    assert by_id["examA"].text == docs[0].text
    assert by_id["examA"].bloom_level == ""  # no aplica a nivel de examen completo


def test_save_and_load_bank_round_trip(tmp_path):
    items = _synthetic_items(n_per_group=2, n_groups=2)
    path = tmp_path / "banco.jsonl"

    save_bank(items, path)
    loaded = load_bank(path)

    assert loaded == items


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


def _synthetic_items_by_subject(n_per_group=6, n_groups=6):
    """Igual que _synthetic_items pero la etiqueta variable es la materia, no Bloom —
    para probar label_attr='subject' con StratifiedGroupKFold."""
    items = []
    for g in range(n_groups):
        subject = "history" if g % 2 == 0 else "technology"
        for i in range(n_per_group):
            text = f"Pregunta {subject} {g}-{i} sobre un tema cualquiera."
            items.append(
                LabeledQuestion(text=text, bloom_level="Recordar", document_id=f"doc{g}", subject=subject, grade=7)
            )
    return items


def test_run_full_report_with_label_attr_subject():
    items = _synthetic_items_by_subject()
    # run_full_report reconstruye el dataset internamente desde los documentos reales por
    # defecto, así que aquí se prueban las piezas generalizadas directamente.
    comparison = evaluate_models(items, label_attr="subject")
    winner = comparison["ganador"]
    hyperparams = comparison["modelos"][winner]["mejores_hiperparametros"]
    report = train_test_report(items, winner, hyperparams, label_attr="subject")

    assert report["sin_fuga_confirmada"] is True
    assert set(report["clases"]) <= {"history", "technology"}


def test_run_full_report_accepts_prebuilt_items(monkeypatch):
    # Si se pasa `items` ya construido (ej. build_document_dataset para materia a nivel de
    # examen completo), run_full_report no debe reconstruir el dataset desde los documentos.
    def _boom(*_args, **_kwargs):
        raise AssertionError("build_dataset no debería llamarse cuando se pasa items=")

    monkeypatch.setattr(mod, "build_dataset", _boom)

    items = _synthetic_items_by_subject()
    report = run_full_report(label_attr="subject", items=items)

    assert report["estado"] == "ok"
    assert report["total_preguntas"] == len(items)
