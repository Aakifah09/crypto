"""Final graphs (Module 2, Task 6). Reads the summaries written by analysis/summarize.py.

    python -m analysis.plots --summary results/summary --out results/figures

Needs pandas, numpy and matplotlib on the host.

    latency_vs_profile.png   median latency per operation across profiles; bars are the IQR;
                             a hollow marker means some trials in that point failed
    throughput.png           median ops/s per operation and profile; bars are the IQR over batches
    memory.png               worker peak RSS, RSS growth during an operation, container peak
    failure_rate.png         failure rate per algorithm, operation and profile
Object-size tables are written by analysis/summarize.py (object_sizes.csv, tables.md).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .summarize import profile_key

OP_ORDER = ["keygen", "encaps", "encrypt", "decaps", "decrypt", "sign", "verify"]
PQC = "post-quantum"


def _ops(df: pd.DataFrame) -> list[str]:
    present = set(df["operation"])
    return [o for o in OP_ORDER if o in present] + sorted(present - set(OP_ORDER))


def _profiles(df: pd.DataFrame) -> list[str]:
    return sorted(df["profile"].unique(), key=profile_key)


def _algorithms(df: pd.DataFrame) -> dict[str, tuple]:
    """algorithm -> (colour, linestyle). Post-quantum solid, classical dashed."""
    fam = df.drop_duplicates("algorithm").set_index("algorithm")["family"]
    cmap = plt.get_cmap("tab10")
    return {a: (cmap(i % 10), "-" if fam[a] == PQC else "--") for i, a in enumerate(sorted(fam.index))}


def _grid(n: int, w: float = 5.0, h: float = 3.8):
    cols = min(3, n)
    rows = -(-n // cols)
    fig, axes = plt.subplots(rows, cols, figsize=(w * cols, h * rows), squeeze=False)
    for ax in axes.flat[n:]:
        ax.axis("off")
    return fig, axes


def _legend(fig, axes) -> None:
    handles = {}
    for ax in axes.flat:
        for h, l in zip(*ax.get_legend_handles_labels()):
            handles.setdefault(l, h)
    fig.legend(handles.values(), handles.keys(), loc="lower center", ncol=min(len(handles), 4), frameon=False)
    fig.tight_layout(rect=(0, 0.09, 1, 1))


def plot_latency(lat: pd.DataFrame, out: Path) -> None:
    profiles, style = _profiles(lat), _algorithms(lat)
    pos = {p: i for i, p in enumerate(profiles)}
    ops = _ops(lat)
    fig, axes = _grid(len(ops))
    for ax, op in zip(axes.flat, ops):
        for alg, (color, ls) in style.items():
            d = lat[(lat["operation"] == op) & (lat["algorithm"] == alg) & lat["median_ms"].notna()]
            d = d.assign(_x=d["profile"].map(pos)).sort_values("_x")
            if d.empty:
                continue
            yerr = np.vstack([d["median_ms"] - d["q1_ms"], d["q3_ms"] - d["median_ms"]]).clip(min=0)
            ax.errorbar(d["_x"], d["median_ms"], yerr=yerr, color=color, ls=ls, marker="o", capsize=3, label=alg)
            part = d[d["failure_rate"] > 0]
            ax.plot(part["_x"], part["median_ms"], "o", mfc="white", mec=color, ms=9, zorder=3)
        ax.set_yscale("log")
        ax.set_xticks(range(len(profiles)), profiles)
        ax.set_title(op)
        ax.set_ylabel("median latency (ms)")
        ax.grid(alpha=0.3, which="both")
    _legend(fig, axes)
    fig.suptitle("Latency vs resource profile (bars: IQR; hollow marker: some trials failed)", y=1.0)
    fig.savefig(out / "latency_vs_profile.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_throughput(tp: pd.DataFrame, out: Path) -> None:
    if tp.empty:
        return
    profiles, style = _profiles(tp), _algorithms(tp)
    ops = _ops(tp)
    fig, axes = _grid(len(ops))
    for ax, op in zip(axes.flat, ops):
        n = len(style)
        width = 0.8 / n
        for k, (alg, (color, _)) in enumerate(style.items()):
            d = tp[(tp["operation"] == op) & (tp["algorithm"] == alg)].set_index("profile")
            xs, ys, lo, hi = [], [], [], []
            for i, p in enumerate(profiles):
                if p in d.index and not np.isnan(d.loc[p, "median_ops_per_sec"]):
                    r = d.loc[p]
                    xs.append(i + (k - (n - 1) / 2) * width)
                    ys.append(r["median_ops_per_sec"])
                    lo.append(max(r["median_ops_per_sec"] - r["q1_ops_per_sec"], 0))
                    hi.append(max(r["q3_ops_per_sec"] - r["median_ops_per_sec"], 0))
            ax.bar(xs, ys, width, yerr=[lo, hi], color=color, capsize=2, label=alg)
        ax.set_yscale("log")
        ax.set_xticks(range(len(profiles)), profiles)
        ax.set_title(op)
        ax.set_ylabel("operations / second")
        ax.grid(alpha=0.3, axis="y", which="both")
    _legend(fig, axes)
    fig.suptitle("Throughput (median of batches; bars: IQR)", y=1.0)
    fig.savefig(out / "throughput.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_memory(mem: pd.DataFrame, out: Path) -> None:
    profiles = _profiles(mem)
    algs = sorted(mem["algorithm"].unique())
    panels = [("worker_rss_peak_median_mb", "Worker peak RSS (MB)\nmedian trial, max over operations"),
              ("worker_rss_growth_median_mb", "RSS growth during one operation (MB)\nmedian trial, max over operations"),
              ("container_mem_peak_max_mb", "Container memory peak (MB)\ncgroup, cumulative, includes page cache")]
    colors = plt.get_cmap("viridis")(np.linspace(0.1, 0.9, max(len(profiles), 2)))
    fig, axes = plt.subplots(1, 3, figsize=(17, 4.6))
    for ax, (col, title) in zip(axes, panels):
        agg = mem.groupby(["algorithm", "profile"])[col].max().unstack("profile").reindex(index=algs, columns=profiles)
        width = 0.8 / len(profiles)
        for k, p in enumerate(profiles):
            ax.bar(np.arange(len(algs)) + (k - (len(profiles) - 1) / 2) * width, agg[p].fillna(0), width,
                   color=colors[k], label=p)
        ax.set_xticks(range(len(algs)), algs, rotation=35, ha="right")
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.3, axis="y")
    axes[0].legend(title="profile", frameon=False)
    fig.tight_layout()
    fig.savefig(out / "memory.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_failure(lat: pd.DataFrame, out: Path) -> None:
    profiles = _profiles(lat)
    ops = _ops(lat)
    d = lat.assign(_o=lat["operation"].map({o: i for i, o in enumerate(ops)})).sort_values(["algorithm", "_o"])
    d = d.assign(label=d["algorithm"] + "  " + d["operation"])
    grid = d.pivot(index="label", columns="profile", values="failure_rate").reindex(
        index=list(dict.fromkeys(d["label"])), columns=profiles)
    fig, ax = plt.subplots(figsize=(1.2 * len(profiles) + 4, 0.32 * len(grid) + 1.5))
    im = ax.imshow(grid.to_numpy(float), cmap="Reds", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(profiles)), profiles)
    ax.set_yticks(range(len(grid)), grid.index, fontsize=8)
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            v = grid.iat[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{100 * v:.0f}%", ha="center", va="center", fontsize=8,
                        color="white" if v > 0.6 else "black")
    fig.colorbar(im, ax=ax, label="failure rate (error + timeout + killed + skipped)")
    ax.set_title("Failure rate per algorithm, operation and profile")
    fig.savefig(out / "failure_rate.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--summary", type=Path, default=Path("results/summary"))
    p.add_argument("--out", type=Path, default=Path("results/figures"))
    args = p.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    lat = pd.read_csv(args.summary / "summary_latency.csv")
    tp = pd.read_csv(args.summary / "summary_throughput.csv")
    mem = pd.read_csv(args.summary / "summary_memory.csv")
    plot_latency(lat, args.out)
    plot_throughput(tp, args.out)
    plot_memory(mem, args.out)
    plot_failure(lat, args.out)
    print(f"Wrote figures to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
