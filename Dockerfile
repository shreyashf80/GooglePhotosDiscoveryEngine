# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml
COPY pyproject.toml ./

# Create wheels for our dependencies (including fastembed as requested by spec)
RUN pip install --no-cache-dir build && \
    pip wheel --no-cache-dir --wheel-dir /app/wheels .[backend,pipeline] fastembed

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Copy the built wheels and install them
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Pre-download fastembed model assets to bake them into the image
# This prevents downloading large ML models on cold boot/scaling
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')" || true

# Copy application code
COPY shared/ ./shared/
COPY backend/ ./backend/
COPY pipeline/ ./pipeline/
COPY pyproject.toml ./

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Expose port
EXPOSE 8000

# Run as non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Start the uvicorn server
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
