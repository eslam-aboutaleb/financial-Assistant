# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Set environment variables for Python runtime optimization
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
# - build-essential: required for sentence-transformers C/C++ extensions
# - curl: required for container healthcheck against /api/v1/health
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements specification and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy backend application source code
COPY app/ ./app/

# Run the RAG ingestion script to pre-populate Chroma vector database at build time
RUN python -m app.rag.ingest

# Expose backend API port
EXPOSE 8000

# Start FastAPI application using Uvicorn server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
