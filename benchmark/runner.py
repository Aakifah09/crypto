"""Trial runner (Task 2), memory + throughput measurement (Task 3) and CSV logging (Task 4).

Run inside the container, one resource profile per container:

    python -m benchmark.runner --profile C1 [--out results] [--targets ML-KEM-512,ECDSA-P256-SHA256]

Design (report Sec. 4.4):
  * Every warm-up, latency trial and throughput batch runs in its OWN fresh Python process
    (step 7). The worker builds fresh keys / inputs, performs untimed setup, makes
    `--prime-calls` untimed calls (absorbs lazy library initialisation, e.g. liboqs context
    creation), then times exactly one operation (or one 100-operation batch).
  * Correctness checks and size measurements happen after the timer stops.
  * Order is randomised (seeded): all warm-ups first, then all trials shuffled across
    algorithms and operations, then all batches shuffled.
  * A failed trial is never dropped. Exceptions, wrong results, timeouts (120 s), OOM kills
    and crashes are logged as rows with success=0 and an error_type.

Outputs (appended, one row each):
    results/trials.csv       one row per recorded latency trial
    results/throughput.csv   one row per recorded 100-operation batch
    results/run_meta_<run_id>_<profile>.json   configuration, environment, observed limits
Exit status: 0 done, 3 container limits do not match --profile, 4 correctness gate not passed.
"""
from __future__ import annotations

import argparse
import csv
import gc
import importlib
import json
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .measure import Cgroup, peak_rss_kb, rss_kb, timed_batch, timed_call, timer_info

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULT_MARK, PROGRESS_MARK = "@@RESULT@@", "@@PROGRESS@@"
BATCH_CHUNKS = 10
EXIT_OK, EXIT_PROFILE, EXIT_CORRECTNESS = 0, 3, 4


# ---------------------------------------------------------------------------
# Resource profiles (report Sec. 4.3). Single source of truth for the Docker flags.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Profile:
    name: str
    cpus: float | None
    memory_mib: int | None

    def docker_flags(self) -> list[str]:
        if self.cpus is None:
            return []
        return [f"--cpus={self.cpus:g}", f"--memory={self.memory_mib}m", f"--memory-swap={self.memory_mib}m"]

    def expected_limits(self) -> dict[str, str]:
        if self.cpus is None:
            return {"cpu_max": "max 100000", "memory_max": "max"}
        return {"cpu_max": f"{round(self.cpus * 100000)} 100000",
                "memory_max": str(self.memory_mib * 1024 * 1024),
                "memory_swap_max": "0"}          # --memory-swap == --memory means no swap


PROFILES = {p.name: p for p in (Profile("C0", None, None), Profile("C1", 1, 512),
                                Profile("C2", 0.5, 256), Profile("C3", 0.25, 128))}


def verify_profile(cg: Cgroup, profile: Profile) -> tuple[dict, bool, list[str]]:
    """Compare the limits the container really has with what the profile label promises."""
    seen = cg.limits()
    problems, verified = [], True
    for key, want in profile.expected_limits().items():
        got = seen.get(key)
        if got is None:
            verified = False
        elif got != want:
            problems.append(f"{key}: profile {profile.name} expects {want!r}, container has {got!r}")
    return seen, verified, problems


# ---------------------------------------------------------------------------
# Targets and operations. The runner only needs the uniform interface from algorithms.py
#   keygen / encaps / decaps / sign / verify / encrypt / decrypt / load_secret_key
# or, for tests, a plain zero-argument function ("fn:module:attr").
# ---------------------------------------------------------------------------
@dataclass
class Operation:
    setup: Callable[[Any], Any]                       # untimed: build keys / inputs, returns state
    run: Callable[[Any, Any], Any]                    # the ONLY thing that is timed: run(subject, state)
    check: Callable[[Any, Any, Any], bool] | None = None                 # untimed: check(subject, state, result)
    sizes: Callable[[Any, Any, Any], dict[str, int]] | None = None       # untimed: byte sizes of outputs


@dataclass
class Target:
    spec: str
    name: str
    kind: str
    family: str
    subject: Any
    operations: dict[str, Operation]


def _keys(alg):
    pk, sk = alg.keygen()
    return pk, sk, alg.load_secret_key(sk)            # load_secret_key is setup, never timed


def algorithm_operations(alg) -> dict[str, Operation]:
    from . import workloads
    ops = {"keygen": Operation(
        lambda a: None, lambda a, s: a.keygen(),
        sizes=lambda a, s, r: {"public_key_bytes": len(a.encode_public_key(r[0])),
                               "secret_key_bytes": len(a.encode_secret_key(r[1]))})}
    if alg.kind == "kem":
        def s_dec(a):
            pk, _, skh = _keys(a)
            ct, ss = a.encaps(pk)
            return {"skh": skh, "ct": ct, "ss": ss}
        ops["encaps"] = Operation(
            lambda a: {"pk": a.keygen()[0]}, lambda a, s: a.encaps(s["pk"]),
            sizes=lambda a, s, r: {"ciphertext_bytes": len(r[0]), "shared_secret_bytes": len(r[1])})
        ops["decaps"] = Operation(
            s_dec, lambda a, s: a.decaps(s["skh"], s["ct"]),
            check=lambda a, s, r: r == s["ss"],        # shared secrets match, outside timing
            sizes=lambda a, s, r: {"shared_secret_bytes": len(r)})
    elif alg.kind == "signature":
        msg = workloads.SIGNATURE_MESSAGE

        def s_sign(a):
            pk, _, skh = _keys(a)
            return {"pk": pk, "skh": skh}

        def s_verify(a):
            st = s_sign(a)
            st["sig"] = a.sign(st["skh"], msg)
            return st
        ops["sign"] = Operation(
            s_sign, lambda a, s: a.sign(s["skh"], msg),
            check=lambda a, s, r: a.verify(s["pk"], msg, r) is True,
            sizes=lambda a, s, r: {"signature_bytes": len(r)})
        ops["verify"] = Operation(
            s_verify, lambda a, s: a.verify(s["pk"], msg, s["sig"]),
            check=lambda a, s, r: r is True,
            sizes=lambda a, s, r: {"signature_bytes": len(s["sig"])})
    elif alg.kind == "pke":
        pt = workloads.RSA_PAYLOAD

        def s_enc(a):
            pk, _, skh = _keys(a)
            return {"pk": pk, "skh": skh}

        def s_dec(a):
            st = s_enc(a)
            st["ct"] = a.encrypt(st["pk"], pt)
            return st
        ops["encrypt"] = Operation(
            s_enc, lambda a, s: a.encrypt(s["pk"], pt),
            check=lambda a, s, r: a.decrypt(s["skh"], r) == pt,
            sizes=lambda a, s, r: {"ciphertext_bytes": len(r)})
        ops["decrypt"] = Operation(
            s_dec, lambda a, s: a.decrypt(s["skh"], s["ct"]),
            check=lambda a, s, r: r == pt,
            sizes=lambda a, s, r: {"plaintext_bytes": len(r)})
    else:
        raise ValueError(f"unknown algorithm kind {alg.kind!r}")
    return ops


def resolve_target(spec: str) -> Target:
    """'alg:ML-KEM-512' (or just 'ML-KEM-512') or 'fn:package.module:function'."""
    scheme, _, rest = spec.partition(":")
    if scheme == "fn":
        module, _, attr = rest.partition(":")
        fn = getattr(importlib.import_module(module), attr)
        return Target(spec, attr, "function", "test", fn,
                      {"call": Operation(lambda f: None, lambda f, s: f())})
    from .algorithms import get_algorithm
    alg = get_algorithm(rest if scheme == "alg" else spec)
    return Target(f"alg:{alg.name}", alg.name, alg.kind, alg.info.family, alg, algorithm_operations(alg))


# ---------------------------------------------------------------------------
# Worker process: one fresh process per warm-up / trial / batch
# ---------------------------------------------------------------------------
def worker_main() -> int:
    req = json.load(sys.stdin)
    out: dict[str, Any] = {"ok": False, "error_type": None, "error_message": None}
    stage = "import"
    try:
        gc.collect()
        target = resolve_target(req["target"])
        op, subject = target.operations[req["operation"]], target.subject
        out["baseline_rss_kb"] = rss_kb()            # interpreter + imports, before any benchmark work
        stage = "setup"
        state = op.setup(subject)
        stage = "prime"
        for _ in range(req["prime_calls"]):
            op.run(subject, state)
        stage = "timed"
        if req["mode"] == "latency":
            out["latency_ms"], result = timed_call(op.run, subject, state)
        else:
            br = timed_batch(op.run, subject, state, n=req["batch_size"], chunks=BATCH_CHUNKS,
                             on_progress=lambda d: print(f"{PROGRESS_MARK}{d}", flush=True))
            out["ops_completed"], out["duration_ms"], result = br.completed, br.duration_ms, br.last_result
            if br.error is not None:
                raise br.error
        stage = "check"
        if op.check is not None and not op.check(subject, state, result):
            out.update(error_type="IncorrectResult", error_message="correctness check failed after timing")
        else:
            out["ok"] = True
            if op.sizes is not None:
                out["sizes"] = op.sizes(subject, state, result)
    except (Exception, SystemExit) as exc:      # liboqs-python can raise SystemExit
        out.update(ok=False, error_type=type(exc).__name__, error_message=f"[{stage}] {exc}"[:300])
    finally:
        out["peak_rss_kb"] = peak_rss_kb()
        print(RESULT_MARK + json.dumps(out), flush=True)
    return 0


def run_worker(req: dict[str, Any], timeout_s: float, cg: Cgroup) -> dict[str, Any]:
    """Run one worker, enforce the timeout, and classify however it ended."""
    start = cg.begin()
    t0 = time.perf_counter()
    proc = subprocess.Popen([sys.executable, "-m", "benchmark.runner", "--worker"], cwd=REPO_ROOT,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    timed_out = False
    try:
        stdout, stderr = proc.communicate(json.dumps(req), timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        timed_out = True
    res: dict[str, Any] = {"worker_wall_ms": (time.perf_counter() - t0) * 1000.0,
                           "exit_code": proc.returncode, **cg.end(start)}
    payload, progress = None, 0
    for line in (stdout or "").splitlines():      # liboqs may print other lines; only trust our markers
        try:
            if line.startswith(RESULT_MARK):
                payload = json.loads(line[len(RESULT_MARK):])
            elif line.startswith(PROGRESS_MARK):
                progress = int(line[len(PROGRESS_MARK):])
        except ValueError:
            pass
    if payload is not None and not timed_out:
        res.update(payload)
        return res
    res["ok"] = False
    if timed_out:
        res.update(error_type="Timeout", error_message=f"no result after {timeout_s:g} s")
    elif proc.returncode == -9 and (res.get("oom_kills") or 0) > 0:
        res.update(error_type="OOMKilled", error_message="worker killed by the cgroup OOM killer")
    elif proc.returncode < 0:
        res.update(error_type=f"Killed(signal {-proc.returncode})", error_message="worker killed")
    else:
        tail = (stderr or "").strip().splitlines()[-1:] or [""]
        res.update(error_type="WorkerCrash", error_message=f"exit {proc.returncode}: {tail[0]}"[:300])
    if req["mode"] == "batch":
        res["ops_completed"] = progress               # last progress report before the worker died
    return res


# ---------------------------------------------------------------------------
# CSV logging (Task 4)
# ---------------------------------------------------------------------------
SIZE_COLS = ["public_key_bytes", "secret_key_bytes", "ciphertext_bytes", "shared_secret_bytes",
             "signature_bytes", "plaintext_bytes"]
COMMON_COLS = ["run_id", "timestamp_utc", "profile", "algorithm", "kind", "family", "operation"]
RESOURCE_COLS = ["worker_baseline_rss_kb", "worker_peak_rss_kb", "container_mem_peak_kb",
                 "container_peak_reset", "oom_kills", "throttled_periods", "throttled_ms",
                 "worker_wall_ms", "exit_code"]
TRIAL_COLS = (COMMON_COLS + ["trial", "order_index", "latency_ms", "success", "error_type", "error_message"]
              + SIZE_COLS + RESOURCE_COLS)
BATCH_COLS = (COMMON_COLS + ["batch", "order_index", "batch_size", "ops_completed", "duration_ms",
                             "throughput_ops_s", "success", "error_type", "error_message"] + RESOURCE_COLS)


class CsvLog:
    """Append-only CSV. Flushes every row so a killed run keeps everything logged so far."""

    def __init__(self, path: Path, columns: list[str]):
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists() or path.stat().st_size == 0
        if not new:
            with open(path, newline="") as f:
                if next(csv.reader(f), []) != columns:
                    raise SystemExit(f"{path} has a different header; refusing to append to it")
        self._f = open(path, "a", newline="")
        self._w = csv.DictWriter(self._f, fieldnames=columns, lineterminator="\n")
        if new:
            self._w.writeheader()
            self._f.flush()

    def write(self, row: dict[str, Any]) -> None:
        self._w.writerow({k: ("" if v is None else v) for k, v in row.items()})
        self._f.flush()

    def close(self) -> None:
        self._f.close()


def _base_row(run_id: str, profile: str, target: Target, op: str, order: int, res: dict) -> dict[str, Any]:
    err = (res.get("error_message") or "").replace("\n", " ")
    return {"run_id": run_id, "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "profile": profile, "algorithm": target.name, "kind": target.kind, "family": target.family,
            "operation": op, "order_index": order, "success": int(bool(res.get("ok"))),
            "error_type": res.get("error_type"), "error_message": err,
            "worker_baseline_rss_kb": res.get("baseline_rss_kb"), "worker_peak_rss_kb": res.get("peak_rss_kb"),
            **{k: res.get(k) for k in RESOURCE_COLS if k not in ("worker_baseline_rss_kb", "worker_peak_rss_kb")}}


def trial_row(run_id, profile, target, op, trial, order, res):
    row = _base_row(run_id, profile, target, op, order, res)
    row.update(trial=trial, latency_ms=res.get("latency_ms"), **(res.get("sizes") or {}))
    return row


def batch_row(run_id, profile, target, op, batch, order, batch_size, res):
    row = _base_row(run_id, profile, target, op, order, res)
    done, dur = res.get("ops_completed"), res.get("duration_ms")
    row.update(batch=batch, batch_size=batch_size, ops_completed=done, duration_ms=dur,
               throughput_ops_s=(done / (dur / 1000.0)) if done and dur else None)
    return row


# ---------------------------------------------------------------------------
# Orchestration inside one container
# ---------------------------------------------------------------------------
def correctness_gate(out_dir: Path, targets: list[Target]) -> str | None:
    """Module 1 rule: benchmark only algorithms that passed results/correctness.json."""
    names = [t.name for t in targets if t.spec.startswith("alg:")]
    if not names:
        return None
    path = out_dir / "correctness.json"
    if not path.exists():
        return f"{path} not found. Run `python -m benchmark.correctness` first (or pass --skip-correctness-check)."
    algs = json.loads(path.read_text()).get("algorithms", {})
    bad = [f"{n}={algs.get(n, {}).get('status', 'MISSING')}" for n in names if algs.get(n, {}).get("status") != "PASS"]
    return f"correctness gate failed: {', '.join(bad)}" if bad else None


def write_meta(path: Path, meta: dict[str, Any]) -> None:
    path.write_text(json.dumps(meta, indent=2, default=str))


def run_profile(a: argparse.Namespace) -> int:
    profile, out = PROFILES[a.profile], Path(a.out)
    cg = Cgroup()
    seen, verified, problems = verify_profile(cg, profile)
    if problems:
        print("PROFILE MISMATCH:\n  " + "\n  ".join(problems), file=sys.stderr)
        if not a.allow_profile_mismatch:
            print("Refusing to label this run as " + profile.name + ". Start the container with: "
                  + " ".join(profile.docker_flags() or ["(no limit flags)"]), file=sys.stderr)
            return EXIT_PROFILE
    elif not verified:
        print("WARNING: container limits could not be read; profile is UNVERIFIED", file=sys.stderr)

    specs = [s for s in a.targets.split(",") if s] if a.targets else None
    if specs is None:
        from .algorithms import get_algorithms
        specs = [f"alg:{x.name}" for x in get_algorithms()]
    targets = [resolve_target(s) for s in specs]
    if not a.skip_correctness_check:
        msg = correctness_gate(out, targets)
        if msg:
            print(msg, file=sys.stderr)
            return EXIT_CORRECTNESS
    wanted = set(a.operations.split(",")) if a.operations else None
    cells = [(t, op) for t in targets for op in t.operations if wanted is None or op in wanted]

    rng = random.Random(a.seed)
    cg_note = {"memory_peak_resettable": cg.peak_resettable, "limits_seen": seen, "limits_verified": verified}
    meta: dict[str, Any] = {"run_id": a.run_id, "profile": a.profile, "docker_flags": profile.docker_flags(),
                            "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                            "config": {k: v for k, v in vars(a).items() if k != "worker"},
                            "cells": [f"{t.name}/{op}" for t, op in cells], "timer": timer_info(), **cg_note}
    try:
        from .environment import environment_info
        meta["environment"] = environment_info()
    except Exception as exc:                          # metadata must never block a run
        meta["environment_error"] = f"{type(exc).__name__}: {exc}"
    meta_path = out / f"run_meta_{a.run_id}_{a.profile}.json"
    out.mkdir(parents=True, exist_ok=True)
    write_meta(meta_path, meta)

    def req(t, op, mode):
        return {"target": t.spec, "operation": op, "mode": mode, "prime_calls": a.prime_calls,
                "batch_size": a.batch_size}

    plan: list[tuple[str, Target, str, int]] = [("warmup", t, op, i + 1) for t, op in cells for i in range(a.warmups)]
    rng.shuffle(plan)
    warm_fail = 0
    for n, (_, t, op, _i) in enumerate(plan, 1):
        r = run_worker(req(t, op, "latency"), a.timeout, cg)
        warm_fail += not r.get("ok")
        if n % 25 == 0 or n == len(plan):
            print(f"[{a.profile}] warm-ups {n}/{len(plan)} (failed: {warm_fail})", flush=True)

    trials = [(t, op, i + 1) for t, op in cells for i in range(a.trials)]
    batches = [(t, op, i + 1) for t, op in cells for i in range(a.batches)]
    rng.shuffle(trials)
    rng.shuffle(batches)
    order, failed = 0, 0
    trial_log, batch_log = CsvLog(out / "trials.csv", TRIAL_COLS), CsvLog(out / "throughput.csv", BATCH_COLS)
    try:
        for n, (t, op, trial) in enumerate(trials, 1):
            order += 1
            r = run_worker(req(t, op, "latency"), a.timeout, cg)
            failed += not r.get("ok")
            trial_log.write(trial_row(a.run_id, a.profile, t, op, trial, order, r))
            if n % 25 == 0 or n == len(trials):
                print(f"[{a.profile}] trials {n}/{len(trials)} (failed so far: {failed})", flush=True)
        if not a.no_throughput:
            for n, (t, op, b) in enumerate(batches, 1):
                order += 1
                r = run_worker(req(t, op, "batch"), a.batch_timeout, cg)
                batch_log.write(batch_row(a.run_id, a.profile, t, op, b, order, a.batch_size, r))
                if n % 10 == 0 or n == len(batches):
                    print(f"[{a.profile}] batches {n}/{len(batches)}", flush=True)
    finally:
        trial_log.close()
        batch_log.close()
    meta.update(finished_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                warmup_failures=warm_fail, trial_failures=failed, trials_recorded=len(trials))
    write_meta(meta_path, meta)
    print(f"[{a.profile}] done: {len(trials)} trials ({failed} failed). Data in {out.resolve()}")
    return EXIT_OK


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--profile", choices=sorted(PROFILES), help="resource profile this container was started with")
    p.add_argument("--out", default="results")
    p.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--targets", help="comma list: algorithm names and/or fn:module:function (default: all available)")
    p.add_argument("--operations", help="comma list to restrict operations, e.g. keygen,sign")
    p.add_argument("--warmups", type=int, default=5)
    p.add_argument("--trials", type=int, default=30)
    p.add_argument("--batches", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=100)
    p.add_argument("--timeout", type=float, default=120, help="seconds per trial before it counts as a failure")
    p.add_argument("--batch-timeout", type=float, default=120, help="seconds per throughput batch")
    p.add_argument("--prime-calls", type=int, default=1, help="untimed calls inside each worker before timing")
    p.add_argument("--seed", type=int, default=1, help="seed for the randomised run order")
    p.add_argument("--no-throughput", action="store_true")
    p.add_argument("--skip-correctness-check", action="store_true")
    p.add_argument("--allow-profile-mismatch", action="store_true")
    a = p.parse_args(argv)
    if not a.worker and not a.profile:
        p.error("--profile is required")
    return a


def main(argv: list[str] | None = None) -> int:
    a = parse_args(argv)
    return worker_main() if a.worker else run_profile(a)


if __name__ == "__main__":
    sys.exit(main())