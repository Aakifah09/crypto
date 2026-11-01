# Reproducible environment for the PQC benchmark.
# The base image is pinned by digest and liboqs is built from a pinned tag,
# so every team member measures exactly the same implementation (report Sec. 4.1).
ARG BASE_IMAGE=python:3.11-slim-bookworm@sha256:94a8fee35252d06ab75856f15f12c7bae67b10e8a6da93c7fded82b2610926cd
FROM ${BASE_IMAGE}
ARG BASE_IMAGE

ARG LIBOQS_VERSION=0.16.0

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential cmake ninja-build git ca-certificates libssl-dev \
 && rm -rf /var/lib/apt/lists/*

# Build liboqs as a shared library into /usr/local (liboqs-python finds it there)
# and record exactly which source commit was built.
RUN git clone --depth 1 --branch ${LIBOQS_VERSION} \
        https://github.com/open-quantum-safe/liboqs.git /tmp/liboqs \
 && cmake -S /tmp/liboqs -B /tmp/liboqs/build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_SHARED_LIBS=ON \
        -DOQS_BUILD_ONLY_LIB=ON \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
 && cmake --build /tmp/liboqs/build \
 && cmake --install /tmp/liboqs/build \
 && ldconfig \
 && printf '{"liboqs_tag": "%s", "liboqs_commit": "%s", "build_method": "docker", "compiler": "%s"}\n' \
        "${LIBOQS_VERSION}" "$(git -C /tmp/liboqs rev-parse HEAD)" "$(cc --version | head -1)" \
        > /usr/local/share/liboqs-build.json \
 && rm -rf /tmp/liboqs

ENV OQS_INSTALL_PATH=/usr/local \
    PYTHONUNBUFFERED=1 \
    BASE_IMAGE=${BASE_IMAGE}

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "benchmark.correctness"]
