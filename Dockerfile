# ==========================================
# STAGE 1: Builder - Swiss TTS Backend Engine
# ==========================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies (only needed during compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files and README (hatchling requires README)
COPY pyproject.toml uv.lock README.md ./

# Copy source code (needed for editable install)
COPY src/ ./src

# Create virtual environment and install dependencies
RUN uv venv && uv sync --frozen

# ==========================================
# STAGE 2: Runtime - Swiss TTS Backend Engine
# ==========================================
FROM python:3.12-slim AS backend

WORKDIR /app

# Install only runtime dependencies (libsndfile1, no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source code and static web UI files (for package imports and public assets)
COPY src/ ./src
COPY public/ ./public

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src:$PYTHONPATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random

# Healthcheck to detect when API is ready
HEALTHCHECK --interval=10s --timeout=5s --start-period=45s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["uvicorn", "src.swiss_tts.api:app", "--host", "0.0.0.0", "--port", "8000"]

# ==========================================
# STAGE 3: Expo Mobile Frontend
# ==========================================
FROM node:20-alpine AS frontend

# Move into the app folder so expo finds app.json automatically
WORKDIR /app

# Copy only the package files first to leverage Docker cache
COPY package*.json ./
RUN npm install

# Copy the rest of the project
COPY . .

EXPOSE 8081
CMD ["./node_modules/.bin/expo", "start", "--lan", "-c"]