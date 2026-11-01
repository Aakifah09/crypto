# PQC Benchmark

Compares post-quantum algorithms (ML-KEM, ML-DSA via liboqs) with classical baselines (RSA-2048-OAEP, ECDSA P-256 via pyca/cryptography).

## Layout

| Path | Purpose |
|---|---|
| `benchmark/algorithms.py` | Uniform implementations of all algorithms and an availability check |
| `benchmark/workloads.py` | Fixed 1,024-byte signature message and 32-byte RSA payload |
| `benchmark/correctness.py` | Correctness checks that must pass before benchmarking |
| `benchmark/environment.py` | Records versions, build commit, image digest, enabled algorithm names and container limits |
| `tests/test_fault_injection.py` | Self-test: breaks each algorithm on purpose and confirms the checks catch it |
| `results/` | Output of the correctness run |
| `docs/module1_test_report.md` | Module 1 test report |

Everything runs inside Docker, as the report specifies (Sec. 4.1): liboqs is compiled at a pinned version inside the image, and the resource profiles C0–C3 are Docker CPU/memory limits.

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows / macOS) or Docker Engine (Linux), **running**
- Internet access for the first build (it downloads and compiles liboqs: a few minutes the first time, seconds after that)

Nothing else is needed on your machine: no Python, compiler or CMake.

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

## Troubleshooting

- `failed to connect to the docker API` means Docker Desktop is not running. Start it and retry.
- Output appears to stop after `liboqs-python faulthandler is disabled`. That line is normal; the checks take about 30 seconds.

## Pinned versions

liboqs 0.16.0, liboqs-python 0.16.0.2, cryptography 46.0.7, Python 3.11.
