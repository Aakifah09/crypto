"""Fixed workloads shared by every algorithm and every benchmark run.

The inputs are deterministic, so every run and every team member signs and
encrypts exactly the same bytes. They come from SHAKE-256 over a fixed label,
which gives incompressible bytes with no special structure, and anyone can
regenerate them.
"""
import hashlib

SIGNATURE_MESSAGE_SIZE = 1024  # bytes, used for ML-DSA and ECDSA sign/verify
RSA_PAYLOAD_SIZE = 32          # bytes, used for RSA-OAEP encrypt/decrypt

SIGNATURE_MESSAGE: bytes = hashlib.shake_256(
    b"pqc-benchmark/signature-message/v1"
).digest(SIGNATURE_MESSAGE_SIZE)

RSA_PAYLOAD: bytes = hashlib.shake_256(
    b"pqc-benchmark/rsa-payload/v1"
).digest(RSA_PAYLOAD_SIZE)

assert len(SIGNATURE_MESSAGE) == SIGNATURE_MESSAGE_SIZE
assert len(RSA_PAYLOAD) == RSA_PAYLOAD_SIZE


def fingerprint(data: bytes) -> str:
    """Short SHA-256 fingerprint so reports can show which input was used."""
    return hashlib.sha256(data).hexdigest()[:16]
