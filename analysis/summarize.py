"""Summary statistics from the raw measurement CSVs (Module 2, Task 5).

    python -m analysis.summarize --raw results/measurements --out results/summary

Needs pandas and numpy (install them on the host; they are not in the Docker image).

Inputs : raw_trials.csv, raw_throughput.csv          (written by benchmark/runner.py)
Outputs: summary_latency.csv      median, IQR, bootstrap CI, slowdown vs C0, completion/failure rates
         summary_throughput.csv   median ops/s over batches, IQR, slowdown vs C0, failure rate
         summary_memory.csv       worker RSS and container memory per group
         object_sizes.csv         cryptographic object sizes in bytes
         tables.md                the same tables, ready to paste into the report

Definitions
    completion_rate = ok trials / planned trials            failure_rate = 1 - completion_rate
    Failed trials (error, timeout, killed, skipped) count as failures in the denominator.
    Latency statistics use ok trials only, so n_ok is always printed beside them
    (a median from 3 survivors out of 30 is not comparable to one from 30 of 30).
    slowdown        = median latency in this profile / median latency in C0   (>1 is slower)
    throughput slowdown = C0 ops/s / this profile's ops/s                       (>1 is slower)
    median_ci       = 95 % percentile-bootstrap interval of the median (2000 resamples, fixed seed)
"""
from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

KEY = ["algorithm", "family", "operation", "profile"]
GROUP = ["algorithm", "operation", "profile"]
SIZE_COLUMNS = ["public_key_bytes", "secret_key_bytes", "ciphertext_bytes",
                "shared_secret_bytes", "signature_bytes", "plaintext_bytes"]
FAILED = ["error", "timeout", "killed", "skipped"]
N_BOOT = 2000
SHORT_BATCH_MS = 100  # the Linux CFS quota period; shorter batches usually cannot see a CPU limit


def profile_key(p: str) -> tuple[int, str]:
    m = re.search(r"\d+", str(p))
    return (int(m.group()) if m else 10**9, str(p))


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def _latest_run_only(df: pd.DataFrame) -> pd.DataFrame:
    """If a group was measured more than once (e.g. after --resume), keep its newest run."""
    newest = df.groupby(GROUP)["run_id"].transform("max")
    return df[df["run_id"] == newest].copy()


def load(raw_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    trials = pd.read_csv(raw_dir / "raw_trials.csv", dtype={"run_id": str})
    path = raw_dir / "raw_throughput.csv"
    batches = pd.read_csv(path, dtype={"run_id": str}) if path.exists() else pd.DataFrame(
        columns=["run_id", "algorithm", "family", "operation", "profile", "status", "ops_per_sec",
                 "elapsed_ms", "error_type"])
    for df in (trials, batches):
        df["error_type"] = df["error_type"].fillna("")
    num_t = ["latency_ms", "worker_rss_before_mb", "worker_rss_peak_mb", "container_mem_current_mb",
             "container_mem_peak_mb", "cpu_throttled_ms", *SIZE_COLUMNS]
    for c in num_t:
        trials[c] = pd.to_numeric(trials[c], errors="coerce")
    for c in ["ops_per_sec", "elapsed_ms", "worker_rss_peak_mb", "container_mem_peak_mb", "cpu_throttled_ms"]:
        if c in batches:
            batches[c] = pd.to_numeric(batches[c], errors="coerce")
    return _latest_run_only(trials), (_latest_run_only(batches) if len(batches) else batches)


# ---------------------------------------------------------------------------
# Bootstrap helpers
# ---------------------------------------------------------------------------
def _boot_medians(x: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    return np.median(x[rng.integers(0, len(x), size=(N_BOOT, len(x)))], axis=1)


def median_ci(x: np.ndarray, rng) -> tuple[float, float]:
    if len(x) < 2:
        return (np.nan, np.nan)
    lo, hi = np.quantile(_boot_medians(x, rng), [0.025, 0.975])
    return float(lo), float(hi)


def ratio_ci(x: np.ndarray, base: np.ndarray, rng) -> tuple[float, float]:
    if len(x) < 2 or len(base) < 2:
        return (np.nan, np.nan)
    lo, hi = np.quantile(_boot_medians(x, rng) / _boot_medians(base, rng), [0.025, 0.975])
    return float(lo), float(hi)


def _quartiles(x: np.ndarray) -> tuple[float, float, float]:
    if len(x) == 0:
        return (np.nan, np.nan, np.nan)
    q1, med, q3 = np.percentile(x, [25, 50, 75])
    return float(q1), float(med), float(q3)


def _breakdown(g: pd.DataFrame) -> str:
    bad = g[g["status"] != "ok"]
    return "; ".join(f"{k}:{v}" for k, v in Counter(bad["error_type"]).most_common())


# ---------------------------------------------------------------------------
# Latency, throughput, memory, sizes
# ---------------------------------------------------------------------------
def summarize_latency(trials: pd.DataFrame, planned: int, baseline: str, rng) -> pd.DataFrame:
    ok_values = {}
    rows = []
    for key, g in trials.groupby(KEY, sort=False):
        ok = g.loc[g["status"] == "ok", "latency_ms"].dropna().to_numpy(float)
        ok_values[(key[0], key[2], key[3])] = ok
        denom = max(len(g), planned)
        q1, med, q3 = _quartiles(ok)
        lo, hi = median_ci(ok, rng)
        counts = g["status"].value_counts()
        rows.append({
            **dict(zip(KEY, key)), "n_planned": denom, "n_ok": len(ok),
            **{f"n_{s}": int(counts.get(s, 0)) for s in FAILED},
            "completion_rate": len(ok) / denom, "failure_rate": 1 - len(ok) / denom,
            "failure_breakdown": _breakdown(g),
            "median_ms": med, "q1_ms": q1, "q3_ms": q3, "iqr_ms": q3 - q1,
            "median_ci_low_ms": lo, "median_ci_high_ms": hi,
            "min_ms": float(ok.min()) if len(ok) else np.nan, "max_ms": float(ok.max()) if len(ok) else np.nan,
            "low_n_flag": len(ok) < 10,
        })
    out = pd.DataFrame(rows)
    slow, slo, shi = [], [], []
    for r in out.itertuples():
        base = ok_values.get((r.algorithm, r.operation, baseline))
        if base is None or len(base) == 0 or np.isnan(r.median_ms):
            slow.append(np.nan); slo.append(np.nan); shi.append(np.nan)
        elif r.profile == baseline:
            slow.append(1.0); slo.append(np.nan); shi.append(np.nan)
        else:
            lo, hi = ratio_ci(ok_values[(r.algorithm, r.operation, r.profile)], base, rng)
            slow.append(r.median_ms / float(np.median(base))); slo.append(lo); shi.append(hi)
    out["slowdown_vs_baseline"], out["slowdown_ci_low"], out["slowdown_ci_high"] = slow, slo, shi
    return _sorted(out)


def summarize_throughput(batches: pd.DataFrame, planned: int, baseline: str) -> pd.DataFrame:
    rows = []
    for key, g in batches.groupby(KEY, sort=False):
        ok = g[g["status"] == "ok"]
        v = ok["ops_per_sec"].dropna().to_numpy(float)
        denom = max(len(g), planned)
        q1, med, q3 = _quartiles(v)
        elapsed = float(ok["elapsed_ms"].median()) if len(ok) else np.nan
        rows.append({**dict(zip(KEY, key)), "n_planned": denom, "n_ok": len(v),
                     "completion_rate": len(v) / denom, "failure_rate": 1 - len(v) / denom,
                     "failure_breakdown": _breakdown(g), "median_ops_per_sec": med,
                     "q1_ops_per_sec": q1, "q3_ops_per_sec": q3, "iqr_ops_per_sec": q3 - q1,
                     "batch_elapsed_median_ms": elapsed,
                     "short_batch_flag": bool(elapsed < SHORT_BATCH_MS) if not np.isnan(elapsed) else False})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    base = out[out["profile"] == baseline].set_index(["algorithm", "operation"])["median_ops_per_sec"]
    out["slowdown_vs_baseline"] = [
        base.get((r.algorithm, r.operation), np.nan) / r.median_ops_per_sec if r.median_ops_per_sec else np.nan
        for r in out.itertuples()]
    return _sorted(out)


def summarize_memory(trials: pd.DataFrame) -> pd.DataFrame:
    t = trials.assign(rss_growth_mb=trials["worker_rss_peak_mb"] - trials["worker_rss_before_mb"])
    rows = []
    for key, g in t.groupby(KEY, sort=False):
        rows.append({**dict(zip(KEY, key)),
                     "n_with_memory": int(g["worker_rss_peak_mb"].notna().sum()),
                     "worker_rss_peak_median_mb": g["worker_rss_peak_mb"].median(),
                     "worker_rss_peak_max_mb": g["worker_rss_peak_mb"].max(),
                     "worker_rss_growth_median_mb": g["rss_growth_mb"].median(),
                     "container_mem_current_median_mb": g["container_mem_current_mb"].median(),
                     "container_mem_peak_max_mb": g["container_mem_peak_mb"].max(),
                     "cpu_throttled_total_ms": g["cpu_throttled_ms"].sum(min_count=1)})
    return _sorted(pd.DataFrame(rows))


def object_sizes(trials: pd.DataFrame) -> pd.DataFrame:
    ok = trials[trials["status"] == "ok"]
    rows = []
    for (alg, fam), g in ok.groupby(["algorithm", "family"], sort=False):
        row = {"algorithm": alg, "family": fam}
        for c in SIZE_COLUMNS:
            s = g[c].dropna()
            row[c.removesuffix("_bytes")] = "-" if s.empty else (
                str(int(s.min())) if s.min() == s.max() else f"{int(s.min())}-{int(s.max())}")
        rows.append(row)
    return pd.DataFrame(rows)


def _sorted(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.assign(_p=df["profile"].map(profile_key)).sort_values(
        ["algorithm", "operation", "_p"], kind="stable").drop(columns="_p").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Markdown tables
# ---------------------------------------------------------------------------
def _cell(v) -> str:
    if isinstance(v, (float, np.floating)):
        return "-" if np.isnan(v) else f"{v:.4g}"
    return str(v)


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_(no data)_\n"
    lines = ["| " + " | ".join(df.columns) + " |", "|" + "|".join("---" for _ in df.columns) + "|"]
    lines += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines) + "\n"


def write_tables(path: Path, lat, tp, mem, sizes) -> None:
    l = lat.assign(ok=lat["n_ok"].astype(str) + "/" + lat["n_planned"].astype(str),
                   fail_pct=100 * lat["failure_rate"])
    l = l[["algorithm", "operation", "profile", "ok", "median_ms", "iqr_ms", "slowdown_vs_baseline", "fail_pct"]]
    t = tp[["algorithm", "operation", "profile", "median_ops_per_sec", "iqr_ops_per_sec",
            "slowdown_vs_baseline", "short_batch_flag"]] if len(tp) else tp
    f = lat[lat["failure_rate"] > 0][["algorithm", "operation", "profile", "n_planned", "n_ok", "n_error",
                                      "n_timeout", "n_killed", "n_skipped", "failure_breakdown"]]
    m = mem[["algorithm", "operation", "profile", "worker_rss_peak_median_mb", "worker_rss_growth_median_mb",
             "container_mem_peak_max_mb"]]
    path.write_text(
        "# Summary tables\n\n## Latency (ms; median over ok trials, IQR = Q3-Q1)\n\n" + md_table(l)
        + "\n## Throughput (operations per second; median of batches)\n\n" + md_table(t)
        + "\n## Failures (only groups with at least one failed trial)\n\n" + md_table(f)
        + "\n## Memory (MB)\n\n" + md_table(m)
        + "\n## Cryptographic object sizes (bytes)\n\n" + md_table(sizes))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raw", type=Path, default=Path("results/measurements"))
    p.add_argument("--out", type=Path, default=Path("results/summary"))
    p.add_argument("--planned-trials", type=int, default=30)
    p.add_argument("--planned-batches", type=int, default=5)
    p.add_argument("--baseline", default="C0", help="profile that slowdown is measured against")
    p.add_argument("--seed", type=int, default=20261102, help="bootstrap seed (fixed so results reproduce)")
    args = p.parse_args(argv)

    rng = np.random.default_rng(args.seed)
    trials, batches = load(args.raw)
    args.out.mkdir(parents=True, exist_ok=True)
    lat = summarize_latency(trials, args.planned_trials, args.baseline, rng)
    tp = summarize_throughput(batches, args.planned_batches, args.baseline)
    mem = summarize_memory(trials)
    sizes = object_sizes(trials)
    for name, df in [("summary_latency", lat), ("summary_throughput", tp),
                     ("summary_memory", mem), ("object_sizes", sizes)]:
        df.to_csv(args.out / f"{name}.csv", index=False, float_format="%.6g")
    write_tables(args.out / "tables.md", lat, tp, mem, sizes)

    if args.baseline not in set(trials["profile"]):
        print(f"WARNING: baseline profile {args.baseline} not in the data; slowdowns are empty")
    if len(lat) and lat["low_n_flag"].any():
        print(f"NOTE: {int(lat['low_n_flag'].sum())} group(s) have fewer than 10 ok trials; read their medians with care")
    if len(tp) and tp["short_batch_flag"].any():
        print(f"NOTE: {int(tp['short_batch_flag'].sum())} throughput group(s) ran batches shorter than "
              f"{SHORT_BATCH_MS} ms; they cannot reveal CPU-quota throttling (see docs)")
    print(f"Wrote summaries to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
