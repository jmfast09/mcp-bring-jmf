# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ src/

RUN pip install --no-cache-dir uv \
    && uv pip install --system --no-cache .

# ── Final image ──────────────────────────────────────────────────────────────
FROM python:3.12-slim

RUN groupadd --gid 1000 appgroup \
 && useradd --uid 1000 --gid appgroup --no-create-home appuser

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/mcp-bring /usr/local/bin/mcp-bring

USER appuser

ENV LOG_LEVEL=WARNING
# FastMCP 3.x native env vars (read via pydantic-settings)
ENV FASTMCP_TRANSPORT="streamable-http"
ENV FASTMCP_HOST="0.0.0.0"
ENV FASTMCP_PORT="3000"

ENTRYPOINT ["mcp-bring"]
