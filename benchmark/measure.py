"""Measurement primitives for Module 2: timing (Task 1) and memory / cgroup readers (Task 3).

Nothing in this file knows about any cryptographic algorithm. It only knows how to
time a callable, count completed operations, and read process / container counters.

Timing contract (report Sec. 4.4 step 3): only the call itself sits between the two
perf_counter_ns() reads. Setup, input generation, correctness checks and logging are
done by the caller, outside the timer.
"""
from __future__ import annotations

import gc
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

try:
    import resource
except ImportError:  # Windows. The benchmark itself only runs in Linux containers.
    resource = None

NS_PER_MS = 1_000_000


def timer_info() -> dict[str, Any]:
    ci = time.get_clock_info("perf_counter")
    return {"clock": ci.implementation, "resolution_ns": ci.resolution * 1e9, "monotonic": ci.monotonic}


# ---------------------------------------------------------------------------
# Task 1: timing
# ---------------------------------------------------------------------------
def timed_call(fn: Callable[..., Any], *args: Any, _collect: bool = True, **kwargs: Any) -> tuple[float, Any]:
    """Call fn once. Returns (elapsed_ms, result). If fn raises, the exception propagates.
    _collect=False skips the gc.collect() that normally runs just before the timer (the caller
    has already collected; a collection right before timing would burn CPU quota)."""
    if _collect:
        gc.collect()                   # before the timer: no collection pause inside it
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        t0 = time.perf_counter_ns()
        result = fn(*args, **kwargs)
        t1 = time.perf_counter_ns()
    finally:
        if was_enabled:
            gc.enable()
    return (t1 - t0) / NS_PER_MS, result


@dataclass
class BatchResult:
    attempted: int
    completed: int
    duration_ms: float          # wall-clock of the whole batch, first call to last call
    last_result: Any = None
    error: BaseException | None = None

    @property
    def ops_per_s(self) -> float | None:
        if self.completed and self.duration_ms > 0:
            return self.completed / (self.duration_ms / 1000.0)
        return None


def timed_batch(fn: Callable[..., Any], *args: Any, n: int = 100, chunks: int = 10,
                on_progress: Callable[[int], None] | None = None, collect: bool = True) -> BatchResult:
    """Run fn(*args) n times back to back and return the wall-clock time of the whole batch.

    The batch is run in `chunks` blocks and on_progress(done) is called between blocks so that
    the parent can learn how many operations finished if the worker is later killed. The
    callback is INSIDE the measured time, so it must be a few microseconds (the runner writes
    one integer into a memory-mapped file, no system call). Wall-clock is used on purpose:
    under a CPU quota a stall can land between two calls, and time spent outside the calls is
    still time the batch took. A failing call stops the batch; .error holds it and .completed
    the number of calls that finished before it.
    """
    sizes = [s for s in (n // chunks + (1 if i < n % chunks else 0) for i in range(chunks)) if s > 0]
    done, last, error = 0, None, None
    if collect:
        gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    t0 = time.perf_counter_ns()
    try:
        for size in sizes:
            k = 0
            try:
                for k in range(size):
                    last = fn(*args)
                k = size
            except Exception as exc:
                done += k           # k = number of calls that finished before the failure
                error = exc
                break
            done += size
            if on_progress is not None:
                on_progress(done)
    finally:
        total_ns = time.perf_counter_ns() - t0
        if was_enabled:
            gc.enable()
    return BatchResult(n, done, total_ns / NS_PER_MS, last, error)


# ---------------------------------------------------------------------------
# Task 3: worker memory (this process) and container memory (cgroup v2)
# ---------------------------------------------------------------------------
def _proc_status_kb(field: str) -> int | None:
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith(field + ":"):
                    return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return None


def _windows_rss_kb() -> tuple[int | None, int | None]:
    if sys.platform != "win32":
        return None, None
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        psapi = ctypes.windll.psapi
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        hproc = ctypes.windll.kernel32.GetCurrentProcess()
        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(counters)
        if psapi.GetProcessMemoryInfo(hproc, ctypes.byref(counters), ctypes.sizeof(counters)):
            return counters.WorkingSetSize // 1024, counters.PeakWorkingSetSize // 1024
    except (AttributeError, OSError, ValueError):
        pass
    return None, None


def rss_kb() -> int | None:
    """Current resident set size of this process (kB)."""
    v = _proc_status_kb("VmRSS")
    if v is not None:
        return v
    if sys.platform == "win32":
        current, _ = _windows_rss_kb()
        return current
    if resource is not None:
        ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return ru // 1024 if sys.platform == "darwin" else ru   # Linux reports kB
    return None


def peak_rss_kb() -> int | None:
    """Peak resident set size of this process since it started (kB)."""
    v = _proc_status_kb("VmHWM")
    if v is not None:
        return v
    if sys.platform == "win32":
        _, peak = _windows_rss_kb()
        return peak
    if resource is not None:
        ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return ru // 1024 if sys.platform == "darwin" else ru   # Linux reports kB
    return None


class Cgroup:
    """Reader for the container's cgroup v2 files. Every value is None if unreadable
    (not Linux, cgroup v1, no permission), so callers must tolerate missing data."""

    def __init__(self, root: str | os.PathLike | None = None, reset_peak: bool = True):
        self.root = Path(root or os.environ.get("CGROUP_ROOT", "/sys/fs/cgroup"))
        self.peak_resettable = False
        fd = None
        path = self.root / "memory.peak"
        if reset_peak:
            try:                         # kernels >= 6.12: writing to memory.peak resets it for this fd
                fd = os.open(path, os.O_RDWR)
                os.write(fd, b"0")
                self.peak_resettable = True
            except OSError:
                if fd is not None:
                    os.close(fd)
                fd = None
        if fd is None:
            try:
                fd = os.open(path, os.O_RDONLY)   # still readable, but a container-lifetime peak
            except OSError:
                fd = None
        self._peak_fd = fd

    def _read(self, name: str) -> str | None:
        try:
            return (self.root / name).read_text().strip()
        except OSError:
            return None

    def _kv(self, name: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for line in (self._read(name) or "").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1].lstrip("-").isdigit():
                out[parts[0]] = int(parts[1])
        return out

    def limits(self) -> dict[str, str | None]:
        return {"cpu_max": self._read("cpu.max"), "memory_max": self._read("memory.max"),
                "memory_swap_max": self._read("memory.swap.max")}

    def memory_peak_kb(self) -> int | None:
        if self._peak_fd is None:
            return None
        try:
            if hasattr(os, "pread"):
                raw = os.pread(self._peak_fd, 64, 0)
            else:
                os.lseek(self._peak_fd, 0, os.SEEK_SET)
                raw = os.read(self._peak_fd, 64)
            return int(raw.split()[0]) // 1024
        except (OSError, ValueError, IndexError, TypeError):
            return None

    def reset_memory_peak(self) -> bool:
        if not self.peak_resettable or self._peak_fd is None:
            return False
        try:
            os.write(self._peak_fd, b"0")
            return True
        except OSError:
            return False

    def sample(self) -> dict[str, Any]:
        """Point-in-time container counters: memory incl. page cache, anonymous memory (no page
        cache) and the cumulative CPU-throttle counters. A few small file reads, so call it
        OUTSIDE any timer. Values are None where the cgroup file is unreadable."""
        cur = self._read("memory.current")
        anon = self._kv("memory.stat").get("anon")
        cpu = self._kv("cpu.stat")
        return {"mem_kb": int(cur) // 1024 if cur and cur.isdigit() else None,
                "anon_kb": None if anon is None else anon // 1024,
                "throttled": cpu.get("nr_throttled"), "throttled_usec": cpu.get("throttled_usec")}

    def begin(self) -> dict[str, Any]:
        """Call just before starting a worker: resets the peak and snapshots the counters."""
        self.reset_memory_peak()
        return {"events": self._kv("memory.events"), "cpu": self._kv("cpu.stat")}

    def end(self, start: dict[str, Any]) -> dict[str, Any]:
        """Call after the worker exited: container peak plus OOM-kill and CPU-throttle deltas."""
        ev, cpu = self._kv("memory.events"), self._kv("cpu.stat")

        def delta(a: dict, b: dict, k: str):
            return (b[k] - a[k]) if (k in a and k in b) else None

        usec = delta(start["cpu"], cpu, "throttled_usec")
        return {"container_mem_peak_kb": self.memory_peak_kb(),
                "container_peak_reset": int(self.peak_resettable),
                "oom_kills": delta(start["events"], ev, "oom_kill"),
                "throttled_periods": delta(start["cpu"], cpu, "nr_throttled"),
                "throttled_ms": None if usec is None else usec / 1000.0}
