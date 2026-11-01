"""Correctness checks that must pass before any algorithm is benchmarked.

Run:  python -m benchmark.correctness [--trials N] [--out results]

Writes:
    results/environment.json           library versions and every algorithm name liboqs enables
    results/supported_algorithms.json  requested algorithms, availability, parameters
    results/correctness.json           every check, pass/fail, per algorithm
    results/output_sizes.csv           key, ciphertext, signature and shared-secret sizes

Exits with status 1 if any check fails, so a CI job or the benchmark runner can
refuse to continue.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Callable

from . import workloads
from .algorithms import EXPECTED_SIZES, REQUESTED_ALGORITHMS, availability
from .environment import environment_info


def flip_bit(data: bytes, index: int = 0, bit: int = 0) -> bytes:
    b = bytearray(data)
    b[index % len(b)] ^= 1 << bit
    return bytes(b)


class CheckRecorder:
    def __init__(self, algorithm: str):
        self.algorithm = algorithm
        self.results: dict[str, dict[str, Any]] = {}

    def record(self, check: str, passed: bool, detail: str | None = None) -> None:
        r = self.results.setdefault(check, {"passed": 0, "failed": 0, "details": []})
        if passed:
            r["passed"] += 1
        else:
            r["failed"] += 1
            if detail and len(r["details"]) < 5:
                r["details"].append(detail)

    def run(self, check: str, fn: Callable[[], bool], detail: str | None = None) -> None:
        try:
            self.record(check, bool(fn()), detail)
        except Exception as exc:  # an unexpected exception is a failure, not a crash
            self.record(check, False, f"{type(exc).__name__}: {exc}")

    @property
    def ok(self) -> bool:
        return all(r["failed"] == 0 for r in self.results.values())


def _size_check(rec: CheckRecorder, alg_name: str, field: str, actual: int) -> None:
    expected = EXPECTED_SIZES.get(alg_name, {}).get(field)
    if expected is not None:
        rec.record(f"size:{field}=={expected}", actual == expected, f"got {actual}")


# ---------------------------------------------------------------------------
# Per-kind checks. Each trial uses a fresh key pair.
# ---------------------------------------------------------------------------
def check_kem(alg, trials: int, sizes: dict) -> CheckRecorder:
    rec = CheckRecorder(alg.name)
    pk2, sk2 = alg.keygen()  # an unrelated key pair for the wrong-key check
    for t in range(trials):
        pk, sk = alg.keygen()
        ct, ss_enc = alg.encaps(pk)
        skh = alg.load_secret_key(sk)   # the handle the benchmark times decaps with
        ss_dec = alg.decaps(skh, ct)
        rec.record("decaps_from_raw_secret_key_bytes_matches", alg.decaps(sk, ct) == ss_enc)

        rec.record("shared_secrets_match", ss_enc == ss_dec, f"trial {t}")
        _size_check(rec, alg.name, "public_key", len(pk))
        _size_check(rec, alg.name, "secret_key", len(sk))
        _size_check(rec, alg.name, "ciphertext", len(ct))
        _size_check(rec, alg.name, "shared_secret", len(ss_enc))

        # ML-KEM uses implicit rejection: a modified ciphertext must NOT give the real secret.
        rec.run("tampered_ciphertext_gives_different_secret",
                lambda: alg.decaps(skh, flip_bit(ct, t)) != ss_enc)
        rec.run("wrong_secret_key_gives_different_secret",
                lambda: alg.decaps(sk2, ct) != ss_enc)
        _, ss_again = alg.encaps(pk)
        rec.record("encapsulation_is_randomized", ss_again != ss_enc)

        if t == 0:
            sizes.update(public_key=len(pk), secret_key=len(sk),
                         ciphertext=len(ct), shared_secret=len(ss_enc))
    return rec


def check_signature(alg, trials: int, sizes: dict) -> CheckRecorder:
    rec = CheckRecorder(alg.name)
    msg = workloads.SIGNATURE_MESSAGE
    pk2, _ = alg.keygen()
    sig_lengths: list[int] = []
    for t in range(trials):
        pk, sk = alg.keygen()
        skh = alg.load_secret_key(sk)   # the handle the benchmark times signing with
        sig = alg.sign(skh, msg)
        sig_lengths.append(len(sig))

        rec.run("valid_signature_verifies", lambda: alg.verify(pk, msg, sig) is True)
        rec.run("modified_message_rejected",
                lambda: alg.verify(pk, flip_bit(msg, t * 7), sig) is False)
        rec.run("truncated_message_rejected", lambda: alg.verify(pk, msg[:-1], sig) is False)
        rec.run("modified_signature_rejected",
                lambda: alg.verify(pk, msg, flip_bit(sig, t * 13)) is False)
        rec.run("wrong_public_key_rejected", lambda: alg.verify(pk2, msg, sig) is False)

        pk_enc = alg.encode_public_key(pk)
        sk_enc = alg.encode_secret_key(sk)
        _size_check(rec, alg.name, "public_key", len(pk_enc))
        _size_check(rec, alg.name, "secret_key", len(sk_enc))
        _size_check(rec, alg.name, "signature", len(sig))

        if t == 0:
            sizes.update(public_key=len(pk_enc), secret_key=len(sk_enc))
            if hasattr(alg, "secondary_sizes"):
                sizes.update(alg.secondary_sizes(pk, sk))
            # Does signing the same message twice give the same bytes? (informational)
            sizes["_signing_deterministic"] = alg.sign(skh, msg) == sig

    sizes["signature_min"] = min(sig_lengths)
    sizes["signature_max"] = max(sig_lengths)
    sizes["signature"] = sig_lengths[0] if min(sig_lengths) == max(sig_lengths) else None
    return rec


def check_pke(alg, trials: int, sizes: dict) -> CheckRecorder:
    rec = CheckRecorder(alg.name)
    pt = workloads.RSA_PAYLOAD
    _, sk2 = alg.keygen()
    for t in range(trials):
        pk, sk = alg.keygen()
        skh = alg.load_secret_key(sk)
        ct = alg.encrypt(pk, pt)

        rec.run("decrypt_recovers_payload", lambda: alg.decrypt(skh, ct) == pt)
        rec.record("modulus_is_2048_bits", pk.key_size == 2048, f"got {pk.key_size}")
        rec.record("public_exponent_is_65537", pk.public_numbers().e == 65537)
        _size_check(rec, alg.name, "ciphertext", len(ct))
        _size_check(rec, alg.name, "public_key", len(alg.encode_public_key(pk)))

        def rejects(fn) -> bool:
            try:
                fn()
                return False
            except ValueError:
                return True

        rec.run("tampered_ciphertext_rejected", lambda: rejects(lambda: alg.decrypt(skh, flip_bit(ct, t))))
        rec.run("wrong_private_key_rejected", lambda: rejects(lambda: alg.decrypt(sk2, ct)))
        rec.record("encryption_is_randomized", alg.encrypt(pk, pt) != ct)

        if t == 0:
            sizes.update(public_key=len(alg.encode_public_key(pk)),
                         secret_key=len(alg.encode_secret_key(sk)),
                         ciphertext=len(ct), plaintext=len(pt))
            sizes.update(alg.secondary_sizes(pk, sk))
    return rec


CHECKERS = {"kem": check_kem, "signature": check_signature, "pke": check_pke}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run(trials: int, out_dir: Path) -> bool:
    out_dir.mkdir(parents=True, exist_ok=True)
    env = environment_info()
    avail = availability()

    supported = []
    correctness: dict[str, Any] = {
        "trials_per_algorithm": trials,
        "workloads": {
            "signature_message_bytes": len(workloads.SIGNATURE_MESSAGE),
            "signature_message_sha256_16": workloads.fingerprint(workloads.SIGNATURE_MESSAGE),
            "rsa_payload_bytes": len(workloads.RSA_PAYLOAD),
            "rsa_payload_sha256_16": workloads.fingerprint(workloads.RSA_PAYLOAD),
        },
        "algorithms": {},
    }
    size_rows: list[dict[str, Any]] = []
    all_ok = True

    for alg in REQUESTED_ALGORITHMS:
        entry = {**alg.info.__dict__, **avail[alg.name]}
        if not avail[alg.name]["available"]:
            entry["correctness_passed"] = None
            supported.append(entry)
            correctness["algorithms"][alg.name] = {"status": "UNAVAILABLE",
                                                   "reason": avail[alg.name]["reason"]}
            print(f"[UNAVAILABLE] {alg.name}: {avail[alg.name]['reason']}")
            continue

        sizes: dict[str, Any] = {}
        rec = CHECKERS[alg.kind](alg, trials, sizes)
        all_ok &= rec.ok
        entry["correctness_passed"] = rec.ok
        supported.append(entry)

        correctness["algorithms"][alg.name] = {
            "status": "PASS" if rec.ok else "FAIL",
            "checks": rec.results,
            "signing_deterministic": sizes.pop("_signing_deterministic", None),
        }
        size_rows.append({"algorithm": alg.name, "kind": alg.kind, "family": alg.info.family, **sizes})

        status = "PASS" if rec.ok else "FAIL"
        n = sum(r["passed"] + r["failed"] for r in rec.results.values())
        print(f"[{status}] {alg.name}: {len(rec.results)} checks, {n} assertions")
        for check, r in rec.results.items():
            if r["failed"]:
                print(f"    FAILED {check}: {r['failed']}x {r['details']}")

    (out_dir / "environment.json").write_text(json.dumps(env, indent=2))
    (out_dir / "supported_algorithms.json").write_text(json.dumps(
        {"liboqs_version": env.get("liboqs_version"),
         "liboqs_python_version": env.get("liboqs_python_version"),
         "cryptography_version": env["cryptography_version"],
         "openssl_version": env["openssl_version"],
         "algorithms": supported}, indent=2))
    (out_dir / "correctness.json").write_text(json.dumps(correctness, indent=2))

    columns = ["algorithm", "kind", "family", "public_key", "secret_key", "ciphertext",
               "shared_secret", "plaintext", "signature", "signature_min", "signature_max"]
    extra = sorted({k for row in size_rows for k in row} - set(columns))
    with open(out_dir / "output_sizes.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns + extra)
        w.writeheader()
        w.writerows(size_rows)

    print(f"\nResults written to {out_dir.resolve()}")
    print("ALL CHECKS PASSED" if all_ok else "SOME CHECKS FAILED")
    return all_ok


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--trials", type=int, default=100, help="fresh key pairs per algorithm (default 100)")
    p.add_argument("--out", type=Path, default=Path("results"))
    args = p.parse_args(argv)
    return 0 if run(args.trials, args.out) else 1


if __name__ == "__main__":
    sys.exit(main())
