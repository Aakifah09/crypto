### Median latency in ms [Q1 to Q3], successful trials only

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|
| synthetic_fn | call | 0.5217 [0.5095 to 0.5268] | 0.7772 [0.7651 to 0.7852] | 1.523 [1.493 to 1.549] | 3.032 [2.997 to 3.059] |

### Slowdown vs C0 (median ratio, 95 % bootstrap interval)

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|
| synthetic_fn | call | x1.00 (0.99 to 1.02) | x1.49 (1.47 to 1.51) | x2.92 (2.87 to 2.97) | x5.81 (5.74 to 5.90) |

### 95th percentile latency in ms (tail; medians hide CPU throttling)

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|
| synthetic_fn | call | 0.5387 | 0.7941 | 1.562 | 3.094 |

### Median throughput in operations/s

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|
| synthetic_fn | call | 1989 | 1314 | n/a | n/a |

### Trial failure rate (failed / attempted)

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|
| synthetic_fn | call | 0 % (0/30) | 0 % (0/30) | 3 % (1/30) | 37 % (11/30) |
