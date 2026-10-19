from pipeline.difficulty.bloom_dok_rules import classify_question


def test_recordar_default_for_recall_style_question():
    bloom, dok = classify_question("¿Cuál de los siguientes es un dato correcto?")
    assert bloom == "Recordar"
    assert dok == 1


def test_detects_comprender():
    bloom, dok = classify_question("Explica con tus propias palabras el concepto de mestizaje.")
    assert bloom == "Comprender"


def test_detects_analizar():
    bloom, dok = classify_question("Compara las causas de la Guerra Hispanoamericana con las del Grito de Lares.")
    assert bloom == "Analizar"
    assert dok == 3


def test_detects_crear_as_highest_priority():
    text = "Explica el contexto histórico y luego diseña una línea de tiempo original con los eventos."
    bloom, dok = classify_question(text)
    assert bloom == "Crear"
    assert dok == 4
