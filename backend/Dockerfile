FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends libmagic1 \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/pip pip install hatchling

# ===== dev =====
FROM base AS dev
COPY pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/pip pip install -e ".[dev]"
COPY . .

# ===== prod =====
FROM base AS prod
ENV PYTHONPATH=/app
COPY pyproject.toml .
COPY app/ app/
COPY alembic/ alembic/
COPY scripts/ scripts/
COPY alembic.ini .
RUN --mount=type=cache,target=/root/.cache/pip pip install .
RUN useradd -m -u 2000 app && mkdir -p /data/uploads && chown -R app:app /app /data
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
