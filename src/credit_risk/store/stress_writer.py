"""Stress storage (Phase 8, D58).

A SEPARATE writer with no access to the `scores` table, by design (D59).

A stressed grade written into `scores` would carry the score fingerprint
rather than the stress policy fingerprint, and would occupy the
`(cik, period_end)` CURRENT slot `uq_scores_current` reserves for the real
grade — superseding a genuine grade with a hypothetical one and leaving no way
to tell them apart afterwards. That is corruption of score history, not merely
a misleading row, so the separation is structural rather than disciplinary:
this module never names `scores`, and a test asserts a stress run adds zero
rows to it.
"""

from datetime import datetime, timezone

TABLES = ("stress_runs", "stress_results", "stress_drivers")


def _now():
    return datetime.now(timezone.utc).isoformat()


def store_stress_runs(conn, cik, runs, fingerprint) -> None:
    """Append-with-history per (cik, period_end, scenario)."""
    created_at = _now()
    for run in runs:
        existing = conn.execute(
            """SELECT id, stressed_score, config_fingerprint FROM stress_runs
               WHERE cik=? AND period_end=? AND scenario=? AND status='CURRENT'""",
            (cik, run.period_end, run.scenario),
        ).fetchone()
        if (existing is not None
                and existing["stressed_score"] == run.stressed_score
                and existing["config_fingerprint"] == fingerprint):
            continue
        conn.execute(
            """UPDATE stress_runs SET status='SUPERSEDED'
               WHERE cik=? AND period_end=? AND scenario=? AND status='CURRENT'""",
            (cik, run.period_end, run.scenario),
        )
        cur = conn.execute(
            """INSERT INTO stress_runs
               (cik, period_end, scenario, revenue_shock, margin_shock,
                rate_shock_bps, additional_debt, capex_shock, ebitda_mode,
                fixed_cost_share, floating_share, new_debt_rate_used,
                new_debt_rate_source, new_debt_rate_reason, base_score,
                base_grade, stressed_score, stressed_grade, config_fingerprint,
                status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'CURRENT',?)""",
            (cik, run.period_end, run.scenario,
             run.shocks["revenue_shock"], run.shocks["margin_shock"],
             run.shocks["rate_shock_bps"], run.shocks["additional_debt"],
             run.shocks["capex_shock"], run.ebitda_mode, run.fixed_cost_share,
             run.floating_share, run.new_debt_rate_used,
             run.new_debt_rate_source, run.new_debt_rate_reason,
             run.base_score, run.base_grade, run.stressed_score,
             run.stressed_grade, fingerprint, created_at),
        )
        run_id = cur.lastrowid
        for metric, (base, stressed, change, status, reason) in run.results.items():
            conn.execute(
                """INSERT INTO stress_results
                   (run_id, metric, base_value, stressed_value, change,
                    data_status, reason_code)
                   VALUES (?,?,?,?,?,?,?)""",
                (run_id, metric, base, stressed, change, status, reason),
            )
        for (shock, metric), change in run.drivers.items():
            conn.execute(
                """INSERT INTO stress_drivers (run_id, shock, metric, change)
                   VALUES (?,?,?,?)""",
                (run_id, shock, metric, change),
            )
    conn.commit()
