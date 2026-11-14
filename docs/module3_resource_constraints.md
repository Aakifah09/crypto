
# Module 3: Resource Constraints, Hardware Environment and Integration

## 1. Overview

Module 3 focuses on configuring resource-constrained execution environments, integrating the cryptographic algorithms with the benchmark framework, and evaluating their performance under different CPU and memory limits.

The experiments were conducted using Docker containers on a laptop running Ubuntu through WSL2. Four resource profiles (C0–C3) were configured to simulate different resource availability levels.

## 2. Docker Environment and Dependencies

A Docker-based environment was used to provide a consistent execution environment for the benchmark.

The environment included:

- Python 3.11.18
- liboqs 0.16.0
- liboqs-python 0.16.0.2
- cryptography 46.0.7
- OpenSSL 3.5.6
- Debian GCC compiler (cc 12.2.0)

The Docker image was built using a pinned Python 3.11 slim Bookworm base-image digest. The post-quantum cryptographic library was compiled and installed within the container.

The host environment used WSL2 on an x86-64 system, with 8 reported CPUs and approximately 3.77 GiB of memory.

## 3. Resource Constraint Configuration

Four Docker resource profiles were configured.

| Profile | CPU limit | Memory limit |
|---|---:|---:|
| C0 | Unrestricted | Unrestricted |
| C1 | 1 CPU | 512 MiB |
| C2 | 0.5 CPU | 256 MiB |
| C3 | 0.25 CPU | 128 MiB |

For C1–C3, Docker's combined memory-and-swap limit (`--memory-swap`) was set equal to the memory limit (`--memory`). Consequently, no additional swap was available, and the cgroup v2 `memory.swap.max` value was `0`.

### 3.1 Verification of Resource Limits

Docker cgroup v2 values were inspected to verify that the containers received the intended resource constraints.

| Profile | CPU quota | Memory limit | Swap limit |
|---|---|---:|---:|
| C0 | max 100000 | max | max |
| C1 | 100000 100000 | 536870912 bytes | 0 |
| C2 | 50000 100000 | 268435456 bytes | 0 |
| C3 | 25000 100000 | 134217728 bytes | 0 |

The benchmark runner checks the actual container limits against the expected profile configuration. The runner was also hardened to stop execution when required cgroup values are missing or the profile cannot be verified.

All four profiles passed the subsequent verification checks.

## 4. Integration with the Benchmark Framework

The resource profiles were integrated with the common benchmark runner.

The implementation supports the following operation interfaces:

- Key encapsulation mechanisms (KEM): key generation, encapsulation and decapsulation.
- Digital signatures: key generation, signing and verification.
- Public-key encryption baseline: key generation, encryption and decryption.

The integrated algorithms were tested under the four resource profiles before the main experiments.

The smoke tests completed successfully across all six algorithms and four profiles.

## 5. Experimental Procedure

The main experiment was conducted on 12 November 2026.

Two complete benchmark sweeps were performed using the four resource profiles.

The experimental configuration included:

- 5 warm-up iterations per operation.
- 30 recorded latency trials per operation and profile.
- 5 throughput batches per operation and profile.
- 100 operations per throughput batch.
- Separate processes for individual trials and throughput batches.
- Measurement of worker memory usage and container memory.
- Recording of CPU throttling, failures and execution outcomes.

The primary dataset combines the two November 12 runs:

- 4,320 recorded latency trials.
- 720 throughput batches.
- 72,000 throughput operations.

The primary datasets are stored in `results/filtered/trials.csv` and `results/filtered/throughput.csv`.

## 6. Memory and Object-Size Measurements

Worker peak resident set size (RSS), worker memory changes and container memory measurements were collected during the experiments.

The observed median worker peak RSS ranged from approximately 27,608 KiB to 31,650 KiB across the recorded operations and profiles.

The maximum worker peak RSS ranged from 28,260 KiB to 32,088 KiB.

The median container memory measurements ranged from approximately 31,598 KiB to 34,746 KiB.

The recorded measurements remained below the configured 128 MiB memory limit of profile C3. No out-of-memory failures were recorded in the primary benchmark dataset.

Cryptographic object sizes were also measured. The post-quantum algorithms generally produced larger keys, ciphertexts and signatures than the classical baselines. These differences are relevant to storage and communication requirements in resource-constrained IoT environments.

## 7. Validation and Reproducibility

Correctness checks were performed before benchmarking to ensure that the cryptographic operations produced valid results.

Fault-injection tests were also executed to verify that the framework could detect deliberately introduced algorithm failures.

The validation process included:

- Cryptographic correctness checks.
- Algorithm availability checks.
- Fault-injection tests.
- Resource-profile verification.
- Benchmark execution and CSV output validation.
- Environment and run metadata collection.

The November 12 environment metadata and individual run metadata were retained alongside the experimental results.

The primary filtered datasets were preserved separately from older and supplementary experiment data to maintain consistency during analysis.

## 8. Experimental Limitations

The resource constraints were simulated using Docker CPU and memory limits on a laptop running WSL2.

Therefore, these experiments represent software-controlled resource-constrained environments and do not directly reproduce the architecture, power consumption, thermal characteristics or hardware behaviour of physical IoT devices.

The exact host processor model was not captured in the environment metadata.

Physical hardware evaluation using a Raspberry Pi or another IoT device should be reported separately if such experiments are conducted.

## 9. Module 3 Contribution

The Module 3 contribution included:

- Configuring the Docker execution environment and cryptographic dependencies.
- Setting up and verifying four CPU and memory resource profiles.
- Integrating the cryptographic algorithms with the common benchmark runner.
- Executing the resource-constrained benchmark experiments.
- Collecting memory, CPU throttling and execution data.
- Performing additional profile-verification and fault-injection validation.
- Organising experimental outputs, metadata, graphs and summary tables for analysis.
