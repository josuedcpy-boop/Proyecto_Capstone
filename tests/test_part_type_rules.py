from pipeline.difficulty.part_type_rules import detect_part_type, points_for, strip_option_prefix


def test_points_scale_with_dok():
    assert points_for(1) == 5
    assert points_for(2) == 8
    assert points_for(3) == 12
    assert points_for(4) == 15
    assert points_for(None) == 5
    assert points_for(99) == 5  # nivel desconocido -> default


def test_detects_opcion_multiple():
    text = "¿Cuál es la capital? a) San Juan b) Ponce c) Arecibo d) Caguas"
    assert detect_part_type(text) == "opcion_multiple"


def test_detects_verdadero_falso():
    assert detect_part_type("Verdadero o Falso: Colón llegó en 1492.") == "verdadero_falso"


def test_detects_completar():
    assert detect_part_type("Colón llegó a América en el año ______.") == "completar"


def test_detects_ensayo_by_length():
    text = "Explica en detalle. " * 20
    assert detect_part_type(text) == "ensayo"


def test_defaults_to_respuesta_corta():
    assert detect_part_type("¿Quién fue Colón?") == "respuesta_corta"


def test_strip_option_prefix_removes_existing_letter():
    assert strip_option_prefix("a) La conquista de nuevos territorios") == "La conquista de nuevos territorios"
    assert strip_option_prefix("B. Otra opción") == "Otra opción"


def test_strip_option_prefix_leaves_clean_text_untouched():
    assert strip_option_prefix("La conquista de nuevos territorios") == "La conquista de nuevos territorios"
