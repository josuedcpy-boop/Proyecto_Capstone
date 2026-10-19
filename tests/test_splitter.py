from pipeline.difficulty.splitter import split_questions


def test_splits_numbered_questions():
    text = (
        "Instrucciones: conteste todas las preguntas.\n"
        "1. ¿Quién fue el primer gobernador de Puerto Rico?\n"
        "Explique brevemente.\n"
        "2. Compare las causas del Grito de Lares con las de la Guerra Hispanoamericana.\n"
    )
    questions = split_questions(text)
    assert len(questions) == 2
    assert questions[0].startswith("1.")
    assert "Explique brevemente" in questions[0]
    assert questions[1].startswith("2.")


def test_no_numbering_falls_back_to_whole_text():
    text = "Un examen sin preguntas numeradas, solo párrafos de contenido."
    questions = split_questions(text)
    assert questions == [text]


def test_empty_text_returns_nothing():
    assert split_questions("") == []
