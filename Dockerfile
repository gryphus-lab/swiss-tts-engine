# Stage 1: Build stage
FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy only dependency definitions first (maximize layer cache)
COPY pyproject.toml README.md ./

# Create virtual environment and sync dependencies (only production deps via optional groups)
RUN uv venv && uv sync --no-dev

# Stage 2: Runtime stage
FROM python:3.12-slim

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source code
COPY src/ ./src/

# Set up PATH to use virtual environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Healthcheck to detect when API is ready
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=3)" || exit 1

# Run the FastAPI server
CMD ["uvicorn", "swiss_tts.api:app", "--host", "0.0.0.0", "--port", "8000"]
