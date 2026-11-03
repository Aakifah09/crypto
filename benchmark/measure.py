"""Timing and memory primitives (Module 2, Tasks 1 and 3).

Nothing in this file knows about cryptography. An `Operation` is three callables:

    setup()                     untimed: build keys / inputs, return a state object
    run(state)                  the ONLY thing that is timed
    validate(state, result)     untimed: False is recorded as a failed trial
    sizes(state, result)        untimed: output sizes in bytes

`run_trial` measures one execution of an operation; `run_batch` measures N back-to-back
executions (throughput). Both return a plain dict that never raises: a failure is a
result (status="error"), not an exception, so the caller cannot lose it.

Memory has two deliberately separate sources:
    worker_rss_*          peak resident set of THIS process (/proc/self/status VmHWM,
                          reset before each measurement through /proc/self/clear_refs)
    container_mem_*       cgroup counters for the whole container: includes the parent
                          runner and page cache, and `peak` is cumulative since the
                          container started (the cgroup filesystem is read-only in Docker,
                          so the watermark cannot be reset)
"""
from __future__ import annotations

import gc
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

try:
    import resource
except ImportError:  # Windows host; real measurements run in the Linux container
    resource = None

NS_PER_MS = 1_000_000


def ns_to_ms(ns: int) -> float:
    return ns / NS_PER_MS


def _noop() -> None:
    return None


@dataclass
class Operation:
    name: str
    run: Callable[[Any], Any]
    setup: Callable[[], Any] = _noop
    validate: Callable[[Any, Any], bool] | None = None
    sizes: Callable[[Any, Any], dict[str, int]] | None = None


# ---------------------------------------------------------------------------
# Timing (Task 1)
# ---------------------------------------------------------------------------
def timed(fn: Callable[..., Any], *args: Any) -> tuple[float, Any]:
    """Run fn(*args) once. Returns (elapsed_ms, result). Exceptions propagate.

    The garbage collector is run before and disabled during the call so a collection
    cannot land inside the timed region. Only the call itself sits between the two
    perf_counter_ns() reads.
    """
    gc_was_on = gc.isenabled()
    gc.collect()
    gc.disable()
    try:
        t0 = time.perf_counter_ns()
        result = fn(*args)
        t1 = time.perf_counter_ns()
    finally:
        if gc_was_on:
            gc.enable()
    return ns_to_ms(t1 - t0), result


# ---------------------------------------------------------------------------
# Linux readers (all return None when the source does not exist)
# ---------------------------------------------------------------------------
_CG = "/sys/fs/cgroup"          # cgroup v2 (unified) or v1 root
_CG1_MEM = f"{_CG}/memory"
_CG1_CPU = f"{_CG}/cpu"
_MB = 1024 * 1024


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def _read_int(path: str) -> int | None:
    txt = _read_text(path)
    try:
        return int(txt) if txt is not None else None
    except ValueError:  # "max"
        return None


def _stat_value(path: str, key: str) -> int | None:
    txt = _read_text(path)
    for line in (txt or "").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == key:
            return int(parts[1])
    return None


def _proc_status_kb(key: str) -> int | None:
    txt = _read_text("/proc/self/status")
    for line in (txt or "").splitlines():
        if line.startswith(key + ":"):
            return int(line.split()[1])
    return None


def rss_mb() -> float | None:
    kb = _proc_status_kb("VmRSS")
    return kb / 1024 if kb is not None else None


def reset_peak_rss() -> bool:
    """Reset VmHWM to the current RSS. False if the kernel/container forbids it."""
    try:
        with open("/proc/self/clear_refs", "w") as f:
            f.write("5")
        return True
    except OSError:
        return False


def peak_rss_mb() -> float | None:
    """Peak RSS of this process since the last reset_peak_rss() (cumulative if reset is unavailable)."""
    kb = _proc_status_kb("VmHWM")
    if kb is None and resource is not None:
        kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # KB on Linux, never resets
    return kb / 1024 if kb is not None else None


def container_memory_mb() -> tuple[float | None, float | None]:
    """(current, peak) container memory in MB from the cgroup. Container-wide; peak is cumulative."""
    cur = _read_int(f"{_CG}/memory.current")
    peak = _read_int(f"{_CG}/memory.peak")
    if cur is None:  # cgroup v1
        cur = _read_int(f"{_CG1_MEM}/memory.usage_in_bytes")
        peak = _read_int(f"{_CG1_MEM}/memory.max_usage_in_bytes")
    return (None if cur is None else cur / _MB, None if peak is None else peak / _MB)


def cpu_throttled_ms() -> float | None:
    """Cumulative time the container's processes were held back by the CPU quota."""
    us = _stat_value(f"{_CG}/cpu.stat", "throttled_usec")
    if us is not None:
        return us / 1000
    ns = _stat_value(f"{_CG1_CPU}/cpu.stat", "throttled_time")
    return None if ns is None else ns / 1_000_000


def oom_kill_count() -> int | None:
    """Number of OOM kills the container's cgroup has recorded so far."""
    n = _stat_value(f"{_CG}/memory.events", "oom_kill")
    return n if n is not None else _stat_value(f"{_CG1_MEM}/memory.oom_control", "oom_kill")


def cgroup_limits() -> dict[str, Any]:
    """Effective limits seen from inside the container. None means 'no limit'."""
    cpu_limit = None
    raw = _read_text(f"{_CG}/cpu.max")
    if raw:
        quota, period = raw.split()
        cpu_limit = None if quota == "max" else int(quota) / int(period)
    else:
        quota, period = _read_int(f"{_CG1_CPU}/cpu.cfs_quota_us"), _read_int(f"{_CG1_CPU}/cpu.cfs_period_us")
        if quota and quota > 0 and period:
            cpu_limit = quota / period
    mem = _read_int(f"{_CG}/memory.max")
    if mem is None:
        mem = _read_int(f"{_CG1_MEM}/memory.limit_in_bytes")
    if mem is not None and mem >= 2**60:  # cgroup v1 "unlimited"
        mem = None
    swap = _read_int(f"{_CG}/memory.swap.max")
    return {"cpu_limit_cores": cpu_limit,
            "memory_limit_mb": None if mem is None else round(mem / _MB, 1),
            "swap_limit_mb": None if swap is None else round(swap / _MB, 1),
            "os_cpu_count": os.cpu_count()}


def capabilities() -> dict[str, Any]:
    """Which measurements this environment actually supports (saved with every run)."""
    cur, peak = container_memory_mb()
    return {"rss_peak_resettable": reset_peak_rss(),
            "container_memory_available": cur is not None,
            "container_peak_available": peak is not None,
            "cpu_throttle_counter_available": cpu_throttled_ms() is not None,
            "oom_counter_available": oom_kill_count() is not None}


# ---------------------------------------------------------------------------
# One measurement = one dict. Never raises.
# ---------------------------------------------------------------------------
def _fail(out: dict[str, Any], where: str, exc: BaseException) -> None:
    out.update(status="error", error_type=type(exc).__name__, error_message=f"{where}: {exc}"[:300])


def _memory_fields(out: dict[str, Any], throttled_before: float | None) -> None:
    cur, peak = container_memory_mb()
    out["worker_rss_peak_mb"] = peak_rss_mb()
    out["container_mem_current_mb"] = cur
    out["container_mem_peak_mb"] = peak
    after = cpu_throttled_ms()
    out["cpu_throttled_ms"] = None if after is None or throttled_before is None else after - throttled_before


def run_trial(op: Operation) -> dict[str, Any]:
    """One recorded trial: untimed setup, one timed call, untimed validation, sizes and memory."""
    out: dict[str, Any] = {"status": "ok", "error_type": "", "error_message": "", "latency_ms": None}
    try:
        state = op.setup()
    except Exception as exc:
        _fail(out, "setup", exc)
        return out

    gc.collect()
    reset_peak_rss()
    out["worker_rss_before_mb"] = rss_mb()
    throttled_before = cpu_throttled_ms()
    result = None
    try:
        out["latency_ms"], result = timed(op.run, state)
    except Exception as exc:
        _fail(out, "run", exc)
    _memory_fields(out, throttled_before)

    if out["status"] == "ok" and op.validate is not None:
        try:
            if not op.validate(state, result):
                out.update(status="error", error_type="ValidationFailed",
                           error_message="operation returned a wrong result")
                out["latency_ms"] = None
        except Exception as exc:
            _fail(out, "validate", exc)
    if out["status"] == "ok" and op.sizes is not None:
        try:
            out.update(op.sizes(state, result))
        except Exception as exc:
            _fail(out, "sizes", exc)
    return out


def run_batch(op: Operation, n: int) -> dict[str, Any]:
    """One throughput batch: n back-to-back calls timed as a whole (setup happens once, untimed)."""
    out: dict[str, Any] = {"status": "ok", "error_type": "", "error_message": "",
                           "batch_size": n, "elapsed_ms": None, "ops_per_sec": None}
    try:
        state = op.setup()
    except Exception as exc:
        _fail(out, "setup", exc)
        return out

    gc.collect()
    reset_peak_rss()
    throttled_before = cpu_throttled_ms()
    run = op.run
    result = None
    gc_was_on = gc.isenabled()
    gc.disable()
    try:
        t0 = time.perf_counter_ns()
        for _ in range(n):
            result = run(state)
        t1 = time.perf_counter_ns()
        out["elapsed_ms"] = ns_to_ms(t1 - t0)
        out["ops_per_sec"] = n / (out["elapsed_ms"] / 1000)
    except Exception as exc:
        _fail(out, "run", exc)
    finally:
        if gc_was_on:
            gc.enable()
    _memory_fields(out, throttled_before)

    if out["status"] == "ok" and op.validate is not None:
        try:
            if not op.validate(state, result):
                out.update(status="error", error_type="ValidationFailed",
                           error_message="operation returned a wrong result")
                out["elapsed_ms"] = out["ops_per_sec"] = None
        except Exception as exc:
            _fail(out, "validate", exc)
    return out
