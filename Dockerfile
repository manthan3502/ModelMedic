FROM ghcr.io/astral-sh/uv:0.11.0 AS uv
FROM python:3.12-slim-bookworm AS backend
COPY --from=uv /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev
COPY backend ./backend
COPY migrations ./migrations
COPY alembic.ini ./
RUN useradd --create-home --uid 10001 modelmedic && mkdir /artifacts && chown modelmedic /artifacts
USER modelmedic
CMD ["uvicorn", "backend.app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM backend AS test
USER root
RUN uv sync --locked
COPY scripts ./scripts
USER modelmedic
CMD ["pytest", "-q", "-p", "no:cacheprovider"]
