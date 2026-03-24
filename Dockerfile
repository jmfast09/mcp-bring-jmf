FROM python:3.12-slim AS builder

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ src/

RUN pip install --no-cache-dir uv \
    && uv pip install --system --no-cache .

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/mcp-bring /usr/local/bin/mcp-bring
COPY src/ src/

RUN useradd --create-home appuser
USER appuser

ENTRYPOINT ["mcp-bring"]
