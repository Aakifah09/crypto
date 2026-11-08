"""Statistical analysis (Task 5): raw CSVs -> summary tables. Standard library only.

    python -m analysis.summarize --trials results/trials.csv --throughput results/throughput.csv \
                                 --out results/summary [--run-id ID | --pool-runs]

Writes latency_summary.csv, throughput_summary.csv, completion_summary.csv, memory_summary.csv,
size_check.csv and summary_tables.md. Everything is recomputed from the raw rows, so the
same raw CSV always gives the same tables (bootstrap seeded).

Conventions (see docs/statistical_analysis.md):
  * Latency and throughput statistics use SUCCESSFUL runs only; failures are counted
    separately in completion_summary.csv so they are never hidden.
  * Quartiles use linear interpolation (numpy default). IQR = Q3 - Q1.
  * slowdown = median latency in profile / median latency in C0, with a 95 % percentile
    bootstrap interval. throughput slowdown = median ops/s in C0 / median ops/s in profile.
"""
from __future__ import annotations

import argparse
import csv
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

TEXT_COLS = {"run_id", "timestamp_utc", "profile", "algorithm", "kind", "family", "operation",
             "error_type", "error_message"}
SIZE_FIELDS = ["public_key_bytes", "secret_key_bytes", "ciphertext_bytes", "shared_secret_bytes",
               "signature_bytes", "plaintext_bytes"]
BOOT_REPS = 2000


def read_rows(path: str | Path) -> list[dict[str, Any]]:
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k, v in r.items():
            r[k] = None if v in ("", None) else (v if k in TEXT_COLS else float(v))
    return rows


def select_runs(rows: list[dict], run_id: str | None = None, pool: bool = False) -> list[dict]:
    """One run per profile by default (the latest), so a re-run never silently doubles n."""
    if run_id:
        return [r for r in rows if r["run_id"] == run_id]
    if pool:
        return rows
    latest: dict[str, tuple[str, str]] = {}
    for r in rows:
        if r["profile"] not in latest or r["timestamp_utc"] > latest[r["profile"]][0]:
            latest[r["profile"]] = (r["timestamp_utc"], r["run_id"])
    return [r for r in rows if r["run_id"] == latest[r["profile"]][1]]


# ---------------------------------------------------------------- statistics
def percentile(xs: Iterable[float], p: float) -> float:
    s = sorted(xs)
    k = (len(s) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def quartiles(xs: list[float]) -> tuple[float, float, float]:
    return percentile(xs, 25), statistics.median(xs), percentile(xs, 75)


def bootstrap_ratio_ci(num: list[float], den: list[float], seed: int = 0) -> tuple[float, float]:
    """95 % percentile bootstrap interval for median(num) / median(den)."""
    rng = random.Random(seed)
    ratios = []
    for _ in range(BOOT_REPS):
        d = statistics.median(rng.choices(den, k=len(den)))
        if d > 0:
            ratios.append(statistics.median(rng.choices(num, k=len(num))) / d)
    ratios.sort()
    return ratios[int(0.025 * len(ratios))], ratios[int(0.975 * len(ratios)) - 1]


def group(rows: Iterable[dict], keys: tuple[str, ...]) -> dict[tuple, list[dict]]:
    d: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        d[tuple(r[k] for k in keys)].append(r)
    return d


CELL = ("algorithm", "operation", "profile")


def _ok(rows: list[dict], field: str) -> list[float]:
    return [r[field] for r in rows if r["success"] == 1 and r.get(field) is not None]


def _med(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


# ---------------------------------------------------------------- summaries
def summarize_latency(trials: list[dict]) -> list[dict]:
    by = group(trials, CELL)
    base = {(a, o): _ok(rs, "latency_ms") for (a, o, p), rs in by.items() if p == "C0"}
    out = []
    for (a, o, p), rs in sorted(by.items()):
        ok = _ok(rs, "latency_ms")
        row: dict[str, Any] = {"algorithm": a, "operation": o, "profile": p,
                               "n_recorded": len(rs), "n_success": len(ok)}
        if ok:
            q1, med, q3 = quartiles(ok)
            row.update(median_ms=med, q1_ms=q1, q3_ms=q3, iqr_ms=q3 - q1, p95_ms=percentile(ok, 95),
                       min_ms=min(ok), max_ms=max(ok))
            b = base.get((a, o))
            if b:
                lo, hi = bootstrap_ratio_ci(ok, b)
                row.update(slowdown_vs_c0=med / statistics.median(b), slowdown_ci_low=lo, slowdown_ci_high=hi)
        known = [r for r in rs if r.get("timed_throttled_periods") is not None]
        row["trials_throttled_in_timed_call"] = sum(1 for r in known if r["timed_throttled_periods"] > 0) if known else None
        out.append(row)
    return out


def summarize_throughput(batches: list[dict]) -> list[dict]:
    by = group(batches, CELL)
    base = {(a, o): _ok(rs, "throughput_ops_s") for (a, o, p), rs in by.items() if p == "C0"}
    out = []
    for (a, o, p), rs in sorted(by.items()):
        ok = _ok(rs, "throughput_ops_s")
        attempted = sum(r["batch_size"] or 0 for r in rs)
        done = sum(r["ops_completed"] or 0 for r in rs)
        row: dict[str, Any] = {"algorithm": a, "operation": o, "profile": p, "n_batches": len(rs),
                               "n_batches_success": len(ok), "ops_attempted": attempted, "ops_completed": done,
                               "op_completion_rate": done / attempted if attempted else None}
        if ok:
            q1, med, q3 = quartiles(ok)
            row.update(median_ops_s=med, q1_ops_s=q1, q3_ops_s=q3, iqr_ops_s=q3 - q1,
                       min_ops_s=min(ok), max_ops_s=max(ok))
            if base.get((a, o)):
                row["throughput_slowdown_vs_c0"] = statistics.median(base[(a, o)]) / med
        known = [r for r in rs if r.get("timed_throttled_periods") is not None]
        row["batches_throttled"] = sum(1 for r in known if r["timed_throttled_periods"] > 0) if known else None
        out.append(row)
    return out


def summarize_completion(trials: list[dict], batches: list[dict]) -> list[dict]:
    bt, bb = group(trials, CELL), group(batches, CELL)
    out = []
    for key in sorted(set(bt) | set(bb)):
        ts, bs = bt.get(key, []), bb.get(key, [])
        tf = [r for r in ts if r["success"] != 1]
        bf = [r for r in bs if r["success"] != 1]
        errs = Counter(r["error_type"] or "unknown" for r in tf + bf)
        att = sum(r["batch_size"] or 0 for r in bs)
        done = sum(r["ops_completed"] or 0 for r in bs)
        out.append({"algorithm": key[0], "operation": key[1], "profile": key[2],
                    "trials_attempted": len(ts), "trials_succeeded": len(ts) - len(tf),
                    "trial_failure_rate": len(tf) / len(ts) if ts else None,
                    "batches_attempted": len(bs), "batches_failed": len(bf),
                    "batch_ops_attempted": att, "batch_ops_completed": done,
                    "batch_op_failure_rate": 1 - done / att if att else None,
                    "oom_kills": sum((r.get("oom_kills") or 0) for r in ts + bs),
                    "error_types": "; ".join(f"{k}:{v}" for k, v in sorted(errs.items()))})
    return out


def summarize_memory(trials: list[dict]) -> list[dict]:
    out = []
    for (a, o, p), rs in sorted(group(trials, CELL).items()):
        peak, base = _ok(rs, "worker_peak_rss_kb"), _ok(rs, "worker_baseline_rss_kb")
        cont = [r["container_mem_peak_kb"] for r in rs if r.get("container_mem_peak_kb") is not None]
        out.append({"algorithm": a, "operation": o, "profile": p, "n": len(peak),
                    "median_worker_peak_rss_kb": _med(peak), "max_worker_peak_rss_kb": max(peak, default=None),
                    "median_worker_baseline_rss_kb": _med(base),
                    "median_container_peak_kb": _med(cont), "max_container_peak_kb": max(cont, default=None),
                    "median_container_anon_kb": _med(_ok(rs, "container_anon_kb")),
                    "median_container_mem_kb": _med(_ok(rs, "container_mem_kb")),
                    "container_peak_is_per_worker": int(any(r.get("container_peak_reset") == 1 for r in rs))})
    return out


def check_sizes(trials: list[dict]) -> list[dict]:
    """Report Sec. 4.5: sizes must not change with the profile. Anything that varies is flagged;
    ECDSA DER signature length is the one variation that is expected (integer encoding)."""
    out = []
    for (a, o), rs in sorted(group([r for r in trials if r["success"] == 1], ("algorithm", "operation")).items()):
        for f in SIZE_FIELDS:
            vals = [r[f] for r in rs if r.get(f) is not None]
            if vals:
                out.append({"algorithm": a, "operation": o, "size_field": f, "min_bytes": min(vals),
                            "max_bytes": max(vals), "distinct_values": len(set(vals)),
                            "varies": "yes" if len(set(vals)) > 1 else "no",
                            "profiles": ",".join(sorted({r["profile"] for r in rs if r.get(f) is not None}))})
    return out


# ---------------------------------------------------------------- output
def fmt(v: Any) -> Any:
    return f"{v:.6g}" if isinstance(v, float) else ("" if v is None else v)


def write_csv(path: Path, rows: list[dict]) -> None:
    cols: list[str] = []
    for r in rows:
        cols += [k for k in r if k not in cols]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: fmt(r.get(k)) for k in cols})


def pivot_md(title: str, rows: list[dict], cell_fn, profiles: list[str]) -> str:
    table: dict[tuple, dict[str, str]] = defaultdict(dict)
    for r in rows:
        table[(r["algorithm"], r["operation"])][r["profile"]] = cell_fn(r)
    lines = [f"### {title}", "", "| Algorithm | Operation | " + " | ".join(profiles) + " |",
             "|---|---|" + "---|" * len(profiles)]
    for (a, o), cells in sorted(table.items()):
        lines.append(f"| {a} | {o} | " + " | ".join(cells.get(p, "n/a") for p in profiles) + " |")
    return "\n".join(lines) + "\n"


def markdown_tables(lat, thr, comp, profiles) -> str:
    g = lambda v: "n/a" if v is None else f"{v:.4g}"
    parts = [pivot_md("Median latency in ms [Q1 to Q3], successful trials only", lat,
                      lambda r: f"{g(r.get('median_ms'))} [{g(r.get('q1_ms'))} to {g(r.get('q3_ms'))}]", profiles),
             pivot_md("Slowdown vs C0 (median ratio, 95 % bootstrap interval)", lat,
                      lambda r: "n/a" if r.get("slowdown_vs_c0") is None else
                      f"x{r['slowdown_vs_c0']:.2f} ({r['slowdown_ci_low']:.2f} to {r['slowdown_ci_high']:.2f})", profiles),
             pivot_md("95th percentile latency in ms (tail; medians hide CPU throttling)", lat,
                      lambda r: g(r.get("p95_ms")), profiles)]
    if thr:
        parts.append(pivot_md("Median throughput in operations/s", thr, lambda r: g(r.get("median_ops_s")), profiles))
    parts.append(pivot_md("Trials whose timed call hit CPU throttling (count of recorded trials)", lat,
                          lambda r: "n/a" if r.get("trials_throttled_in_timed_call") is None else
                          f"{r['trials_throttled_in_timed_call']}/{r['n_recorded']}", profiles))
    if thr:
        parts.append(pivot_md("Batches that hit CPU throttling (count of batches; a stall waits up to one 100 ms period)",
                              thr, lambda r: "n/a" if r.get("batches_throttled") is None else
                              f"{r['batches_throttled']}/{r['n_batches']}", profiles))
    parts.append(pivot_md("Trial failure rate (failed / attempted)", comp,
                          lambda r: "n/a" if r["trial_failure_rate"] is None else
                          f"{100 * r['trial_failure_rate']:.0f} % ({r['trials_attempted'] - r['trials_succeeded']}/{r['trials_attempted']})",
                          profiles))
    return "\n".join(parts)


def load_summaries(trials_path, throughput_path=None, run_id=None, pool=False) -> dict[str, Any]:
    trials = select_runs(read_rows(trials_path), run_id, pool)
    batches = []
    if throughput_path and Path(throughput_path).exists():
        batches = select_runs(read_rows(throughput_path), run_id, pool)
    profiles = sorted({r["profile"] for r in trials + batches})
    return {"trials": trials, "batches": batches, "profiles": profiles,
            "latency": summarize_latency(trials), "throughput": summarize_throughput(batches),
            "completion": summarize_completion(trials, batches), "memory": summarize_memory(trials),
            "sizes": check_sizes(trials), "runs": sorted({r["run_id"] for r in trials + batches})}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--trials", default="results/trials.csv")
    p.add_argument("--throughput", default="results/throughput.csv")
    p.add_argument("--out", default="results/summary")
    p.add_argument("--run-id")
    p.add_argument("--pool-runs", action="store_true", help="pool every run_id instead of using the latest per profile")
    a = p.parse_args(argv)
    s = load_summaries(a.trials, a.throughput, a.run_id, a.pool_runs)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name in ("latency", "throughput", "completion", "memory"):
        write_csv(out / f"{name}_summary.csv", s[name])
    write_csv(out / "size_check.csv", s["sizes"])
    md = markdown_tables(s["latency"], s["throughput"], s["completion"], s["profiles"])
    (out / "summary_tables.md").write_text(md)
    print(f"runs used: {', '.join(s['runs'])}\nprofiles: {', '.join(s['profiles'])}\nwritten to {out.resolve()}\n")
    print(md)
    varying = [r for r in s["sizes"] if r["varies"] == "yes"]
    for r in varying:
        print(f"NOTE size varies: {r['algorithm']}/{r['operation']} {r['size_field']} "
              f"{r['min_bytes']:.0f} to {r['max_bytes']:.0f} bytes (expected only for DER outputs: "
              f"ECDSA signature, RSA PKCS#8 private key)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
