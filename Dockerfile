# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:0.8.15 AS uv

FROM python:3.13-slim AS builder
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.13-slim AS runtime
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN groupadd --system --gid 10001 valor \
    && useradd --system --uid 10001 --gid valor --home-dir /app valor
WORKDIR /app
COPY --from=builder --chown=valor:valor /app/.venv .venv
USER valor
EXPOSE 8000
CMD ["uvicorn", "valor.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
