FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY contracts ./contracts
COPY demo_fixtures ./demo_fixtures
COPY web ./web

RUN pip install --no-cache-dir -e .

ENTRYPOINT ["demo"]
CMD ["--help"]
