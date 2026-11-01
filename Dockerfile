# Reproducible environment for the PQC benchmark.
# liboqs is built from source at a pinned tag so every team member
# measures exactly the same implementation.
FROM python:3.11-slim-bookworm

ARG LIBOQS_VERSION=0.16.0
ARG LIBOQS_PYTHON_VERSION=0.16.0.2

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential cmake ninja-build git ca-certificates libssl-dev \
 && rm -rf /var/lib/apt/lists/*

# Build liboqs as a shared library into /usr/local (liboqs-python finds it there).
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
 && rm -rf /tmp/liboqs

ENV OQS_INSTALL_PATH=/usr/local \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "benchmark.correctness"]
