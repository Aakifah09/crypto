# Module 1 Test Report: Cryptographic Operations and Correctness

**Project:** Performance Analysis of Post-Quantum Cryptographic Algorithms Under Simulated Resource Constraints for IoT Applications
**Module owner:** Aakifah Minhaj
**Date:** 2026-11-01
**Result:** All 6 algorithms required by the report are available and pass every correctness check (100 trials each, fresh key pair per trial, 0 failures). They are ready to hand to the benchmarking framework.

## 1. Environment (Task 1; report Sec. 4.1)

| Component | Value |
|---|---|
| Base image (pinned by digest) | `python:3.11-slim-bookworm@sha256:94a8fee35252d06ab75856f15f12c7bae67b10e8a6da93c7fded82b2610926cd` |
| liboqs | 0.16.0, commit `5a1a854b0dc9f2141bdc771c555ee60c37950183`, built from source in the image |
| Compiler | GCC 12.2.0 (Debian 12.2.0-14+deb12u1) |
| liboqs-python | 0.16.0.2 |
| cryptography (pyca) | 46.0.7 |
| OpenSSL (cryptography backend) | 3.5.6 (7 Apr 2026) |
| Python | 3.11.18 |
| Host | Windows laptop, Docker Desktop Linux container (WSL2 kernel 6.18), 12 logical CPUs, ~7.6 GiB visible to the VM |
| Container limits for this run | none (`cpu.max = max`, `memory.max = max`), i.e. profile C0 |

Every value above is read from the live setup and saved to `results/environment.json`, as the report requires ("we won't guess version numbers"). The liboqs build enables **41 KEMs and 221 signature schemes**. The full lists are in the same file. The names this project uses are `ML-KEM-512`, `ML-KEM-768`, `ML-DSA-44` and `ML-DSA-65`.

## 2. Supported algorithms

| Algorithm | Operations | Library | Standard | Status |
|---|---|---|---|---|
| ML-KEM-512 | keygen, encaps, decaps | liboqs | FIPS 203 | Available, PASS |
| ML-KEM-768 | keygen, encaps, decaps | liboqs | FIPS 203 | Available, PASS |
| ML-DSA-44 | keygen, sign, verify | liboqs | FIPS 204 | Available, PASS |
| ML-DSA-65 | keygen, sign, verify | liboqs | FIPS 204 | Available, PASS |
| RSA-2048-OAEP-SHA256 | keygen, encrypt, decrypt | cryptography/OpenSSL | RFC 8017 | Available, PASS |
| ECDSA-P256-SHA256 | keygen, sign, verify | cryptography/OpenSSL | FIPS 186-5 | Available, PASS |

**Unavailable algorithms:** none. `algorithms.availability()` checks this on every run. If a liboqs build lacks one of these names, the algorithm is reported as `UNAVAILABLE` with a reason, and no other algorithm is substituted. The report's rule (Sec. 4.1) is to document the constraint and switch to a compatible *build*.

## 3. Parameters, encodings and workloads (Tasks 2–5; report Sec. 4.2 and Table 2)

| Algorithm | Report requirement | Implemented |
|---|---|---|
| ML-KEM-512/768 | Shared-secret match checked outside timing | ✅ `decaps()` only returns the secret. The comparison happens in `correctness.py` |
| ML-DSA-44/65 | 1,024-byte fixed message; empty context; no prehash | ✅ Pure ML-DSA with empty context (liboqs `sign`). Signing is hedged (randomized), the liboqs default |
| RSA-2048 | OAEP-SHA-256; exponent 65537; 32-byte payload; MGF1-SHA-256; empty label | ✅ All checked in code (`label=None` is the empty label) |
| ECDSA P-256 | SHA-256; same 1,024-byte message; DER signatures | ✅ DER `ECDSA-Sig-Value` signatures |
| Object sizes | liboqs raw byte strings for PQC; DER SubjectPublicKeyInfo for classical (Sec. 4.4 step 5) | ✅ Classical private keys use DER PKCS#8. Raw point/scalar/r‖s sizes are kept as secondary columns |

**Workloads** (`benchmark/workloads.py`) are fixed and deterministic, as the report specifies. The content is SHAKE-256 output over a fixed label, which anyone can regenerate:

| Workload | Size | SHA-256 (first 16 hex) |
|---|---|---|
| Signature message (ML-DSA, ECDSA) | 1,024 bytes | `2d8d54375019ef51` |
| RSA-OAEP payload | 32 bytes | `40c05e1ab2aade4f` |

## 4. Correctness checks (report Sec. 4.4 step 2, "Sanity check")

Each algorithm ran 100 trials, each with a fresh key pair. A check passes only if it held in all 100 trials. 0 failures were recorded.

**ML-KEM-512 / ML-KEM-768**
- Encapsulated and decapsulated shared secrets match (secret agreement)
- Decapsulating from raw secret-key bytes gives the same secret as decapsulating from the prepared handle
- Public key, secret key, ciphertext and shared-secret sizes equal the FIPS 203 values
- A ciphertext with one bit flipped decapsulates to a *different* secret (implicit rejection)
- An unrelated secret key gives a different secret
- Two encapsulations to the same key give different secrets (fresh randomness)

**ML-DSA-44 / ML-DSA-65, ECDSA P-256** (signature validation and rejection)
- A valid signature verifies
- A message with one bit flipped is rejected, and so is a message truncated by one byte
- A signature with one bit flipped is rejected
- An unrelated public key is rejected
- Key and signature sizes equal FIPS 204 (ML-DSA) or the expected DER sizes (ECDSA)

**RSA-2048-OAEP-SHA256**
- Decryption recovers the 32-byte payload
- Modulus is 2048 bits and e = 65537. Ciphertext is 256 bytes and the SPKI public key is 294 bytes
- A ciphertext with one bit flipped is rejected, and so is an unrelated private key
- Encrypting the same payload twice gives different ciphertexts (OAEP randomization)

## 5. Output sizes in bytes (report encodings)

| Algorithm | Public key | Secret key | Ciphertext | Shared secret | Signature |
|---|---|---|---|---|---|
| ML-KEM-512 | 800 | 1,632 | 768 | 32 | – |
| ML-KEM-768 | 1,184 | 2,400 | 1,088 | 32 | – |
| ML-DSA-44 | 1,312 | 2,560 | – | – | 2,420 |
| ML-DSA-65 | 1,952 | 4,032 | – | – | 3,309 |
| RSA-2048-OAEP-SHA256 | 294 (DER SPKI) | ≈1,217 (DER PKCS#8) | 256 | – | – |
| ECDSA-P256-SHA256 | 91 (DER SPKI) | 138 (DER PKCS#8) | – | – | ≤ 72, variable (DER) |

Secondary encodings: the RSA public key is 270 bytes as PKCS#1 DER. The ECDSA public key is 65 bytes as a raw uncompressed point, the private key a 32-byte raw scalar, and a raw r‖s signature 64 bytes.

As the report expects (Sec. 4.5), ML-KEM/ML-DSA sizes and the RSA ciphertext are fixed. ECDSA DER signatures vary in length because of DER integer encoding, not resource limits. The maximum is 72 bytes. A 100-trial run typically sees 70–72, occasionally 69. Each run records the observed minimum and maximum in `results/output_sizes.csv` (`signature_min`, `signature_max`). The RSA PKCS#8 private key also varies by a few bytes for the same reason.

## 6. Notes for the benchmarking framework (report Sec. 4.4 step 3)

The report says setup must stay outside the timed blocks. Creating a liboqs context object roughly doubled the measured time of an operation (ML-KEM-512 decapsulation: 54 µs with a context created per call, 28–38 µs with a reused one). So the module separates setup from the operations:

```python
pk, sk = alg.keygen()            # timed: key generation
skh = alg.load_secret_key(sk)    # NOT timed (setup)
ct, ss = alg.encaps(pk)          # timed
alg.decaps(skh, ct)              # timed
sig = alg.sign(skh, msg)         # timed
alg.verify(pk, msg, sig)         # timed
```

- `benchmark.algorithms.get_algorithms()` returns only the algorithms that are available.
- Keys come out of `keygen()` as plain bytes (PQC), so they can be passed to a separate worker process, as the report requires (Sec. 4.4 step 7).
- `results/environment.json` records the cgroup CPU and memory limits seen inside the container, so each benchmark run can save the limits it actually had (Sec. 4.3).
- Run `python -m benchmark.correctness` before benchmarking, and continue only if the exit status is 0. Status 1 means a check failed. Status 2 means a required algorithm is missing from liboqs: it is reported, never substituted, and the build must be fixed first (report Sec. 4.1).

## 7. Do the checks catch faults? (self-test)

A check that always passes proves nothing. `tests/test_fault_injection.py` breaks each algorithm on purpose and confirms the suite reports it. Result: **all 15 faults caught, 0 false alarms.**

| Injected fault | Caught by |
|---|---|
| ML-KEM decaps returns a wrong secret | `shared_secrets_match` |
| ML-KEM without implicit rejection | `tampered_ciphertext_gives_different_secret` |
| ML-KEM accepts a wrong secret key | `wrong_secret_key_gives_different_secret` |
| ML-KEM encapsulation not randomized | `encapsulation_is_randomized` |
| "ML-KEM-768" actually running ML-KEM-512 | `size:ciphertext==1088` |
| ML-DSA-44/65 verify accepts everything | `modified_message_rejected`, `wrong_public_key_rejected` |
| ML-DSA verify rejects valid signatures | `valid_signature_verifies` |
| ML-DSA only signs the first 512 bytes | `truncated_message_rejected` |
| ECDSA verify accepts everything | `modified_signature_rejected` |
| ECDSA on P-384 instead of P-256 | `size:public_key==91` |
| RSA 1024-bit key / exponent 3 | `modulus_is_2048_bits` / `public_exponent_is_65537` |
| RSA decrypt returns garbage | `decrypt_recovers_payload` |
| RSA encryption not randomized | `encryption_is_randomized` |

Run-level behaviour verified by the same self-test:
- A crashing algorithm is recorded as FAIL, the other algorithms still run, and the exit status is 1.
- A missing algorithm is reported UNAVAILABLE with a reason, is not handed to the benchmark, nothing is substituted, and the exit status is 2.
- All 6 healthy algorithms pass.

## 8. How to reproduce

```
docker build -t pqc-benchmark .
docker run --rm -v "%cd%\results:/app/results" pqc-benchmark
docker run --rm pqc-benchmark python -m tests.test_fault_injection
```

Everything runs in Docker, as the report specifies (Sec. 4.1), because the resource profiles C0–C3 are Docker CPU/memory limits.
