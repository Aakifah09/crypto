"""Self-test of the correctness checks: do they actually CATCH broken algorithms?

A check that always passes is worthless. Each case below wraps a real algorithm
with a deliberate, realistic fault and asserts that benchmark/correctness.py
reports it as failed, naming the expected check. A last group asserts the
healthy algorithms still pass (no false alarms) and that a missing algorithm
blocks the run instead of being substituted.

Run inside the container:
    docker run --rm pqc-benchmark python -m tests.test_fault_injection
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from benchmark import algorithms, correctness
from benchmark.algorithms import ECDSAP256, OQSKEM, RSAOAEP, get_algorithm
from cryptography.hazmat.primitives.asymmetric import ec, rsa

TRIALS = 5


class Wrapper:
    """Delegates everything to a real algorithm; cases override single methods."""

    def __init__(self, inner):
        self.inner = inner

    def __getattr__(self, attr):
        return getattr(self.inner, attr)


# ---------------------------------------------------------------- KEM faults
class KEMWrongSecret(Wrapper):
    def decaps(self, sk, ct):
        ss = bytearray(self.inner.decaps(sk, ct))
        ss[0] ^= 1
        return bytes(ss)


class KEMNoImplicitRejection(Wrapper):
    """Returns the last real secret no matter which ciphertext or key is used."""
    last = b""

    def encaps(self, pk):
        ct, ss = self.inner.encaps(pk)
        self.last = ss
        return ct, ss

    def decaps(self, sk, ct):
        return self.last


class KEMDeterministicEncaps(Wrapper):
    cache: dict

    def encaps(self, pk):
        if not hasattr(self, "cache"):
            self.cache = {}
        if pk not in self.cache:
            self.cache[pk] = self.inner.encaps(pk)
        return self.cache[pk]


class KEMWrongParameterSet(OQSKEM):
    """Claims to be ML-KEM-768 but actually runs ML-KEM-512."""

    def __init__(self):
        super().__init__("ML-KEM-512", "NIST category 1")

    @property
    def name(self):
        return "ML-KEM-768"


# ---------------------------------------------------------- signature faults
class SigAcceptsEverything(Wrapper):
    def verify(self, pk, msg, sig):
        return True


class SigRejectsEverything(Wrapper):
    def verify(self, pk, msg, sig):
        return False


class SigOnlyCoversPrefix(Wrapper):
    """Bug: only the first 512 bytes of the message are signed and verified."""

    def sign(self, sk, msg):
        return self.inner.sign(sk, msg[:512])

    def verify(self, pk, msg, sig):
        return self.inner.verify(pk, msg[:512], sig)


class ECDSAWrongCurve(ECDSAP256):
    def keygen(self):
        sk = ec.generate_private_key(ec.SECP384R1())
        return sk.public_key(), sk


# ---------------------------------------------------------------- RSA faults
class RSAWeakKey(RSAOAEP):
    def keygen(self):
        sk = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        return sk.public_key(), sk


class RSAWrongExponent(RSAOAEP):
    def keygen(self):
        sk = rsa.generate_private_key(public_exponent=3, key_size=2048)
        return sk.public_key(), sk


class RSAGarbledDecrypt(Wrapper):
    def decrypt(self, sk, ct):
        return bytes(32)


class RSADeterministic(Wrapper):
    cache: dict

    def encrypt(self, pk, pt):
        if not hasattr(self, "cache"):
            self.cache = {}
        key = id(pk)
        if key not in self.cache:
            self.cache[key] = self.inner.encrypt(pk, pt)
        return self.cache[key]


# ---------------------------------------------------------------- crash
class KeygenCrashes(Wrapper):
    def keygen(self):
        raise RuntimeError("simulated library failure")


FAULT_CASES = [
    # (description, broken algorithm, check that must fail)
    ("ML-KEM-512: decaps returns a wrong secret", KEMWrongSecret(get_algorithm("ML-KEM-512")), "shared_secrets_match"),
    ("ML-KEM-768: no implicit rejection", KEMNoImplicitRejection(get_algorithm("ML-KEM-768")), "tampered_ciphertext_gives_different_secret"),
    ("ML-KEM-768: wrong secret key accepted", KEMNoImplicitRejection(get_algorithm("ML-KEM-768")), "wrong_secret_key_gives_different_secret"),
    ("ML-KEM-512: encapsulation not randomized", KEMDeterministicEncaps(get_algorithm("ML-KEM-512")), "encapsulation_is_randomized"),
    ("ML-KEM-768 label running ML-KEM-512", KEMWrongParameterSet(), "size:ciphertext==1088"),
    ("ML-DSA-44: verify accepts everything", SigAcceptsEverything(get_algorithm("ML-DSA-44")), "modified_message_rejected"),
    ("ML-DSA-65: verify accepts everything", SigAcceptsEverything(get_algorithm("ML-DSA-65")), "wrong_public_key_rejected"),
    ("ML-DSA-44: verify rejects valid signatures", SigRejectsEverything(get_algorithm("ML-DSA-44")), "valid_signature_verifies"),
    ("ML-DSA-65: only first 512 bytes signed", SigOnlyCoversPrefix(get_algorithm("ML-DSA-65")), "truncated_message_rejected"),
    ("ECDSA: verify accepts everything", SigAcceptsEverything(get_algorithm("ECDSA-P256-SHA256")), "modified_signature_rejected"),
    ("ECDSA: P-384 instead of P-256", ECDSAWrongCurve(), "size:public_key==91"),
    ("RSA: 1024-bit key", RSAWeakKey(), "modulus_is_2048_bits"),
    ("RSA: exponent 3 instead of 65537", RSAWrongExponent(), "public_exponent_is_65537"),
    ("RSA: decrypt returns garbage", RSAGarbledDecrypt(get_algorithm("RSA-2048-OAEP-SHA256")), "decrypt_recovers_payload"),
    ("RSA: encryption not randomized", RSADeterministic(get_algorithm("RSA-2048-OAEP-SHA256")), "encryption_is_randomized"),
]


def run_checker(alg) -> correctness.CheckRecorder:
    try:
        return correctness.CHECKERS[alg.kind](alg, TRIALS, {})
    except Exception as exc:
        rec = correctness.CheckRecorder(alg.name)
        rec.record("checker_completed", False, f"{type(exc).__name__}: {exc}")
        return rec


def main() -> int:
    failures = 0

    def report(ok: bool, text: str) -> None:
        nonlocal failures
        failures += not ok
        print(f"[{'OK' if ok else 'MISSED'}] {text}")

    print("Fault injection: each broken algorithm must be caught\n")
    for desc, alg, expected_check in FAULT_CASES:
        rec = run_checker(alg)
        caught = expected_check in rec.results and rec.results[expected_check]["failed"] > 0
        report(caught and not rec.ok, f"{desc}  ->  caught by '{expected_check}'")

    # A crashing algorithm is recorded as FAIL and the run continues with the others.
    print("\nRun-level behaviour\n")
    crash = KeygenCrashes(get_algorithm("ML-KEM-512"))
    with tempfile.TemporaryDirectory() as tmp:
        saved = correctness.REQUESTED_ALGORITHMS
        correctness.REQUESTED_ALGORITHMS = [crash, get_algorithm("ECDSA-P256-SHA256")]
        try:
            status = correctness.run(TRIALS, Path(tmp))
        finally:
            correctness.REQUESTED_ALGORITHMS = saved
    report(status == correctness.EXIT_FAILED, "keygen crash -> recorded as FAIL, run continues, exit status 1")

    # A required algorithm missing from liboqs: reported, never substituted, run blocked.
    missing = OQSKEM("ML-KEM-999", "fake")
    saved_a, saved_c = algorithms.REQUESTED_ALGORITHMS, correctness.REQUESTED_ALGORITHMS
    algorithms.REQUESTED_ALGORITHMS = correctness.REQUESTED_ALGORITHMS = [missing, get_algorithm("ECDSA-P256-SHA256")]
    try:
        avail = algorithms.availability()
        handed_over = [a.name for a in algorithms.get_algorithms()]
        with tempfile.TemporaryDirectory() as tmp:
            status = correctness.run(TRIALS, Path(tmp))
    finally:
        algorithms.REQUESTED_ALGORITHMS, correctness.REQUESTED_ALGORITHMS = saved_a, saved_c
    report(avail["ML-KEM-999"]["available"] is False and avail["ML-KEM-999"]["reason"],
           "missing algorithm -> reported UNAVAILABLE with a reason")
    report(handed_over == ["ECDSA-P256-SHA256"],
           "missing algorithm -> not handed to the benchmark, nothing substituted")
    report(status == correctness.EXIT_UNAVAILABLE, "missing algorithm -> run blocked, exit status 2")

    # No false alarms: every real algorithm passes.
    print("\nNo false alarms\n")
    for alg in algorithms.REQUESTED_ALGORITHMS:
        rec = run_checker(alg)
        report(rec.ok, f"healthy {alg.name} passes")

    print(f"\n{'SELF-TEST PASSED' if failures == 0 else f'SELF-TEST FAILED ({failures})'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
