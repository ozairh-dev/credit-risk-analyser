"""Evidence pack export (Phase 9, docs/ai-governance.md).

Produces everything the model is allowed to reason from, **and nothing else**.
That boundary is the point: the pack is not a report, it is the complete and
exclusive input to a manual analysis workflow, and the validator downstream
checks the memo against exactly this content.

Three things the governance doc predates and this exporter supplies (D73):

- **The assumption register is built from config at export time.** The
  `assumptions` table exists but nothing writes to it (deliberately unwired in
  v1), while the ASSUMED values genuinely live in `config/`. Shipping an empty
  section would be worse than either.
- **The five stress output duties travel with the stressed figures** — taken
  verbatim from `StressRun.assumptions` so the pack cannot disagree with the
  CLI. A pack carrying stressed numbers without the assumptions behind them
  lets a model reason from figures whose basis it cannot see.
- **The cap line travels with the grade**, from D57's own generator, so a
  capped grade can never read as a judged one.
"""

from credit_risk import config
from credit_risk.scoring.engine import _cap_line
from credit_risk.scoring.fingerprint import score_fingerprint
from credit_risk.store.fingerprint import config_fingerprint
from credit_risk.store.provenance import filing_url
from credit_risk.stress.fingerprint import stress_fingerprint
from credit_risk.trends.fingerprint import trend_fingerprint

# ASSUMED values that feed the engine. Sourced from config at export time
# because the assumptions table is unwired in v1 (D73a).
REGISTERED_ASSUMPTIONS = (
    ("composites", "include_operating_leases", "boolean",
     "operating leases are debt-like post-ASC 842 (D6)"),
    ("composites", "include_st_investments", "boolean",
     "short-term investments net against debt (D33)"),
    ("composites", "component_aggregate_tolerance", "ratio",
     "debt components vs aggregate before refusing (D26)"),
    ("stress", "ebitda_mode", "mode",
     "constant margin unless operating leverage is chosen (D53)"),
    ("stress", "fixed_cost_share", "ratio",
     "share of costs held fixed under operating leverage (D53a)"),
    ("stress", "floating_share", "ratio",
     "share of debt repricing; the split is unreachable from XBRL (D54)"),
    ("stress", "default_tax_rate", "ratio",
     "statutory rate used when the effective rate is unusable (D55)"),
    ("stress", "new_debt_rate_default", "ratio",
     "priced on new borrowing when the implied rate is out of band (D53b)"),
)


def _fmt(value, unit=None):
    if value is None:
        return "—"
    if unit == "ratio":
        return f"{value:,.4f}"
    if isinstance(value, float) and abs(value) >= 1000:
        return f"{value:,.0f}"
    return f"{value:,}" if isinstance(value, int) else f"{value:,.4f}"


def _table(rows, headers):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def build_pack(raw, analysis, period_end, ticker=None) -> str:
    """One period's evidence pack, as Markdown."""
    selection, mapping, composites, integrity, metrics, trends, scores, stress = analysis
    cik = raw["cik"]
    L = []

    # ---- 1. header and provenance
    # The filing that sourced THIS period's data, not the company's newest
    # filing: in a period-specific pack the latter is misleading — a 2019 pack
    # would cite a 2026 accession the figures did not come from.
    period_accns = {c.accn for c in mapping.concepts if c.end == period_end}
    latest = max((f for f in selection.selected
                  if f.filed and f.accn in period_accns),
                 key=lambda f: (f.filed, f.accn), default=None)
    L += [f"# Evidence pack — {raw['entityName']} — {period_end}", "",
          "**This pack is the complete and exclusive basis for any memo written "
          "from it.** Every number a memo cites must appear below.", "",
          "## 1. Company and filing", ""]
    L += _table([
        ("Company", raw["entityName"]), ("CIK", cik), ("Ticker", ticker or "—"),
        ("Period end", period_end),
        ("Sourcing filing", f"{latest.form} {latest.accn} filed {latest.filed}"
         if latest else "—"),
        ("Filing link", filing_url(cik, latest.accn) if latest else "—"),
    ], ["Field", "Value"])
    L += ["", "Engine config fingerprints (a figure computed under different "
          "settings is not comparable with one computed under these):", ""]
    L += _table([("composites", config_fingerprint()),
                 ("scores", score_fingerprint()),
                 ("trends and warnings", trend_fingerprint()),
                 ("stress policy", stress_fingerprint())], ["Scope", "Fingerprint"])

    # ---- 2. grade, carrying the cap line (D57)
    score = next((s for s in scores if s.period_end == period_end), None)
    L += ["", "## 2. Grade", ""]
    if score is None:
        L += ["No score for this period — it was excluded from scoring "
              "(integrity FAIL) or no category could be scored.", ""]
    else:
        L += [f"**{_cap_line(score)}**", "",
              f"Total score {score.total_score:.1f} of 100. "
              f"Internal analytical grade for this project — not a credit "
              f"rating, and never mapped to an agency scale.", "",
              "A memo may not state or imply any grade other than this one.", ""]
        rows = []
        for c in score.categories:
            for comp in c.components:
                rows.append((c.name, comp.metric,
                             _fmt(comp.value), _fmt(comp.points),
                             f"{c.weight:g}", comp.treatment,
                             comp.reason_code or "—", comp.trend or "—"))
        L += _table(rows, ["Category", "Component", "Value", "Points",
                           "Weight", "Treatment", "Reason", "Trend"])

    # ---- 3. REPORTED concepts with filing links
    L += ["", "## 3. Reported concepts", "",
          "Every figure below is as filed. `Source tag` is the XBRL tag used.", ""]
    rows = []
    for c in sorted((c for c in mapping.concepts if c.end == period_end),
                    key=lambda c: c.concept):
        rows.append((c.concept, _fmt(c.value), c.unit, c.source_tag,
                     c.form or "—", c.accn or "—",
                     filing_url(cik, c.accn) or "—"))
    L += _table(rows, ["Concept", "Value", "Unit", "Source tag", "Form",
                       "Accession", "Filing link"])

    unavailable = [u for u in mapping.unavailable if u.period_end == period_end]
    if unavailable:
        L += ["", "Concepts with no usable value this period — a memo must say "
              "\"Data not available\" rather than estimating these:", ""]
        L += _table([(u.concept, u.reason_code) for u in sorted(
            unavailable, key=lambda u: u.concept)], ["Concept", "Reason"])

    # ---- 4. CALCULATED composites and metrics
    L += ["", "## 4. Calculated values", "", "### Composites", ""]
    rows = []
    for c in sorted((c for c in composites if c.end == period_end),
                    key=lambda c: c.concept):
        rows.append((c.concept, _fmt(c.value), c.method or "—",
                     ", ".join(n for n, _ in c.inputs) or "—",
                     c.reason_code or "—", c.detail or "—"))
    L += _table(rows, ["Concept", "Value", "Method", "Inputs", "Reason", "Detail"])
    L += ["", "### Metrics", ""]
    rows = []
    for m in sorted((m for m in metrics.metrics if m.end == period_end),
                    key=lambda m: m.metric):
        rows.append((m.metric, _fmt(m.value, "ratio") if m.value is not None else "—",
                     m.method or "—", ", ".join(n for n, _ in m.inputs) or "—",
                     m.reason_code or "—"))
    L += _table(rows, ["Metric", "Value", "Formula", "Inputs", "Reason"])

    # ---- 5. trends and warnings
    L += ["", "## 5. Trends and early warnings", "", "### Trend classifications", ""]
    rows = []
    for t in sorted((t for t in trends.trends if t.period_end == period_end),
                    key=lambda t: t.metric):
        rows.append((t.metric, t.verdict,
                     _fmt(t.change_1y, "ratio") if t.change_1y is not None else "—",
                     _fmt(t.change_over_window, "ratio")
                     if t.change_over_window is not None else "—",
                     " to ".join(t.window) if t.window else "—",
                     t.reason or "—"))
    L += _table(rows, ["Metric", "Verdict", "1y change", "Window change",
                       "Window", "Reason"])
    warns = [w for w in trends.warnings if w.period_end == period_end]
    L += ["", "### Warnings", ""]
    if warns:
        L += _table([(w.indicator, w.severity, w.base_severity,
                      "yes" if w.escalated else "no",
                      _fmt(w.current_value), _fmt(w.previous_value),
                      _fmt(w.threshold, "ratio") if w.threshold is not None else "—",
                      ", ".join(w.evidence_concepts) or "—")
                     for w in sorted(warns, key=lambda w: w.indicator)],
                    ["Indicator", "Severity", "Base", "Escalated", "Current",
                     "Previous", "Threshold", "Evidence"])
        esc = next((w.escalation_reason for w in warns if w.escalation_reason), None)
        if esc:
            L += ["", f"Escalation applied: {esc}"]
    else:
        L += ["None fired this period.", ""]

    # ---- 6. stress, carrying the five duties verbatim
    runs = [r for r in stress if r.period_end == period_end]
    L += ["", "## 6. Stress scenarios", ""]
    if not runs:
        L += ["This period cannot be stress tested: both EBITDA modes require "
              "revenue and EBITDA in the same period.", ""]
    else:
        for run in sorted(runs, key=lambda r: r.scenario):
            L += [f"### Scenario: {run.scenario}", "",
                  f"Base grade {run.base_grade} ({run.base_score:.1f}) -> "
                  f"stressed grade {run.stressed_grade} "
                  f"({run.stressed_score:.1f}).", ""]
            L += _table([(m, _fmt(b, "ratio") if b is not None else "—",
                          _fmt(s, "ratio") if s is not None else "—",
                          _fmt(c, "ratio") if c is not None else "—",
                          reason or st)
                         for m, (b, s, c, st, reason) in sorted(run.results.items())],
                        ["Metric", "Base", "Stressed", "Change", "Status"])
            if run.drivers:
                L += ["", "Driver attribution — each shock run **alone** against "
                      "base. Drivers do not sum to the combined run: the "
                      "propagation is multiplicative and tax is floored.", ""]
                L += _table([(sh, m, _fmt(v, "ratio"))
                             for (sh, m), v in sorted(run.drivers.items())],
                            ["Shock", "Metric", "Change alone"])
            L += ["", "Assumptions and simplifications behind these figures:", ""]
            L += [f"- {line}" for line in run.assumptions]
            L += [""]

    # ---- 7. data quality and integrity
    L += ["", "## 7. Data quality and integrity", ""]
    L += _table([(r.check_name, r.outcome, r.detail or "—")
                 for r in sorted((r for r in integrity.results
                                  if r.period_end == period_end),
                                 key=lambda r: r.check_name)],
                ["Check", "Outcome", "Detail"])
    L += ["", "`SKIP` means an input was unavailable so the check could not run "
          "— a data gap, not a pass.", ""]

    # ---- 8. assumption register
    L += ["", "## 8. Assumption register", "",
          "Every value below is `ASSUMED` and sourced from project config, not "
          "from the filing. A memo must not present any of them as reported "
          "fact.", ""]
    rows = []
    for family, key, unit, reason in REGISTERED_ASSUMPTIONS:
        loaded = config.stress() if family == "stress" else config.load("composites")
        rows.append((key, _fmt(loaded.get(key)) if not isinstance(
            loaded.get(key), (str, bool, type(None))) else str(loaded.get(key)),
            unit, "config", reason))
    L += _table(rows, ["Assumption", "Value", "Unit", "Source", "Why"])

    # ---- 9. the boundary
    L += ["", "## 9. What this pack does not contain", "",
          "Nothing below is available to a memo written from this pack. Where a "
          "memo would need any of it, the required answer is "
          "**\"Data not available\"**:", "",
          "- market data, share prices or market capitalisation",
          "- management commentary, guidance or transcripts",
          "- peer or industry comparisons",
          "- forward estimates or analyst forecasts",
          "- credit ratings from any agency",
          "- any filing content beyond the tagged XBRL facts above", ""]
    return "\n".join(L) + "\n"
