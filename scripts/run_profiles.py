"""Host-side driver: one Docker container per resource profile, profiles in randomised order.

Profiles are Docker limits, so they cannot be switched from inside a container. This script
starts one container per profile with the flags from benchmark.runner.PROFILES, and the
runner inside checks that the limits really match the label before it measures anything.
Needs only the Python standard library on the host (and Docker).

    python scripts/run_profiles.py --image pqc-benchmark                # all four profiles
    python scripts/run_profiles.py --repeat 2 --dry-run                  # print the commands only
Extra runner options go after --, e.g.   ... -- --trials 10 --targets ML-KEM-512

--repeat N runs the whole sweep N times (new run_id and new random profile order each time),
which spreads slow drift (thermal state, background load) across profiles. Pool the repeats
in the analysis with --pool-runs.
"""
from __future__ import annotations

import argparse
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark.runner import PROFILES  # noqa: E402  (stdlib-only import, safe on the host)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", default="pqc-benchmark")
    ap.add_argument("--profiles", default=",".join(PROFILES))
    ap.add_argument("--results", default="results", help="host folder mounted at /app/results")
    ap.add_argument("--order", choices=["random", "fixed"], default="random")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("runner_args", nargs="*", help="passed to benchmark.runner (put them after --)")
    a = ap.parse_args()

    rng = random.Random(a.seed)
    results = Path(a.results).resolve()
    results.mkdir(parents=True, exist_ok=True)
    worst = 0
    for rep in range(a.repeat):
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + (f"-r{rep + 1}" if a.repeat > 1 else "")
        order = a.profiles.split(",")
        if a.order == "random":
            rng.shuffle(order)
        print(f"== sweep {rep + 1}/{a.repeat}, run_id {run_id}, profile order: {' '.join(order)}", flush=True)
        for name in order:
            cmd = ["docker", "run", "--rm", "--name", f"pqc-{name}-{run_id}", *PROFILES[name].docker_flags(),
                   "-v", f"{results}:/app/results", a.image,
                   "python", "-m", "benchmark.runner", "--profile", name, "--run-id", run_id,
                   "--out", "results", *a.runner_args]
            print("$ " + " ".join(cmd), flush=True)
            if a.dry_run:
                continue
            rc = subprocess.run(cmd).returncode
            if rc != 0:   # e.g. 137 = the container itself was OOM-killed: keep going, report at the end
                print(f"!! profile {name} exited with status {rc}", file=sys.stderr)
            worst = max(worst, rc)
    return worst


if __name__ == "__main__":
    sys.exit(main())