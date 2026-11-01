# Module 1 Test Report: Cryptographic Operations and Correctness

**Owner:** Aakifah Minhaj
**Date:** 2026-11-01
**Result:** All 6 requested algorithms are available and pass every correctness check (100 trials each, fresh key pair per trial). They are ready to hand to the benchmarking framework.

## 1. Environment (Task 1)

| Component | Version |
|---|---|
| liboqs (C library, built from source, tag `0.16.0`) | 0.16.0 |
| liboqs-python | 0.16.0.2 |
| cryptography (pyca) | 46.0.7 |
| OpenSSL (cryptography backend) | 3.5.6 (7 Apr 2026) |
| Python | 3.11.18 |
| Platform | Docker `python:3.11-slim-bookworm`, Linux x86_64 (WSL2 kernel 6.18) |

These results were produced in Docker (see `Dockerfile`). `setup_liboqs.py` builds the same pinned liboqs version natively for machines without Docker. Either way, every team member uses the same implementation.

The installed liboqs build enables **41 KEMs and 221 signature schemes**. The full lists are in `results/environment.json` (`liboqs_enabled_kems`, `liboqs_enabled_sigs`). The names relevant to this project are:

- KEM: `ML-KEM-512`, `ML-KEM-768`, `ML-KEM-1024`
- Signature: `ML-DSA-44`, `ML-DSA-65`, `ML-DSA-87`

## 2. Supported algorithms

| Algorithm | Kind | Library | Standard | Status |
|---|---|---|---|---|
| ML-KEM-512 | KEM | liboqs | FIPS 203 | Available, PASS |
| ML-KEM-768 | KEM | liboqs | FIPS 203 | Available, PASS |
| ML-DSA-44 | Signature | liboqs | FIPS 204 | Available, PASS |
| ML-DSA-65 | Signature | liboqs | FIPS 204 | Available, PASS |
| RSA-2048-OAEP-SHA256 | Public-key encryption | cryptography/OpenSSL | RFC 8017 | Available, PASS |
| ECDSA-P256-SHA256 | Signature | cryptography/OpenSSL | FIPS 186-5 | Available, PASS |

**Unavailable algorithms:** none. Every requested algorithm exists under its exact name in the chosen library versions, and no substitution was made. `algorithms.availability()` checks this on every run. If a future liboqs build drops one of these names, the algorithm is reported as `UNAVAILABLE` with a reason and left out. Nothing replaces it.

## 3. Parameters and encodings (Tasks 2–5)

| Algorithm | Parameters | Encoding used for sizes |
|---|---|---|
| ML-KEM-512/768 | liboqs defaults | Raw FIPS 203 byte strings |
| ML-DSA-44/65 | Pure ML-DSA, empty context, liboqs default signing (observed to be randomized/hedged) | Raw FIPS 204 byte strings |
| RSA-2048 | n = 2048 bits, e = 65537, OAEP, SHA-256, MGF1-SHA-256, no label | Public key: DER SubjectPublicKeyInfo. Private key: DER PKCS#8. Ciphertext: raw 256 bytes |
| ECDSA P-256 | secp256r1, SHA-256, random nonce (OpenSSL default) | Public key: SEC1 uncompressed point. Private key: raw 32-byte scalar. Signature: DER |

**Workloads** (`benchmark/workloads.py`) are fixed and deterministic:

| Workload | Size | SHA-256 (first 16 hex) |
|---|---|---|
| Signature message (ML-DSA, ECDSA) | 1,024 bytes | `2d8d54375019ef51` |
| RSA-OAEP payload | 32 bytes | `40c05e1ab2aade4f` |

Both are SHAKE-256 output over a fixed label. Anyone can regenerate them, and the fingerprints let any benchmark result show which inputs it used.

## 4. Correctness checks

Each algorithm ran 100 trials, each with a fresh key pair. A check passes only if it held in all 100 trials. 0 failures were recorded.

**ML-KEM-512 / ML-KEM-768**
- Encapsulated and decapsulated shared secrets match
- Public key, secret key, ciphertext and shared-secret sizes equal the FIPS 203 values
- A ciphertext with one bit flipped decapsulates to a *different* secret (implicit rejection)
- Decapsulating with an unrelated secret key gives a different secret
- Two encapsulations to the same key give different secrets (randomized)

**ML-DSA-44 / ML-DSA-65, ECDSA P-256**
- A valid signature verifies
- A message with one bit flipped is rejected
- A message truncated by one byte is rejected
- A signature with one bit flipped is rejected
- An unrelated public key is rejected
- Key and signature sizes equal the FIPS 204 values (ML-DSA) or the expected encodings (ECDSA)

**RSA-2048-OAEP-SHA256**
- Decryption recovers the 32-byte payload
- Modulus is 2048 bits and e = 65537
- Ciphertext is 256 bytes and the SPKI public key is 294 bytes
- A ciphertext with one bit flipped raises a decryption error
- Decrypting with an unrelated private key raises a decryption error
- Encrypting the same payload twice gives different ciphertexts (OAEP is randomized)

## 5. Output sizes (bytes)

| Algorithm | Public key | Secret key | Ciphertext | Shared secret | Signature |
|---|---|---|---|---|---|
| ML-KEM-512 | 800 | 1,632 | 768 | 32 | – |
| ML-KEM-768 | 1,184 | 2,400 | 1,088 | 32 | – |
| ML-DSA-44 | 1,312 | 2,560 | – | – | 2,420 |
| ML-DSA-65 | 1,952 | 4,032 | – | – | 3,309 |
| RSA-2048-OAEP-SHA256 | 294 (SPKI) | ≈1,218 (PKCS#8) | 256 | – | – |
| ECDSA-P256-SHA256 | 65 (raw point) | 32 (raw scalar) | – | – | 70–72 (DER) |

Secondary encodings: the RSA public key is 270 bytes as PKCS#1 DER. The ECDSA public key is 91 bytes as SPKI DER, the private key 138 bytes as PKCS#8 DER, and a raw r‖s signature is 64 bytes.

Notes:
- ECDSA DER signatures vary in length because r and s are DER INTEGERs. The 100 trials observed 70–72 bytes.
- The RSA PKCS#8 private key length varies by a few bytes between keys, also because of DER integer encoding. The table shows the value from the first trial.
- All ML-KEM and ML-DSA sizes are constant and match the standards exactly.

## 6. Notes for the benchmarking framework

- Use `benchmark.algorithms.get_algorithms()`. It returns only algorithms that are available, and each one has `keygen`, `encaps`/`decaps`, `sign`/`verify` or `encrypt`/`decrypt` to time separately.
- The liboqs wrappers create and free a small liboqs context object on every call. This keeps each operation independent, and its overhead is included in the timing of every operation.
- Run `python -m benchmark.correctness` before every benchmark run. It exits with status 1 if any check fails.

## 7. How to reproduce

```
docker build -t pqc-benchmark .
docker run --rm -v "%cd%\results:/app/results" pqc-benchmark
```

Or, without Docker (needs a C compiler; see README):

```
python setup_liboqs.py
python -m benchmark.correctness
```

The run writes `results/environment.json`, `results/supported_algorithms.json`, `results/correctness.json` and `results/output_sizes.csv`.
