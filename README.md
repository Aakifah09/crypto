# PQC Benchmark

Compares post-quantum algorithms (ML-KEM, ML-DSA via liboqs) with classical baselines (RSA-2048-OAEP, ECDSA P-256 via pyca/cryptography).

## Layout

| Path | Purpose |
|---|---|
| `benchmark/algorithms.py` | Uniform implementations of all algorithms and an availability check |
| `benchmark/workloads.py` | Fixed 1,024-byte signature message and 32-byte RSA payload |
| `benchmark/correctness.py` | Correctness checks that must pass before benchmarking |
| `benchmark/environment.py` | Records library versions and enabled algorithm names |
| `results/` | Output of the correctness run |
| `docs/module1_test_report.md` | Module 1 test report |

There are two ways to run it. Both use the same pinned versions and give the same results. Pick whichever fits your machine.

## Option A: Without Docker

You need **Python 3.9+** and a **C compiler** (used once to build liboqs):

| OS | How to get a C compiler |
|---|---|
| Windows | Install [Build Tools for Visual Studio](https://visualstudio.microsoft.com/visual-cpp-build-tools/) and tick **"Desktop development with C++"**. Open a new terminal afterwards. |
| macOS | `xcode-select --install` |
| Linux | `sudo apt install build-essential` (Debian/Ubuntu) |

Then, from the repository folder:

```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

python setup_liboqs.py              # one time: installs packages, builds liboqs into ~/_oqs (a few minutes)
python -m benchmark.correctness     # run the checks
```

Expected ending: `ALL CHECKS PASSED`. `setup_liboqs.py` can be re-run safely; it skips the build if liboqs is already installed.

## Option B: With Docker

You need [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine on Linux), **running**. Nothing else: no Python or compiler needed.

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

## Using the algorithms from other modules

```python
from benchmark.algorithms import get_algorithms
from benchmark.workloads import SIGNATURE_MESSAGE, RSA_PAYLOAD

for alg in get_algorithms():          # only algorithms that are available
    pk, sk = alg.keygen()
    if alg.kind == "kem":
        ct, ss = alg.encaps(pk); alg.decaps(sk, ct)
    elif alg.kind == "signature":
        sig = alg.sign(sk, SIGNATURE_MESSAGE); alg.verify(pk, SIGNATURE_MESSAGE, sig)
    elif alg.kind == "pke":
        ct = alg.encrypt(pk, RSA_PAYLOAD); alg.decrypt(sk, ct)
```

With Option A, run that code normally (`python your_script.py`). With Option B, run it inside the container:
`docker run --rm -v "$(pwd):/app" pqc-benchmark python your_script.py`.

## Troubleshooting

- `No C compiler found` / `CMake could not configure the build` means the C compiler from Option A is missing. Install it, open a new terminal, and re-run `python setup_liboqs.py`.
- `liboqs-python` starts trying to download and build liboqs by itself. That means `setup_liboqs.py` was not run (or failed). Stop it (Ctrl+C) and run the setup script.
- `failed to connect to the docker API` means Docker Desktop is not running. Start it and retry.
- Output appears to stop after `liboqs-python faulthandler is disabled`. That line is normal; the checks take about 30 seconds.

## Pinned versions

liboqs 0.16.0, liboqs-python 0.16.0.2, cryptography 46.0.7, Python 3.11.
