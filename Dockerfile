FROM python:3.12-slim

ARG CODEX_CLI_VERSION=0.130.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git nodejs npm \
    && npm install -g @openai/codex@${CODEX_CLI_VERSION} \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md Dockerfile docker-compose.yml .env.example ./
COPY src ./src
COPY scripts ./scripts
COPY contracts ./contracts
COPY demo_fixtures ./demo_fixtures
COPY web ./web
COPY tests ./tests

RUN pip install --no-cache-dir -e ".[dev,observability]"

CMD ["demo", "--help"]
