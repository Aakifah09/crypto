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
5. **Memory.** Worker peak RSS includes the interpreter, imported libraries and the untimed setup, not only the algorithm call. It is the main per-trial memory metric. Inside the container the cgroup files are read-only, so `memory.peak` cannot be reset (`container_peak_reset = 0`): `container_mem_peak_kb` is then a container-lifetime high-water mark that is the same on every row and is mostly page cache. Use `container_anon_kb` (anonymous memory of the whole container, i.e. runner plus worker, no page cache) for container memory.
6. **Profiles are run as separate container blocks**, not interleaved in time. Trial order inside a block is randomised, profile order is randomised by `scripts/run_profiles.py`, and `--repeat` repeats the whole sweep. Drift between blocks is reduced, not removed.
7. **Output sizes** must not change with the profile (report Sec. 4.5). `size_check.csv` flags any size that varies; the only expected variations are DER-encoded outputs: the ECDSA signature (70 to 72 bytes) and the RSA PKCS#8 private key (a few bytes).
8. Results come from one laptop (Docker Desktop on WSL2). They compare algorithms and profiles on that machine; they do not predict absolute timings on an IoT device.

## 5. Reproducing the tables and graphs

```
python -m analysis.summarize --trials results/trials.csv --throughput results/throughput.csv --out results/summary
python -m analysis.plots     --trials results/trials.csv --throughput results/throughput.csv --sizes results/output_sizes.csv --out results/figures
```

`examples/` holds a synthetic data set (generated by `scripts/make_example_data.py`) that shows the file formats and lets the pipeline be checked against known slowdowns. It contains no real measurements.
