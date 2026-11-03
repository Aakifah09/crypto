# Module 2: Statistical Analysis Method

**Scope:** how the raw measurements are turned into the numbers, tables and graphs in the report. Code: `benchmark/measure.py`, `benchmark/runner.py`, `analysis/summarize.py`, `analysis/plots.py`.

## 1. What is measured

| Quantity | Design | Where it comes from |
|---|---|---|
| Latency | 5 warm-ups (not recorded), then 30 recorded trials per algorithm, operation and profile. One timed call per trial, fresh keys/inputs per trial. | `time.perf_counter_ns()` around the operation only, converted to ms. Setup, validation and size measurement are outside the timer. GC is run before and disabled during the call. |
| Throughput | 5 batches of 100 back-to-back operations per algorithm, operation and profile. | Whole-batch time; ops/s = 100 / batch seconds. Setup once per batch, outside the timer. |
| Worker memory | Peak RSS of the worker process, per trial. | `VmHWM` from `/proc/self/status`, reset before each measurement. Also `worker_rss_before_mb`, so growth = peak - before. |
| Container memory | `memory.current` and `memory.peak` of the cgroup, per trial. | Whole container (includes the runner process and page cache). The peak is cumulative since container start. Kept in separate columns from worker memory. |
| CPU throttling | Time held back by the CPU quota, per trial. | `throttled_usec` (cgroup v2) or `throttled_time` (v1). Explains a slowdown rather than just measuring it. |
| Object sizes | Bytes of public key, secret key, ciphertext, shared secret, signature, plaintext. | Module 1's encodings (raw bytes for PQC, DER for classical), taken from the trials themselves. |

Every algorithm runs in its own **worker process** with a hard timeout per trial. A worker that is killed (OOM) or times out is replaced by a new one for the next trial, so one failure does not decide the other trials.

## 2. Failures are data

The runner writes exactly 30 trial rows and 5 batch rows per group, no matter what happens.

| status | meaning |
|---|---|
| `ok` | measured and the result validated (decaps secret matches, signature verifies, decrypt returns the payload) |
| `error` | the operation raised, returned a wrong result, or setup failed (`error_type` holds the exception class) |
| `timeout` | no reply within the timeout; worker killed |
| `killed` | worker process died; `OOMKilled` if the cgroup OOM counter moved, else `WorkerCrashed` |
| `skipped` | not attempted after 5 crashes or timeouts in a row (the constraint is clearly fatal); counted as failed |

**completion rate** = ok / planned trials. **failure rate** = 1 - completion rate. Failed, timed-out, killed and skipped trials all stay in the denominator.

## 3. Summary statistics

* **Median and IQR (Q3 - Q1)** of latency over `ok` trials. Latency distributions are right-skewed (scheduler noise, cache effects, CPU throttling), so the mean and standard deviation are driven by a few outliers. The median and IQR are not.
* **95 % confidence interval of the median**: percentile bootstrap, 2000 resamples, fixed seed (`--seed`), so the numbers reproduce exactly.
* **Slowdown vs C0** = median latency in the profile / median latency in C0 (greater than 1 means slower). Its 95 % CI comes from bootstrapping both samples independently and taking the ratio of resampled medians.
* **Throughput**: median and IQR of ops/s over the 5 batches. **Throughput slowdown** = C0 ops/s / profile ops/s.
* **Survivorship caveat.** Latency statistics use `ok` trials only. A group with 3 ok trials out of 30 has a median that describes the lucky survivors. `n_ok` is printed beside every median and groups with fewer than 10 ok trials get `low_n_flag`. Always read latency together with the failure rate.
* With 30 trials the CI on a median is wide for noisy operations. Differences smaller than the CI overlap should not be reported as differences. No hypothesis tests are run: with 4 profiles x 6 algorithms x 3 operations, uncorrected p-values would mostly be noise. Use the CIs.

## 4. Known limitations (state these in the report)

1. **Short batches cannot see CPU quotas.** Docker `--cpus` is a CFS quota enforced in 100 ms periods. 100 ML-KEM operations take a few milliseconds, which fits inside one period, so the batch is almost never throttled. A CPU limit then shows up as rare large outliers in single trials, not in the median and not in 100-operation throughput. `summary_throughput.csv` flags this (`short_batch_flag`, batches under 100 ms). If the CPU profiles show no slowdown for fast operations, this is why. Re-run with `--batch-size 2000` or larger as an additional measurement and report it as such.
2. **Peak RSS of one microsecond operation is almost the baseline.** The worker's RSS is dominated by the interpreter and the loaded libraries (tens of MB). Differences between algorithms are a few pages. `worker_rss_growth_median_mb` is the informative number; the absolute peak mainly shows whether a memory limit is above the baseline.
3. **Container memory is not attributable.** It includes the runner process and page cache, and its peak is cumulative. Use it to see whether a profile is close to its limit, not to compare algorithms.
4. **Docker needs swap disabled for memory limits to kill.** With `--memory 256m` alone, Docker allows swap up to twice that, so a process slows down instead of failing. Use `--memory-swap` equal to `--memory` if the profiles are meant to produce out-of-memory failures.
5. **Python overhead.** liboqs is called through `liboqs-python` and the classical algorithms through pyca/cryptography. Call overhead is a fixed cost per operation and is a visible fraction of a 10-30 microsecond operation. Compare PQC against classical ratios with that in mind; slowdown vs C0 within one algorithm is unaffected.
6. **Host noise.** Docker Desktop on Windows runs the container in a WSL2 VM. Absolute numbers depend on the laptop and its power state, so all profiles must be measured on the same machine in one session.
7. **Run order.** Groups run in a fixed order, so slow drift (thermal throttling) is confounded with algorithm order. Repeat the full set of profiles once in reverse order and compare.
8. **Failure-injection caveat.** The runner only knows a worker was OOM-killed if the cgroup counter moved; otherwise it is recorded as `WorkerCrashed`.

## 5. Reproducing everything

```bash
# on the host, after the container runs have written results/measurements/*.csv
pip install pandas numpy matplotlib
python -m analysis.summarize --raw results/measurements --out results/summary
python -m analysis.plots     --summary results/summary --out results/figures
```

`results/example/` contains the output of the same commands on the toy algorithms in `benchmark/demo.py`. Those numbers are synthetic and demonstrate the format only. They say nothing about real cryptographic performance.
