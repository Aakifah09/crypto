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
| ECDSA-P256-SHA256 | 91 (DER SPKI) | 138 (DER PKCS#8) | – | – | 69–72 (DER) |

Secondary encodings: the RSA public key is 270 bytes as PKCS#1 DER. The ECDSA public key is 65 bytes as a raw uncompressed point, the private key a 32-byte raw scalar, and a raw r‖s signature 64 bytes.

As the report expects (Sec. 4.5), ML-KEM/ML-DSA sizes and the RSA ciphertext are fixed. ECDSA DER signatures vary (69–72 bytes observed over 100 trials) because of DER integer encoding, not resource limits. The RSA PKCS#8 private key also varies by a few bytes for the same reason.

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
- Run `python -m benchmark.correctness` before benchmarking. It exits with status 1 if any check fails.

## 7. How to reproduce

```
docker build -t pqc-benchmark .
docker run --rm -v "%cd%\results:/app/results" pqc-benchmark
```

Everything runs in Docker, as the report specifies (Sec. 4.1), because the resource profiles C0–C3 are Docker CPU/memory limits.
