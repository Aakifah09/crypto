"""Install everything needed to run the benchmark WITHOUT Docker.

    python setup_liboqs.py

What it does:
  1. pip-installs the pinned Python packages (liboqs-python, cryptography)
     plus the build tools cmake and ninja.
  2. Downloads the liboqs source code at the pinned version.
  3. Compiles it and installs it to ~/_oqs, the folder liboqs-python checks
     automatically, so you don't need to set any environment variables.
  4. Checks that Python can load it.

You need a C compiler (the only thing pip cannot install):
  Windows : "Build Tools for Visual Studio" with the "Desktop development with C++" workload
            https://visualstudio.microsoft.com/visual-cpp-build-tools/
  macOS   : xcode-select --install
  Linux   : sudo apt install build-essential   (or your distro's equivalent)
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

LIBOQS_VERSION = "0.16.0"
SOURCE_URL = f"https://github.com/open-quantum-safe/liboqs/archive/refs/tags/{LIBOQS_VERSION}.tar.gz"
INSTALL_DIR = Path(os.environ.get("OQS_INSTALL_PATH", Path.home() / "_oqs"))
REPO_DIR = Path(__file__).resolve().parent
SYSTEM = platform.system()

COMPILER_HELP = {
    "Windows": 'Install "Build Tools for Visual Studio" and tick "Desktop development with C++":\n'
               "  https://visualstudio.microsoft.com/visual-cpp-build-tools/\n"
               "Then open a NEW terminal and run this script again.",
    "Darwin": "Run:  xcode-select --install   then run this script again.",
    "Linux": "Run:  sudo apt install build-essential   (Debian/Ubuntu)\n"
             "  or: sudo dnf groupinstall 'Development Tools'   (Fedora)\nthen run this script again.",
}


def step(msg: str) -> None:
    print(f"\n==> {msg}", flush=True)


def fail(msg: str) -> None:
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str], **kw) -> None:
    print("   $", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def liboqs_installed() -> bool:
    candidates = {
        "Windows": ["bin/oqs.dll", "bin/liboqs.dll"],
        "Darwin": ["lib/liboqs.dylib"],
    }.get(SYSTEM, ["lib/liboqs.so", "lib64/liboqs.so"])
    return any((INSTALL_DIR / c).exists() for c in candidates)


def oqs_loads() -> str | None:
    """Return the liboqs version if Python can load it, else None."""
    r = subprocess.run(
        [sys.executable, "-c", "import oqs, sys; sys.stdout.write(oqs.oqs_version())"],
        capture_output=True, text=True, cwd=tempfile.gettempdir(),
        env={**os.environ, "OQS_INSTALL_PATH": str(INSTALL_DIR)},
    )
    lines = r.stdout.strip().splitlines()  # liboqs-python may print a notice line first
    return lines[-1].strip() if r.returncode == 0 and lines else None


def check_compiler() -> None:
    if SYSTEM == "Windows":
        return  # CMake finds Visual Studio itself; a missing install is reported at configure time
    if not any(shutil.which(c) for c in ("cc", "gcc", "clang")):
        fail("No C compiler found.\n" + COMPILER_HELP.get(SYSTEM, COMPILER_HELP["Linux"]))


def main() -> None:
    if sys.version_info < (3, 9):
        fail(f"Python 3.9 or newer is required (you have {platform.python_version()}).")

    step("Installing Python packages")
    run([sys.executable, "-m", "pip", "install", "-r", REPO_DIR / "requirements.txt", "cmake", "ninja"])

    if liboqs_installed() and oqs_loads() == LIBOQS_VERSION:
        step(f"liboqs {LIBOQS_VERSION} is already installed in {INSTALL_DIR}. Nothing to do.")
        return

    step("Checking for a C compiler")
    check_compiler()

    import cmake  # installed above
    import ninja
    cmake_exe = Path(cmake.CMAKE_BIN_DIR) / ("cmake.exe" if SYSTEM == "Windows" else "cmake")
    ninja_exe = Path(ninja.BIN_DIR) / ("ninja.exe" if SYSTEM == "Windows" else "ninja")

    with tempfile.TemporaryDirectory(prefix="liboqs-build-") as tmp:
        tmp = Path(tmp)
        step(f"Downloading liboqs {LIBOQS_VERSION}")
        archive = tmp / "liboqs.tar.gz"
        urllib.request.urlretrieve(SOURCE_URL, archive)
        with tarfile.open(archive) as tf:
            if hasattr(tarfile, "data_filter"):
                tf.extractall(tmp, filter="data")
            else:
                tf.extractall(tmp)
        src = tmp / f"liboqs-{LIBOQS_VERSION}"
        build = tmp / "build"

        step("Configuring (CMake)")
        cfg = [cmake_exe, "-S", src, "-B", build,
               "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_SHARED_LIBS=ON",
               "-DOQS_BUILD_ONLY_LIB=ON", f"-DCMAKE_INSTALL_PREFIX={INSTALL_DIR}"]
        if SYSTEM == "Windows":
            cfg.append("-DCMAKE_WINDOWS_EXPORT_ALL_SYMBOLS=TRUE")  # Visual Studio generator, auto-detected
        else:
            cfg += ["-G", "Ninja", f"-DCMAKE_MAKE_PROGRAM={ninja_exe}"]
        try:
            run(cfg)
        except subprocess.CalledProcessError:
            fail("CMake could not configure the build. This usually means no C compiler was found.\n"
                 + COMPILER_HELP.get(SYSTEM, COMPILER_HELP["Linux"]))

        step("Compiling liboqs (this takes a few minutes)")
        run([cmake_exe, "--build", build, "--config", "Release", "--parallel"])

        step(f"Installing to {INSTALL_DIR}")
        run([cmake_exe, "--install", build, "--config", "Release"])

    step("Checking that Python can load liboqs")
    version = oqs_loads()
    if version != LIBOQS_VERSION:
        fail(f"liboqs was built but Python could not load it (got {version!r}).")
    print(f"   liboqs {version} OK")

    extra = "" if "OQS_INSTALL_PATH" not in os.environ else \
        f"\n(Keep OQS_INSTALL_PATH={INSTALL_DIR} set when running the benchmark.)"
    step("Done. Now run:  python -m benchmark.correctness" + extra)


if __name__ == "__main__":
    main()
