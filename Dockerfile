# ==========================================
# STAGE 1: Swiss TTS Backend Engine
# ==========================================
FROM python:3.12-slim AS backend

WORKDIR /app



# Install system dependencies required for compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libsndfile1 \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the uv binary straight from the official Astral image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
# Copy python configuration files
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src
# Create a virtual environment and install dependencies via uv (frozen lock)
RUN uv venv && uv sync --frozen

# Copy backend source code and static web UI files
COPY public/ ./public

# Put the virtual environment on the system PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create non-root user and set permissions
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Healthcheck to detect when API is ready
HEALTHCHECK --interval=10s --timeout=5s --start-period=45s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["uvicorn", "src.swiss_tts.api:app", "--host", "0.0.0.0", "--port", "8000"]

# ==========================================
# STAGE 2: Expo Mobile Frontend
# ==========================================
FROM node:25-alpine AS frontend

WORKDIR /app
RUN apk add --no-cache bash

# Copy package configurations relative to the root context
COPY swiss-tts-app/package*.json ./
RUN npm install --ignore-scripts

# Copy the rest of the mobile application source code
COPY swiss-tts-app/ .

# Create non-root user and set permissions
RUN adduser -D -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8081
CMD ["npx", "expo", "start", "--lan", "-c", "--config", "./app.json"]