# PQC Benchmark

Compares post-quantum algorithms (ML-KEM, ML-DSA via liboqs) with classical baselines (RSA-2048-OAEP, ECDSA P-256 via pyca/cryptography).

- **Module 1** (algorithms and correctness): `benchmark/algorithms.py`, `benchmark/correctness.py`. Described in the sections below.
- **Module 2** (performance measurement, data and analysis): the section *Module 2: performance measurement* below.
- **Module 3** (resource constraints and experimental results): the section *Module 3: resource constraints and experimental results* below.

## Layout

| Path | Purpose |
|---|---|
| `benchmark/algorithms.py` | Uniform implementations of all algorithms and an availability check |
| `benchmark/workloads.py` | Fixed 1,024-byte signature message and 32-byte RSA payload |
| `benchmark/correctness.py` | Correctness checks that must pass before benchmarking |
| `benchmark/environment.py` | Records versions, build commit, image digest, enabled algorithm names and container limits |
| `tests/test_fault_injection.py` | Self-test: breaks each algorithm on purpose and confirms the checks catch it |
| `benchmark/measure.py` | Module 2: timing utility, worker RSS and cgroup readers |
| `benchmark/runner.py` | Module 2: trial runner, throughput batches, CSV logging, resource profiles C0 to C3 |
| `analysis/summarize.py` | Module 2: statistics (median, IQR, p95, slowdown vs C0, throughput, completion and failure rates) |
| `analysis/plots.py` | Module 2: graphs and the object-size table |
| `scripts/run_profiles.py` | Module 2: starts one container per profile, in random order |
| `scripts/make_example_data.py` | Module 2: generates the synthetic example CSVs |
| `tests/test_measurement.py`, `tests/fixtures.py` | Module 2 self-test and test functions |
| `results/` | Module 1 correctness output; Module 2 raw data, summaries and figures; Module 3 experimental results |
| `sustained/`, `sustained_long/` | Module 2 sustained-load runs |
| `examples/` | Synthetic example data (not real measurements) |
| `docs/module1_test_report.md` | Module 1 test report |
| `docs/module2_statistical_analysis.md` | Module 2 method, limits and findings |
| `docs/module3_resource_constraints.md` | Module 3 resource constraints, experimental methodology, findings and limitations |
| `results/filtered/` | Module 3 primary latency and throughput datasets |
| `results/summary_nov12/` | Module 3 experimental summaries |
| `results/figures_nov12/` | Module 3 experimental graphs |
| `results/validation/` | Module 3 validation evidence |

Everything runs inside Docker, as the report specifies (Sec. 4.1): liboqs is compiled at a pinned version inside the image, and the resource profiles C0–C3 are Docker CPU/memory limits.

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows / macOS) or Docker Engine (Linux), **running**
- Internet access for the first build (it downloads and compiles liboqs: a few minutes the first time, seconds after that)

Module 1 needs nothing else on your machine: no Python, compiler or CMake.

Module 2's profile driver (`scripts/run_profiles.py`) is a small standard-library Python script and needs Python 3 on the host. Without it, start each profile by hand with the Docker commands shown in the Module 2 section (`--dry-run` prints them).

## Run

From the repository folder:

```bash
docker build -t pqc-benchmark .
```

Then run the correctness checks (pick your shell):

```powershell
# Windows PowerShell
docker run --rm -v "${PWD}\results:/app/results" pqc-benchmark
```
```bat
:: Windows Command Prompt
docker run --rm -v "%cd%\results:/app/results" pqc-benchmark
```
```bash
# macOS / Linux / Git Bash
docker run --rm -v "$(pwd)/results:/app/results" pqc-benchmark
```

Expected ending: `ALL CHECKS PASSED`. The `results/` folder is then refreshed.

More trials: append `python -m benchmark.correctness --trials 500` to the run command.

Exit status: `0` means all checks passed, `1` means a check failed, `2` means a required algorithm is missing from liboqs. Only benchmark after status `0`.

Self-test (proves the checks catch broken algorithms):

```bash
docker run --rm pqc-benchmark python -m tests.test_fault_injection
```

Expected ending: `SELF-TEST PASSED`.

## Using the algorithms from other modules

```python
from benchmark.algorithms import get_algorithms
from benchmark.workloads import SIGNATURE_MESSAGE, RSA_PAYLOAD

for alg in get_algorithms():          # only algorithms that are available
    pk, sk = alg.keygen()             # timed: key generation
    skh = alg.load_secret_key(sk)     # setup: do this BEFORE starting the timer
    if alg.kind == "kem":
        ct, ss = alg.encaps(pk); alg.decaps(skh, ct)
    elif alg.kind == "signature":
        sig = alg.sign(skh, SIGNATURE_MESSAGE); alg.verify(pk, SIGNATURE_MESSAGE, sig)
    elif alg.kind == "pke":
        ct = alg.encrypt(pk, RSA_PAYLOAD); alg.decrypt(skh, ct)
```

Time each operation call on its own. Keep `load_secret_key` and any correctness comparisons outside the timed block (report Sec. 4.4).

Run your own scripts inside the container too (liboqs is only installed there):
`docker run --rm -v "$(pwd):/app" pqc-benchmark python your_script.py`.

## Module 2: performance measurement

Measures, for every algorithm and operation under each resource profile: latency (5 discarded warm-ups, 30 recorded trials), throughput (5 batches of 100 operations), worker peak RSS, container memory, CPU throttling and failures. Every warm-up, trial and batch runs in its own fresh Python process. Failed trials (exceptions, wrong results, timeouts, OOM kills, crashes) are logged as rows with `success = 0`; they are never dropped.

| Profile | Docker flags |
|---|---|
| C0 | none |
| C1 | `--cpus=1 --memory=512m --memory-swap=512m` |
| C2 | `--cpus=0.5 --memory=256m --memory-swap=256m` |
| C3 | `--cpus=0.25 --memory=128m --memory-swap=128m` |

### Run the benchmark

1. Run the Module 1 correctness check first (above). The runner refuses to start unless `results/correctness.json` says PASS for every algorithm.
2. From the repository folder, on the host:

```bash
python scripts/run_profiles.py --repeat 2
```

This starts one container per profile (C0 to C3) in random order and does the whole sweep twice. It took about 25 minutes per sweep on the authors' laptop. Run it from a standalone terminal (not one that you will close), keep the laptop plugged in and awake, and do not use the machine meanwhile. Options for the runner go after `--`, for example `-- --trials 5 --targets ML-KEM-512`; `--dry-run` only prints the Docker commands.

To run a single profile by hand:

```powershell
docker run --rm --cpus=0.25 --memory=128m --memory-swap=128m -v "${PWD}\results:/app/results" pqc-benchmark python -m benchmark.runner --profile C3
```

The runner reads the limits the container really has and stops (exit status 3) if they do not match the profile. Exit status 4 means the correctness gate has not passed.

### Tables and graphs

```powershell
# Windows PowerShell
docker run --rm -v "${PWD}\results:/app/results" pqc-benchmark python -m analysis.summarize --pool-runs
docker run --rm -v "${PWD}\results:/app/results" pqc-benchmark python -m analysis.plots --pool-runs
```
```bash
# macOS / Linux / Git Bash
docker run --rm -v "$(pwd)/results:/app/results" pqc-benchmark python -m analysis.summarize --pool-runs
docker run --rm -v "$(pwd)/results:/app/results" pqc-benchmark python -m analysis.plots --pool-runs
```

`--pool-runs` merges the sweeps (60 trials per cell for `--repeat 2`); without it only the latest run per profile is used, and `--run-id <id>` selects one run.

| Output | Content |
|---|---|
| `results/trials.csv` | one row per recorded latency trial (latency, memory, output sizes, success, error type, CPU throttling) |
| `results/throughput.csv` | one row per recorded batch of 100 operations |
| `results/run_meta_<run id>_<profile>.json` | configuration, environment and the limits seen inside the container |
| `results/summary/` | median, IQR, p95, slowdown vs C0, throughput, completion and failure rates, memory, size check, `summary_tables.md` |
| `results/figures/` | latency, slowdown, memory, throughput, throughput-slowdown and failure-rate graphs, `object_sizes.md` |

### Sustained-load runs

Short operations never use up a CPU quota, so the profiles only show up in long batches. These runs write to their own folders and have no latency trials:

```bash
python scripts/run_profiles.py --results sustained -- --skip-correctness-check --trials 0 --warmups 0 --batches 3 --batch-size 10000 --operations encaps,decaps,sign,verify,encrypt,decrypt
python scripts/run_profiles.py --profiles C0,C2,C3 --results sustained_long -- --skip-correctness-check --trials 0 --warmups 0 --batches 3 --batch-size 100000 --targets ML-KEM-512,ML-KEM-768 --operations encaps,decaps
```

### Measure your own function

The runner is not tied to the algorithms. Any zero-argument function can be a target:

```bash
docker run --rm pqc-benchmark python -m benchmark.runner --profile C0 --out /tmp/demo --targets fn:tests.fixtures:ok_fn --trials 5 --batches 1
```

`python -m benchmark.runner --help` lists all options (`--targets`, `--operations`, `--trials`, `--warmups`, `--batches`, `--batch-size`, `--timeout`, `--settle-ms`, `--seed`).

### Module 2 self-test

```bash
docker run --rm pqc-benchmark python -m tests.test_measurement
```

Expected ending: `SELF-TEST PASSED`. It runs the framework on test functions and on the classical algorithms, checks the CSV format, that failures are recorded, and that the summary statistics can be reproduced from the raw rows.

Method, assumptions, limits and findings: `docs/module2_statistical_analysis.md`. `examples/` holds synthetic data (from `scripts/make_example_data.py`) that shows the file formats; it is not a measurement of anything.


## Module 3: resource constraints and experimental results

Module 3 evaluates the cryptographic algorithms under simulated resource-constrained environments. Docker CPU and memory limits were used on a laptop running Ubuntu through WSL2.

### Resource profiles

| Profile | CPU limit | Memory limit |
|---|---:|---:|
| C0 | Unrestricted | Unrestricted |
| C1 | 1 CPU | 512 MiB |
| C2 | 0.5 CPU | 256 MiB |
| C3 | 0.25 CPU | 128 MiB |

For C1–C3, no additional swap was available. The benchmark runner verifies the actual resource limits before allowing an experiment to proceed.

### Experimental setup

The main experiments were conducted on 12 November 2026. Two complete benchmark sweeps were performed across all four profiles.

- 5 warm-up iterations per operation.
- 30 recorded latency trials per operation and profile.
- 5 throughput batches per operation and profile.
- 100 operations per throughput batch.
- Worker memory, container memory, CPU throttling and execution failures were recorded.

### Primary experimental results

| Measurement | Total |
|---|---:|
| Recorded latency trials | 4,320 |
| Throughput batches | 720 |
| Throughput operations | 72,000 |

All recorded trials and throughput batches in the primary dataset completed successfully. No out-of-memory failures were recorded.

The experiments also measured worker peak memory, container memory and cryptographic object sizes, comparing post-quantum algorithms (ML-KEM and ML-DSA) with classical baselines (RSA and ECDSA).

### Results and documentation

| Path | Description |
|---|---|
| `docs/module3_resource_constraints.md` | Full experimental methodology, environment, findings and limitations |
| `results/filtered/trials.csv` | Primary latency-trial dataset |
| `results/filtered/throughput.csv` | Primary throughput dataset |
| `results/summary_nov12/` | Completion, latency, memory, throughput and object-size summaries |
| `results/figures_nov12/` | Latency, throughput, memory, slowdown and failure-rate graphs |
| `results/validation/fault_injection_test.log` | Fault-injection validation output |
| `results/run_meta_*.json` | Individual experiment configuration and environment metadata |

### Validation

The contribution included cryptographic correctness checks, fault-injection tests, resource-profile verification and validation of benchmark output.

The benchmark runner was hardened to stop execution if required cgroup resource limits could not be verified.

### Limitations

The resource constraints were simulated using Docker on WSL2. They do not directly reproduce the processor architecture, power consumption, thermal behaviour or hardware characteristics of physical IoT devices. These results represent software-controlled resource-constrained experiments, not direct measurements on physical IoT hardware.

## Troubleshooting

- `failed to connect to the docker API` means Docker Desktop is not running. Start it and retry.
- Output appears to stop after `liboqs-python faulthandler is disabled`. That line is normal; the checks take about 30 seconds.
- `PROFILE MISMATCH` (exit status 3): the container was not started with the limits of the profile named in `--profile`. Use `scripts/run_profiles.py`, which passes the right flags.
- `correctness gate failed` or `correctness.json not found` (exit status 4): run `python -m benchmark.correctness` first and make sure it ends with `ALL CHECKS PASSED`.
- `has a different header; refusing to append to it`: `trials.csv` or `throughput.csv` in that folder comes from an older version of the runner. Move or delete the old file.
- A Module 2 run that was interrupted leaves partial rows in `trials.csv` and `throughput.csv`. Delete both (not the Module 1 files) and start again; there is no resume.

## Pinned versions

liboqs 0.16.0, liboqs-python 0.16.0.2, cryptography 46.0.7, Python 3.11, matplotlib 3.11.2.