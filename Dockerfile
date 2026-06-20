# Use the official Python 3.12 slim image
FROM python:3.12-slim

# Install system dependencies required for audio processing and native builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libsndfile1 \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Grab the ultra-fast uv executable from Astral's official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set the working directory inside the container
WORKDIR /app

# Copy dependency definitions and lock file FIRST (maximize layer cache)
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
COPY public/ ./public/

# Create a virtual environment and install dependencies via uv (frozen lock)
RUN uv venv && uv sync --frozen

# Put the virtual environment on the system PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Healthcheck to detect when API is ready
HEALTHCHECK --interval=10s --timeout=5s --start-period=45s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set the default command to run the FastAPI server
CMD ["uvicorn", "swiss_tts.api:app", "--host", "0.0.0.0", "--port", "8000"]
