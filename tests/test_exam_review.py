from pipeline.audit.exam_review import _check_internal_duplicates, _check_parts, _check_points
from pipeline.schemas import Question


def _q(id_, text, part_type=None, points=None, dok_level=None):
    return Question(id=id_, text=text, source="historical", part_type=part_type, points=points, dok_level=dok_level)


def test_check_points_fails_under_50():
    questions = [_q("1", "a", points=10), _q("2", "b", points=10)]
    result = _check_points(questions)
    assert result["aprobado"] is False
    assert result["explicacion"]  # debe explicar por qué falla


def test_check_points_passes_over_50():
    questions = [_q(str(i), "x", points=15) for i in range(4)]  # 60 pts
    result = _check_points(questions)
    assert result["aprobado"] is True
    assert result["explicacion"] == ""


def test_check_parts_requires_four_distinct():
    questions = [
        _q("1", "a", part_type="opcion_multiple"),
        _q("2", "b", part_type="verdadero_falso"),
        _q("3", "c", part_type="ensayo"),
    ]
    result = _check_parts(questions)
    assert result["aprobado"] is False
    assert result["explicacion"]

    questions.append(_q("4", "d", part_type="completar"))
    assert _check_parts(questions)["aprobado"] is True


def test_check_internal_duplicates_with_few_questions_passes_trivially():
    result = _check_internal_duplicates([_q("1", "única pregunta")], embedding_model="sentence-transformers/all-MiniLM-L6-v2")
    assert result["aprobado"] is True
