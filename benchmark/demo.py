"""Toy algorithms for testing the measurement framework (NOT cryptography).

They have the same interface as benchmark/algorithms.py, so the runner treats them exactly
like the real ones:

    python -m benchmark.runner --demo --profile C0

Each one misbehaves in a different, deterministic way so every failure path of the runner
can be exercised without Docker limits or liboqs:

    DEMO-KEM      healthy KEM (keygen / encaps / decaps)
    DEMO-SIG      healthy signature scheme (keygen / sign / verify)
    DEMO-HEAVY    sign() touches DEMO_HEAVY_MB of memory (default 64): shows up in RSS and is
                  OOM-killed under a small --memory limit
    DEMO-FLAKY    every 7th sign() call raises ValueError
    DEMO-CRASH    sign() SIGKILLs its own process on its 8th call (looks like an OOM kill)
    DEMO-HANG     sign() sleeps for an hour on its 9th call (the runner must time it out)

Call counts are per worker process and include the warm-ups. DEMO_SLOWDOWN multiplies the
amount of work, which is how the example data fakes a tighter resource profile.
"""
from __future__ import annotations

import hashlib
import os
import signal
import time
from collections import Counter
from types import SimpleNamespace

from . import workloads

_CALLS: Counter = Counter()


def _work(data: bytes) -> bytes:
    for _ in range(200 * int(os.environ.get("DEMO_SLOWDOWN", "1"))):
        data = hashlib.sha256(data).digest()
    return data


class DemoSignature:
    kind = "signature"

    def __init__(self, name: str, family: str = "post-quantum", fault: str | None = None):
        self.name = name
        self.fault = fault
        self.info = SimpleNamespace(name=name, family=family, kind="signature")

    def keygen(self):
        sk = os.urandom(32)
        return hashlib.sha256(sk).digest(), sk

    def load_secret_key(self, sk):
        return sk

    def encode_public_key(self, pk):
        return pk

    def encode_secret_key(self, sk):
        return sk

    def _inject_fault(self) -> None:
        _CALLS[self.name] += 1
        n = _CALLS[self.name]
        if self.fault == "flaky" and n % 7 == 0:
            raise ValueError("simulated intermittent failure")
        if self.fault == "crash" and n == 8:
            os.kill(os.getpid(), signal.SIGKILL)
        if self.fault == "hang" and n == 9:
            time.sleep(3600)
        if self.fault == "heavy":
            size = int(os.environ.get("DEMO_HEAVY_MB", "64")) * 1024 * 1024
            buf = bytearray(size)
            buf[::4096] = b"\x01" * len(range(0, size, 4096))  # touch every page so it is resident

    def sign(self, sk, msg):
        self._inject_fault()
        return hashlib.sha256(hashlib.sha256(sk).digest() + _work(msg)).digest()

    def verify(self, pk, msg, sig):
        return hashlib.sha256(pk + _work(msg)).digest() == sig


class DemoKEM:
    kind = "kem"

    def __init__(self, name: str = "DEMO-KEM", family: str = "post-quantum"):
        self.name = name
        self.info = SimpleNamespace(name=name, family=family, kind="kem")

    def keygen(self):
        sk = os.urandom(32)
        return hashlib.sha256(sk).digest(), sk

    def load_secret_key(self, sk):
        return sk

    def encode_public_key(self, pk):
        return pk

    def encode_secret_key(self, sk):
        return sk

    def encaps(self, pk):
        ct = os.urandom(48)
        return ct, hashlib.sha256(pk + _work(ct)).digest()

    def decaps(self, sk, ct):
        return hashlib.sha256(hashlib.sha256(sk).digest() + _work(ct)).digest()


_ALGORITHMS = [
    DemoKEM("DEMO-KEM"),
    DemoSignature("DEMO-SIG"),
    DemoSignature("DEMO-HEAVY", family="classical", fault="heavy"),
    DemoSignature("DEMO-FLAKY", family="classical", fault="flaky"),
    DemoSignature("DEMO-CRASH", family="classical", fault="crash"),
    DemoSignature("DEMO-HANG", family="classical", fault="hang"),
]


def availability() -> dict:
    return {a.name: {"available": True, "reason": None} for a in _ALGORITHMS}


def get_algorithms(only_available: bool = True) -> list:
    return list(_ALGORITHMS)


def get_algorithm(name: str):
    for a in _ALGORITHMS:
        if a.name == name:
            return a
    raise KeyError(name)


SIGNATURE_MESSAGE = workloads.SIGNATURE_MESSAGE  # same workload bytes as the real algorithms
