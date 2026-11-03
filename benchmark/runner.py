"""Trial runner (Module 2, Tasks 2-4): measures every algorithm Module 1 provides.

Run inside the container, once per resource profile:

    docker run --rm --cpus 0.5 --memory 256m --memory-swap 256m \\
        -v "$(pwd)/results:/app/results" pqc-benchmark \\
        python -m benchmark.runner --profile C2

    python -m benchmark.runner --demo --profile C0        # toy algorithms, no liboqs needed

For every (algorithm, operation) the runner:
    1. starts a fresh WORKER process (setup, 5 warm-ups, then waits for commands);
    2. asks it for 30 recorded trials, one at a time, each with a hard timeout;
    3. asks it for 5 throughput batches of 100 operations (a second worker);
    4. appends every result to the CSV files immediately.

Failures are data, never dropped. Exactly `--trials` rows are written per group, each with
a status:
    ok        measured and validated
    error     the operation raised, returned a wrong result, or could not be set up
    timeout   no answer within --timeout seconds; worker killed
    killed    worker process died (status "OOMKilled" when the cgroup OOM counter moved)
    skipped   not attempted because --max-consecutive-failures crashes/timeouts happened in a row
A worker that was killed or timed out is replaced by a new one (with fresh warm-ups) for the
next trial, so one bad trial does not decide the fate of the other 29.

Outputs (in --out, default results/measurements):
    raw_trials.csv       one row per recorded trial
    raw_throughput.csv   one row per throughput batch
    run_meta.jsonl       one JSON line per invocation: profile, cgroup limits, versions, arguments
"""
from __future__ import annotations

import argparse
import csv
import importlib
import json
import multiprocessing as mp
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import measure, workloads
from .measure import Operation

SIZE_COLUMNS = ["public_key_bytes", "secret_key_bytes", "ciphertext_bytes",
                "shared_secret_bytes", "signature_bytes", "plaintext_bytes"]
TRIAL_COLUMNS = ["run_id", "timestamp_utc", "algorithm", "family", "operation", "profile", "trial",
                 "status", "error_type", "error_message", "latency_ms",
                 "worker_rss_before_mb", "worker_rss_peak_mb",
                 "container_mem_current_mb", "container_mem_peak_mb", "cpu_throttled_ms",
                 *SIZE_COLUMNS]
BATCH_COLUMNS = ["run_id", "timestamp_utc", "algorithm", "family", "operation", "profile", "batch",
                 "batch_size", "status", "error_type", "error_message", "elapsed_ms", "ops_per_sec",
                 "worker_rss_peak_mb", "container_mem_peak_mb", "cpu_throttled_ms"]


# ---------------------------------------------------------------------------
# Adapter: Module 1's algorithm interface -> Operations (the only crypto-aware code here)
# ---------------------------------------------------------------------------
def operations_for(alg) -> dict[str, Operation]:
    """Turn an algorithm object (keygen/encaps/... interface of benchmark/algorithms.py) into Operations."""
    def keygen_sizes(_state, res):
        pk, sk = res
        return {"public_key_bytes": len(alg.encode_public_key(pk)),
                "secret_key_bytes": len(alg.encode_secret_key(sk))}

    ops = {"keygen": Operation("keygen", run=lambda _s: alg.keygen(), sizes=keygen_sizes)}

    if alg.kind == "kem":
        def encaps_setup():
            return alg.keygen()[0]

        def decaps_setup():
            pk, sk = alg.keygen()
            ct, ss = alg.encaps(pk)
            return alg.load_secret_key(sk), ct, ss          # load_secret_key is untimed setup

        ops["encaps"] = Operation(
            "encaps", setup=encaps_setup, run=lambda pk: alg.encaps(pk),
            sizes=lambda s, r: {"ciphertext_bytes": len(r[0]), "shared_secret_bytes": len(r[1])})
        ops["decaps"] = Operation(
            "decaps", setup=decaps_setup, run=lambda s: alg.decaps(s[0], s[1]),
            validate=lambda s, r: r == s[2],
            sizes=lambda s, r: {"ciphertext_bytes": len(s[1]), "shared_secret_bytes": len(r)})

    elif alg.kind == "signature":
        msg = workloads.SIGNATURE_MESSAGE

        def sign_setup():
            return alg.load_secret_key(alg.keygen()[1])

        def verify_setup():
            pk, sk = alg.keygen()
            return pk, alg.sign(alg.load_secret_key(sk), msg)

        ops["sign"] = Operation(
            "sign", setup=sign_setup, run=lambda skh: alg.sign(skh, msg),
            sizes=lambda s, r: {"signature_bytes": len(r)})
        ops["verify"] = Operation(
            "verify", setup=verify_setup, run=lambda s: alg.verify(s[0], msg, s[1]),
            validate=lambda s, r: r is True,
            sizes=lambda s, r: {"signature_bytes": len(s[1])})

    elif alg.kind == "pke":
        pt = workloads.RSA_PAYLOAD

        def encrypt_setup():
            return alg.keygen()[0]

        def decrypt_setup():
            pk, sk = alg.keygen()
            return alg.load_secret_key(sk), alg.encrypt(pk, pt)

        ops["encrypt"] = Operation(
            "encrypt", setup=encrypt_setup, run=lambda pk: alg.encrypt(pk, pt),
            sizes=lambda s, r: {"ciphertext_bytes": len(r)})
        ops["decrypt"] = Operation(
            "decrypt", setup=decrypt_setup, run=lambda s: alg.decrypt(s[0], s[1]),
            validate=lambda s, r: r == pt,
            sizes=lambda s, r: {"ciphertext_bytes": len(s[1]), "plaintext_bytes": len(r)})
    else:
        raise ValueError(f"unknown algorithm kind {alg.kind!r}")
    return ops


# ---------------------------------------------------------------------------
# Worker process: owns one (algorithm, operation); does all timing in its own interpreter
# ---------------------------------------------------------------------------
def _worker(conn, module_name: str, alg_name: str, op_name: str, warmups: int) -> None:
    try:
        alg = importlib.import_module(module_name).get_algorithm(alg_name)
        op = operations_for(alg)[op_name]
        for _ in range(warmups):                     # warm-ups: not recorded, exceptions ignored
            try:
                op.run(op.setup())
            except Exception:
                pass
        conn.send({"event": "ready"})
    except BaseException as exc:                     # liboqs-python can raise SystemExit
        conn.send({"event": "init_error", "error_type": type(exc).__name__,
                   "error_message": f"worker start-up: {exc}"[:300]})
        return
    while True:
        try:
            cmd = conn.recv()
        except EOFError:
            return
        if cmd[0] == "trial":
            conn.send(measure.run_trial(op))
        elif cmd[0] == "batch":
            conn.send(measure.run_batch(op, cmd[1]))
        else:
            return


def _failure(status: str, error_type: str, message: str) -> dict[str, Any]:
    return {"status": status, "error_type": error_type, "error_message": message}


class Worker:
    """Parent-side handle: spawn, receive with a timeout, detect death, kill."""

    def __init__(self, module_name: str, alg_name: str, op_name: str, warmups: int):
        ctx = mp.get_context("spawn")
        self.conn, child = ctx.Pipe()
        self._oom_before = measure.oom_kill_count()
        self.proc = ctx.Process(target=_worker, args=(child, module_name, alg_name, op_name, warmups),
                                daemon=True)
        self.proc.start()
        child.close()                                # so the pipe reports EOF if the child dies

    def wait(self, timeout: float) -> dict[str, Any]:
        """Next message from the worker, or a failure dict (status timeout / killed)."""
        if not self.conn.poll(timeout):
            self.kill()
            return _failure("timeout", "Timeout", f"no reply within {timeout:g} s; worker killed")
        try:
            return self.conn.recv()
        except (EOFError, ConnectionError, OSError):
            self.proc.join(2)
            oom = self._oom_before is not None and (measure.oom_kill_count() or 0) > self._oom_before
            return _failure("killed", "OOMKilled" if oom else "WorkerCrashed",
                            f"worker exited with code {self.proc.exitcode}")

    def kill(self) -> None:
        if self.proc.is_alive():
            self.proc.kill()
        self.proc.join(2)
        self.conn.close()

    def close(self) -> None:
        try:
            self.conn.send(("exit",))
        except (OSError, ValueError):
            pass
        self.proc.join(2)
        self.kill()


# ---------------------------------------------------------------------------
# CSV logging (Task 4): every row is flushed as soon as it exists
# ---------------------------------------------------------------------------
def _fmt(v: Any) -> Any:
    if v is None:
        return ""
    return round(v, 6) if isinstance(v, float) else v


class CsvLog:
    def __init__(self, path: Path, columns: list[str]):
        self.columns = columns
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists() or path.stat().st_size == 0
        self._f = open(path, "a", newline="")
        self._w = csv.DictWriter(self._f, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        if new:
            self._w.writeheader()
            self._f.flush()

    def write(self, row: dict[str, Any]) -> None:
        self._w.writerow({c: _fmt(row.get(c)) for c in self.columns})
        self._f.flush()

    def close(self) -> None:
        self._f.close()


def _existing_counts(path: Path) -> Counter:
    counts: Counter = Counter()
    if path.exists():
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                counts[(r["algorithm"], r["operation"], r["profile"])] += 1
    return counts


# ---------------------------------------------------------------------------
# One series = the trials (or the throughput batches) of one (algorithm, operation, profile)
# ---------------------------------------------------------------------------
@dataclass
class Config:
    module: str
    profile: str
    trials: int = 30
    warmups: int = 5
    batches: int = 5
    batch_size: int = 100
    timeout: float = 30.0
    batch_timeout: float = 120.0
    max_consecutive_failures: int = 5


def _attempt(cfg: Config, worker: Worker | None, alg_name: str, op_name: str,
             cmd: tuple, timeout: float) -> tuple[dict[str, Any], Worker | None]:
    """One request. Returns (reply, worker); worker is None when it died and must be replaced."""
    if worker is None:
        worker = Worker(cfg.module, alg_name, op_name, cfg.warmups)
        first = worker.wait(timeout * (cfg.warmups + 2))      # start-up includes the warm-ups
        if first.get("event") != "ready":
            worker.kill()
            if first.get("event") == "init_error":
                return _failure("error", first["error_type"], first["error_message"]), None
            return first, None
    try:
        worker.conn.send(cmd)
    except (OSError, ValueError):
        worker.kill()
        return _failure("killed", "WorkerCrashed", "worker gone before the request"), None
    reply = worker.wait(timeout)
    if reply["status"] in ("timeout", "killed"):
        worker.kill()
        return reply, None
    return reply, worker


def run_series(cfg: Config, alg, op_name: str, kind: str, run_id: str, log: CsvLog) -> Counter:
    """Write exactly cfg.trials (kind='trial') or cfg.batches (kind='batch') rows. Returns status counts."""
    count = cfg.trials if kind == "trial" else cfg.batches
    timeout = cfg.timeout if kind == "trial" else cfg.batch_timeout
    cmd = ("trial",) if kind == "trial" else ("batch", cfg.batch_size)
    base = {"run_id": run_id, "algorithm": alg.name, "family": alg.info.family,
            "operation": op_name, "profile": cfg.profile}
    worker, consecutive, statuses = None, 0, Counter()
    try:
        for i in range(1, count + 1):
            row = {**base, kind: i, "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            if consecutive >= cfg.max_consecutive_failures:
                row.update(_failure("skipped", "SkippedAfterRepeatedFailures",
                                    f"{consecutive} crashes/timeouts in a row; not attempted"))
            else:
                reply, worker = _attempt(cfg, worker, alg.name, op_name, cmd, timeout)
                consecutive = consecutive + 1 if worker is None else 0
                row.update(reply)
                if kind == "batch":
                    row["batch_size"] = cfg.batch_size
            statuses[row["status"]] += 1
            log.write(row)
    finally:
        if worker is not None:
            worker.close()
    return statuses


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def _meta(args, cfg: Config, run_id: str, module, unavailable: list[str]) -> dict[str, Any]:
    env: dict[str, Any] = {}
    if cfg.module == "benchmark.algorithms":
        try:
            from .environment import environment_info
            env = {k: v for k, v in environment_info().items() if not k.startswith("liboqs_enabled")}
        except Exception as exc:
            env = {"environment_error": f"{type(exc).__name__}: {exc}"}
    return {"run_id": run_id, "profile": cfg.profile, "module": cfg.module, "args": vars(args),
            "limits": measure.cgroup_limits(), "capabilities": measure.capabilities(),
            "unavailable_algorithms": unavailable, "environment": env}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--profile", required=True, help="label stored in every row, e.g. C0, C1, C2, C3")
    p.add_argument("--demo", action="store_true", help="measure the toy algorithms in benchmark/demo.py")
    p.add_argument("--module", default="benchmark.algorithms",
                   help="module exposing get_algorithms()/get_algorithm(name)/availability()")
    p.add_argument("--algorithms", nargs="*", help="only these algorithm names")
    p.add_argument("--ops", nargs="*", help="only these operations (keygen, encaps, decaps, sign, ...)")
    p.add_argument("--trials", type=int, default=30)
    p.add_argument("--warmups", type=int, default=5)
    p.add_argument("--batches", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=100)
    p.add_argument("--timeout", type=float, default=30.0, help="seconds per trial")
    p.add_argument("--batch-timeout", type=float, default=120.0, help="seconds per throughput batch")
    p.add_argument("--max-consecutive-failures", type=int, default=5)
    p.add_argument("--skip-throughput", action="store_true")
    p.add_argument("--resume", action="store_true", help="skip groups already complete in the CSV files")
    p.add_argument("--allow-missing", action="store_true", help="run even if a required algorithm is unavailable")
    p.add_argument("--out", type=Path, default=Path("results/measurements"))
    args = p.parse_args(argv)

    cfg = Config(module="benchmark.demo" if args.demo else args.module, profile=args.profile,
                 trials=args.trials, warmups=args.warmups, batches=args.batches,
                 batch_size=args.batch_size, timeout=args.timeout, batch_timeout=args.batch_timeout,
                 max_consecutive_failures=args.max_consecutive_failures)
    module = importlib.import_module(cfg.module)

    unavailable = [n for n, v in module.availability().items() if not v["available"]]
    if unavailable and not args.allow_missing:
        print(f"REFUSING TO RUN: required algorithm(s) unavailable: {', '.join(unavailable)} "
              "(fix the liboqs build first, or pass --allow-missing)")
        return 2

    limits = measure.cgroup_limits()
    constrained = limits["cpu_limit_cores"] is not None or limits["memory_limit_mb"] is not None
    if cfg.profile == "C0" and constrained:
        print(f"WARNING: profile C0 should be unconstrained but the container has limits: {limits}")
    if cfg.profile != "C0" and not constrained:
        print(f"WARNING: profile {cfg.profile} but no CPU/memory limit is visible inside the container "
              "(forgot --cpus / --memory on docker run?)")
    print(f"profile {cfg.profile}; limits seen inside the container: {limits}")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "run_meta.jsonl", "a") as f:
        f.write(json.dumps(_meta(args, cfg, run_id, module, unavailable), default=str) + "\n")

    done_t = _existing_counts(args.out / "raw_trials.csv") if args.resume else Counter()
    done_b = _existing_counts(args.out / "raw_throughput.csv") if args.resume else Counter()
    trial_log = CsvLog(args.out / "raw_trials.csv", TRIAL_COLUMNS)
    batch_log = CsvLog(args.out / "raw_throughput.csv", BATCH_COLUMNS)

    try:
        for alg in module.get_algorithms():
            if args.algorithms and alg.name not in args.algorithms:
                continue
            for op_name in operations_for(alg):
                if args.ops and op_name not in args.ops:
                    continue
                key = (alg.name, op_name, cfg.profile)
                line = f"[{cfg.profile}] {alg.name:<22} {op_name:<8}"
                if done_t[key] < cfg.trials:
                    line += f" trials {dict(run_series(cfg, alg, op_name, 'trial', run_id, trial_log))}"
                else:
                    line += " trials (already done)"
                if not args.skip_throughput:
                    if done_b[key] < cfg.batches:
                        line += f" | batches {dict(run_series(cfg, alg, op_name, 'batch', run_id, batch_log))}"
                    else:
                        line += " | batches (already done)"
                print(line, flush=True)
    finally:
        trial_log.close()
        batch_log.close()
    print(f"\nWrote {args.out / 'raw_trials.csv'} and {args.out / 'raw_throughput.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
