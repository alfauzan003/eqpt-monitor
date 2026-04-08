FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

COPY services/api/pyproject.toml ./
COPY services/api/src/ ./src/
COPY services/api/alembic/ ./alembic/
COPY services/api/alembic.ini ./
RUN pip install --no-cache-dir .

COPY --from=frontend-build /frontend/dist ./static

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
