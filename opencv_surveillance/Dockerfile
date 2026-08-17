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
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    pkg-config \
    libopencv-dev \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libboost-python-dev \
    portaudio19-dev \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --user --no-cache-dir -r requirements.txt && \
    pip install --user --no-cache-dir \
      "ecosystem-auth @ git+https://github.com/M1K31/appEcosystem.git@7bdeed0d2af8d6afbb28ef90bc10687267ab51f6#subdirectory=auth/python"

# ============================================
# Stage 3: Runtime - Minimal production image
# ============================================
FROM python:3.11-slim

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
