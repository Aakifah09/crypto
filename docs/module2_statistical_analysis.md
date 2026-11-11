# Module 2: Statistical Analysis Method

**Project:** Performance Analysis of Post-Quantum Cryptographic Algorithms Under Simulated Resource Constraints for IoT Applications
**Module owner:** Soorya Kiran Kakkarayil
**Code:** `benchmark/measure.py`, `benchmark/runner.py`, `analysis/summarize.py`, `analysis/plots.py`

## 1. What is measured

| Quantity | How | Unit |
|---|---|---|
| Latency | `time.perf_counter_ns()` around exactly one call; setup, input generation and correctness checks are outside the timer | ms |
| Throughput | 5 batches of 100 back-to-back operations; `completed operations / wall-clock time of the whole batch` (first call to last call, including a few microseconds of progress bookkeeping) | operations/s |
| Worker memory | `VmHWM` (peak RSS) of the worker process, plus `VmRSS` right after imports as a baseline | kB |
| Container memory | cgroup v2, sampled inside the worker right after the timed call: anonymous memory (`memory.stat`, no page cache) and `memory.current` (with page cache). `memory.peak` is also read, but see limit 5 | kB |
| Failures | exception, wrong result, 120 s timeout, OOM kill, crash; each one is a row with `success = 0` and an `error_type` | count |
| CPU throttling | change in cgroup `nr_throttled` / `throttled_usec` between just before and just after the timed call (`timed_throttled_*`). The whole-worker values (`throttled_*`) include process start-up, which is always throttled under a small quota, and must not be read as "the timed call was throttled" | periods, ms |

Each warm-up, trial and batch runs in its own fresh Python process with fresh keys. Per cell (algorithm, operation, profile) there are 5 discarded warm-ups, 30 recorded trials and 5 recorded batches. Run order is randomised with a recorded seed.

## 2. Statistics

All statistics are computed from the raw CSV by `analysis/summarize.py`; nothing is typed in by hand.

- **Median latency**, **Q1/Q3** and **IQR = Q3 − Q1**, quartiles by linear interpolation. Medians and IQR are used because latency is right-skewed (scheduler noise only ever adds time).
- **95th percentile and maximum** are reported next to them (extra, not in the task list). CPU quotas act on whole 100 ms scheduling periods, so an operation that fits inside the quota is untouched and one that straddles a period boundary waits for the next period. That produces rare, large outliers that the median and IQR do not show.
- **Slowdown vs C0** = median latency in the profile / median latency in C0, for the same algorithm and operation, with a 95 % percentile bootstrap interval (2,000 resamples of each sample, fixed seed). A ratio whose interval contains 1 is not evidence of a slowdown.
- **Throughput** = median over successful batches. **Throughput slowdown** = median ops/s in C0 / median ops/s in the profile.
- **Completion and failure rates** = successful / attempted for trials, and completed / attempted operations for batches. Error types are tallied per cell.

## 3. How failures are handled

Failed runs are never removed from the raw files. Latency and throughput statistics use successful runs only, so under heavy constraints they describe the survivors. A cell with 40 % failures and a healthy-looking median is a cell where the median is hiding the problem. Always read the median next to `trial_failure_rate`. A cell with no successful run gets no latency statistics and shows `n/a`.

A batch that fails part-way (exception, timeout, OOM) keeps the number of operations that finished. When the worker was killed this count comes from a memory-mapped counter updated every 10 operations, so it is exact to within one block of 10.

## 4. Assumptions and limits

1. **n = 30 per cell** gives wide bootstrap intervals for ratios of fast operations; the interval is reported so that this is visible.
2. **Every timed call starts with a full CPU quota.** After setup and the priming call, each worker collects garbage and sleeps 120 ms (`--settle-ms`), slightly more than one 100 ms scheduling period, and only then reads the counters and starts the timer. Without the sleep, the quota left at that moment depends on how much CPU start-up burned, and a throttle stall lands inside or just outside the timed region more or less at random (smoke data: about half of the stalled batches showed the stall outside their measured time). With it, a call or batch that needs less CPU than the quota is not throttled, and a longer one is stalled deterministically. The measured quantity is therefore "an isolated operation or batch started on an idle device", not "an operation in the middle of sustained load". Sustained load needs larger batches (`--batch-size`).
3. **Fresh process per run, one priming call.** Each worker makes one untimed call before the timed one, so lazy initialisation (for example liboqs context creation, which Module 1 measured as doubling a decapsulation time) is not counted. Cold-start cost is therefore not measured.
4. **CPU limits are quotas, not slower clocks.** A 0.25-CPU profile allows 25 ms of CPU per 100 ms. Operations of tens of microseconds will mostly show a slowdown near 1 regardless of profile; only operations or batches that need a meaningful fraction of the quota (RSA key generation, large batches) can be throttled. A slowdown near 1 is a valid result, not a harness failure. Throttling shows up as stalls, not as a smooth slowdown: a call or batch that runs out of quota waits for the next 100 ms period. A batch of 100 operations that each take about 0.15 ms, hit by one stall, ends up near 1,200 operations/s whatever the operation is (about 15 ms of work plus a wait of up to 100 ms), so batch medians can flip between "no effect" and "stalled" depending on how many batches hit one. The `timed_throttled_*` columns and the `trials_throttled_in_timed_call` / `batches_throttled` summary columns say which runs were hit.
5. **Memory.** Worker peak RSS includes the interpreter, imported libraries and the untimed setup, not only the algorithm call. It is the main per-trial memory metric; the interpreter and imported libraries alone account for about 26 MiB of it, so `median_worker_delta_rss_kb` (peak minus the baseline taken right after the imports) is the part attributable to key setup and the call, and is what differs between algorithms. Inside the container the cgroup files are read-only, so `memory.peak` cannot be reset (`container_peak_reset = 0`): `container_mem_peak_kb` is then a container-lifetime high-water mark that is the same on every row and is mostly page cache. Use `container_anon_kb` (anonymous memory of the whole container, i.e. runner plus worker, no page cache) for container memory.
6. **Profiles are run as separate container blocks**, not interleaved in time. Trial order inside a block is randomised, profile order is randomised by `scripts/run_profiles.py`, and `--repeat` repeats the whole sweep. Drift between blocks is reduced, not removed.
7. **Output sizes** must not change with the profile (report Sec. 4.5). `size_check.csv` flags any size that varies; the only expected variations are DER-encoded outputs: the ECDSA signature (69 to 72 bytes in the data) and the RSA PKCS#8 private key (1,214 to 1,219 bytes in the data).
8. Results come from one laptop (Docker Desktop on WSL2). They compare algorithms and profiles on that machine; they do not predict absolute timings on an IoT device.

## 5. Reproducing the tables and graphs

Main run (4 profiles, run twice, in random profile order each time), then the tables and graphs, all inside the container:

```
python scripts/run_profiles.py --repeat 2
docker run --rm -v "${PWD}\results:/app/results" pqc-benchmark python -m analysis.summarize --pool-runs
docker run --rm -v "${PWD}\results:/app/results" pqc-benchmark python -m analysis.plots --pool-runs
```

`analysis.plots` writes `latency_vs_profile.png`, `slowdown_vs_profile.png`, `throughput.png`, `throughput_slowdown.png` (throughput in C0 / throughput in the profile, with the ideal CPU-quota slowdown as a dashed line), `memory_comparison.png`, `failure_rate.png` and the object-size table (`object_sizes.md`, `object_sizes.csv`).

Sustained-load runs (batches long enough to exceed the CPU quota; no latency trials). Their output folders have no latency data, so only the throughput and throttling tables and figures are meaningful:

```
python scripts/run_profiles.py --results sustained -- --skip-correctness-check --trials 0 --warmups 0 --batches 3 --batch-size 10000 --operations encaps,decaps,sign,verify,encrypt,decrypt
python scripts/run_profiles.py --profiles C0,C2,C3 --results sustained_long -- --skip-correctness-check --trials 0 --warmups 0 --batches 3 --batch-size 100000 --targets ML-KEM-512,ML-KEM-768 --operations encaps,decaps
docker run --rm -v "${PWD}\sustained:/app/results" pqc-benchmark python -m analysis.summarize --pool-runs
docker run --rm -v "${PWD}\sustained_long:/app/results" pqc-benchmark python -m analysis.summarize --pool-runs
```

`examples/` holds a synthetic data set (generated by `scripts/make_example_data.py`) that shows the file formats and lets the pipeline be checked against known slowdowns. It contains no real measurements.

## 6. Findings

Data: `results/` (4 profiles, 18 algorithm/operation cells, 2 sweeps = 60 trials and 10 batches of 100 operations per cell), `sustained/` (3 batches of 10,000 operations per cell, encaps/decaps/sign/verify/encrypt/decrypt only) and `sustained_long/` (3 batches of 100,000 operations, ML-KEM-512 and ML-KEM-768 encaps/decaps only, C0, C2 and C3). One laptop, Docker Desktop on WSL2.

**Reliability.** 0 failures in 4,320 recorded trials and 720 batches, and none in the warm-ups: no exceptions, wrong results, timeouts or OOM kills in any profile. Every run verified that the container limits matched its profile.

**Single-operation latency is not affected by the profiles.** For every operation except RSA-2048 key generation, the median latency in C1, C2 and C3 is between x0.97 and x1.09 of C0. These operations take about 0.1 to 0.5 ms, far below the 25 ms of CPU a C3 container gets per 100 ms, so a call that starts with a full quota is never throttled (0 of 60 trials throttled in each such cell). The 95 % bootstrap intervals are within a few percent for most cells; ML-DSA signing is wider (for example x0.92 to x1.27 for ML-DSA-65 in C3) because its signing time varies from call to call (rejection sampling).

**RSA-2048 key generation is the exception.** Its median is 61 ms in C0 (95th percentile 187 ms). In C3 it is x2.88 (interval 1.62 to 3.90) and 54 of 60 trials hit throttling. In C2, 19 of 60 trials hit throttling but the median did not visibly change (x0.94, interval 0.73 to 1.29).

**Short batches (100 operations).** Only the slow operations are affected. RSA key generation runs at 14.9 operations/s in C0, 15.3 in C1, 7.5 in C2 (x2.0) and 3.6 in C3 (x4.2). RSA decryption drops from 2,213 to 1,176 operations/s in C3 (x1.9, 10 of 10 batches throttled; in C2 1 of 10). A 100-operation RSA decryption batch needs about 45 ms of CPU, more than one C3 quota period (25 ms), so it is throttled; the quota available at its start is why the slowdown is below the x4 seen with long batches. All ML-KEM, ML-DSA and ECDSA batches and RSA encryption were not throttled in any profile.

**Sustained throughput falls in proportion to the CPU quota, for classical and post-quantum algorithms alike.** Throughput slowdown vs C0, 10,000-operation batches (median of 3 batches per cell):

| Algorithm | Operation | C1 | C2 | C3 |
|---|---|---|---|---|
| ECDSA-P256-SHA256 | sign | x0.99 | x1.78 | x3.74 |
| ECDSA-P256-SHA256 | verify | x0.98 | x1.93 | x3.89 |
| ML-DSA-44 | sign | x0.99 | x1.95 | x3.87 |
| ML-DSA-44 | verify | x1.03 | x1.79 | x3.84 |
| ML-DSA-65 | sign | x1.00 | x1.95 | x3.98 |
| ML-DSA-65 | verify | x1.00 | x1.86 | x3.76 |
| ML-KEM-512 | decaps | x1.00 | x1.34 | x3.46 |
| ML-KEM-512 | encaps | x1.01 | x1.42 | x3.29 |
| ML-KEM-768 | decaps | x1.09 | x1.58 | x3.48 |
| ML-KEM-768 | encaps | x1.00 | x1.57 | x3.52 |
| RSA-2048-OAEP-SHA256 | decrypt | x1.00 | x1.98 | x4.00 |
| RSA-2048-OAEP-SHA256 | encrypt | x1.01 | x1.85 | x3.82 |

Every cell was throttled in 3 of 3 batches at C2 and C3 and in none at C0 and C1. C1 (1 CPU) shows no slowdown (x0.98 to x1.09; the x1.09 is one ML-KEM-768 cell with 3 batches). For ECDSA, ML-DSA and RSA the slowdown is x1.8 to x2.0 at C2 and x3.7 to x4.0 at C3, matching the x2 and x4 of a fully CPU-bound process under a 0.5 and a 0.25 CPU quota. ML-KEM is lower with 10,000-operation batches (x1.3 to x1.6 at C2, x3.3 to x3.5 at C3), because one such batch needs only 140 to 180 ms of CPU and the unused quota at the start of the batch is then a large share of the total. With 100,000-operation batches (`sustained_long/`) ML-KEM follows the quota like the others:

| Algorithm | Operation | C2 | C3 |
|---|---|---|---|
| ML-KEM-512 | decaps | x1.98 | x3.94 |
| ML-KEM-512 | encaps | x1.94 | x4.00 |
| ML-KEM-768 | decaps | x1.98 | x3.93 |
| ML-KEM-768 | encaps | x1.98 | x3.99 |

Each cell has only 3 batches, so differences of a few percent are noise.

**Memory is unaffected by the profiles.** Worker peak RSS is 26.9 to 30.7 MiB, and within one algorithm and operation it differs by at most 0.15 MiB between profiles. About 26 MiB of it is the Python interpreter and imported libraries (baseline after the imports: 25.8 to 26.0 MiB). Key setup and the operation add 1.0 to 1.3 MiB for RSA, 1.4 to 1.8 MiB for ECDSA and 4.7 to 4.8 MiB for ML-KEM and ML-DSA. Container anonymous memory is 27.8 to 30.7 MiB. The smallest memory limit used (C3, 128 MiB) is more than four times the worker peak, so no memory failure occurred.

**Output sizes** are fixed for ML-KEM and ML-DSA objects and for RSA ciphertexts. Only DER-encoded outputs vary: ECDSA signatures 69 to 72 bytes, RSA PKCS#8 private keys 1,214 to 1,219 bytes.

**Absolute speed differs between algorithms and is not uniformly in favour of either family.** In C0 with 10,000-operation batches, ECDSA signs about 2.4 times faster than ML-DSA-44 (25,190 against 10,480 operations/s) and ML-DSA-44 verifies about 3.2 times faster than ECDSA (30,320 against 9,332). These numbers include the Python call overhead of liboqs-python and pyca/cryptography, which was not measured separately.

**What this does and does not show.** Under Docker CPU quotas, post-quantum algorithms are not slowed more than classical ones: any CPU-bound workload slows by the same factor as the quota, once its demand exceeds it. Isolated operations of 0.1 to 0.5 ms are unaffected. The experiment does not model IoT hardware: it has no slower memory or cache, no frequency scaling and no energy measurement, and no memory limit was low enough to cause a failure, so the failure-rate chart is flat zero.