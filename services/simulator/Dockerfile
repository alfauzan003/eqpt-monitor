FROM python:3.12-slim

WORKDIR /app

# Install runtime deps first (before src/ exists)
COPY pyproject.toml ./
RUN pip install --no-cache-dir asyncua pyyaml "pydantic>=2.6"

# Copy source and install package (no-deps: deps already installed above)
COPY src/ ./src/
RUN pip install --no-cache-dir -e . --no-deps

ENV PYTHONUNBUFFERED=1
EXPOSE 4840

CMD ["python", "-m", "simulator.main"]
