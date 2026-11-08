"""Self-test of the Module 2 framework (task 7 definition of done).

Runs the real runner on test functions and on Aakifah's classical algorithms, then checks the
raw CSV format, that failures are recorded instead of dropped, and that the summary statistics
can be reproduced independently from the raw rows.

Run inside the container (or locally, from the repo root):
    docker run --rm pqc-benchmark python -m tests.test_measurement
"""
from __future__ import annotations

import csv
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from analysis import summarize
from benchmark import measure, runner

ROOT = Path(__file__).resolve().parents[1]
failures = 0


def check(ok: bool, text: str) -> None:
    global failures
    failures += not ok
    print(f"[{'OK' if ok else 'FAIL'}] {text}")


def run_runner(out: Path, profile: str, targets: str, env: dict | None = None, **opts) -> int:
    args = {"warmups": 1, "trials": 6, "batches": 2, "batch-size": 20, "settle-ms": 0, **opts}
    cmd = [sys.executable, "-m", "benchmark.runner", "--profile", profile, "--out", str(out),
           "--targets", targets, "--skip-correctness-check", "--allow-profile-mismatch"]
    for k, v in args.items():
        cmd += [f"--{k}", str(v)]
    return subprocess.run(cmd, cwd=ROOT, env={**os.environ, **(env or {})}, capture_output=True).returncode


def rows(path: Path) -> list[dict]:
    return list(csv.DictReader(open(path, newline="")))


def main() -> int:
    print("Timing utility\n")
    ms, _ = measure.timed_call(time.sleep, 0.02)
    check(19.0 <= ms < 100.0, f"timed_call(sleep 20 ms) -> {ms:.2f} ms, in milliseconds")
    n = [0]

    def flaky():
        n[0] += 1
        if n[0] == 37:
            raise ValueError("boom")
    b = measure.timed_batch(flaky, n=100)
    check(b.completed == 36 and isinstance(b.error, ValueError), "failing batch reports 36 completed + the error")
    b = measure.timed_batch(lambda: None, n=100)
    check(b.completed == 100 and b.ops_per_s and b.ops_per_s > 0, "clean batch completes 100 operations")

    marks = []
    t0 = time.perf_counter()
    b = measure.timed_batch(lambda: None, n=100, on_progress=lambda d: (marks.append(d), time.sleep(0.005)))
    check(marks == list(range(10, 101, 10)) and b.duration_ms >= 45.0,
          f"batch duration is wall-clock incl. gaps between blocks ({b.duration_ms:.0f} ms, progress {marks[0]}..{marks[-1]})")

    print("\ncgroup reader and profile check\n")
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        (d / "cpu.max").write_text("25000 100000\n")
        (d / "memory.max").write_text("134217728\n")
        (d / "memory.swap.max").write_text("0\n")
        (d / "memory.events").write_text("low 0\nhigh 0\nmax 3\noom 1\noom_kill 1\n")
        (d / "cpu.stat").write_text("usage_usec 5\nnr_periods 10\nnr_throttled 4\nthrottled_usec 9000\n")
        (d / "memory.current").write_text("52428800\n")
        (d / "memory.stat").write_text("anon 31457280\nfile 20971520\n")
        cg = measure.Cgroup(d, reset_peak=False)
        smp = cg.sample()
        check(smp == {"mem_kb": 51200, "anon_kb": 30720, "throttled": 4, "throttled_usec": 9000},
              "sample() reads memory.current, anon memory and throttle counters")
        check(cg._kv("memory.events")["oom_kill"] == 1 and cg._kv("cpu.stat")["nr_throttled"] == 4, "parses events and cpu.stat")
        _, verified, problems = runner.verify_profile(cg, runner.PROFILES["C3"])
        check(verified and not problems, "C3 limits accepted when container really has 0.25 CPU / 128 MiB / no swap")
        _, _, problems = runner.verify_profile(cg, runner.PROFILES["C1"])
        check(len(problems) >= 2, "mislabelled run (C1 on a C3 container) is detected")
    check(runner.PROFILES["C2"].docker_flags() == ["--cpus=0.5", "--memory=256m", "--memory-swap=256m"], "C2 docker flags")

    print("\nEnd to end on test functions\n")
    with tempfile.TemporaryDirectory() as t:
        out = Path(t)
        check(run_runner(out, "C0", "fn:tests.fixtures:ok_fn") == 0, "runner finishes")
        tr = rows(out / "trials.csv")
        check(list(tr[0].keys()) == runner.TRIAL_COLS, "trials.csv has the documented columns")
        check(len(tr) == 6 and all(r["success"] == "1" and r["latency_ms"] for r in tr), "6 recorded trials, all with latency")
        check(sorted(int(r["trial"]) for r in tr) == [1, 2, 3, 4, 5, 6], "trial numbers 1..6 (warm-up excluded)")
        th = rows(out / "throughput.csv")
        check(len(th) == 2 and all(r["ops_completed"] == "20" and float(r["throughput_ops_s"]) > 0 for r in th), "2 throughput batches of 20")

    with tempfile.TemporaryDirectory() as t:
        out = Path(t)
        run_runner(out, "C3", "fn:tests.fixtures:raises_fn,fn:tests.fixtures:sleeps_fn", timeout=1,
                   **{"trials": 2, "batches": 1, "warmups": 0, "batch-timeout": 1})
        tr = rows(out / "trials.csv")
        by_err = {r["algorithm"]: r["error_type"] for r in tr}
        check(len(tr) == 4 and all(r["success"] == "0" for r in tr), "failed trials are recorded, not dropped (4 rows)")
        check(by_err == {"raises_fn": "RuntimeError", "sleeps_fn": "Timeout"}, f"error types recorded: {by_err}")
        check(all(r["latency_ms"] == "" for r in tr), "failed trials carry no latency value")
        s = summarize.load_summaries(out / "trials.csv", out / "throughput.csv")
        check(all(c["trial_failure_rate"] == 1.0 for c in s["completion"]), "summary shows 100 % failure rate")
        check(all(r["n_batches_success"] == 0 and "median_ops_s" not in r for r in s["throughput"]),
              "cells with no successful run get no latency/throughput statistics, only failure counts")
        timeout_cell = [r for r in s["throughput"] if r["algorithm"] == "sleeps_fn"][0]
        check(timeout_cell["op_completion_rate"] == 0, "timed-out batch counted as 0 completed operations")

    with tempfile.TemporaryDirectory() as t:
        out = Path(t)
        run_runner(out, "C0", "fn:tests.fixtures:slowish_fn", trials=0, warmups=0, batches=1,
                   **{"batch-size": 20, "batch-timeout": 3})
        th = rows(out / "throughput.csv")
        done = int(th[0]["ops_completed"]) if th else -1
        check(len(th) == 1 and th[0]["error_type"] == "Timeout" and 0 < done < 20 and done % 2 == 0,
              f"batch killed by the timeout keeps its partial progress ({done} of 20 operations)")

    with tempfile.TemporaryDirectory() as t:
        out = Path(t)
        run_runner(out, "C0", "fn:tests.fixtures:ok_fn", trials=2, warmups=0, batches=1, **{"settle-ms": 300})
        walls = [float(r["worker_wall_ms"]) for r in rows(out / "trials.csv") + rows(out / "throughput.csv")]
        check(len(walls) == 3 and all(w >= 300 for w in walls), "--settle-ms 300 makes every worker idle 300 ms before timing")
    ms, _ = measure.timed_call(lambda: None, _collect=False)
    check(ms >= 0 and measure.timed_batch(lambda: None, n=10, collect=False).completed == 10,
          "timing helpers can skip the pre-timer garbage collection")

    print("\nIn-worker cgroup sampling (fake cgroup directory)\n")
    with tempfile.TemporaryDirectory() as t, tempfile.TemporaryDirectory() as fake:
        f = Path(fake)
        (f / "memory.current").write_text("52428800\n")
        (f / "memory.stat").write_text("anon 31457280\nfile 20971520\n")
        (f / "cpu.stat").write_text("nr_periods 10\nnr_throttled 4\nthrottled_usec 9000\n")
        run_runner(Path(t), "C0", "fn:tests.fixtures:ok_fn", {"CGROUP_ROOT": str(f)}, trials=2, batches=1)
        r0 = rows(Path(t) / "trials.csv")[0]
        check(r0["container_anon_kb"] == "30720" and r0["container_mem_kb"] == "51200",
              "worker records container anonymous memory and memory.current around the timed call")
        check(r0["timed_throttled_periods"] == "0", "no throttling counted when the counter did not move")

    print("\nSummary statistics reproduce from raw data\n")
    with tempfile.TemporaryDirectory() as t:
        out = Path(t)
        for prof, slow in (("C0", "1"), ("C1", "2")):
            run_runner(out, prof, "fn:tests.fixtures:synthetic_fn", {"SYNTH_SLOWDOWN": slow}, trials=30, **{"run-id": f"t-{prof}"})
        raw = summarize.read_rows(out / "trials.csv")
        s = summarize.load_summaries(out / "trials.csv", out / "throughput.csv")
        lat = {r["profile"]: r for r in s["latency"]}
        c0 = [r["latency_ms"] for r in raw if r["profile"] == "C0" and r["success"] == 1]
        q = statistics.quantiles(c0, n=4, method="inclusive")
        check(len(c0) == 30 and lat["C0"]["median_ms"] == statistics.median(c0), "median equals an independent computation")
        check(abs(lat["C0"]["iqr_ms"] - (q[2] - q[0])) < 1e-9, "IQR equals Q3 - Q1 (inclusive quartiles)")
        check(1.7 < lat["C1"]["slowdown_vs_c0"] < 2.3, f"injected x2 slowdown recovered: x{lat['C1']['slowdown_vs_c0']:.2f}")
        check(lat["C1"]["slowdown_ci_low"] < lat["C1"]["slowdown_vs_c0"] < lat["C1"]["slowdown_ci_high"], "bootstrap interval brackets the estimate")
        again = summarize.summarize_latency(raw)
        check(again == summarize.summarize_latency(raw), "summary is deterministic (seeded bootstrap)")

    print("\nKEM operation wiring (stand-in KEM; liboqs is only available in the container)\n")
    import hashlib

    class FakeKEM:
        name, kind = "FakeKEM", "kem"
        keygen = staticmethod(lambda: ((k := os.urandom(32)), k))
        load_secret_key = staticmethod(lambda sk: sk)
        encode_public_key = encode_secret_key = staticmethod(lambda k: k)

        def encaps(self, pk):
            ct = os.urandom(48)
            return ct, hashlib.sha256(pk + ct).digest()

        def decaps(self, skh, ct):
            return hashlib.sha256(skh + ct).digest()
    ops = runner.algorithm_operations(FakeKEM())
    check(sorted(ops) == ["decaps", "encaps", "keygen"], "KEM exposes keygen / encaps / decaps")
    got = {}
    for name, op in ops.items():
        st = op.setup(FakeKEM())
        _, res = measure.timed_call(op.run, FakeKEM(), st)
        got[name] = (op.check is None or op.check(FakeKEM(), st, res), op.sizes(FakeKEM(), st, res))
    check(all(v[0] for v in got.values()), "decaps check (secrets match) passes outside the timer")
    check(got["encaps"][1] == {"ciphertext_bytes": 48, "shared_secret_bytes": 32}, "encaps output sizes recorded")
    st = ops["decaps"].setup(FakeKEM())
    st["ss"] = b"wrong"
    check(not ops["decaps"].check(FakeKEM(), st, ops["decaps"].run(FakeKEM(), st)), "wrong shared secret is flagged as IncorrectResult")

    print("\nReal algorithms (classical, from Module 1)\n")
    with tempfile.TemporaryDirectory() as t:
        out = Path(t)
        rc = run_runner(out, "C0", "ECDSA-P256-SHA256,RSA-2048-OAEP-SHA256", trials=3, batches=1, **{"batch-size": 10})
        tr = rows(out / "trials.csv")
        check(rc == 0 and len(tr) == 18 and all(r["success"] == "1" for r in tr), "ECDSA + RSA: 6 operations x 3 trials all succeed")
        sizes = {(r["algorithm"], r["operation"]): r for r in tr}
        check(sizes[("ECDSA-P256-SHA256", "keygen")]["public_key_bytes"] == "91", "ECDSA public key 91 bytes in CSV")
        check(sizes[("RSA-2048-OAEP-SHA256", "encrypt")]["ciphertext_bytes"] == "256", "RSA ciphertext 256 bytes in CSV")
        check(all(r["worker_peak_rss_kb"] and r["worker_baseline_rss_kb"] for r in tr), "worker RSS recorded for every trial")

    print(f"\n{'SELF-TEST PASSED' if failures == 0 else f'SELF-TEST FAILED ({failures})'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
