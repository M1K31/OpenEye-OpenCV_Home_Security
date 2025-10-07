# Multi-stage build for optimized production image

# ============================================
# Stage 1: Builder - Compile dependencies
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
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --user --no-cache-dir -r requirements.txt

# ============================================
# Stage 2: Runtime - Minimal production image
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
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Set PATH to include local Python packages
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Create app directory
WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 openeye && \
    mkdir -p /app/data /app/config /app/models /app/logs && \
    chown -R openeye:openeye /app

# Copy application code
COPY --chown=openeye:openeye . .

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
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
