"""Phase 1 checks: the project imports and its configuration is coherent.

These are deliberately about wiring, not finance. Real calculation tests
arrive in Phase 5.
"""

import tomllib

from credit_risk import __version__, config


def test_version_is_the_expected_value_and_agrees_with_pyproject():
    """`assert __version__` passed for any non-empty string (audit finding 14).

    Two assertions doing different jobs: the literal pins what the version
    actually is, and the pyproject comparison catches the real failure mode —
    bumping one of the two files and forgetting the other.
    """
    assert __version__ == "0.1.0"
    pyproject = tomllib.loads(
        (config.PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert pyproject["project"]["version"] == __version__


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
    """Values hand-checked against docs/credit-methodology.md's preset descriptions:
    Moderate = rev -10%, margin -2pp, rates +100bps; Severe = rev -20%, margin -5pp,
    rates +200bps. margin_shock is positive because it is *subtracted* from the base
    margin in the propagation formula (positive shock = margin reduction)."""
    presets = config.stress()["presets"]
    assert {"base", "moderate", "severe"} <= set(presets)
    assert presets["base"]["revenue_shock"] == 0.0
    assert presets["moderate"] == {
        "revenue_shock": -0.10,
        "margin_shock": 0.02,
        "rate_shock_bps": 100,
        "additional_debt": 0,
        "capex_shock": 0.0,
    }
    assert presets["severe"] == {
        "revenue_shock": -0.20,
        "margin_shock": 0.05,
        "rate_shock_bps": 200,
        "additional_debt": 0,
        "capex_shock": 0.0,
    }


def test_tag_map_concept_count_is_written_down():
    """The literal concept count, deliberately not derived (audit finding 13).

    Six assertions elsewhere size themselves from `len(config.tag_map())`,
    which is correct for an incidental total but self-referential: a concept
    accidentally deleted from `config/tag_map.yaml` would shrink the code's
    expectation and the test's together and still pass. This is the one place
    the number is written down, so a deletion fails here and only here —
    one invariant, one layer (CLAUDE.md rule 13).

    Update it deliberately when a concept is added: 31 -> 34 when the
    lease-inclusive concepts arrived (D27).
    """
    assert len(config.tag_map()) == 34


def test_tag_map_entries_are_ordered_candidate_lists():
    tags = config.tag_map()
    assert "revenue" in tags and "ebit" in tags and "cfo" in tags
    for concept, candidates in tags.items():
        assert isinstance(candidates, list) and candidates, concept
    # exact candidate tags checked against docs/data-sources.md's mapping table
    assert tags["revenue"] == [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
    ]
    assert tags["ebit"] == ["OperatingIncomeLoss"]


def test_stress_config_carries_the_d53_structure():
    """Phase 8 step one (D53): the keys exist ahead of the engine, like D26's
    tolerance before Task 9. The engine wires them in step two; this pins that
    they are present, typed, and ordered sensibly until then."""
    stress = config.stress()
    assert stress["fixed_cost_share"] == 0.3
    assert stress["new_debt_rate"] is None          # explicit override, unset
    assert stress["new_debt_rate_default"] == 0.06
    low, high = stress["new_debt_rate_band"]
    assert 0 < low < stress["new_debt_rate_default"] < high
    # presets deliberately carry no incremental borrowing (D53c)
    for name, preset in stress["presets"].items():
        assert preset["additional_debt"] == 0, name


def test_stress_config_per_run_and_policy_keys_are_both_present():
    """D54-D56: the policy keys the stress fingerprint will cover, and the
    per-run levers it must NOT. Pinned before the engine so the split cannot be
    quietly collapsed when step two wires it."""
    stress = config.stress()
    policy = {"presets", "sensitivity_grid", "default_tax_rate",
              "new_debt_rate_default", "new_debt_rate_band"}
    per_run = {"ebitda_mode", "fixed_cost_share", "floating_share",
               "new_debt_rate"}
    assert policy <= set(stress)
    assert per_run <= set(stress)
    assert not (policy & per_run)          # a key is one or the other, never both
    assert stress["floating_share"] == 1.0
    assert stress["default_tax_rate"] == 0.21


def test_the_four_fingerprint_scopes_are_disjoint():
    """D56: four fingerprints, no key in two of them. File location is
    incidental — trend_points lives in thresholds.yaml and belongs to the score
    scope; default_tax_rate lives in stress.yaml and belongs to the stress
    scope. Blast radius is the boundary."""
    from credit_risk.scoring.fingerprint import FINGERPRINTED_KEYS as SCORE
    from credit_risk.store.fingerprint import FINGERPRINTED_KEYS as COMPOSITE
    from credit_risk.trends.fingerprint import FINGERPRINTED_KEYS as TREND
    STRESS = ("presets", "sensitivity_grid", "default_tax_rate",
              "new_debt_rate_default", "new_debt_rate_band")
    scopes = [set(COMPOSITE), set(SCORE), set(TREND), set(STRESS)]
    for i, a in enumerate(scopes):
        for b in scopes[i + 1:]:
            assert not (a & b), (a & b)
    assert "trend_points" in set(SCORE)          # not the trend scope
    assert "default_tax_rate" in set(STRESS)     # not the score scope
