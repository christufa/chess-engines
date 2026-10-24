# chess-engines: the analysis API, its playground UI and its UCI engines. Bases pinned by
# digest (Dependabot bumps them); Python dependencies from uv.lock, the UI's from
# web/package-lock.json; each engine a pinned, checksum-verified release. Runs as a non-root user on a read-only root filesystem (only /tmp is writable).
FROM python:3.13-slim@sha256:57b29a7c050c4e679e4bea572e14b3965cf4b5839de2da49d55e49ffc4024f39 AS base

# ---- Engines: one stage per engine, each landing in /opt/engines/<name> ----
FROM base AS stockfish
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY engines/stockfish/fetch.sh /tmp/fetch.sh
RUN sh /tmp/fetch.sh /opt/engines/stockfish

# Lc0, built from source for CPU (it publishes no Linux binaries), and the Maia nets it runs.
FROM base AS lc0
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates g++ meson \
      ninja-build zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*
COPY engines/lc0/build.sh /tmp/build.sh
RUN sh /tmp/build.sh /opt/engines/lc0
COPY engines/maia/fetch.sh /tmp/fetch-maia.sh
RUN sh /tmp/fetch-maia.sh /opt/engines/maia

# ---- The playground UI (web/): typecheck, unit tests and the production build ----
FROM node:26.12.0-alpine@sha256:6f08a523443ddedf52941874c203475b0ad503e859ad70cb26ab8be9a517dbd5 AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run typecheck && npm test && npx vite build

# ---- Python environment, with the UI in the package ----
FROM base AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.1@sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY --from=web /web/dist/ ./src/chess_engines/web/
RUN uv sync --frozen --no-dev --no-editable

# ---- Runtime ----
FROM base
# OS security updates on top of the pinned base (CI fails on fixable critical CVEs).
RUN apt-get update && apt-get -y upgrade && rm -rf /var/lib/apt/lists/*
COPY --from=stockfish /opt/engines/stockfish /opt/engines/stockfish
COPY --from=lc0 /opt/engines/lc0 /opt/engines/lc0
COPY --from=lc0 /opt/engines/maia /opt/engines/maia
COPY --from=build /app/.venv /app/.venv
COPY engines/engines.yaml /etc/chess-engines/engines.yaml
ARG CODE_VERSION=dev
LABEL org.opencontainers.image.source="https://github.com/christufa/chess-engines" \
      org.opencontainers.image.revision="${CODE_VERSION}" \
      org.opencontainers.image.licenses="Apache-2.0 AND GPL-3.0-or-later"
ENV PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp \
    CHESS_ENGINES_CONFIG=/etc/chess-engines/engines.yaml
USER 10001:10001
EXPOSE 8000
CMD ["chess-engines"]
