### Median latency in ms [Q1 to Q3], successful trials only

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|

### Slowdown vs C0 (median ratio, 95 % bootstrap interval)

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|

### 95th percentile latency in ms (tail; medians hide CPU throttling)

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|

### Median throughput in operations/s

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|
| ECDSA-P256-SHA256 | sign | 2.519e+04 | 2.539e+04 | 1.416e+04 | 6733 |
| ECDSA-P256-SHA256 | verify | 9332 | 9554 | 4826 | 2396 |
| ML-DSA-44 | sign | 1.048e+04 | 1.063e+04 | 5386 | 2705 |
| ML-DSA-44 | verify | 3.032e+04 | 2.957e+04 | 1.695e+04 | 7896 |
| ML-DSA-65 | sign | 7123 | 7114 | 3648 | 1791 |
| ML-DSA-65 | verify | 2.1e+04 | 2.109e+04 | 1.127e+04 | 5584 |
| ML-KEM-512 | decaps | 7.305e+04 | 7.331e+04 | 5.449e+04 | 2.109e+04 |
| ML-KEM-512 | encaps | 6.674e+04 | 6.639e+04 | 4.7e+04 | 2.029e+04 |
| ML-KEM-768 | decaps | 5.123e+04 | 4.684e+04 | 3.24e+04 | 1.472e+04 |
| ML-KEM-768 | encaps | 5.056e+04 | 5.046e+04 | 3.224e+04 | 1.437e+04 |
| RSA-2048-OAEP-SHA256 | decrypt | 2203 | 2214 | 1112 | 550.2 |
| RSA-2048-OAEP-SHA256 | encrypt | 2.755e+04 | 2.739e+04 | 1.492e+04 | 7208 |

### Trials whose timed call hit CPU throttling (count of recorded trials)

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|

### Batches that hit CPU throttling (count of batches; a stall waits up to one 100 ms period)

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|
| ECDSA-P256-SHA256 | sign | 0/3 | 0/3 | 3/3 | 3/3 |
| ECDSA-P256-SHA256 | verify | 0/3 | 0/3 | 3/3 | 3/3 |
| ML-DSA-44 | sign | 0/3 | 0/3 | 3/3 | 3/3 |
| ML-DSA-44 | verify | 0/3 | 0/3 | 3/3 | 3/3 |
| ML-DSA-65 | sign | 0/3 | 0/3 | 3/3 | 3/3 |
| ML-DSA-65 | verify | 0/3 | 0/3 | 3/3 | 3/3 |
| ML-KEM-512 | decaps | 0/3 | 0/3 | 3/3 | 3/3 |
| ML-KEM-512 | encaps | 0/3 | 0/3 | 3/3 | 3/3 |
| ML-KEM-768 | decaps | 0/3 | 0/3 | 3/3 | 3/3 |
| ML-KEM-768 | encaps | 0/3 | 0/3 | 3/3 | 3/3 |
| RSA-2048-OAEP-SHA256 | decrypt | 0/3 | 0/3 | 3/3 | 3/3 |
| RSA-2048-OAEP-SHA256 | encrypt | 0/3 | 0/3 | 3/3 | 3/3 |

### Trial failure rate (failed / attempted)

| Algorithm | Operation | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|
| ECDSA-P256-SHA256 | sign | n/a | n/a | n/a | n/a |
| ECDSA-P256-SHA256 | verify | n/a | n/a | n/a | n/a |
| ML-DSA-44 | sign | n/a | n/a | n/a | n/a |
| ML-DSA-44 | verify | n/a | n/a | n/a | n/a |
| ML-DSA-65 | sign | n/a | n/a | n/a | n/a |
| ML-DSA-65 | verify | n/a | n/a | n/a | n/a |
| ML-KEM-512 | decaps | n/a | n/a | n/a | n/a |
| ML-KEM-512 | encaps | n/a | n/a | n/a | n/a |
| ML-KEM-768 | decaps | n/a | n/a | n/a | n/a |
| ML-KEM-768 | encaps | n/a | n/a | n/a | n/a |
| RSA-2048-OAEP-SHA256 | decrypt | n/a | n/a | n/a | n/a |
| RSA-2048-OAEP-SHA256 | encrypt | n/a | n/a | n/a | n/a |
