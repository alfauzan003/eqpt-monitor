FROM python:3.12-slim

WORKDIR /app

# Install runtime deps from pyproject.toml
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy source
COPY src/ ./src/
RUN pip install --no-cache-dir -e . --no-deps

ENV PYTHONUNBUFFERED=1
EXPOSE 4840

CMD ["python", "-m", "simulator.main"]
