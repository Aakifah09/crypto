"""Self-test of the measurement framework (Module 2 definition of done).

Runs the real runner on the toy algorithms in benchmark/demo.py, which deliberately raise,
crash and hang, then checks that:
    * setup time never leaks into the timed region
    * exactly the planned number of rows is written per group (nothing is dropped)
    * every failure type is recorded with its status and error type
    * summarize.py reproduces consistent rates, and plots.py writes every figure

Run (from the repository root; needs pandas, numpy and matplotlib):
    python -m tests.test_module2
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

import pandas as pd

from analysis import plots, summarize
from benchmark import measure, runner

TRIALS, BATCHES = 6, 2


def test_setup_is_not_timed() -> None:
    op = measure.Operation("probe", setup=lambda: time.sleep(0.2), run=lambda _s: None)
    out = measure.run_trial(op)
    assert out["status"] == "ok" and out["latency_ms"] < 50, out
    batch = measure.run_batch(op, 100)
    assert batch["status"] == "ok" and batch["elapsed_ms"] < 50, batch


def test_exceptions_become_results() -> None:
    def boom(_s):
        raise ValueError("nope")
    out = measure.run_trial(measure.Operation("boom", run=boom))
    assert out["status"] == "error" and out["error_type"] == "ValueError" and out["latency_ms"] is None
    wrong = measure.run_trial(measure.Operation("wrong", run=lambda _s: 1, validate=lambda s, r: False))
    assert wrong["status"] == "error" and wrong["error_type"] == "ValidationFailed"


def test_end_to_end() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        raw, summ, figs = Path(tmp, "raw"), Path(tmp, "summary"), Path(tmp, "figures")
        code = runner.main(["--demo", "--profile", "C0", "--trials", str(TRIALS), "--batches", str(BATCHES),
                            "--timeout", "1.5", "--batch-timeout", "1.5",
                            "--algorithms", "DEMO-KEM", "DEMO-FLAKY", "DEMO-CRASH", "DEMO-HANG",
                            "--ops", "keygen", "sign", "decaps", "--out", str(raw)])
        assert code == 0

        trials = pd.read_csv(raw / "raw_trials.csv")
        assert list(trials.columns) == runner.TRIAL_COLUMNS
        counts = trials.groupby(["algorithm", "operation"]).size()
        assert (counts == TRIALS).all(), f"a trial was dropped: {counts.to_dict()}"
        assert set(trials["status"]) <= {"ok", "error", "timeout", "killed", "skipped"}

        def statuses(alg: str, op: str) -> set:
            return set(trials[(trials.algorithm == alg) & (trials.operation == op)]["status"])
        assert statuses("DEMO-KEM", "decaps") == {"ok"}
        assert "error" in statuses("DEMO-FLAKY", "sign")
        assert "killed" in statuses("DEMO-CRASH", "sign")
        assert "timeout" in statuses("DEMO-HANG", "sign")
        ok = trials[trials["status"] == "ok"]
        assert (ok["latency_ms"] > 0).all() and ok["worker_rss_peak_mb"].notna().all()
        assert trials[trials["status"] != "ok"]["latency_ms"].isna().all()

        batches = pd.read_csv(raw / "raw_throughput.csv")
        assert (batches.groupby(["algorithm", "operation"]).size() == BATCHES).all()

        assert summarize.main(["--raw", str(raw), "--out", str(summ), "--planned-trials", str(TRIALS),
                               "--planned-batches", str(BATCHES)]) == 0
        lat = pd.read_csv(summ / "summary_latency.csv")
        assert ((lat["completion_rate"] + lat["failure_rate"]) - 1).abs().max() < 1e-9
        rate = lambda a, o: float(lat[(lat.algorithm == a) & (lat.operation == o)]["failure_rate"].iloc[0])
        assert rate("DEMO-KEM", "decaps") == 0 and rate("DEMO-CRASH", "sign") > 0 and rate("DEMO-HANG", "sign") > 0

        assert plots.main(["--summary", str(summ), "--out", str(figs)]) == 0
        for name in ("latency_vs_profile", "throughput", "memory", "failure_rate"):
            assert (figs / f"{name}.png").stat().st_size > 10_000, name


def main() -> int:
    failed = 0
    for fn in (test_setup_is_not_timed, test_exceptions_become_results, test_end_to_end):
        try:
            fn()
            print(f"[OK]     {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"[FAILED] {fn.__name__}: {exc}")
    print("\nMODULE 2 SELF-TEST PASSED" if not failed else f"\nMODULE 2 SELF-TEST FAILED ({failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
