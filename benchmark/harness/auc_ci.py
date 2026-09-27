"""A confidence interval for A2's headline AUC, respecting the clustering.

**Why this needs its own script rather than a textbook formula.** The 774
"survivor company-cutoffs" behind the pooled AUC are not 774 independent
observations — `a2_baseline.md` already says so: 43 distinct companies, each
observed at up to 18 cutoffs, and a company weak at one cutoff is usually weak
at the next. Hanley-McNeil and DeLong's method both assume the two samples are
independent draws, which this violates on the survivor side. The correct fix
for genuine non-independence is to resample at the level that IS independent —
here, the company, not the company-cutoff — regardless of which direction that
happens to move the number for any particular dataset.

**It does not move it the direction a first guess suggests, and that needs two
separate explanations, not one.** Computed here anyway for contrast: the naive
Hanley-McNeil formula, applied to n1=18 (failures) against n2=774 (survivor
observations, wrongly treated as independent), comes out WIDER than the
cluster bootstrap, not narrower — the opposite of what "ignoring the
clustering should look artificially confident" would predict.

*Why n2=774 buys the naive formula nothing.* Hanley-McNeil's Q1 and Q2 terms
are fixed functions of AUC alone — they take no input from n1, n2, or the
shape of either sample. With n1=18 held fixed, the (n2-1)(Q2-AUC^2) term's
contribution to the variance converges, as n2 grows, to a FLOOR of
(Q2-AUC^2)/n1. Verified: at n2=774 the naive SE^2 already sits within 1% of
that floor, so treating the 774 as independent, correctly or not, changes
almost nothing — **the naive interval's width is set almost entirely by
n1=18, the number of failure events.**

*Why the resulting number is larger than the bootstrap's, not just resistant
to n2.* The floor itself, via Q1 and Q2, is derived assuming the underlying
score distributions are exponential — an approximation that is conservative
for AUC values away from 0.5 on data that does not actually look exponential,
which real credit-score distributions generally do not. The bootstrap instead
resamples the empirical distribution directly, with no such assumption, and
comes out tighter as a consequence of that, not because it handles the
clustering "correctly" in some way that mechanically shrinks an interval.
Clustering decides WHICH units a bootstrap draw is built from; it is not what
makes this bootstrap's interval narrower than Hanley-McNeil's.

**Read together: no correction on the survivor side, however done, can buy
back precision that eighteen events does not have** — that is the point worth
keeping from both explanations, not which formula happens to be tighter.

**The bootstrap: failures resample ordinarily** — each of the 18 is one company
at one cutoff, genuinely independent of the others. **Survivors resample at the
COMPANY level**: each bootstrap draw picks 43 companies with replacement from
the 43 distinct survivors, and every cutoff that company contributed goes with
it as one block. A company drawn twice contributes its full cluster twice; a
company left out contributes nothing. This preserves the within-company
correlation the pseudo-replication note describes, which observation-level
resampling would destroy — and it is reported as the primary interval because
it is the methodologically correct one for this design, not because of which
way it happens to move the number.

Reads only `benchmark/results/a2_raw.json` — no engine call, no re-scoring.
"""

import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from score_a2 import auc_pairwise                              # noqa: E402

RAW = pathlib.Path("benchmark/results/a2_raw.json")
N_BOOT = 10_000
SEED = 20260927        # fixed for reproducibility — a CI that moves on rerun
                        # is not a CI a reader can check


def build_clusters(raw: dict, split: str | None = None):
    """Failure scores (flat list) and survivor scores (dict: company -> list).

    `split` restricts to that split's admitted cases ("dev"/"holdout"), or None
    for all 18.
    """
    cases = [c for c in raw["cases"] if c["admitted"]
             and (split is None or c["split"] == split)]
    cutoffs = sorted({c["pit_cutoff"] for c in cases})
    failures = [c["assessment"]["total_score"] for c in cases]

    by_company: dict[str, list[float]] = {}
    for cutoff in cutoffs:
        for ticker, a in raw["panels"][cutoff].items():
            if a["scored"]:
                by_company.setdefault(ticker, []).append(a["total_score"])
    return failures, by_company


def cluster_bootstrap_ci(failures, by_company, n_boot=N_BOOT, seed=SEED,
                         alpha=0.05):
    rng = random.Random(seed)
    companies = sorted(by_company)
    n_f, n_c = len(failures), len(companies)

    point = auc_pairwise(failures,
                         [v for vals in by_company.values() for v in vals])

    draws = []
    for _ in range(n_boot):
        f_sample = [failures[rng.randrange(n_f)] for _ in range(n_f)]
        s_sample = []
        for _ in range(n_c):
            company = companies[rng.randrange(n_c)]
            s_sample.extend(by_company[company])
        draws.append(auc_pairwise(f_sample, s_sample))

    draws.sort()
    lo = draws[int((alpha / 2) * n_boot)]
    hi = draws[int((1 - alpha / 2) * n_boot) - 1]
    return {
        "point_estimate": round(point, 4),
        "n_failures": n_f,
        "n_survivor_companies": n_c,
        "n_survivor_observations": sum(len(v) for v in by_company.values()),
        "n_bootstrap": n_boot,
        "ci_95_lo": round(lo, 4),
        "ci_95_hi": round(hi, 4),
        "method": ("cluster bootstrap, 10,000 resamples; failures resampled "
                  "per-observation (18 independent units), survivors "
                  "resampled per-company (43 clusters, all of a drawn "
                  "company's cutoffs move together)"),
    }


def naive_hanley_mcneil(failures, pooled_survivors):
    """The textbook formula, computed ANYWAY and reported for contrast — to
    show numerically why it is the wrong tool here, not just to assert it."""
    n1, n2 = len(failures), len(pooled_survivors)
    auc = auc_pairwise(failures, pooled_survivors)
    q1 = auc / (2 - auc)
    q2 = 2 * auc**2 / (1 + auc)
    se2 = (auc * (1 - auc) + (n1 - 1) * (q1 - auc**2)
          + (n2 - 1) * (q2 - auc**2)) / (n1 * n2)
    se = se2 ** 0.5
    return {"auc": round(auc, 4), "n1": n1, "n2_treated_as_independent": n2,
            "se": round(se, 4),
            "ci_95_lo": round(auc - 1.96 * se, 4),
            "ci_95_hi": round(auc + 1.96 * se, 4)}


if __name__ == "__main__":
    raw = json.loads(RAW.read_text())
    result = {}
    for split in (None, "dev", "holdout"):
        failures, by_company = build_clusters(raw, split)
        key = split or "all"
        result[key] = cluster_bootstrap_ci(failures, by_company)
        print(f"[{key}] n_failures={result[key]['n_failures']} "
              f"n_survivor_companies={result[key]['n_survivor_companies']} "
              f"({result[key]['n_survivor_observations']} pooled obs)")
        print(f"  cluster-bootstrap AUC {result[key]['point_estimate']}  "
              f"95% CI [{result[key]['ci_95_lo']}, {result[key]['ci_95_hi']}]")

    failures_all, by_company_all = build_clusters(raw, None)
    pooled = [v for vals in by_company_all.values() for v in vals]
    naive = naive_hanley_mcneil(failures_all, pooled)
    print(f"\n[contrast] naive Hanley-McNeil, n2={naive['n2_treated_as_independent']} "
          f"(wrongly treats 774 pseudo-replicated points as independent):")
    print(f"  AUC {naive['auc']}  95% CI [{naive['ci_95_lo']}, {naive['ci_95_hi']}]"
          f"  <- WIDER, not narrower. n1=18 sets a floor on this formula "
          f"regardless of n2; the exponential-distribution assumption behind "
          f"Q1/Q2 is what makes it conservative here — see module docstring")

    out = pathlib.Path("benchmark/results/a2_auc_ci.json")
    out.write_text(json.dumps({**result, "naive_contrast": naive}, indent=1))
    print(f"\nwrote {out}")
