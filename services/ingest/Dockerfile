FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir asyncua asyncpg "redis>=5.0" "pydantic>=2.6" "pydantic-settings>=2.2"

COPY src/ ./src/
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e . --no-deps

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "ingest.main"]
