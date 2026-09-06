# ==========================================
# STAGE 1: Builder - Swiss TTS Backend Engine
# ==========================================
FROM python:3.14-slim AS builder

WORKDIR /app

# Install build dependencies (only needed during compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    g++ \
    git \
    libsndfile1-dev \
    pkg-config \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install pre-built sentencepiece to avoid compilation issues
RUN pip install --no-cache-dir sentencepiece==0.1.99

# Copy the uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files and README files (hatchling requires package README)
COPY pyproject.toml uv.lock README.md ./
COPY apps/swiss-tts-engine/pyproject.toml apps/swiss-tts-engine/README.md ./apps/swiss-tts-engine/

# Copy source code (needed for editable install)
COPY apps/swiss-tts-engine/src/ ./apps/swiss-tts-engine/src

# Create virtual environment and install dependencies
RUN uv venv && uv sync --frozen --package swiss-tts-engine

# Compile Python bytecode for faster startup
RUN /app/.venv/bin/python -m compileall -q /app/.venv || true

# ==========================================
# STAGE 2: Runtime - Swiss TTS Backend Engine
# ==========================================
FROM python:3.14-slim AS backend

WORKDIR /app

# Install only runtime dependencies (libsndfile1, no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source code and static web UI files (for package imports and public assets)
COPY apps/swiss-tts-engine/src/ ./apps/swiss-tts-engine/src
COPY apps/swiss-tts-engine/public/ ./apps/swiss-tts-engine/public

# Set proper ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/apps/swiss-tts-engine/src:$PYTHONPATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random

# Healthcheck to detect when API is ready
HEALTHCHECK --interval=10s --timeout=5s --start-period=45s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["uvicorn", "swiss_tts.api:app", "--host", "0.0.0.0", "--port", "8000"]

# ==========================================
# STAGE 3: Expo Mobile Frontend
# ==========================================
FROM node:26-alpine AS frontend

# Move into the app folder so expo finds app.json automatically
WORKDIR /app/apps/swiss-tts-app

# Create non-root user for security
RUN addgroup -g 1001 appuser && adduser -D -u 1001 -G appuser appuser

# Copy only the package files first to leverage Docker cache
COPY apps/swiss-tts-app/package*.json ./
RUN npm install --legacy-peer-deps

# Copy the rest of the mobile app
COPY apps/swiss-tts-app/ ./

# Set proper ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

EXPOSE 8081
CMD ["./node_modules/.bin/expo", "start", "--lan", "-c"]
