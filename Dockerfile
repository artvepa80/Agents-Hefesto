# Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# System deps (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Copy only dependency manifests first for better layer caching
COPY pyproject.toml README.md ./

# Copy source
COPY hefesto/ hefesto/
COPY scripts/ scripts/

# Install deps
RUN python -m pip install --upgrade pip \
  && python -m pip install ".[ci]"

# Cloud Run listens on $PORT
EXPOSE 8080

CMD ["uvicorn", "hefesto.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
