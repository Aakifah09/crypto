# Summary tables

## Latency (ms; median over ok trials, IQR = Q3-Q1)

| algorithm | operation | profile | ok | median_ms | iqr_ms | slowdown_vs_baseline | fail_pct |
|---|---|---|---|---|---|---|---|
| DEMO-CRASH | keygen | C0 | 30/30 | 0.01533 | 0.004153 | 1 | 0 |
| DEMO-CRASH | keygen | C1 | 30/30 | 0.01278 | 0.0006385 | 0.8333 | 0 |
| DEMO-CRASH | keygen | C2 | 30/30 | 0.0112 | 0.0007857 | 0.7302 | 0 |
| DEMO-CRASH | keygen | C3 | 30/30 | 0.01199 | 0.0009605 | 0.7821 | 0 |
| DEMO-CRASH | sign | C0 | 20/30 | 0.09661 | 0.005128 | 1 | 33.33 |
| DEMO-CRASH | sign | C1 | 20/30 | 0.1787 | 0.02903 | 1.849 | 33.33 |
| DEMO-CRASH | sign | C2 | 20/30 | 0.3399 | 0.06795 | 3.518 | 33.33 |
| DEMO-CRASH | sign | C3 | 20/30 | 0.6761 | 0.05682 | 6.998 | 33.33 |
| DEMO-CRASH | verify | C0 | 20/30 | 0.09652 | 0.0213 | 1 | 33.33 |
| DEMO-CRASH | verify | C1 | 20/30 | 0.1901 | 0.09068 | 1.97 | 33.33 |
| DEMO-CRASH | verify | C2 | 20/30 | 0.3378 | 0.02898 | 3.5 | 33.33 |
| DEMO-CRASH | verify | C3 | 20/30 | 0.6935 | 0.06695 | 7.185 | 33.33 |
| DEMO-FLAKY | keygen | C0 | 30/30 | 0.01178 | 0.000861 | 1 | 0 |
| DEMO-FLAKY | keygen | C1 | 30/30 | 0.0121 | 0.002067 | 1.028 | 0 |
| DEMO-FLAKY | keygen | C2 | 30/30 | 0.01194 | 0.0005647 | 1.014 | 0 |
| DEMO-FLAKY | keygen | C3 | 30/30 | 0.01557 | 0.001104 | 1.322 | 0 |
| DEMO-FLAKY | sign | C0 | 25/30 | 0.09309 | 0.01194 | 1 | 16.67 |
| DEMO-FLAKY | sign | C1 | 25/30 | 0.1791 | 0.02556 | 1.924 | 16.67 |
| DEMO-FLAKY | sign | C2 | 25/30 | 0.3283 | 0.02189 | 3.527 | 16.67 |
| DEMO-FLAKY | sign | C3 | 25/30 | 0.6842 | 0.0438 | 7.35 | 16.67 |
| DEMO-FLAKY | verify | C0 | 25/30 | 0.09277 | 0.008741 | 1 | 16.67 |
| DEMO-FLAKY | verify | C1 | 25/30 | 0.1882 | 0.04594 | 2.028 | 16.67 |
| DEMO-FLAKY | verify | C2 | 25/30 | 0.3415 | 0.02434 | 3.681 | 16.67 |
| DEMO-FLAKY | verify | C3 | 25/30 | 0.6869 | 0.04348 | 7.405 | 16.67 |
| DEMO-HANG | keygen | C0 | 30/30 | 0.01233 | 0.00114 | 1 | 0 |
| DEMO-HANG | keygen | C1 | 30/30 | 0.01146 | 0.001085 | 0.9293 | 0 |
| DEMO-HANG | keygen | C2 | 30/30 | 0.0121 | 0.0006657 | 0.9816 | 0 |
| DEMO-HANG | keygen | C3 | 30/30 | 0.01292 | 0.000868 | 1.048 | 0 |
| DEMO-HANG | sign | C0 | 23/30 | 0.09906 | 0.0173 | 1 | 23.33 |
| DEMO-HANG | sign | C1 | 23/30 | 0.1758 | 0.01395 | 1.775 | 23.33 |
| DEMO-HANG | sign | C2 | 23/30 | 0.3627 | 0.1295 | 3.661 | 23.33 |
| DEMO-HANG | sign | C3 | 23/30 | 1.058 | 0.4225 | 10.68 | 23.33 |
| DEMO-HANG | verify | C0 | 23/30 | 0.09704 | 0.006962 | 1 | 23.33 |
| DEMO-HANG | verify | C1 | 23/30 | 0.1837 | 0.0533 | 1.893 | 23.33 |
| DEMO-HANG | verify | C2 | 23/30 | 0.3729 | 0.08857 | 3.843 | 23.33 |
| DEMO-HANG | verify | C3 | 23/30 | 0.6995 | 0.06428 | 7.209 | 23.33 |
| DEMO-HEAVY | keygen | C0 | 30/30 | 0.01237 | 0.002451 | 1 | 0 |
| DEMO-HEAVY | keygen | C1 | 30/30 | 0.01251 | 0.0009385 | 1.012 | 0 |
| DEMO-HEAVY | keygen | C2 | 30/30 | 0.01275 | 0.0007098 | 1.031 | 0 |
| DEMO-HEAVY | keygen | C3 | 30/30 | 0.01214 | 0.002113 | 0.9813 | 0 |
| DEMO-HEAVY | sign | C0 | 30/30 | 0.7714 | 0.03784 | 1 | 0 |
| DEMO-HEAVY | sign | C1 | 30/30 | 14.94 | 3.354 | 19.37 | 0 |
| DEMO-HEAVY | sign | C2 | 30/30 | 31.67 | 3.378 | 41.05 | 0 |
| DEMO-HEAVY | sign | C3 | 0/30 | - | - | - | 100 |
| DEMO-HEAVY | verify | C0 | 30/30 | 0.0946 | 0.03343 | 1 | 0 |
| DEMO-HEAVY | verify | C1 | 30/30 | 0.1792 | 0.02256 | 1.895 | 0 |
| DEMO-HEAVY | verify | C2 | 30/30 | 0.3506 | 0.08487 | 3.706 | 0 |
| DEMO-HEAVY | verify | C3 | 0/30 | - | - | - | 100 |
| DEMO-KEM | decaps | C0 | 30/30 | 0.08906 | 0.00645 | 1 | 0 |
| DEMO-KEM | decaps | C1 | 30/30 | 0.2818 | 0.125 | 3.165 | 0 |
| DEMO-KEM | decaps | C2 | 30/30 | 0.3444 | 0.05017 | 3.867 | 0 |
| DEMO-KEM | decaps | C3 | 30/30 | 0.693 | 0.03525 | 7.781 | 0 |
| DEMO-KEM | encaps | C0 | 30/30 | 0.09587 | 0.05671 | 1 | 0 |
| DEMO-KEM | encaps | C1 | 30/30 | 0.1848 | 0.02743 | 1.928 | 0 |
| DEMO-KEM | encaps | C2 | 30/30 | 0.3594 | 0.05528 | 3.749 | 0 |
| DEMO-KEM | encaps | C3 | 30/30 | 0.7267 | 0.08553 | 7.58 | 0 |
| DEMO-KEM | keygen | C0 | 30/30 | 0.01194 | 0.0009588 | 1 | 0 |
| DEMO-KEM | keygen | C1 | 30/30 | 0.01194 | 0.0006463 | 1 | 0 |
| DEMO-KEM | keygen | C2 | 30/30 | 0.01279 | 0.001522 | 1.072 | 0 |
| DEMO-KEM | keygen | C3 | 30/30 | 0.01262 | 0.001187 | 1.058 | 0 |
| DEMO-SIG | keygen | C0 | 30/30 | 0.01203 | 0.001514 | 1 | 0 |
| DEMO-SIG | keygen | C1 | 30/30 | 0.01157 | 0.0009888 | 0.9613 | 0 |
| DEMO-SIG | keygen | C2 | 30/30 | 0.01252 | 0.000988 | 1.04 | 0 |
| DEMO-SIG | keygen | C3 | 30/30 | 0.01255 | 0.0007352 | 1.043 | 0 |
| DEMO-SIG | sign | C0 | 30/30 | 0.09542 | 0.004481 | 1 | 0 |
| DEMO-SIG | sign | C1 | 30/30 | 0.1837 | 0.02546 | 1.926 | 0 |
| DEMO-SIG | sign | C2 | 30/30 | 0.3676 | 0.05969 | 3.853 | 0 |
| DEMO-SIG | sign | C3 | 30/30 | 0.7039 | 0.05213 | 7.377 | 0 |
| DEMO-SIG | verify | C0 | 30/30 | 0.09409 | 0.003626 | 1 | 0 |
| DEMO-SIG | verify | C1 | 30/30 | 0.194 | 0.025 | 2.062 | 0 |
| DEMO-SIG | verify | C2 | 30/30 | 0.3611 | 0.0413 | 3.838 | 0 |
| DEMO-SIG | verify | C3 | 30/30 | 0.9537 | 0.3273 | 10.14 | 0 |

## Throughput (operations per second; median of batches)

| algorithm | operation | profile | median_ops_per_sec | iqr_ops_per_sec | slowdown_vs_baseline | short_batch_flag |
|---|---|---|---|---|---|---|
| DEMO-CRASH | keygen | C0 | 9.545e+05 | 7.568e+04 | 1 | True |
| DEMO-CRASH | keygen | C1 | 1.013e+06 | 697.2 | 0.9427 | True |
| DEMO-CRASH | keygen | C2 | 1.056e+06 | 1.203e+05 | 0.9036 | True |
| DEMO-CRASH | keygen | C3 | 9.814e+05 | 1.894e+04 | 0.9726 | True |
| DEMO-CRASH | sign | C0 | - | - | - | False |
| DEMO-CRASH | sign | C1 | - | - | - | False |
| DEMO-CRASH | sign | C2 | - | - | - | False |
| DEMO-CRASH | sign | C3 | - | - | - | False |
| DEMO-CRASH | verify | C0 | 1.195e+04 | 201.2 | 1 | True |
| DEMO-CRASH | verify | C1 | 6213 | 300.5 | 1.924 | True |
| DEMO-CRASH | verify | C2 | 3142 | 163.9 | 3.805 | True |
| DEMO-CRASH | verify | C3 | 1501 | 67.06 | 7.962 | True |
| DEMO-FLAKY | keygen | C0 | 1.008e+06 | 2.692e+04 | 1 | True |
| DEMO-FLAKY | keygen | C1 | 1.012e+06 | 1.28e+05 | 0.9962 | True |
| DEMO-FLAKY | keygen | C2 | 1.053e+06 | 1.948e+04 | 0.9575 | True |
| DEMO-FLAKY | keygen | C3 | 9.87e+05 | 3.772e+05 | 1.022 | True |
| DEMO-FLAKY | sign | C0 | - | - | - | False |
| DEMO-FLAKY | sign | C1 | - | - | - | False |
| DEMO-FLAKY | sign | C2 | - | - | - | False |
| DEMO-FLAKY | sign | C3 | - | - | - | False |
| DEMO-FLAKY | verify | C0 | 1.308e+04 | 887.4 | 1 | True |
| DEMO-FLAKY | verify | C1 | 6059 | 195.8 | 2.159 | True |
| DEMO-FLAKY | verify | C2 | 3166 | 81.72 | 4.131 | True |
| DEMO-FLAKY | verify | C3 | 1402 | 160 | 9.329 | True |
| DEMO-HANG | keygen | C0 | 1.005e+06 | 3.025e+04 | 1 | True |
| DEMO-HANG | keygen | C1 | 1.086e+06 | 1.086e+05 | 0.9254 | True |
| DEMO-HANG | keygen | C2 | 9.678e+05 | 1.33e+04 | 1.038 | True |
| DEMO-HANG | keygen | C3 | 9.819e+05 | 1.245e+04 | 1.023 | True |
| DEMO-HANG | sign | C0 | - | - | - | False |
| DEMO-HANG | sign | C1 | - | - | - | False |
| DEMO-HANG | sign | C2 | - | - | - | False |
| DEMO-HANG | sign | C3 | - | - | - | False |
| DEMO-HANG | verify | C0 | 1.22e+04 | 627.7 | 1 | True |
| DEMO-HANG | verify | C1 | 6131 | 513.1 | 1.989 | True |
| DEMO-HANG | verify | C2 | 2126 | 273 | 5.737 | True |
| DEMO-HANG | verify | C3 | 1553 | 72.81 | 7.857 | True |
| DEMO-HEAVY | keygen | C0 | 9.695e+05 | 2.686e+05 | 1 | True |
| DEMO-HEAVY | keygen | C1 | 1.01e+06 | 2.791e+05 | 0.9601 | True |
| DEMO-HEAVY | keygen | C2 | 1.036e+06 | 1.608e+04 | 0.9356 | True |
| DEMO-HEAVY | keygen | C3 | 1.015e+06 | 1.081e+05 | 0.9554 | True |
| DEMO-HEAVY | sign | C0 | 1315 | 33.93 | 1 | True |
| DEMO-HEAVY | sign | C1 | 80.5 | 1.693 | 16.34 | False |
| DEMO-HEAVY | sign | C2 | - | - | - | False |
| DEMO-HEAVY | sign | C3 | - | - | - | False |
| DEMO-HEAVY | verify | C0 | 6816 | 81.87 | 1 | True |
| DEMO-HEAVY | verify | C1 | 6196 | 1178 | 1.1 | True |
| DEMO-HEAVY | verify | C2 | 3022 | 260.1 | 2.255 | True |
| DEMO-HEAVY | verify | C3 | - | - | - | False |
| DEMO-KEM | decaps | C0 | 1.2e+04 | 345.4 | 1 | True |
| DEMO-KEM | decaps | C1 | 6073 | 739.2 | 1.976 | True |
| DEMO-KEM | decaps | C2 | 2981 | 107.2 | 4.026 | True |
| DEMO-KEM | decaps | C3 | 1373 | 258.2 | 8.742 | True |
| DEMO-KEM | encaps | C0 | 1.298e+04 | 1054 | 1 | True |
| DEMO-KEM | encaps | C1 | 6063 | 93.55 | 2.141 | True |
| DEMO-KEM | encaps | C2 | 2975 | 26.61 | 4.364 | True |
| DEMO-KEM | encaps | C3 | 1457 | 17.87 | 8.912 | True |
| DEMO-KEM | keygen | C0 | 1.045e+06 | 6.66e+04 | 1 | True |
| DEMO-KEM | keygen | C1 | 9.853e+05 | 1.635e+04 | 1.06 | True |
| DEMO-KEM | keygen | C2 | 9.825e+05 | 9.523e+04 | 1.063 | True |
| DEMO-KEM | keygen | C3 | 9.005e+05 | 9.476e+04 | 1.16 | True |
| DEMO-SIG | keygen | C0 | 1.024e+06 | 3.309e+04 | 1 | True |
| DEMO-SIG | keygen | C1 | 9.896e+05 | 3.863e+04 | 1.034 | True |
| DEMO-SIG | keygen | C2 | 9.057e+05 | 1.424e+05 | 1.13 | True |
| DEMO-SIG | keygen | C3 | 9.447e+05 | 7.619e+04 | 1.084 | True |
| DEMO-SIG | sign | C0 | 1.216e+04 | 371.4 | 1 | True |
| DEMO-SIG | sign | C1 | 6020 | 95.01 | 2.02 | True |
| DEMO-SIG | sign | C2 | 3050 | 164 | 3.987 | True |
| DEMO-SIG | sign | C3 | 1405 | 207.5 | 8.656 | True |
| DEMO-SIG | verify | C0 | 1.211e+04 | 423.2 | 1 | True |
| DEMO-SIG | verify | C1 | 6041 | 35.24 | 2.005 | True |
| DEMO-SIG | verify | C2 | 2927 | 81.14 | 4.138 | True |
| DEMO-SIG | verify | C3 | 1491 | 17.84 | 8.122 | True |

## Failures (only groups with at least one failed trial)

| algorithm | operation | profile | n_planned | n_ok | n_error | n_timeout | n_killed | n_skipped | failure_breakdown |
|---|---|---|---|---|---|---|---|---|---|
| DEMO-CRASH | sign | C0 | 30 | 20 | 0 | 0 | 10 | 0 | WorkerCrashed:10 |
| DEMO-CRASH | sign | C1 | 30 | 20 | 0 | 0 | 10 | 0 | WorkerCrashed:10 |
| DEMO-CRASH | sign | C2 | 30 | 20 | 0 | 0 | 10 | 0 | WorkerCrashed:10 |
| DEMO-CRASH | sign | C3 | 30 | 20 | 0 | 0 | 10 | 0 | WorkerCrashed:10 |
| DEMO-CRASH | verify | C0 | 30 | 20 | 0 | 0 | 10 | 0 | WorkerCrashed:10 |
| DEMO-CRASH | verify | C1 | 30 | 20 | 0 | 0 | 10 | 0 | WorkerCrashed:10 |
| DEMO-CRASH | verify | C2 | 30 | 20 | 0 | 0 | 10 | 0 | WorkerCrashed:10 |
| DEMO-CRASH | verify | C3 | 30 | 20 | 0 | 0 | 10 | 0 | WorkerCrashed:10 |
| DEMO-FLAKY | sign | C0 | 30 | 25 | 5 | 0 | 0 | 0 | ValueError:5 |
| DEMO-FLAKY | sign | C1 | 30 | 25 | 5 | 0 | 0 | 0 | ValueError:5 |
| DEMO-FLAKY | sign | C2 | 30 | 25 | 5 | 0 | 0 | 0 | ValueError:5 |
| DEMO-FLAKY | sign | C3 | 30 | 25 | 5 | 0 | 0 | 0 | ValueError:5 |
| DEMO-FLAKY | verify | C0 | 30 | 25 | 5 | 0 | 0 | 0 | ValueError:5 |
| DEMO-FLAKY | verify | C1 | 30 | 25 | 5 | 0 | 0 | 0 | ValueError:5 |
| DEMO-FLAKY | verify | C2 | 30 | 25 | 5 | 0 | 0 | 0 | ValueError:5 |
| DEMO-FLAKY | verify | C3 | 30 | 25 | 5 | 0 | 0 | 0 | ValueError:5 |
| DEMO-HANG | sign | C0 | 30 | 23 | 0 | 7 | 0 | 0 | Timeout:7 |
| DEMO-HANG | sign | C1 | 30 | 23 | 0 | 7 | 0 | 0 | Timeout:7 |
| DEMO-HANG | sign | C2 | 30 | 23 | 0 | 7 | 0 | 0 | Timeout:7 |
| DEMO-HANG | sign | C3 | 30 | 23 | 0 | 7 | 0 | 0 | Timeout:7 |
| DEMO-HANG | verify | C0 | 30 | 23 | 0 | 7 | 0 | 0 | Timeout:7 |
| DEMO-HANG | verify | C1 | 30 | 23 | 0 | 7 | 0 | 0 | Timeout:7 |
| DEMO-HANG | verify | C2 | 30 | 23 | 0 | 7 | 0 | 0 | Timeout:7 |
| DEMO-HANG | verify | C3 | 30 | 23 | 0 | 7 | 0 | 0 | Timeout:7 |
| DEMO-HEAVY | sign | C3 | 30 | 0 | 30 | 0 | 0 | 0 | MemoryError:30 |
| DEMO-HEAVY | verify | C3 | 30 | 0 | 30 | 0 | 0 | 0 | MemoryError:30 |

## Memory (MB)

| algorithm | operation | profile | worker_rss_peak_median_mb | worker_rss_growth_median_mb | container_mem_peak_max_mb |
|---|---|---|---|---|---|
| DEMO-CRASH | keygen | C0 | 19.68 | 0 | 109.2 |
| DEMO-CRASH | keygen | C1 | 19.53 | 0 | 122.7 |
| DEMO-CRASH | keygen | C2 | 19.62 | 0 | 154.8 |
| DEMO-CRASH | keygen | C3 | 19.57 | 0 | 154.8 |
| DEMO-CRASH | sign | C0 | 19.54 | 0 | 109.2 |
| DEMO-CRASH | sign | C1 | 19.62 | 0 | 122.7 |
| DEMO-CRASH | sign | C2 | 19.6 | 0 | 154.8 |
| DEMO-CRASH | sign | C3 | 19.54 | 0 | 154.8 |
| DEMO-CRASH | verify | C0 | 19.56 | 0 | 109.2 |
| DEMO-CRASH | verify | C1 | 19.58 | 0 | 122.7 |
| DEMO-CRASH | verify | C2 | 19.55 | 0 | 154.8 |
| DEMO-CRASH | verify | C3 | 19.55 | 0 | 154.8 |
| DEMO-FLAKY | keygen | C0 | 19.52 | 0 | 109.2 |
| DEMO-FLAKY | keygen | C1 | 19.64 | 0 | 122.7 |
| DEMO-FLAKY | keygen | C2 | 19.53 | 0 | 154.8 |
| DEMO-FLAKY | keygen | C3 | 19.54 | 0 | 154.8 |
| DEMO-FLAKY | sign | C0 | 19.52 | 0 | 109.2 |
| DEMO-FLAKY | sign | C1 | 19.51 | 0 | 122.7 |
| DEMO-FLAKY | sign | C2 | 19.52 | 0 | 154.8 |
| DEMO-FLAKY | sign | C3 | 19.54 | 0 | 154.8 |
| DEMO-FLAKY | verify | C0 | 19.63 | 0 | 109.2 |
| DEMO-FLAKY | verify | C1 | 19.53 | 0 | 122.7 |
| DEMO-FLAKY | verify | C2 | 19.52 | 0 | 154.8 |
| DEMO-FLAKY | verify | C3 | 19.57 | 0 | 154.8 |
| DEMO-HANG | keygen | C0 | 19.68 | 0 | 109.2 |
| DEMO-HANG | keygen | C1 | 19.67 | 0 | 122.7 |
| DEMO-HANG | keygen | C2 | 19.57 | 0 | 154.8 |
| DEMO-HANG | keygen | C3 | 19.55 | 0 | 154.8 |
| DEMO-HANG | sign | C0 | 19.55 | 0 | 109.2 |
| DEMO-HANG | sign | C1 | 19.54 | 0 | 122.7 |
| DEMO-HANG | sign | C2 | 19.62 | 0 | 154.8 |
| DEMO-HANG | sign | C3 | 19.62 | 0 | 154.8 |
| DEMO-HANG | verify | C0 | 19.55 | 0 | 109.2 |
| DEMO-HANG | verify | C1 | 19.54 | 0 | 122.7 |
| DEMO-HANG | verify | C2 | 19.62 | 0 | 154.8 |
| DEMO-HANG | verify | C3 | 19.56 | 0 | 154.8 |
| DEMO-HEAVY | keygen | C0 | 19.66 | 0 | 109.2 |
| DEMO-HEAVY | keygen | C1 | 19.57 | 0 | 109.2 |
| DEMO-HEAVY | keygen | C2 | 19.52 | 0 | 122.7 |
| DEMO-HEAVY | keygen | C3 | 19.67 | 0 | 154.8 |
| DEMO-HEAVY | sign | C0 | 35.55 | 0 | 109.2 |
| DEMO-HEAVY | sign | C1 | 51.49 | 31.91 | 122.7 |
| DEMO-HEAVY | sign | C2 | 83.5 | 63.91 | 154.8 |
| DEMO-HEAVY | sign | C3 | 19.54 | 0.003906 | 154.8 |
| DEMO-HEAVY | verify | C0 | 35.61 | 0 | 109.2 |
| DEMO-HEAVY | verify | C1 | 19.52 | 0 | 122.7 |
| DEMO-HEAVY | verify | C2 | 19.64 | 0 | 154.8 |
| DEMO-HEAVY | verify | C3 | - | - | - |
| DEMO-KEM | decaps | C0 | 19.52 | 0 | 109.2 |
| DEMO-KEM | decaps | C1 | 19.63 | 0 | 109.2 |
| DEMO-KEM | decaps | C2 | 19.5 | 0 | 122.7 |
| DEMO-KEM | decaps | C3 | 19.67 | 0 | 154.8 |
| DEMO-KEM | encaps | C0 | 19.67 | 0 | 109.2 |
| DEMO-KEM | encaps | C1 | 19.53 | 0 | 109.2 |
| DEMO-KEM | encaps | C2 | 19.54 | 0 | 122.7 |
| DEMO-KEM | encaps | C3 | 19.62 | 0 | 154.8 |
| DEMO-KEM | keygen | C0 | 19.51 | 0 | 109.2 |
| DEMO-KEM | keygen | C1 | 19.57 | 0 | 109.2 |
| DEMO-KEM | keygen | C2 | 19.68 | 0 | 122.7 |
| DEMO-KEM | keygen | C3 | 19.63 | 0 | 154.8 |
| DEMO-SIG | keygen | C0 | 19.52 | 0 | 109.2 |
| DEMO-SIG | keygen | C1 | 19.54 | 0 | 109.2 |
| DEMO-SIG | keygen | C2 | 19.55 | 0 | 122.7 |
| DEMO-SIG | keygen | C3 | 19.67 | 0 | 154.8 |
| DEMO-SIG | sign | C0 | 19.52 | 0 | 109.2 |
| DEMO-SIG | sign | C1 | 19.58 | 0 | 109.2 |
| DEMO-SIG | sign | C2 | 19.5 | 0 | 122.7 |
| DEMO-SIG | sign | C3 | 19.52 | 0 | 154.8 |
| DEMO-SIG | verify | C0 | 19.64 | 0 | 109.2 |
| DEMO-SIG | verify | C1 | 19.55 | 0 | 109.2 |
| DEMO-SIG | verify | C2 | 19.55 | 0 | 122.7 |
| DEMO-SIG | verify | C3 | 19.51 | 0 | 154.8 |

## Cryptographic object sizes (bytes)

| algorithm | family | public_key | secret_key | ciphertext | shared_secret | signature | plaintext |
|---|---|---|---|---|---|---|---|
| DEMO-KEM | post-quantum | 32 | 32 | 48 | 32 | - | - |
| DEMO-SIG | post-quantum | 32 | 32 | - | - | 32 | - |
| DEMO-HEAVY | classical | 32 | 32 | - | - | 32 | - |
| DEMO-FLAKY | classical | 32 | 32 | - | - | 32 | - |
| DEMO-CRASH | classical | 32 | 32 | - | - | 32 | - |
| DEMO-HANG | classical | 32 | 32 | - | - | 32 | - |
