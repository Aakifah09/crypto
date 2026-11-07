"""Generate SYNTHETIC example CSVs to demonstrate the pipeline (not real measurements).

Runs the real runner on tests.fixtures:synthetic_fn once per profile label, with a made-up
slowdown factor and failure rate injected through environment variables. The numbers mean
nothing about any cryptographic algorithm; they only show the file formats, the failure
rows and that summarize/plots recover the injected slowdowns to within a few percent (C1 x1.5, C2 x3, C3 x6).

    python scripts/make_example_data.py [--out examples]
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

SYNTH = {"C0": ("1", "0"), "C1": ("1.5", "0"), "C2": ("3", "0.05"), "C3": ("6", "0.20")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="examples")
    a = ap.parse_args()
    out = Path(a.out)
    for f in ("trials.csv", "throughput.csv"):
        (out / f).unlink(missing_ok=True)
    for profile, (slow, fail) in SYNTH.items():
        env = {**os.environ, "SYNTH_SLOWDOWN": slow, "SYNTH_FAIL_RATE": fail}
        cmd = [sys.executable, "-m", "benchmark.runner", "--profile", profile, "--out", str(out),
               "--run-id", "example-synthetic", "--targets", "fn:tests.fixtures:synthetic_fn",
               "--skip-correctness-check", "--allow-profile-mismatch", "--batch-size", "100"]
        subprocess.run(cmd, env=env, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())