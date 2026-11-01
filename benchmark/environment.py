"""Record the exact environment: library versions, build commits, image digest,
enabled algorithm names and active container limits (report Sec. 4.1 and 4.4 step 1)."""
from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cryptography
from cryptography.hazmat.backends.openssl import backend as openssl_backend

from .algorithms import load_oqs, oqs_load_error


def _read(path: str) -> str | None:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def liboqs_build_info() -> dict[str, Any] | None:
    """Build record (tag, commit, compiler) written by the Dockerfile."""
    p = Path("/usr/local/share/liboqs-build.json")
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def container_limits() -> dict[str, Any]:
    """Effective cgroup v2 limits as seen from inside the process (Linux only)."""
    if platform.system() != "Linux":
        return {"note": "not Linux; no cgroup limits read"}
    return {
        "cgroup_cpu_max": _read("/sys/fs/cgroup/cpu.max"),          # "max 100000" = no CPU quota
        "cgroup_memory_max": _read("/sys/fs/cgroup/memory.max"),    # "max" = no memory cap
        "cgroup_memory_swap_max": _read("/sys/fs/cgroup/memory.swap.max"),
        "os_cpu_count": os.cpu_count(),
        "mem_total_kb": next((int(line.split()[1]) for line in (_read("/proc/meminfo") or "").splitlines()
                              if line.startswith("MemTotal:")), None),
    }


def environment_info() -> dict[str, Any]:
    oqs = load_oqs()
    info: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "in_docker": Path("/.dockerenv").exists(),
        "base_image": os.environ.get("BASE_IMAGE"),
        "cryptography_version": cryptography.__version__,
        "openssl_version": openssl_backend.openssl_version_text(),
        "liboqs_build": liboqs_build_info(),
        "limits": container_limits(),
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
    print(json.dumps(environment_info(), indent=2))
