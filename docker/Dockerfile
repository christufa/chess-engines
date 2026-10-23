# chess-engines: the analysis API plus its UCI engines. Bases pinned by digest (Dependabot
# bumps them); Python dependencies from uv.lock; each engine a pinned, checksum-verified
# release. Runs as a non-root user on a read-only root filesystem (only /tmp is writable).
FROM python:3.13-slim@sha256:57b29a7c050c4e679e4bea572e14b3965cf4b5839de2da49d55e49ffc4024f39 AS base

# ---- Engines: one stage per engine, each landing in /opt/engines/<name> ----
FROM base AS stockfish
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY engines/stockfish/fetch.sh /tmp/fetch.sh
RUN sh /tmp/fetch.sh /opt/engines/stockfish

# ---- Python environment ----
FROM base AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.1@sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

# ---- Runtime ----
FROM base
# OS security updates on top of the pinned base (CI fails on fixable critical CVEs).
RUN apt-get update && apt-get -y upgrade && rm -rf /var/lib/apt/lists/*
COPY --from=stockfish /opt/engines/stockfish /opt/engines/stockfish
COPY --from=build /app/.venv /app/.venv
COPY engines/engines.yaml /etc/chess-engines/engines.yaml
ARG CODE_VERSION=dev
LABEL org.opencontainers.image.source="https://github.com/christufa/chess-engines" \
      org.opencontainers.image.revision="${CODE_VERSION}" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"
ENV PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp \
    CHESS_ENGINES_CONFIG=/etc/chess-engines/engines.yaml
USER 10001:10001
EXPOSE 8000
CMD ["chess-engines"]
