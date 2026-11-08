### Median latency in ms [Q1 to Q3], successful trials only

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|
| synthetic_fn | call | 0.5154 [0.5077 to 0.5239] | 0.7632 [0.7511 to 0.7793] | 1.505 [1.482 to 1.528] | 3.045 [3.008 to 3.066] |

### Slowdown vs C0 (median ratio, 95 % bootstrap interval)

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|
| synthetic_fn | call | x1.00 (0.99 to 1.01) | x1.48 (1.46 to 1.51) | x2.92 (2.87 to 2.97) | x5.91 (5.82 to 5.98) |

### 95th percentile latency in ms (tail; medians hide CPU throttling)

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|
| synthetic_fn | call | 0.5406 | 0.7988 | 1.545 | 3.104 |

### Median throughput in operations/s

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|
| synthetic_fn | call | 1985 | 1317 | n/a | n/a |

### Trials whose timed call hit CPU throttling (count of recorded trials)

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|
| synthetic_fn | call | n/a | n/a | n/a | n/a |

### Batches that hit CPU throttling (count of batches; a stall waits up to one 100 ms period)

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|
| synthetic_fn | call | n/a | n/a | n/a | n/a |

### Trial failure rate (failed / attempted)

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|
| synthetic_fn | call | 0 % (0/30) | 0 % (0/30) | 23 % (7/30) | 33 % (10/30) |
