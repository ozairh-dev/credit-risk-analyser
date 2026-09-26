"""A4 — consistency: the deterministic engine must reproduce identical output.

**What is asserted.** For the same payload, `pipeline.analyse()` returns
bit-identical output across repeated calls within a process, across a fresh
process, and regardless of the order companies are analysed in. Every stage is
covered — selection, mapping, composites, integrity, metrics, trends, scores and
stress — by hashing a canonical serialisation of all eight rather than spot-
checking a grade.

**Why it is worth asserting rather than assuming.** "It is deterministic because
there is no LLM in it" is the kind of claim this project has been wrong about
before (D67 — a path declared unwitnessable that fired on real data). Python
gives several ways to be accidentally non-deterministic without any randomness:
iteration over a set, `dict` ordering that depends on insertion sequence,
floating-point accumulation whose order varies, and anything reading the clock.
`normalise/selection.py`, `metrics/ratios.py` and `trends/engine.py` all iterate
collections built from set comprehensions, so the property is reachable-by-
accident rather than guaranteed by construction. Hash randomisation is tested
under four explicit `PYTHONHASHSEED` values rather than whatever one subprocess
happened to draw.

**What it does NOT assert.** That the numbers are right — only that they do not
move. A consistently wrong engine passes this perfectly. That is A1's job.

The LLM half of A4 (variance over five runs on one pack) is not built: there is
no LLM judgment layer yet, so there is nothing to run five times.

This lives in `benchmark/harness/` rather than `tests/` so that `tests/` stays
byte-identical through the benchmark freeze.
"""

import hashlib
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from assess import load_payload                               # noqa: E402

from credit_risk import pipeline                               # noqa: E402

REPEATS = 3

# A deliberately mixed sample: fixtures that exercise refusal paths, adopted
# companies that score cleanly, and failure-cohort filers whose data is thin.
SAMPLE = [
    ("CCL", 815097, "data/raw"),          # all three total_debt branches
    ("LUMN", 18926, "data/raw"),          # lease-inclusive + phantom period
    ("F", 37996, "data/raw"),             # refuses to compute (D25)
    ("AZO", 866787, "data/raw"),          # scores on all five categories
    ("CAG", 23217, "data/raw"),           # integrity FAIL periods (D69/D76)
    ("JCP", 1166126, "data/benchmark/raw"),
    ("HTZ", 1657853, "data/benchmark/raw"),   # NO_DEBT_DATA throughout
]


def canonical(analysis) -> str:
    """A stable text rendering of all eight stages.

    `default=str` renders dataclasses via repr, which includes every field, so a
    changed reason code or a moved float shows up. `sort_keys` removes any
    dependence on dict insertion order in the serialiser itself — the point is to
    detect non-determinism in the ENGINE, not in json.
    """
    (selection, mapping, composites, integrity, metrics, trends, scores,
     stress) = analysis
    blocks = {
        "selection_selected": [repr(f) for f in selection.selected],
        "selection_unavailable": [repr(u) for u in selection.unavailable],
        "mapping_concepts": [repr(c) for c in mapping.concepts],
        "mapping_unavailable": [repr(u) for u in mapping.unavailable],
        "composites": [repr(c) for c in composites],
        "integrity": [repr(r) for r in integrity.results],
        "metrics": [repr(m) for m in metrics.metrics],
        "trends": [repr(t) for t in trends.trends],
        "warnings": [repr(w) for w in trends.warnings],
        "scores": [repr(s) for s in scores],
        "stress": [repr(r) for r in stress],
    }
    return json.dumps(blocks, sort_keys=True, default=str)


def digest(analysis) -> str:
    return hashlib.sha256(canonical(analysis).encode()).hexdigest()


def child_digests(sample, seed: str | None = None) -> dict:
    """Digests computed in a FRESH interpreter.

    A separate process is the only way to catch state that survives within one —
    `functools.lru_cache` on the config loaders, and any module-level mutable
    default — and to catch dependence on PYTHONHASHSEED, which randomises str
    hashing per process and is the classic source of set-iteration drift.
    """
    code = (
        "import sys, json; sys.path.insert(0, 'benchmark/harness');"
        "from run_a4 import digest, SAMPLE;"
        "from assess import load_payload;"
        "from credit_risk import pipeline;"
        "print(json.dumps({t: digest(pipeline.analyse("
        "load_payload(f'{d}/CIK{c:010d}.json'))) for t, c, d in SAMPLE}))"
    )
    import os
    env = dict(os.environ)
    if seed is not None:
        env["PYTHONHASHSEED"] = seed
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, check=True, cwd=".", env=env)
    return json.loads(out.stdout.strip().splitlines()[-1])


def main() -> int:
    payloads = {t: load_payload(f"{d}/CIK{c:010d}.json") for t, c, d in SAMPLE}

    failures = []
    print(f"A4 — determinism over {len(SAMPLE)} companies, "
          f"{REPEATS} in-process repeats\n")
    print(f"{'company':9} {'digest (first 16)':20} {'repeats':>8}  verdict")
    print("-" * 62)
    in_process = {}
    for tick, _cik, _d in SAMPLE:
        digests = [digest(pipeline.analyse(payloads[tick]))
                   for _ in range(REPEATS)]
        same = len(set(digests)) == 1
        in_process[tick] = digests[0]
        if not same:
            failures.append(f"{tick}: {len(set(digests))} distinct digests "
                            f"across {REPEATS} in-process runs")
        print(f"{tick:9} {digests[0][:16]:20} {REPEATS:>8}  "
              f"{'identical' if same else 'DIFFER'}")

    # 2. reverse order — catches any cross-company state leaking through a
    # module-level cache
    print("\nreversed analysis order:", end=" ")
    reversed_ok = all(
        digest(pipeline.analyse(payloads[t])) == in_process[t]
        for t, _c, _d in reversed(SAMPLE))
    print("identical" if reversed_ok else "DIFFER")
    if not reversed_ok:
        failures.append("digests depend on the order companies are analysed in")

    # 3. fresh process, under four explicit hash seeds.
    # PYTHONHASHSEED randomises str hashing per process, which is the classic
    # route to set-iteration drift. Relying on one subprocess would sample one
    # seed and call it proof; four fixed seeds test the property deliberately.
    seed_results = {}
    for seed in ("0", "1", "12345", "99999"):
        print(f"fresh interpreter, PYTHONHASHSEED={seed:<6}", end=" ")
        child = child_digests(SAMPLE, seed=seed)
        ok = child == in_process
        seed_results[seed] = ok
        print("identical" if ok else "DIFFER")
        if not ok:
            differing = [t for t in in_process if child.get(t) != in_process[t]]
            failures.append(f"digests differ at PYTHONHASHSEED={seed}: "
                            f"{differing}")
    fresh_ok = all(seed_results.values())

    print()
    if failures:
        print("A4 FAILED — the engine is not deterministic:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"A4 PASSED — {len(SAMPLE)} companies × {REPEATS} repeats, plus "
          f"reversed order and four hash seeds in fresh interpreters, all "
          f"bit-identical across all eleven output blocks.")
    print("\nThis asserts only that the output does not MOVE. A consistently "
          "wrong engine passes it perfectly.")
    out = pathlib.Path("benchmark/results/a4_determinism.json")
    out.write_text(json.dumps({
        "repeats": REPEATS,
        "companies": {t: in_process[t] for t, _c, _d in SAMPLE},
        "reversed_order_identical": reversed_ok,
        "fresh_process_identical": fresh_ok,
        "hash_seeds_tested": sorted(seed_results),
        "identical_under_every_hash_seed": fresh_ok,
        "blocks_hashed": 11,
        "asserts": "output does not move on identical input, not that it is correct",
        "llm_variance": "not measured — no LLM judgment layer exists to run five times",
    }, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
