"""Algorithm implementations used by the benchmark.

Every algorithm has the same small interface, so the benchmarking framework can
time each operation on its own:

    KEM        keygen() -> (pk, sk)   encaps(pk) -> (ct, ss)   decaps(sk, ct) -> ss
    Signature  keygen() -> (pk, sk)   sign(sk, msg) -> sig     verify(pk, msg, sig) -> bool
    PKE        keygen() -> (pk, sk)   encrypt(pk, pt) -> ct    decrypt(sk, ct) -> pt

Post-quantum algorithms come from liboqs (through liboqs-python). Classical
baselines come from pyca/cryptography (OpenSSL backend).

Encodings (used for all size measurements):
    ML-KEM / ML-DSA   raw byte encodings defined in FIPS 203 / FIPS 204, as liboqs produces them
    RSA-2048          public key: DER SubjectPublicKeyInfo, private key: DER PKCS#8 (unencrypted)
                      ciphertext: raw 256-byte OAEP block
    ECDSA P-256       public key: DER SubjectPublicKeyInfo, private key: DER PKCS#8 (unencrypted)
                      signature: DER-encoded ECDSA-Sig-Value (variable length, at most 72 bytes)
    These follow the report (Sec. 4.4 step 5: "liboqs raw byte strings for PQC; DER
    SubjectPublicKeyInfo for classical"). Raw point / scalar / r||s and PKCS#1 sizes
    are reported as secondary sizes.

Timing contract for the benchmark (report Sec. 4.4 step 3, setup outside timed blocks):
    pk, sk = alg.keygen()                 # timed: key generation
    skh = alg.load_secret_key(sk)         # NOT timed: setup
    ct, ss = alg.encaps(pk)               # timed            (KEM)
    alg.decaps(skh, ct)                   # timed            (KEM)
    sig = alg.sign(skh, msg)              # timed            (signature)
    alg.verify(pk, msg, sig)              # timed            (signature)
    ct = alg.encrypt(pk, pt); alg.decrypt(skh, ct)   # timed (RSA)
    Correctness comparisons (e.g. shared-secret match) happen outside timing.

If an algorithm is not enabled in the installed liboqs build, it is reported as
unavailable. No other algorithm is ever substituted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

# ---------------------------------------------------------------------------
# liboqs loading (lazy, so the classical code still works without liboqs)
# ---------------------------------------------------------------------------
_oqs = None
_oqs_error: str | None = None


def load_oqs():
    """Import liboqs-python once. Returns the module, or None if it cannot be loaded."""
    global _oqs, _oqs_error
    if _oqs is None and _oqs_error is None:
        try:
            import oqs  # noqa: WPS433 (runtime import on purpose)
            _oqs = oqs
        except (Exception, SystemExit) as exc:  # liboqs-python can raise SystemExit when the C library is missing
            _oqs_error = f"{type(exc).__name__}: {exc}"
    return _oqs


def oqs_load_error() -> str | None:
    load_oqs()
    return _oqs_error


# ---------------------------------------------------------------------------
# Expected sizes in bytes (FIPS 203 Table 3, FIPS 204 Table 2)
# ---------------------------------------------------------------------------
EXPECTED_SIZES: dict[str, dict[str, int]] = {
    "ML-KEM-512": {"public_key": 800, "secret_key": 1632, "ciphertext": 768, "shared_secret": 32},
    "ML-KEM-768": {"public_key": 1184, "secret_key": 2400, "ciphertext": 1088, "shared_secret": 32},
    "ML-DSA-44": {"public_key": 1312, "secret_key": 2560, "signature": 2420},
    "ML-DSA-65": {"public_key": 1952, "secret_key": 4032, "signature": 3309},
    "RSA-2048-OAEP-SHA256": {"public_key": 294, "ciphertext": 256},
    "ECDSA-P256-SHA256": {"public_key": 91, "secret_key": 138},
}


@dataclass(frozen=True)
class AlgorithmInfo:
    name: str                 # name used in this project / reports
    kind: str                 # "kem" | "signature" | "pke"
    family: str               # "post-quantum" | "classical"
    library: str              # implementing library
    library_name: str         # identifier passed to the library
    standard: str
    security_category: str
    parameters: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# liboqs context handling
#
# Creating a liboqs context object costs about as much as an ML-KEM operation
# itself (measured: ML-KEM-512 decaps 54 us with per-call context creation vs
# 28 us with a reused context). The report requires setup to stay outside the
# timed blocks, so:
#   * keygen / encaps / verify reuse one context per algorithm (they do not
#     depend on a secret key);
#   * decaps / sign take a secret-key handle from load_secret_key(), which the
#     benchmark calls BEFORE starting the timer.
# Passing raw secret-key bytes to decaps/sign still works (convenient for
# tests), but then the context is created inside the call.
# ---------------------------------------------------------------------------
class OQSSecretKey:
    """A liboqs context holding a secret key. Freed (and the key wiped) when garbage-collected."""
    __slots__ = ("ctx",)

    def __init__(self, ctx):
        self.ctx = ctx

    def __del__(self):
        try:
            self.ctx.free()
        except Exception:
            pass


class _OQSBase:
    _ctx_class: str  # "KeyEncapsulation" or "Signature"

    @property
    def name(self) -> str:
        return self.info.name

    def _shared(self):
        ctx = getattr(self, "_ctx", None)
        if ctx is None:
            ctx = getattr(load_oqs(), self._ctx_class)(self.info.library_name)
            self._ctx = ctx
        return ctx

    def keygen(self) -> tuple[bytes, bytes]:
        ctx = self._shared()
        pk = ctx.generate_keypair()
        sk = ctx.export_secret_key()
        return bytes(pk), bytes(sk)

    def load_secret_key(self, sk: bytes) -> OQSSecretKey:
        """Untimed setup: wrap secret-key bytes in a reusable liboqs context."""
        return OQSSecretKey(getattr(load_oqs(), self._ctx_class)(self.info.library_name, secret_key=sk))

    def _sk(self, sk) -> OQSSecretKey:
        return sk if isinstance(sk, OQSSecretKey) else self.load_secret_key(sk)

    # Encodings are already raw bytes.
    def encode_public_key(self, pk: bytes) -> bytes:
        return pk

    def encode_secret_key(self, sk: bytes) -> bytes:
        return sk


# ---------------------------------------------------------------------------
# Post-quantum: ML-KEM (FIPS 203)
# ---------------------------------------------------------------------------
class OQSKEM(_OQSBase):
    kind = "kem"
    _ctx_class = "KeyEncapsulation"

    def __init__(self, name: str, category: str):
        self.info = AlgorithmInfo(
            name=name, kind="kem", family="post-quantum", library="liboqs",
            library_name=name, standard="FIPS 203", security_category=category,
            parameters={"encoding": "raw FIPS 203 byte strings (liboqs)"},
        )

    def encaps(self, pk: bytes) -> tuple[bytes, bytes]:
        ct, ss = self._shared().encap_secret(pk)
        return bytes(ct), bytes(ss)

    def decaps(self, sk, ct: bytes) -> bytes:
        handle = self._sk(sk)  # keep a reference so the context is not freed mid-call
        return bytes(handle.ctx.decap_secret(ct))


# ---------------------------------------------------------------------------
# Post-quantum: ML-DSA (FIPS 204)
# ---------------------------------------------------------------------------
class OQSSignature(_OQSBase):
    kind = "signature"
    _ctx_class = "Signature"

    def __init__(self, name: str, category: str):
        self.info = AlgorithmInfo(
            name=name, kind="signature", family="post-quantum", library="liboqs",
            library_name=name, standard="FIPS 204", security_category=category,
            parameters={"encoding": "raw FIPS 204 byte strings (liboqs)",
                        "context": "empty", "prehash": "none (pure ML-DSA)",
                        "signing_mode": "liboqs default (hedged/randomized)"},
        )

    def sign(self, sk, message: bytes) -> bytes:
        handle = self._sk(sk)  # keep a reference so the context is not freed mid-call
        return bytes(handle.ctx.sign(message))

    def verify(self, pk: bytes, message: bytes, signature: bytes) -> bool:
        return bool(self._shared().verify(message, signature, pk))


# ---------------------------------------------------------------------------
# Classical baseline: RSA-2048 with OAEP (SHA-256, MGF1-SHA-256, no label)
# ---------------------------------------------------------------------------
class RSAOAEP:
    kind = "pke"
    KEY_SIZE = 2048
    PUBLIC_EXPONENT = 65537

    def __init__(self):
        self.info = AlgorithmInfo(
            name="RSA-2048-OAEP-SHA256", kind="pke", family="classical",
            library="cryptography (OpenSSL)", library_name="rsa / padding.OAEP",
            standard="RFC 8017 (PKCS #1 v2.2)", security_category="~112-bit classical",
            parameters={"modulus_bits": self.KEY_SIZE, "public_exponent": self.PUBLIC_EXPONENT,
                        "padding": "OAEP", "hash": "SHA-256", "mgf": "MGF1-SHA-256", "label": None,
                        "public_key_encoding": "DER SubjectPublicKeyInfo",
                        "secret_key_encoding": "DER PKCS#8 (unencrypted)"},
        )
        self._padding = padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        )

    @property
    def name(self) -> str:
        return self.info.name

    def keygen(self) -> tuple[rsa.RSAPublicKey, rsa.RSAPrivateKey]:
        sk = rsa.generate_private_key(public_exponent=self.PUBLIC_EXPONENT, key_size=self.KEY_SIZE)
        return sk.public_key(), sk

    def load_secret_key(self, sk):
        return sk  # already a ready-to-use key object

    def encrypt(self, pk: rsa.RSAPublicKey, plaintext: bytes) -> bytes:
        return pk.encrypt(plaintext, self._padding)

    def decrypt(self, sk: rsa.RSAPrivateKey, ciphertext: bytes) -> bytes:
        return sk.decrypt(ciphertext, self._padding)

    def encode_public_key(self, pk: rsa.RSAPublicKey) -> bytes:
        return pk.public_bytes(serialization.Encoding.DER,
                               serialization.PublicFormat.SubjectPublicKeyInfo)

    def encode_secret_key(self, sk: rsa.RSAPrivateKey) -> bytes:
        return sk.private_bytes(serialization.Encoding.DER,
                                serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())

    def secondary_sizes(self, pk, sk) -> dict[str, int]:
        return {
            "public_key_der_pkcs1": len(pk.public_bytes(serialization.Encoding.DER,
                                                        serialization.PublicFormat.PKCS1)),
            "modulus_bytes": (pk.key_size + 7) // 8,
        }


# ---------------------------------------------------------------------------
# Classical baseline: ECDSA over P-256 with SHA-256
# ---------------------------------------------------------------------------
class ECDSAP256:
    kind = "signature"

    def __init__(self):
        self.info = AlgorithmInfo(
            name="ECDSA-P256-SHA256", kind="signature", family="classical",
            library="cryptography (OpenSSL)", library_name="ec.SECP256R1 / ec.ECDSA(SHA256)",
            standard="FIPS 186-5", security_category="~128-bit classical",
            parameters={"curve": "secp256r1 (P-256)", "hash": "SHA-256",
                        "nonce": "random (OpenSSL default)",
                        "public_key_encoding": "DER SubjectPublicKeyInfo",
                        "secret_key_encoding": "DER PKCS#8 (unencrypted)",
                        "signature_encoding": "DER ECDSA-Sig-Value"},
        )
        self._alg = ec.ECDSA(hashes.SHA256())

    @property
    def name(self) -> str:
        return self.info.name

    def keygen(self) -> tuple[ec.EllipticCurvePublicKey, ec.EllipticCurvePrivateKey]:
        sk = ec.generate_private_key(ec.SECP256R1())
        return sk.public_key(), sk

    def sign(self, sk: ec.EllipticCurvePrivateKey, message: bytes) -> bytes:
        return sk.sign(message, self._alg)

    def verify(self, pk: ec.EllipticCurvePublicKey, message: bytes, signature: bytes) -> bool:
        try:
            pk.verify(signature, message, self._alg)
            return True
        except InvalidSignature:
            return False

    def load_secret_key(self, sk):
        return sk  # already a ready-to-use key object

    def encode_public_key(self, pk: ec.EllipticCurvePublicKey) -> bytes:
        return pk.public_bytes(serialization.Encoding.DER,
                               serialization.PublicFormat.SubjectPublicKeyInfo)

    def encode_secret_key(self, sk: ec.EllipticCurvePrivateKey) -> bytes:
        return sk.private_bytes(serialization.Encoding.DER,
                                serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())

    @staticmethod
    def signature_raw_rs(signature: bytes) -> bytes:
        r, s = decode_dss_signature(signature)
        return r.to_bytes(32, "big") + s.to_bytes(32, "big")

    def secondary_sizes(self, pk, sk) -> dict[str, int]:
        return {
            "public_key_raw_point": len(pk.public_bytes(serialization.Encoding.X962,
                                                        serialization.PublicFormat.UncompressedPoint)),
            "secret_key_raw_scalar": 32,
            "signature_raw_r_s": 64,
        }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
REQUESTED_ALGORITHMS = [
    OQSKEM("ML-KEM-512", "NIST category 1"),
    OQSKEM("ML-KEM-768", "NIST category 3"),
    OQSSignature("ML-DSA-44", "NIST category 2"),
    OQSSignature("ML-DSA-65", "NIST category 3"),
    RSAOAEP(),
    ECDSAP256(),
]


def availability() -> dict[str, dict[str, Any]]:
    """For every requested algorithm, say whether the installed library provides it.

    An algorithm that is missing is reported with a reason. Nothing is substituted.
    """
    oqs = load_oqs()
    enabled_kems = set(oqs.get_enabled_kem_mechanisms()) if oqs else set()
    enabled_sigs = set(oqs.get_enabled_sig_mechanisms()) if oqs else set()

    report: dict[str, dict[str, Any]] = {}
    for alg in REQUESTED_ALGORITHMS:
        if alg.info.library == "liboqs":
            if oqs is None:
                report[alg.name] = {"available": False, "reason": f"liboqs could not be loaded ({oqs_load_error()})"}
                continue
            pool = enabled_kems if alg.kind == "kem" else enabled_sigs
            if alg.info.library_name in pool:
                report[alg.name] = {"available": True, "reason": None}
            else:
                report[alg.name] = {"available": False,
                                    "reason": f"'{alg.info.library_name}' is not enabled in liboqs {oqs.oqs_version()}"}
        else:
            report[alg.name] = {"available": True, "reason": None}
    return report


def get_algorithms(only_available: bool = True) -> list:
    """Algorithms to hand to the benchmarking framework (available ones only by default)."""
    if not only_available:
        return list(REQUESTED_ALGORITHMS)
    avail = availability()
    return [a for a in REQUESTED_ALGORITHMS if avail[a.name]["available"]]


def get_algorithm(name: str):
    for alg in REQUESTED_ALGORITHMS:
        if alg.name == name:
            return alg
    raise KeyError(f"Unknown algorithm '{name}'")
