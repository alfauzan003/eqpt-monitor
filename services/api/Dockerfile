FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi "uvicorn[standard]" asyncpg "redis>=5.0" alembic sqlalchemy psycopg2-binary pyyaml "pydantic>=2.6" "pydantic-settings>=2.2" "prometheus-client>=0.21" "python-json-logger>=3.2"

COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e . --no-deps

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
