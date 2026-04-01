FROM python:3.13-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml .
RUN uv sync --frozen --no-dev

COPY app/ ./app/
COPY sync_worker/ ./sync_worker/

CMD ["uv", "run", "python", "-m", "sync_worker.main"]
