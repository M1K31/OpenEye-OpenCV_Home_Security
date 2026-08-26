# Multi-stage build for optimized production image

# ============================================
# Stage 1: Frontend Builder - Build React app
# ============================================
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

# Copy frontend package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci --legacy-peer-deps

# Copy frontend source
COPY frontend/ ./

# Build frontend
RUN npm run build

# ============================================
# Stage 2: Python Builder - Compile dependencies
# ============================================
# 3.12 to match the shipped macOS bundle. Three different Pythons were in
# play — CI on 3.9-3.11, Docker on 3.11, the .app on 3.12.8 — so nothing
# tested what users actually run. The lock below is resolved for 3.12.
FROM python:3.12-slim AS builder

# Install build dependencies
#
# libportaudio2 is the RUNTIME library, not the portaudio19-dev headers this
# previously installed. Two-way audio moved from PyAudio to sounddevice, which
# ships pure-Python wheels and never compiles, so the headers and their
# toolchain are no longer needed to build the image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    pkg-config \
    libopencv-dev \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libboost-python-dev \
    libportaudio2 \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy and install Python dependencies.
#
# The lock is preferred when present. Without it the image resolved fresh from
# PyPI on every build, so two builds of the same commit could ship different
# software — which is not hypothetical: the macOS bundle was found running
# fastapi 0.141 while the test suite validated 0.128.
#
# requirements.txt remains the fallback so a missing or stale lock cannot break
# the build; it describes intent, the lock describes the exact set.
COPY requirements.txt requirements-ecosystem.txt ./
COPY requirements.linux-py312.loc[k] ./
# setuptools is NOT upgraded here. It is pinned below 82 because that
# release removed pkg_resources, which face_recognition_models imports at
# module load. Upgrading it here used to be harmless only because
# installing requirements.txt downgraded it again; installing from the
# lock does not, so the upgrade would leave the image unable to start.
RUN pip install --user --no-cache-dir --upgrade pip wheel && \
    if [ -f requirements.linux-py312.lock ]; then \
        echo "Installing from requirements.linux-py312.lock" && \
        pip install --user --no-cache-dir -r requirements.linux-py312.lock; \
    else \
        echo "No lock found; resolving from requirements.txt" && \
        pip install --user --no-cache-dir -r requirements.txt; \
    fi && \
    # Ecosystem packages now come from PyPI instead of a git URL pinned to a
    # commit SHA. That pin named the PRE-RENAME distribution `ecosystem-auth`,
    # which ships the same `ecosystem_auth` module as the published
    # `appecosystem-auth` — so once anything in this image installed the
    # published package, two distributions would have owned the same files.
    #
    # The SHA pin was a supply-chain control (F-06: stop an unpinned branch
    # changing the build). PyPI releases are immutable per version, so the
    # equivalent control here is the version floor in requirements-ecosystem.txt;
    # pin exact versions there if you want byte-identical rebuilds.
    pip install --user --no-cache-dir -r requirements-ecosystem.txt

# ============================================
# Stage 3: Runtime - Minimal production image
# ============================================
FROM python:3.12-slim

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1 \
    libopenblas0 \
    liblapack3 \
    ffmpeg \
    curl \
    libportaudio2 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user first
RUN useradd -m -u 1000 openeye && \
    mkdir -p /app/data /app/config /app/models /app/logs /app/frontend/dist && \
    chown -R openeye:openeye /app

# Upgrade the base image's pip before anything else lands here.
#
# Docker Scout reports vulnerable msgpack, setuptools and jaraco-context in this
# image, and they are not the application's copies — those are current. They live
# inside pip's vendored tree (pip/_vendor/msgpack and friends), which ships with
# the base image. Pinning them in requirements.txt fixes nothing, because nothing
# imports them: they are pip's own bundled dependencies.
#
# A newer pip vendors newer versions of them, which is the only lever available
# short of deleting pip. pip is deliberately kept: installing the optional
# object-detection and ecosystem sets is a runtime action, and an image without
# pip cannot perform it.
RUN pip install --no-cache-dir --upgrade pip && \
    rm -rf /root/.cache

# Copy Python packages from builder to openeye user's home, applying ownership
# inline. A separate `RUN chown -R` re-wrote the entire multi-GB .local tree into
# a NEW image layer (doubling its on-disk size at that step) and exhausted the
# build disk — `COPY --chown` sets ownership without that extra layer.
COPY --from=builder --chown=openeye:openeye /root/.local /home/openeye/.local

# Set PATH to include local Python packages (using openeye user's path)
# Where the application writes. Set explicitly rather than left to detection:
# the compose file mounts volumes over /app/data, /app/recordings and
# /app/faces, so in a container the application directory is host-backed and is
# the right place for data. Without this the resolver falls back to a home
# directory that no volume covers, and every write is lost when the container
# restarts.
ENV OPENEYE_DATA_ROOT=/app \
    OPENEYE_IN_CONTAINER=1

ENV PATH=/home/openeye/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Create app directory
WORKDIR /app

# Copy application code (exclude frontend source).
# ecosystem_auth is pip-installed in the builder stage (above) and carried over in
# /home/openeye/.local; ecosystem_client is optional (guarded at runtime) — so the
# previously-broken COPY of those (never-committed) vendored dirs is removed.
COPY --chown=openeye:openeye backend/ ./backend/
COPY --chown=openeye:openeye docker/ ./docker/

# Migrations. Without these the image starts and then reports
# "No 'script_location' key found in configuration" — alembic.ini was never
# copied, so no migration could run in a container. A fresh database still gets
# its tables from create_all, which is why this went unnoticed; an upgraded one
# would silently keep an old schema.
#
# The macOS bundle has always shipped them. Only the image was missing them.
COPY --chown=openeye:openeye alembic/ ./alembic/
COPY --chown=openeye:openeye alembic.ini ./alembic.ini
COPY --chown=openeye:openeye requirements.txt ./

# Copy built frontend from frontend-builder
COPY --from=frontend-builder --chown=openeye:openeye /frontend/dist ./frontend/dist

# Switch to non-root user
USER openeye

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Entrypoint
ENTRYPOINT ["/app/docker/entrypoint.sh"]

# Default command
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
