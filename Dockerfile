FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HEFESTO_MCP_ROOT=/workspace \
    HEFESTO_TELEMETRY=0

RUN pip install --no-cache-dir "hefesto-ai[mcp]==4.21.1" \
    && hefesto-mcp --help \
    && python -c "from hefesto.mcp_server import build_server; build_server()" \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin hefesto

USER 10001
WORKDIR /workspace
ENTRYPOINT ["hefesto-mcp"]
