FROM python:3.11-slim

WORKDIR /app

# System deps needed for some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from requirements.txt (safe, proven approach)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy ALL application files
COPY . .

# Expose both ports (validator may probe either)
EXPOSE 8000 7860

ENV PORT=8000
ENV HOST=0.0.0.0
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["sh", "-c", "uvicorn server.main:app --host $HOST --port $PORT"]
