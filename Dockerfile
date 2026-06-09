# syntax=docker/dockerfile:1
# Multi-stage uv build (Constitution Principle II: reproducible, pinned builds).
# Builder uses the uv image; runtime is plain python:3.12-slim-bookworm with NO uv
# binary. Both stages share the same Debian-bookworm Python 3.12, so the copied
# .venv is portable between them.

# ----- Builder ---------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Byte-compile for faster cold start; copy (don't symlink) into the venv so the
# environment is self-contained and survives the stage copy.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Resolve deps first from the locked manifest only (better layer caching), then
# install the project. --locked refuses any implicit re-resolution (Principle II);
# --no-dev keeps dev-only tooling out of the image.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# ----- Runtime ---------------------------------------------------------------
FROM python:3.12-slim-bookworm

# Non-root runtime user, fixed uid/gid 999 (Constitution Principle IV). The bind
# mount at /app/data must be owned by 999 on the host (see .env.example).
RUN groupadd --system --gid 999 echoquize \
    && useradd --system --uid 999 --gid 999 --no-create-home echoquize

# Bring over the project and its prebuilt virtualenv from the builder.
COPY --from=builder --chown=999:999 /app /app

# Put the venv first on PATH so `python` resolves to /app/.venv/bin/python.
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app
USER 999

CMD ["python", "app.py"]
