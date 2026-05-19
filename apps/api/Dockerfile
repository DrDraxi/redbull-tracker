FROM python:3.12-slim

# uv for fast deps + project management
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

# Pillow runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
      libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first so this layer caches across code changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# App code
COPY redbull_api/ ./redbull_api/

# /data is the Railway volume mount; create it for local-only runs too
RUN mkdir -p /data

ENV DATA_DIR=/data \
    PYTHONUNBUFFERED=1

EXPOSE 5000

CMD uv run gunicorn \
    --bind 0.0.0.0:${PORT:-5000} \
    --workers 2 \
    --access-logfile - \
    'redbull_api.app:create_app()'
