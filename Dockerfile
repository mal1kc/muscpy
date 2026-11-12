# Stage 1: Build Stage: install dependencies with uv from the lockfile
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install dependencies first (cached unless the lockfile changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# Install the project itself
COPY readme.md start_muscpy.py ./
COPY src/ ./src/
RUN uv sync --locked --no-dev --no-editable

# Stage 2: Runtime Stage with FFmpeg
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/start_muscpy.py .

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

CMD ["python3", "start_muscpy.py"]
