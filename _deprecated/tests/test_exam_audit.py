from pipeline.audit.exam_audit import _check_leakage, _check_parts, _check_points
from pipeline.schemas import Question


def _q(id_, text, part_type=None, points=None, options=None, correct_option_index=None):
    return Question(
        id=id_,
        text=text,
        source="generated",
        part_type=part_type,
        points=points,
        options=options,
        correct_option_index=correct_option_index,
    )


def test_check_points_fails_under_50():
    questions = [_q("1", "a", points=10), _q("2", "b", points=10)]
    result = _check_points(questions)
    assert result.aprobado is False


def test_check_points_passes_over_50():
    questions = [_q(str(i), "x", points=15) for i in range(4)]  # 60 pts
    result = _check_points(questions)
    assert result.aprobado is True


def test_check_parts_requires_four_distinct():
    questions = [
        _q("1", "a", part_type="opcion_multiple"),
        _q("2", "b", part_type="verdadero_falso"),
        _q("3", "c", part_type="ensayo"),
    ]
    assert _check_parts(questions).aprobado is False

    questions.append(_q("4", "d", part_type="completar"))
    assert _check_parts(questions).aprobado is True


def test_check_leakage_detects_answer_in_stem():
    q = _q(
        "1",
        "¿Cuál es la capital de Puerto Rico? La respuesta es San Juan.",
        part_type="opcion_multiple",
        options=["San Juan", "Ponce", "Arecibo", "Caguas"],
        correct_option_index=0,
    )
    result = _check_leakage([q])
    assert result.aprobado is False


def test_check_leakage_passes_when_clean():
    q = _q(
        "1",
        "¿Cuál es la capital de Puerto Rico?",
        part_type="opcion_multiple",
        options=["San Juan", "Ponce", "Arecibo", "Caguas"],
        correct_option_index=0,
    )
    result = _check_leakage([q])
    assert result.aprobado is True


def test_check_leakage_ignores_non_multiple_choice():
    q = _q("1", "Explica la importancia de San Juan como capital.", part_type="ensayo")
    result = _check_leakage([q])
    assert result.aprobado is True
