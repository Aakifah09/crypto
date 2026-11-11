"""Final graphs and tables (Task 6). Everything is drawn from the raw CSVs via analysis.summarize.

    python -m analysis.plots --trials results/trials.csv --throughput results/throughput.csv \
                             --sizes results/output_sizes.csv --out results/figures

Figures:  latency_vs_profile.png, slowdown_vs_profile.png, memory_comparison.png,
          throughput.png, throughput_slowdown.png, failure_rate.png
Tables:   object_sizes.md / object_sizes.csv  (from Module 1's output_sizes.csv)
Needs matplotlib (pip install -r requirements-analysis.txt).
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter, NullFormatter  # noqa: E402

from .summarize import load_summaries  # noqa: E402
from benchmark.runner import PROFILES  # noqa: E402  (stdlib-only module: the CPU share of each profile)

GROUPS = [("keygen", "Key generation"), ("primary", "Encaps / Sign / Encrypt"),
          ("secondary", "Decaps / Verify / Decrypt")]
OP_GROUP = {"keygen": "keygen", "encaps": "primary", "sign": "primary", "encrypt": "primary",
            "decaps": "secondary", "verify": "secondary", "decrypt": "secondary"}
LABEL = dict(GROUPS)


def op_group(op: str) -> str:
    return OP_GROUP.get(op, op)


def groups_present(rows: list[dict]) -> list[str]:
    present = {op_group(r["operation"]) for r in rows}
    known = [g for g, _ in GROUPS if g in present]
    return known + sorted(present - set(known))


def colours(rows: list[dict]) -> dict[str, Any]:
    cmap = plt.get_cmap("tab10")
    return {a: cmap(i % 10) for i, a in enumerate(sorted({r["algorithm"] for r in rows}))}


def by_alg(rows: list[dict], group: str) -> dict[str, dict[str, dict]]:
    d: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        if op_group(r["operation"]) == group:
            d[r["algorithm"]][r["profile"]] = r
    return d


def _plain_log(ax) -> None:
    """Log axis with plain numbers (0.5, 1, 2) instead of 10^x notation. Minor ticks are only
    labelled when the axis spans less than one decade, otherwise the labels pile up."""
    ax.set_yscale("log")
    f = FuncFormatter(lambda v, _: f"{v:g}")
    ax.yaxis.set_major_formatter(f)
    lo, hi = ax.get_ylim()
    ax.yaxis.set_minor_formatter(f if hi / lo < 10 else NullFormatter())


def _panels(groups: list[str]):
    fig, axes = plt.subplots(1, len(groups), figsize=(5.2 * len(groups), 4.4), squeeze=False)
    return fig, axes[0]


def plot_latency(lat, profiles, path, slowdown=False):
    col, groups = colours(lat), groups_present(lat)
    if not groups:
        return
    fig, axes = _panels(groups)
    for ax, g in zip(axes, groups):
        for alg, per in sorted(by_alg(lat, g).items()):
            xs = [i for i, p in enumerate(profiles) if p in per and per[p].get("median_ms") is not None]
            if not xs:
                continue
            rs = [per[profiles[i]] for i in xs]
            if slowdown:
                rs2 = [(i, r) for i, r in zip(xs, rs) if r.get("slowdown_vs_c0") is not None]
                if not rs2:
                    continue
                x2 = [i for i, _ in rs2]
                ax.plot(x2, [r["slowdown_vs_c0"] for _, r in rs2], marker="o", color=col[alg], label=alg)
                ax.fill_between(x2, [r["slowdown_ci_low"] for _, r in rs2],
                                [r["slowdown_ci_high"] for _, r in rs2], color=col[alg], alpha=0.15)
            else:
                med = [r["median_ms"] for r in rs]
                ax.errorbar(xs, med, yerr=[[m - r["q1_ms"] for m, r in zip(med, rs)],
                                           [r["q3_ms"] - m for m, r in zip(med, rs)]],
                            marker="o", capsize=3, color=col[alg], label=alg)
        if slowdown:
            ax.axhline(1.0, color="grey", lw=0.8, ls="--")
            ax.set_ylabel("slowdown vs C0 (median ratio, 95 % CI band)")
        else:
            _plain_log(ax)
            ax.set_ylabel("median latency, ms (bars = IQR)")
        ax.set_xticks(range(len(profiles)), profiles)
        ax.set_xlabel("resource profile")
        ax.set_title(LABEL.get(g, g))
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _grouped_bars(ax, series: dict[str, dict[str, float]], profiles, colour_by_profile=False):
    """series[category][profile] = value; bars grouped by category, one bar per profile."""
    cats = sorted(series)
    w = 0.8 / max(len(profiles), 1)
    cmap = plt.get_cmap("viridis")
    for j, p in enumerate(profiles):
        xs = [i + j * w - 0.4 + w / 2 for i, c in enumerate(cats) if p in series[c]]
        ys = [series[c][p] for c in cats if p in series[c]]
        ax.bar(xs, ys, w, label=p, color=cmap(j / max(len(profiles) - 1, 1)))
    ax.set_xticks(range(len(cats)), cats, rotation=30, ha="right", fontsize=8)
    ax.grid(axis="y", alpha=0.3)


def plot_memory(mem, profiles, path):
    panels = [("median_worker_peak_rss_kb", "Worker peak RSS, MiB (heaviest operation)"),
              ("median_worker_delta_rss_kb", "Added by setup + call over the\nPython + library baseline, MiB"),
              ("median_container_anon_kb", "Container anonymous memory after the\ncall, MiB (no page cache)")]
    fig, axes = plt.subplots(1, 3, figsize=(17, 4.8))
    for ax, (field, title) in zip(axes, panels):
        s: dict[str, dict[str, float]] = defaultdict(dict)
        for r in mem:
            if r.get(field) is not None:
                s[r["algorithm"]][r["profile"]] = max(s[r["algorithm"]].get(r["profile"], 0), r[field] / 1024)
        if s:
            _grouped_bars(ax, s, profiles)
            ax.set_ylim(0, ax.get_ylim()[1] * 1.3)          # head-room so the legend never covers a bar
            ax.legend(title="profile", fontsize=8, ncol=len(profiles), loc="upper center")
        else:
            ax.text(0.5, 0.5, "no data (cgroup v2 memory files not readable)", ha="center", transform=ax.transAxes)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel("MiB")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_throughput(thr, profiles, path):
    groups = groups_present(thr)
    if not groups:
        return
    fig, axes = _panels(groups)
    for ax, g in zip(axes, groups):
        s = {a: {p: r["median_ops_s"] for p, r in per.items() if r.get("median_ops_s") is not None}
             for a, per in by_alg(thr, g).items()}
        _grouped_bars(ax, s, profiles)
        _plain_log(ax)
        ax.set_ylabel("median throughput, operations/s")
        ax.set_title(LABEL.get(g, g))
    axes[0].legend(title="profile", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_throughput_slowdown(thr, profiles, path):
    """Throughput in C0 / throughput in the profile. The dashed line is the slowdown a fully
    CPU-bound single-threaded process would see under the profile's CPU quota (1 / CPUs, never
    below 1). Only batches that need more CPU time than one quota period can follow it."""
    rows = [r for r in thr if r.get("throughput_slowdown_vs_c0") is not None]
    groups = groups_present(rows)
    if not groups:
        return
    col = colours(rows)
    ideal = [max(1.0, 1.0 / PROFILES[p].cpus) if p in PROFILES and PROFILES[p].cpus else 1.0 for p in profiles]
    fig, axes = _panels(groups)
    for ax, g in zip(axes, groups):
        for alg, per in sorted(by_alg(rows, g).items()):
            xs = [i for i, p in enumerate(profiles) if p in per]
            ax.plot(xs, [per[profiles[i]]["throughput_slowdown_vs_c0"] for i in xs], marker="o", color=col[alg], label=alg)
        ax.plot(range(len(profiles)), ideal, ls="--", color="grey", label="ideal CPU-quota slowdown")
        ax.set_xticks(range(len(profiles)), profiles)
        ax.set_xlabel("resource profile")
        ax.set_ylabel("throughput slowdown vs C0")
        ax.set_title(LABEL.get(g, g))
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_failures(comp, profiles, path):
    rows = sorted({(r["algorithm"], r["operation"]) for r in comp})
    idx = {k: i for i, k in enumerate(rows)}
    fig, axes = plt.subplots(1, 2, figsize=(11, max(2.6, 0.35 * len(rows) + 1.5)), squeeze=False,
                             constrained_layout=True)
    for ax, field, title in zip(axes[0], ["trial_failure_rate", "batch_op_failure_rate"],
                                ["Latency trials failed (%)", "Batch operations not completed (%)"]):
        grid = [[None] * len(profiles) for _ in rows]
        for r in comp:
            if r[field] is not None and r["profile"] in profiles:
                grid[idx[(r["algorithm"], r["operation"])]][profiles.index(r["profile"])] = 100 * r[field]
        im = ax.imshow([[(v if v is not None else float("nan")) for v in row] for row in grid],
                       vmin=0, vmax=100, cmap="Reds", aspect="auto")
        for i, row in enumerate(grid):
            for j, v in enumerate(row):
                ax.text(j, i, "n/a" if v is None else f"{v:.0f}", ha="center", va="center", fontsize=8,
                        color="white" if (v or 0) > 55 else "black")
        ax.set_xticks(range(len(profiles)), profiles)
        if ax is axes[0][0]:
            ax.set_yticks(range(len(rows)), [f"{a} / {o}" for a, o in rows], fontsize=8)
        else:
            ax.set_yticks([])
        ax.set_title(title)
    fig.colorbar(im, ax=axes[0].tolist(), shrink=0.8, label="%")
    fig.savefig(path, dpi=150)
    plt.close(fig)


def object_size_table(sizes_csv: Path, out_dir: Path) -> None:
    """Module 1's output_sizes.csv -> readable table. Variable DER signatures show min to max."""
    def num(v):
        return f"{int(float(v)):,}" if v not in ("", None) else "-"
    cols = [("public_key", "Public key"), ("secret_key", "Secret key"), ("ciphertext", "Ciphertext"),
            ("shared_secret", "Shared secret"), ("signature", "Signature")]
    rows = []
    for r in csv.DictReader(open(sizes_csv, newline="")):
        cells = [r["algorithm"], r.get("family", "")]
        for key, _ in cols:
            v = r.get(key, "")
            if key == "signature" and v == "" and r.get("signature_min") not in ("", None):
                lo, hi = int(float(r["signature_min"])), int(float(r["signature_max"]))
                cells.append(f"{lo} to {hi} (variable)" if lo != hi else num(lo))
            else:
                cells.append(num(v))
        rows.append(cells)
    head = ["Algorithm", "Family"] + [h for _, h in cols]
    md = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(c) + " |" for c in rows]
    (out_dir / "object_sizes.md").write_text("Cryptographic object sizes in bytes\n\n" + "\n".join(md) + "\n")
    with open(out_dir / "object_sizes.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(head)
        w.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--trials", default="results/trials.csv")
    p.add_argument("--throughput", default="results/throughput.csv")
    p.add_argument("--sizes", default="results/output_sizes.csv", help="Module 1 output_sizes.csv")
    p.add_argument("--out", default="results/figures")
    p.add_argument("--run-id")
    p.add_argument("--pool-runs", action="store_true")
    a = p.parse_args(argv)
    s = load_summaries(a.trials, a.throughput, a.run_id, a.pool_runs)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    plot_latency(s["latency"], s["profiles"], out / "latency_vs_profile.png")
    plot_latency(s["latency"], s["profiles"], out / "slowdown_vs_profile.png", slowdown=True)
    plot_memory(s["memory"], s["profiles"], out / "memory_comparison.png")
    plot_throughput(s["throughput"], s["profiles"], out / "throughput.png")
    plot_throughput_slowdown(s["throughput"], s["profiles"], out / "throughput_slowdown.png")
    plot_failures(s["completion"], s["profiles"], out / "failure_rate.png")
    if Path(a.sizes).exists():
        object_size_table(Path(a.sizes), out)
    else:
        print(f"note: {a.sizes} not found, object-size table skipped")
    print(f"figures and tables written to {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
