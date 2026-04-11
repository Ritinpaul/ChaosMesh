# ── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast pip)
RUN pip install --no-cache-dir uv

# Copy application code
COPY README.md pyproject.toml ./
COPY chaosmesh_arena/ ./chaosmesh_arena/
COPY server/ ./server/
COPY graders.py ./graders.py
COPY inference.py ./inference.py
COPY environment.py ./environment.py
COPY openenv.yaml ./openenv.yaml

# Install all dependencies into a virtual env
RUN uv venv /app/.venv --python 3.11
RUN uv pip install --python /app/.venv/bin/python ".[dev]"

# ── Production stage ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS production

WORKDIR /app

# Non-root user for security
RUN groupadd -r chaosmesh && useradd -r -g chaosmesh chaosmesh

# Runtime deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy venv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code from builder
COPY --from=builder /app/chaosmesh_arena ./chaosmesh_arena/
COPY --from=builder /app/server ./server/
COPY --from=builder /app/graders.py ./graders.py
COPY --from=builder /app/inference.py ./inference.py
COPY --from=builder /app/environment.py ./environment.py
COPY --from=builder /app/openenv.yaml ./openenv.yaml
COPY --from=builder /app/pyproject.toml ./pyproject.toml
COPY --from=builder /app/README.md ./README.md

# Create data directories with correct permissions
RUN mkdir -p /app/data/chromadb /app/data/sqlite && \
    chown -R chaosmesh:chaosmesh /app/data

# Switch to non-root
USER chaosmesh

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
