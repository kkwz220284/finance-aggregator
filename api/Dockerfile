FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml .
RUN uv sync --frozen --no-dev

COPY app/ ./app/
COPY api/ ./api/
COPY alembic/ ./alembic/
COPY alembic.ini .

EXPOSE 8080

CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn api.main:app --host 0.0.0.0 --port 8080"]
