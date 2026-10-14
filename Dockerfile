FROM ghcr.io/astral-sh/uv:0.11.0@sha256:e49fde5daf002023f0a2e2643861ce9ca8a8da5b73d0e6db83ef82ff99969baf AS uv
FROM node:24-bookworm-slim@sha256:0e0ff40c39bc087845bfb27465a0df4ea419520094bc35842ff83dd8cbe6f9b6 AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim-bookworm@sha256:54c85f3c47607a77f32adec749d3c81d1348bf25833671f512b26a9b6d778cb3 AS backend
COPY --from=uv /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev
COPY backend/app ./backend/app
COPY backend/__init__.py ./backend/__init__.py
COPY migrations ./migrations
COPY alembic.ini ./
RUN useradd --create-home --uid 10001 modelmedic && mkdir /artifacts && chown modelmedic /artifacts
ARG CODE_VERSION=unknown
ARG CODE_DIRTY=true
ENV MM_CODE_VERSION=$CODE_VERSION MM_CODE_DIRTY=$CODE_DIRTY
USER modelmedic
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/api/v1/health/live', timeout=3)"]
CMD ["uvicorn", "backend.app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM backend AS production
COPY --from=frontend-build /frontend/dist /app/frontend-dist
ENV MM_FRONTEND_ROOT=/app/frontend-dist MM_ARTIFACT_ROOT=/artifacts
CMD ["python", "-m", "backend.app.web"]

FROM backend AS test
USER root
RUN uv sync --locked
COPY scripts ./scripts
COPY backend/tests ./backend/tests
USER modelmedic
CMD ["pytest", "-q", "-p", "no:cacheprovider"]

# Default Docker/Railway build is the production runtime, never the test stage.
FROM production AS runtime
