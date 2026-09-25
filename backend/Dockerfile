# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Set environment variables for Python runtime optimization
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_NO_CACHE=1 \
    UV_PYTHON_PREFER_SYSTEM=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install UV package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy dependency manifests and install Python dependencies via UV
COPY pyproject.toml ./

# Install dependencies FIRST so they are cached if app/ code changes
RUN uv pip install --system .
# Ensure pip is entirely removed
RUN rm -rf /usr/local/bin/pip* /usr/local/lib/python*/site-packages/pip*

# Copy backend application source code
COPY app/ ./app/
COPY tests/ ./tests/

# Expose backend API port

EXPOSE 8000

# Start FastAPI application using Uvicorn server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
