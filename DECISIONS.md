# Decisions

Format: decision · reason · alternatives considered · consequences.

## D1 — Python only, no frontend, no web framework in v1
Reason: one language for a solo builder; every hour on plumbing between Next.js,
TypeScript and Python is an hour not spent on the credit engine.
Alternatives: Next.js + Python (original brief); FastAPI + simple frontend.
Consequences: v1 output is CLI + exported reports. UI is a v2 decision.

## D2 — SQLite instead of PostgreSQL
Reason: 25–50 companies, one user, zero setup. Postgres adds nothing until concurrency
or scale exist.
Alternatives: Postgres locally; Supabase free tier.
Consequences: migration to Postgres later is mechanical via SQLAlchemy if ever needed.

## D3 — SEC EDGAR only in v1; Companies House deferred
Reason: companyfacts is a clean JSON API with standardised tags. UK iXBRL is document
parsing with weak standardisation and many abbreviated filings.
Alternatives: both from the start (original brief).
Consequences: US-listed universe only in v1.

## D4 — No runtime AI in v1; manual evidence-pack workflow with a validator
Reason: £0 constraint; a subscription is not an API; the deterministic engine must be
proven standalone first.
Alternatives: Ollama local model; Claude API.
Consequences: memo drafting is a documented manual process; validator enforces that no
number in a memo is absent from the evidence pack.

## D5 — EBITDA is always EBIT + D&A in v1, labelled as such
Reason: there is no standard us-gaap EBITDA tag; "reported EBITDA" as a first choice
(original brief) is not implementable from XBRL.
Alternatives: parse adjusted EBITDA from filings text (v3 at best).
Consequences: no adjusted EBITDA; D&A missing → EBITDA UNAVAILABLE.

## D6 — Operating lease liabilities included in total debt by default, with toggle
Reason: post-ASC 842 they are fixed obligations; credit analysis and rating agencies
treat them as debt-like. The original brief did not decide this.
Alternatives: exclude; include finance leases only.
Consequences: leverage will be higher for lease-heavy companies; ex-lease figure always
shown alongside.

## D7 — Stress propagation: constant-margin default, operating-leverage optional
Reason: the original brief specified shocks but not how revenue shocks reach EBITDA.
Constant margin is transparent; operating leverage is more realistic but needs an
assumed fixed-cost share.
Alternatives: operating leverage as default.
Consequences: both modes tested; mode and fixed-cost share are ASSUMED and registered.

## D8 — Rate shocks apply to the whole debt stack by default (floating_share = 1.0)
Reason: floating/fixed split is not reliably available from XBRL. Whole-stack repricing
is conservative and stated as a simplification.
Alternatives: assume a floating share; parse debt footnotes.
Consequences: stressed interest is an upper bound; documented in every stress output.

## D9 — Evidence-reason vs data-gap-reason UNAVAILABLE handled differently in scoring
Reason: negative EBITDA is information (score 0); missing interest expense is a gap
(drop and cap the grade). Treating both the same would either punish data gaps or
reward losses.
Alternatives: treat all UNAVAILABLE as neutral.
Consequences: reason codes are load-bearing and must be tested.

## D10 — Grade capped at 3 when a whole scoring category is missing
Reason: a score built on partial data should not be able to show "Very strong".
Alternatives: no cap; refuse to score.
Consequences: cap value is config; stated in the explain output.
