import numpy as np

from pipeline.analysis.topic_balance import ClusterInfo, ClusterReport, auto_select_k, balance_report
from pipeline.standards.loader import TaggableStandard


def test_auto_select_k_detects_three_well_separated_clusters():
    rng = np.random.default_rng(0)
    cluster_a = rng.normal(loc=[0, 0], scale=0.05, size=(20, 2))
    cluster_b = rng.normal(loc=[10, 0], scale=0.05, size=(20, 2))
    cluster_c = rng.normal(loc=[5, 10], scale=0.05, size=(20, 2))
    embeddings = np.vstack([cluster_a, cluster_b, cluster_c])

    k = auto_select_k(embeddings, k_min=2, k_max=6)
    assert k == 3


def _standard(code, name):
    return TaggableStandard(code=code, name=name, text=name)


def test_balance_report_flags_under_and_over_represented():
    standards = [_standard("CC", "Cambio y Continuidad"), _standard("PLA", "Personas, Lugares y Ambiente")]
    clusters = [
        ClusterInfo(cluster_id=0, size=90, sample_questions=["a"], closest_standard=standards[0], closest_standard_similarity=0.8),
        ClusterInfo(cluster_id=1, size=10, sample_questions=["b"], closest_standard=standards[0], closest_standard_similarity=0.6),
    ]
    report = ClusterReport(clusters=clusters, total_questions=100, k=2)

    result = balance_report(report, standards)

    assert result["estado"] == "ok"
    assert result["por_grupo"]["grupo_0"]["estado"] == "sobre-representado"
    assert result["por_grupo"]["grupo_1"]["estado"] == "sub-representado"
    assert "Personas, Lugares y Ambiente" in result["estandares_sin_grupo_cercano"]


def test_balance_report_no_clusters_returns_sin_datos():
    result = balance_report(ClusterReport(clusters=[], total_questions=0, k=0), [])
    assert result["estado"] == "sin_datos"
