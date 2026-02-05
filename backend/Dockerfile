# Stage 1: Build stage with dependencies
FROM python:3.12-slim AS builder

# Install uv for faster package installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock README.md ./

# Install dependencies in a virtual environment
RUN uv sync --frozen --no-dev

# Stage 2: Runtime stage
FROM python:3.12-slim

# Install system dependencies
# - postgresql-client: for health checks and pg_isready
# - libmagic1: required by python-magic for MIME type detection
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-client \
        libmagic1 && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appuser . .

# Make entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
