"""A2 scoring — turns the raw record into the discrimination metrics.

Kept separate from `run_a2.py` so the measurement and the grading of the
measurement can be re-run independently: a change to how a result is judged must
never require re-running the engine, or the two become impossible to tell apart.

Every metric is reported for the development and held-out sets SEPARATELY.
Pooling them would let an overfitted Phase C improvement read as a real one.

**Pseudo-replication, stated because the headline figure invites the wrong
reading.** The survivor population is 43 distinct companies observed at up to 19
cutoffs each, so ~817 "survivor company-cutoffs" are **not 817 independent
observations**. A company weak at one cutoff is usually weak at the next, so the
pooled false-positive rate has far less precision than its denominator suggests.
Both figures are therefore reported: the per-company-cutoff rate, and the share
of **distinct companies** flagged at least once. The second is the honest upper
bound on how many real businesses this rule would put in front of an analyst.
"""

import json
import pathlib
import statistics as st
import sys
from collections import Counter

RAW = pathlib.Path("benchmark/results/a2_raw.json")
OUT = pathlib.Path("benchmark/results/a2_scored.json")

# ---------------------------------------------------------------------------
# The flag rule: the operational definition of "the engine raised a concern".
#
# FROZEN AT grade >= 5 (owner decision, D82).
#
# Chosen on BAND SEMANTICS, not by picking the best row of a sensitivity table:
# grades 5 and 6 are the bottom two of a six-band scale, so "concern" means the
# bottom third, and grade 4 is mid-scale. The measured cost on this cohort is
# 78% sensitivity at a 21% per-company-cutoff false-positive rate, and that is
# reported as a CONSEQUENCE of the rule rather than as its justification.
#
# `grade >= 6` was rejected despite a 4% false-positive rate: it misses 9 of 18
# failures, and in credit a missed default is the worse error.
#
# Warning-based and combined rules were rejected on measured separation — an
# escalated warning reaches 50% of failures against 37% of survivors (13pp), and
# a High-severity warning 72% against 45% (27pp). Neither separates well enough
# to earn a place in the headline metric, and four failures at grade 4-5 (DNR,
# ASNA, DBD, TLRD) raise no escalated warning at all.
# ---------------------------------------------------------------------------
CONCERN_GRADE = 5


def flags_concern(a: dict) -> bool | None:
    """True = concern, False = no concern, **None = no opinion**.

    The tri-state is the substance of this function, not defensiveness. When the
    engine produced no score, collapsing that to False would assert "no score,
    no concern" — which is how the engine's blindness to Hertz would read as a
    clean bill of health. A refusal is an answer, and it is not reassurance
    (CLAUDE.md rule 3). Callers must exclude None from both the sensitivity and
    the false-positive denominators and report it in its own row.
    """
    if not a.get("scored") or a.get("grade") is None:
        return None
    return a["grade"] >= CONCERN_GRADE


# ---------------------------------------------------------------------------
# metrics


def auc_pairwise(failures: list[float], survivors: list[float]) -> float | None:
    """P(a random failure scores WORSE than a random survivor), ties at 0.5.

    Lower total_score is worse, so a failure "wins" a pair when its score is
    lower. Threshold-free, which is why it leads the report.
    """
    if not failures or not survivors:
        return None
    wins = 0.0
    for f in failures:
        for s in survivors:
            wins += 1.0 if f < s else (0.5 if f == s else 0.0)
    return wins / (len(failures) * len(survivors))


def auc_rank(failures: list[float], survivors: list[float]) -> float | None:
    """The same quantity by a different route: the Mann-Whitney U identity.

    Rank every score ascending with ties averaged; then
        U = R_f - n_f(n_f + 1)/2
    counts the pairs in which the FAILURE's score is the GREATER one. Here a
    greater score is a BETTER credit, so the quantity wanted is its complement:
        AUC = 1 - U / (n_f * n_s)

    Present because a single implementation of a headline metric is a single
    point of failure. Two derivations that agree is evidence; one is an
    assertion (CLAUDE.md rule 13).

    **The cross-check earned itself immediately.** First written without the
    complement, this returned 0.0978 against the pairwise 0.9022 — exact
    complements, which is the signature of an inverted orientation rather than an
    arithmetic slip. A single implementation would have published 0.0978 or
    0.9022 with nothing to contradict it.
    """
    if not failures or not survivors:
        return None
    combined = sorted([(v, "f") for v in failures] + [(v, "s") for v in survivors])
    ranks: list[float] = [0.0] * len(combined)
    i = 0
    while i < len(combined):
        j = i
        while j + 1 < len(combined) and combined[j + 1][0] == combined[i][0]:
            j += 1
        average = (i + j) / 2 + 1          # 1-based, ties share the mean rank
        for k in range(i, j + 1):
            ranks[k] = average
        i = j + 1
    r_f = sum(r for r, (_v, kind) in zip(ranks, combined) if kind == "f")
    n_f, n_s = len(failures), len(survivors)
    u = r_f - n_f * (n_f + 1) / 2
    return 1 - u / (n_f * n_s)


def auc_on_grades(failures: list[int], survivors: list[int]) -> float | None:
    """The same measure computed on the GRADE rather than the score.

    Reported alongside the score-based AUC because the grade is what a reader
    sees and it is far coarser — six bands against a continuous 0-100 — so ties
    dominate and the figure is pulled toward 0.5. A higher grade is worse, so a
    failure "wins" a pair when its grade is the greater one.
    """
    if not failures or not survivors:
        return None
    wins = 0.0
    for f in failures:
        for s in survivors:
            wins += 1.0 if f > s else (0.5 if f == s else 0.0)
    return wins / (len(failures) * len(survivors))


def percentile_rank(value: float, population: list[float]) -> float | None:
    """Where `value` sits in `population`; 0.0 = worst of all, 1.0 = best."""
    if not population:
        return None
    below = sum(1 for p in population if p < value)
    equal = sum(1 for p in population if p == value)
    return (below + 0.5 * equal) / len(population)


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def score(raw: dict, rule=flags_concern) -> dict:
    cases = [c for c in raw["cases"] if c["admitted"]]
    excluded = [c for c in raw["cases"] if not c["admitted"]]
    panels = raw["panels"]

    out = {
        "flag_rule": f"grade >= {CONCERN_GRADE}",
        "flag_rule_basis": (
            "Chosen on band semantics — grades 5 and 6 are the bottom two of a "
            "six-band scale, so concern means the bottom third and grade 4 is "
            "mid-scale. NOT selected by comparing the sensitivity/false-positive "
            "table; the measured cost is a consequence, not the justification "
            "(D82)."),
        "unscoreable_handling": (
            "flags_concern returns None when the engine produced no score. Those "
            "cases are excluded from both denominators and reported in their own "
            "row. A refusal is an answer and it is not 'no concern'."),
        "pseudo_replication": (
            "Survivor company-cutoff counts are NOT independent observations: 43 "
            "distinct companies are each observed at up to 19 cutoffs, and a "
            "company weak at one cutoff is usually weak at the next. The pooled "
            "false-positive rate therefore has far less precision than its "
            "denominator implies. `distinct_survivor_companies_flagged` is "
            "reported beside it as the honest upper bound."),
        "coverage_failures": [
            {"ticker": c["ticker"], "event_date": c["event_date"],
             "categories_scored": c["assessment"]["categories_scored"],
             "grade_shown": c["assessment"]["grade"],
             "grade_uncapped": c["assessment"]["grade_uncapped"],
             "total_score": c["assessment"]["total_score"],
             "note": ("scored on too few categories to enter the discrimination "
                      "metrics; retained because hiding it would overstate "
                      "coverage")}
            for c in excluded],
        "splits": {},
    }

    for split in ("dev", "holdout", "all"):
        subset = [c for c in cases if split == "all" or c["split"] == split]
        if not subset:
            continue

        f_scores, f_grades, per_case = [], [], []
        f_flag = Counter()
        seen_cutoffs: set[str] = set()

        for c in subset:
            a = c["assessment"]
            verdict = rule(a)
            f_flag[verdict] += 1
            panel = panels[c["pit_cutoff"]]
            alive = [p for p in panel.values() if p["scored"]]
            if a["scored"]:
                f_scores.append(a["total_score"])
                f_grades.append(a["grade"])
            per_case.append({
                "ticker": c["ticker"], "cutoff": c["pit_cutoff"],
                "grade": a["grade"], "total_score": a["total_score"],
                "categories_scored": a["categories_scored"],
                "survivor_median_grade": (st.median([p["grade"] for p in alive])
                                          if alive else None),
                "score_percentile_vs_panel": (
                    round(percentile_rank(a["total_score"],
                                          [p["total_score"] for p in alive]), 3)
                    if alive and a["scored"] else None),
                "worse_than_panel_median": (
                    a["total_score"] < st.median([p["total_score"]
                                                  for p in alive])
                    if alive and a["scored"] else None),
                "escalated": a["escalated"],
                "high_severity": a["high_severity"],
                "flagged": verdict,
            })
            seen_cutoffs.add(c["pit_cutoff"])

        # Survivor population: each company once per DISTINCT cutoff in the
        # split, carrying its ticker so distinct companies can be counted.
        surv: list[tuple[str, dict]] = [
            (ticker, a) for cut in sorted(seen_cutoffs)
            for ticker, a in panels[cut].items()]
        s_scores = [a["total_score"] for _t, a in surv if a["scored"]]
        s_grades = [a["grade"] for _t, a in surv if a["scored"]]

        s_flag = Counter(rule(a) for _t, a in surv)
        flagged_companies = {t for t, a in surv if rule(a) is True}
        companies_with_any_opinion = {t for t, a in surv if rule(a) is not None}

        sens_denominator = f_flag[True] + f_flag[False]
        fpr_denominator = s_flag[True] + s_flag[False]

        a_pair = auc_pairwise(f_scores, s_scores)
        a_rank = auc_rank(f_scores, s_scores)

        out["splits"][split] = {
            "n_failures": len(subset),
            "n_failures_scored": len(f_scores),
            "n_failures_unscoreable": f_flag[None],
            "n_distinct_cutoffs": len(seen_cutoffs),
            "n_survivor_company_cutoffs": len(surv),
            "n_survivor_company_cutoffs_unscoreable": s_flag[None],
            "n_distinct_survivor_companies": len({t for t, _a in surv}),

            "failure_grade_distribution": dict(sorted(Counter(f_grades).items())),
            "survivor_grade_distribution": dict(sorted(Counter(s_grades).items())),
            "failure_median_grade": st.median(f_grades) if f_grades else None,
            "survivor_median_grade": st.median(s_grades) if s_grades else None,
            "failure_mean_grade": round(st.mean(f_grades), 2) if f_grades else None,
            "survivor_mean_grade": round(st.mean(s_grades), 2) if s_grades else None,
            "failure_median_score": round(st.median(f_scores), 2) if f_scores else None,
            "survivor_median_score": round(st.median(s_scores), 2) if s_scores else None,

            "auc_failure_worse_than_survivor": (round(a_pair, 4)
                                                if a_pair is not None else None),
            "auc_by_rank_identity": (round(a_rank, 4)
                                     if a_rank is not None else None),
            "auc_methods_agree": (a_pair is not None and a_rank is not None
                                  and abs(a_pair - a_rank) < 1e-9),
            "auc_on_grades": (round(a_grade, 4)
                              if (a_grade := auc_on_grades(f_grades,
                                                           s_grades)) is not None
                              else None),
            "failures_worse_than_own_panel_median": sum(
                1 for r in per_case if r["worse_than_panel_median"]),

            "sensitivity": _rate(f_flag[True], sens_denominator),
            "sensitivity_numerator": f_flag[True],
            "sensitivity_denominator": sens_denominator,
            "false_positive_rate_company_cutoffs": _rate(s_flag[True],
                                                         fpr_denominator),
            "false_positive_numerator": s_flag[True],
            "false_positive_denominator": fpr_denominator,
            "distinct_survivor_companies_flagged": len(flagged_companies),
            "distinct_survivor_companies_with_an_opinion": len(
                companies_with_any_opinion),
            "distinct_company_flag_share": _rate(
                len(flagged_companies), len(companies_with_any_opinion)),
            "flagged_survivor_companies": sorted(flagged_companies),

            "escalated_reach_failures": _rate(
                sum(1 for c in subset if c["assessment"]["escalated"]),
                len(subset)),
            "escalated_reach_survivors": _rate(
                sum(1 for _t, a in surv if a["escalated"]), len(surv)),
            "high_severity_reach_failures": _rate(
                sum(1 for c in subset if c["assessment"]["high_severity"]),
                len(subset)),
            "high_severity_reach_survivors": _rate(
                sum(1 for _t, a in surv if a["high_severity"]), len(surv)),

            "cases": per_case,
        }
    return out


if __name__ == "__main__":
    result = score(json.loads(RAW.read_text()))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1))
    print(f"wrote {OUT}")
    print(f"flag rule: {result['flag_rule']}\n")
    for split, s in result["splits"].items():
        print(f"[{split}]  {s['n_failures']} failures "
              f"({s['n_failures_unscoreable']} unscoreable) vs "
              f"{s['n_survivor_company_cutoffs']} survivor company-cutoffs "
              f"over {s['n_distinct_survivor_companies']} companies")
        print(f"  median grade      failures {s['failure_median_grade']}   "
              f"survivors {s['survivor_median_grade']}")
        print(f"  AUC on score      {s['auc_failure_worse_than_survivor']}   "
              f"(rank identity {s['auc_by_rank_identity']}, "
              f"agree: {s['auc_methods_agree']})")
        print(f"  AUC on grade      {s['auc_on_grades']}   "
              f"— coarser, ties dominate")
        print(f"  sensitivity       {s['sensitivity']:.0%} "
              f"({s['sensitivity_numerator']}/{s['sensitivity_denominator']})")
        print(f"  FPR (cutoffs)     {s['false_positive_rate_company_cutoffs']:.0%} "
              f"({s['false_positive_numerator']}/{s['false_positive_denominator']})")
        print(f"  distinct companies flagged  "
              f"{s['distinct_survivor_companies_flagged']}"
              f"/{s['distinct_survivor_companies_with_an_opinion']} = "
              f"{s['distinct_company_flag_share']:.0%}")
        print(f"  escalated reach   failures "
              f"{s['escalated_reach_failures']:.0%}   survivors "
              f"{s['escalated_reach_survivors']:.0%}")
        print()
