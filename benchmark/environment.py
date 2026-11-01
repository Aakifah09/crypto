"""Record the exact library versions and the algorithm names they provide."""
from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone
from typing import Any

import cryptography
from cryptography.hazmat.backends.openssl import backend as openssl_backend

from .algorithms import load_oqs, oqs_load_error


def environment_info() -> dict[str, Any]:
    oqs = load_oqs()
    info: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cryptography_version": cryptography.__version__,
        "openssl_version": openssl_backend.openssl_version_text(),
    }
    if oqs is not None:
        info.update({
            "liboqs_version": oqs.oqs_version(),
            "liboqs_python_version": oqs.oqs_python_version(),
            "liboqs_enabled_kems": list(oqs.get_enabled_kem_mechanisms()),
            "liboqs_enabled_sigs": list(oqs.get_enabled_sig_mechanisms()),
        })
    else:
        info.update({"liboqs_version": None, "liboqs_load_error": oqs_load_error()})
    return info


if __name__ == "__main__":
    import json
    print(json.dumps(environment_info(), indent=2))
