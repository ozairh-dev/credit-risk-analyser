"""Phase 1 checks: the project imports and its configuration is coherent.

These are deliberately about wiring, not finance. Real calculation tests
arrive in Phase 5.
"""

from credit_risk import __version__, config


def test_package_imports():
    assert __version__


def test_thresholds_weights_sum_to_100():
    weights = config.thresholds()["weights"]
    assert sum(weights.values()) == 100


def test_every_band_has_one_more_point_than_edges():
    """A band with N edges divides the number line into N+1 buckets."""
    for name, band in config.thresholds()["bands"].items():
        assert len(band["points"]) == len(band["edges"]) + 1, name
        assert band["direction"] in {"lower_better", "higher_better"}, name


def test_grade_boundaries_are_descending():
    grades = config.thresholds()["grades"]
    lower_bounds = sorted((int(k) for k in grades), reverse=True)
    assert [grades[b] for b in lower_bounds] == [1, 2, 3, 4, 5, 6]


def test_stress_presets_present():
    presets = config.stress()["presets"]
    assert {"base", "moderate", "severe"} <= set(presets)
    assert presets["base"]["revenue_shock"] == 0.0


def test_tag_map_entries_are_ordered_candidate_lists():
    tags = config.tag_map()
    assert "revenue" in tags and "ebit" in tags and "cfo" in tags
    for concept, candidates in tags.items():
        assert isinstance(candidates, list) and candidates, concept
