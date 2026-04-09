# Factory Pulse — Phase 1b: Observability, Testing, CI & Documentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Prometheus metrics, structured JSON logging, integration tests, CI/CD pipeline, Grafana dashboards ("Factory Health" + "System Health"), ADRs, and polish the README. After this plan, every service emits Prometheus metrics and structured logs, the full stack is covered by integration tests, and a GitHub Actions CI pipeline runs lint + unit + integration tests on every push.

**Architecture:** Prometheus metrics via `prometheus_client` (Python) exposed on `/metrics` for each Python service. Structured JSON logs via `python-json-logger`. Integration tests via `testcontainers` running real TimescaleDB + Redis + OPC-UA simulator. GitHub Actions CI with Docker Compose for integration tests. Two new Grafana dashboards provisioned alongside the existing one.

**Tech Stack:** prometheus_client, python-json-logger, testcontainers[postgres,redis], GitHub Actions, Grafana dashboard JSON, ruff, mypy, ESLint, tsc.

**Out of scope (Phase 1c):** Production VM deployment, Caddy/HTTPS, deploy workflow, `scripts/deploy.sh`, `DEPLOY.md`.

---

## File Structure

This is what Plan 1b produces on top of Phase 1a. New files marked with `+`, modified files marked with `~`.

```
factory-pulse/
├── ~ docker-compose.yml                  # healthcheck fix (already done)
├── + docker-compose.dev.yml              # Hot reload for dev
├── + docker-compose.test.yml             # Integration test services
├── ~ .gitignore                          # Add .github
├── .github/
│   └── workflows/
│       └── + ci.yml                      # Lint + unit + integration + frontend
├── services/
│   ├── simulator/
│   │   └── ~ src/simulator/main.py       # Structured logging
│   ├── ingest/
│   │   ├── ~ pyproject.toml              # Add prometheus_client, python-json-logger
│   │   ├── ~ src/ingest/main.py          # Structured logging, metrics
│   │   ├── ~ src/ingest/db_writer.py     # Metrics on writes
│   │   ├── ~ src/ingest/redis_publisher.py  # Metrics on publishes
│   │   ├── + src/ingest/metrics.py       # Prometheus counters/histograms
│   │   ├── + src/ingest/logging_config.py  # JSON log setup
│   │   └── + tests/test_metrics.py       # Unit test for metric helpers
│   └── api/
│       ├── ~ pyproject.toml              # Add prometheus_client, python-json-logger, testcontainers
│       ├── ~ src/api/main.py             # Structured logging, /metrics mount, middleware
│       ├── + src/api/metrics.py          # Prometheus counters/histograms
│       ├── + src/api/logging_config.py   # JSON log setup
│       ├── + src/api/middleware.py        # Request timing middleware
│       └── + tests/test_integration.py   # Integration tests (testcontainers)
├── frontend/
│   └── ~ tests/EquipmentCard.test.tsx    # Verify existing test runs
├── grafana/
│   └── dashboards/
│       ├── + factory-health.json         # Fleet-wide metrics dashboard
│       └── + system-health.json          # Self-monitoring dashboard
├── docs/
│   └── adr/
│       ├── + 001-two-service-split.md
│       ├── + 002-timescaledb-over-influxdb.md
│       ├── + 003-opc-ua-only.md
│       └── + 004-narrow-eav-telemetry-schema.md
└── ~ README.md                           # Polish for recruiter experience
```

---

## Task List

### Task 1: Commit the docker-compose healthcheck fix from Phase 1a verification

**Files:**
- Modified (already): `docker-compose.yml`

- [ ] **Step 1: Verify the change is unstaged**

```bash
cd "d:/Dev/Project 1"
git diff docker-compose.yml
```

Expected: Shows the `healthcheck` block added to `timescaledb` and `condition: service_healthy` on `api` + `ingest`.

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "fix: add healthcheck to timescaledb, use service_healthy for api/ingest depends_on

Without this, api crashes on startup when TimescaleDB isn't ready for
connections yet during alembic upgrade."
```

---

### Task 2: Structured JSON logging — ingest service

**Files:**
- Create: `services/ingest/src/ingest/logging_config.py`
- Modify: `services/ingest/src/ingest/main.py`
- Modify: `services/ingest/pyproject.toml`

- [ ] **Step 1: Add `python-json-logger` dependency**

In `services/ingest/pyproject.toml`, add to `dependencies`:

```toml
dependencies = [
    "asyncua>=1.1.5",
    "asyncpg>=0.29",
    "redis>=5.0",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "python-json-logger>=3.2",
]
```

- [ ] **Step 2: Create `services/ingest/src/ingest/logging_config.py`**

```python
"""Structured JSON logging setup."""
from __future__ import annotations

import logging
import sys

from pythonjsonlogger.json import JsonFormatter


def setup_logging(service: str = "ingest", level: int = logging.INFO) -> None:
    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        static_fields={"service": service},
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet down noisy libraries
    logging.getLogger("asyncua").setLevel(logging.WARNING)
```

- [ ] **Step 3: Replace logging setup in `services/ingest/src/ingest/main.py`**

Replace lines 21-24:

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
```

With:

```python
from ingest.logging_config import setup_logging

setup_logging()
```

- [ ] **Step 4: Rebuild and verify JSON logs**

```bash
cd "d:/Dev/Project 1"
docker compose build ingest
docker compose up -d ingest
docker compose logs --tail=5 ingest
```

Expected: Log lines are JSON objects with `timestamp`, `level`, `service`, `logger`, `message` fields.

- [ ] **Step 5: Commit**

```bash
git add services/ingest/pyproject.toml services/ingest/src/ingest/logging_config.py services/ingest/src/ingest/main.py
git commit -m "feat(ingest): add structured JSON logging

Replace plain text logs with JSON-formatted structured logs using
python-json-logger. Quiets noisy asyncua library logs."
```

---

### Task 3: Structured JSON logging — API service

**Files:**
- Create: `services/api/src/api/logging_config.py`
- Modify: `services/api/src/api/main.py`
- Modify: `services/api/pyproject.toml`

- [ ] **Step 1: Add `python-json-logger` dependency**

In `services/api/pyproject.toml`, add to `dependencies`:

```toml
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "asyncpg>=0.29",
    "redis>=5.0",
    "alembic>=1.13",
    "sqlalchemy>=2.0",
    "psycopg2-binary>=2.9",
    "pyyaml>=6.0",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "python-json-logger>=3.2",
]
```

- [ ] **Step 2: Create `services/api/src/api/logging_config.py`**

```python
"""Structured JSON logging setup."""
from __future__ import annotations

import logging
import sys

from pythonjsonlogger.json import JsonFormatter


def setup_logging(service: str = "api", level: int = logging.INFO) -> None:
    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        static_fields={"service": service},
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet down noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
```

- [ ] **Step 3: Replace logging setup in `services/api/src/api/main.py`**

Replace lines 22-25:

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
```

With:

```python
from api.logging_config import setup_logging

setup_logging()
```

- [ ] **Step 4: Rebuild and verify JSON logs**

```bash
cd "d:/Dev/Project 1"
docker compose build api
docker compose up -d api
docker compose logs --tail=5 api
```

Expected: Log lines are JSON objects.

- [ ] **Step 5: Commit**

```bash
git add services/api/pyproject.toml services/api/src/api/logging_config.py services/api/src/api/main.py
git commit -m "feat(api): add structured JSON logging"
```

---

### Task 4: Structured JSON logging — simulator

**Files:**
- Create: `services/simulator/src/simulator/logging_config.py`
- Modify: `services/simulator/src/simulator/main.py`
- Modify: `services/simulator/pyproject.toml`

- [ ] **Step 1: Add `python-json-logger` dependency**

In `services/simulator/pyproject.toml`, add `"python-json-logger>=3.2"` to the `dependencies` list.

- [ ] **Step 2: Create `services/simulator/src/simulator/logging_config.py`**

```python
"""Structured JSON logging setup."""
from __future__ import annotations

import logging
import sys

from pythonjsonlogger.json import JsonFormatter


def setup_logging(service: str = "simulator", level: int = logging.INFO) -> None:
    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        static_fields={"service": service},
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet down noisy asyncua internals
    logging.getLogger("asyncua").setLevel(logging.WARNING)
```

- [ ] **Step 3: Update simulator `main.py` to use structured logging**

Read the current `services/simulator/src/simulator/main.py` and replace any `logging.basicConfig(...)` call with:

```python
from simulator.logging_config import setup_logging

setup_logging()
```

- [ ] **Step 4: Rebuild and verify**

```bash
cd "d:/Dev/Project 1"
docker compose build simulator
docker compose up -d simulator
docker compose logs --tail=5 simulator
```

Expected: JSON log lines.

- [ ] **Step 5: Commit**

```bash
git add services/simulator/pyproject.toml services/simulator/src/simulator/logging_config.py services/simulator/src/simulator/main.py
git commit -m "feat(simulator): add structured JSON logging"
```

---

### Task 5: Prometheus metrics — ingest service

**Files:**
- Create: `services/ingest/src/ingest/metrics.py`
- Modify: `services/ingest/src/ingest/main.py`
- Modify: `services/ingest/src/ingest/db_writer.py`
- Modify: `services/ingest/src/ingest/redis_publisher.py`
- Modify: `services/ingest/pyproject.toml`
- Create: `services/ingest/tests/test_metrics.py`

- [ ] **Step 1: Add `prometheus_client` dependency**

In `services/ingest/pyproject.toml`, add to `dependencies`:

```toml
    "prometheus-client>=0.21",
```

- [ ] **Step 2: Write the metrics test**

Create `services/ingest/tests/test_metrics.py`:

```python
"""Tests for Prometheus metric definitions."""
from ingest.metrics import (
    INGEST_MESSAGES_TOTAL,
    INGEST_BATCH_SIZE,
    INGEST_BATCH_LATENCY,
    INGEST_DB_WRITE_ERRORS,
    INGEST_INVALID_SAMPLES,
    OPCUA_SUBSCRIPTION_ACTIVE,
    OPCUA_CONNECTION_ATTEMPTS,
    REDIS_PUBLISH_ERRORS,
)


def test_all_metrics_are_defined():
    """All metric objects exist and have the expected type."""
    from prometheus_client import Counter, Histogram, Gauge

    assert isinstance(INGEST_MESSAGES_TOTAL, Counter)
    assert isinstance(INGEST_BATCH_SIZE, Histogram)
    assert isinstance(INGEST_BATCH_LATENCY, Histogram)
    assert isinstance(INGEST_DB_WRITE_ERRORS, Counter)
    assert isinstance(INGEST_INVALID_SAMPLES, Counter)
    assert isinstance(OPCUA_SUBSCRIPTION_ACTIVE, Gauge)
    assert isinstance(OPCUA_CONNECTION_ATTEMPTS, Counter)
    assert isinstance(REDIS_PUBLISH_ERRORS, Counter)
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd "d:/Dev/Project 1/services/ingest"
python -m pytest tests/test_metrics.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'ingest.metrics'`

- [ ] **Step 4: Create `services/ingest/src/ingest/metrics.py`**

```python
"""Prometheus metrics for the ingest service."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

INGEST_MESSAGES_TOTAL = Counter(
    "ingest_messages_total",
    "Total telemetry messages ingested",
    ["equipment_id", "metric_name"],
)

INGEST_BATCH_SIZE = Histogram(
    "ingest_batch_size",
    "Number of samples per DB write batch",
    buckets=[10, 25, 50, 100, 250, 500, 1000],
)

INGEST_BATCH_LATENCY = Histogram(
    "ingest_batch_latency_seconds",
    "Time to write a batch to the database",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

INGEST_DB_WRITE_ERRORS = Counter(
    "ingest_db_write_errors_total",
    "Total DB write errors",
)

INGEST_INVALID_SAMPLES = Counter(
    "ingest_invalid_samples_total",
    "Total samples skipped due to invalid data",
    ["reason"],
)

OPCUA_SUBSCRIPTION_ACTIVE = Gauge(
    "opcua_subscription_active",
    "Whether OPC-UA subscription is currently active",
)

OPCUA_CONNECTION_ATTEMPTS = Counter(
    "opcua_connection_attempts_total",
    "OPC-UA connection attempts",
    ["result"],
)

REDIS_PUBLISH_ERRORS = Counter(
    "redis_publish_errors_total",
    "Total Redis publish errors",
)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd "d:/Dev/Project 1/services/ingest"
python -m pytest tests/test_metrics.py -v
```

Expected: PASS

- [ ] **Step 6: Instrument `db_writer.py`**

Add to top of `services/ingest/src/ingest/db_writer.py`:

```python
import time
from ingest.metrics import INGEST_BATCH_SIZE, INGEST_BATCH_LATENCY, INGEST_DB_WRITE_ERRORS
```

Replace the `write_batch` method body:

```python
    async def write_batch(self, samples: list[Sample]) -> None:
        if not samples:
            return
        INGEST_BATCH_SIZE.observe(len(samples))
        rows = [
            (s.time, s.equipment_id, s.metric_name, s.value, s.status, s.batch_id, s.unit_id)
            for s in samples
        ]
        start = time.monotonic()
        try:
            async with self._pool.acquire() as conn:
                await conn.executemany(
                    """
                    INSERT INTO telemetry (time, equipment_id, metric_name, value, status, batch_id, unit_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (time, equipment_id, metric_name) DO NOTHING
                    """,
                    rows,
                )
            INGEST_BATCH_LATENCY.observe(time.monotonic() - start)
        except Exception:
            INGEST_DB_WRITE_ERRORS.inc()
            raise
```

- [ ] **Step 7: Instrument `redis_publisher.py`**

Add to top of `services/ingest/src/ingest/redis_publisher.py`:

```python
from ingest.metrics import REDIS_PUBLISH_ERRORS
```

In the `publish` method, change the `except` block:

```python
        except Exception:
            REDIS_PUBLISH_ERRORS.inc()
            logger.warning("redis publish failed for %s", equipment_id, exc_info=True)
```

In the `update_hot_cache` method, change the `except` block:

```python
        except Exception:
            REDIS_PUBLISH_ERRORS.inc()
            logger.warning("redis hot cache update failed for %s", equipment_id, exc_info=True)
```

- [ ] **Step 8: Instrument `main.py` and start HTTP metrics server**

Add to imports in `services/ingest/src/ingest/main.py`:

```python
from prometheus_client import start_http_server
from ingest.metrics import (
    INGEST_MESSAGES_TOTAL,
    OPCUA_SUBSCRIPTION_ACTIVE,
    OPCUA_CONNECTION_ATTEMPTS,
)
```

At the start of the `run()` function, before `pool = await _connect_db_with_retry()`, add:

```python
    start_http_server(9090)
    logger.info("prometheus metrics server started on :9090")
```

In `_connect_opcua_with_retry`, instrument connection attempts:

```python
async def _connect_opcua_with_retry(on_update, state_store):
    delay = 1.0
    while True:
        try:
            result = await connect_and_subscribe(
                settings.opcua_endpoint, on_update, state_store
            )
            OPCUA_CONNECTION_ATTEMPTS.labels(result="success").inc()
            OPCUA_SUBSCRIPTION_ACTIVE.set(1)
            return result
        except Exception:
            OPCUA_CONNECTION_ATTEMPTS.labels(result="failure").inc()
            logger.warning("opcua connect failed, retrying in %.1fs", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60.0)
```

In the `on_update` callback, after the `if st.metrics is None: return` guard, add:

```python
        for metric_name in st.metrics:
            INGEST_MESSAGES_TOTAL.labels(
                equipment_id=equipment_id, metric_name=metric_name
            ).inc()
```

- [ ] **Step 9: Expose ingest metrics port in docker-compose.yml**

In `docker-compose.yml`, add to the `ingest` service:

```yaml
    ports:
      - "9090:9090"
```

- [ ] **Step 10: Run all ingest tests**

```bash
cd "d:/Dev/Project 1/services/ingest"
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Expected: All tests pass (7 original + 1 new = 8 total).

- [ ] **Step 11: Rebuild and verify metrics endpoint**

```bash
cd "d:/Dev/Project 1"
docker compose build ingest
docker compose up -d ingest
# Wait a few seconds
curl -s http://localhost:9090/metrics | head -30
```

Expected: Prometheus text format with `ingest_messages_total`, `ingest_batch_size`, etc.

- [ ] **Step 12: Commit**

```bash
git add services/ingest/ docker-compose.yml
git commit -m "feat(ingest): add Prometheus metrics

Expose /metrics on :9090 with counters for messages ingested, batch
sizes, DB write latency/errors, OPC-UA connection status, and Redis
publish errors."
```

---

### Task 6: Prometheus metrics — API service

**Files:**
- Create: `services/api/src/api/metrics.py`
- Create: `services/api/src/api/middleware.py`
- Modify: `services/api/src/api/main.py`
- Modify: `services/api/src/api/websocket.py`
- Modify: `services/api/pyproject.toml`

- [ ] **Step 1: Add `prometheus_client` dependency**

In `services/api/pyproject.toml`, add to `dependencies`:

```toml
    "prometheus-client>=0.21",
```

- [ ] **Step 2: Create `services/api/src/api/metrics.py`**

```python
"""Prometheus metrics for the API service."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)

WS_CONNECTIONS_ACTIVE = Gauge(
    "websocket_connections_active",
    "Currently active WebSocket connections",
)

WS_MESSAGES_SENT = Counter(
    "websocket_messages_sent_total",
    "Total WebSocket messages sent to clients",
)

WS_CLIENT_DROPPED = Counter(
    "websocket_client_dropped_total",
    "WebSocket messages dropped due to slow consumer",
    ["reason"],
)

DB_QUERY_DURATION = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["query"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)
```

- [ ] **Step 3: Create `services/api/src/api/middleware.py`**

```python
"""Request timing and metrics middleware."""
from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from api.metrics import HTTP_REQUESTS_TOTAL, HTTP_REQUEST_DURATION


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip metrics endpoint itself to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        # Normalize path to avoid cardinality explosion
        path = request.url.path
        for segment in path.split("/"):
            if segment and not segment.startswith(("api", "ws", "equipment", "telemetry", "batches", "health", "metrics")):
                # Likely an ID segment — normalize
                path = path.replace(segment, "{id}", 1)
                break

        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start

        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=response.status_code).inc()
        HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(duration)

        return response
```

- [ ] **Step 4: Mount `/metrics` endpoint and middleware in `services/api/src/api/main.py`**

Add these imports at the top of `main.py`:

```python
from prometheus_client import make_asgi_app
from api.middleware import MetricsMiddleware
```

After the `app = FastAPI(...)` line, add:

```python
app.add_middleware(MetricsMiddleware)
```

After the `app.include_router(ws_router)` line, add:

```python
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

- [ ] **Step 5: Instrument WebSocket in `services/api/src/api/websocket.py`**

Add import at top:

```python
from api.metrics import WS_CONNECTIONS_ACTIVE, WS_MESSAGES_SENT, WS_CLIENT_DROPPED
```

In `ws_telemetry`, after `await ws.accept()`, add:

```python
    WS_CONNECTIONS_ACTIVE.inc()
```

In the `sender` function, after `await ws.send_text(msg)`, add:

```python
                WS_MESSAGES_SENT.inc()
```

In the `forwarder` function, inside the `except asyncio.QueueFull` block, after `send_queue.get_nowait()`, add:

```python
                        WS_CLIENT_DROPPED.labels(reason="queue_full").inc()
```

At the end of `ws_telemetry`, before the `await pubsub.close()` line, add:

```python
    WS_CONNECTIONS_ACTIVE.dec()
```

- [ ] **Step 6: Run all API tests**

```bash
cd "d:/Dev/Project 1/services/api"
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Expected: All 17 tests pass.

- [ ] **Step 7: Rebuild and verify**

```bash
cd "d:/Dev/Project 1"
docker compose build api
docker compose up -d api
curl -s http://localhost:8000/metrics | head -20
```

Expected: Prometheus text format with `http_requests_total`, `websocket_connections_active`, etc.

- [ ] **Step 8: Commit**

```bash
git add services/api/
git commit -m "feat(api): add Prometheus metrics and request timing middleware

Expose /metrics with HTTP request counters/latency histograms, WebSocket
connection gauge, and message counters."
```

---

### Task 7: Grafana — Factory Health dashboard

**Files:**
- Create: `grafana/dashboards/factory-health.json`

- [ ] **Step 1: Create the dashboard JSON**

Create `grafana/dashboards/factory-health.json`:

```json
{
  "annotations": { "list": [] },
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 1,
  "id": null,
  "links": [],
  "panels": [
    {
      "title": "Equipment Status Distribution",
      "type": "piechart",
      "gridPos": { "h": 8, "w": 8, "x": 0, "y": 0 },
      "datasource": { "type": "grafana-postgresql-datasource", "uid": "timescaledb" },
      "targets": [
        {
          "rawSql": "SELECT status, COUNT(DISTINCT equipment_id) AS count FROM telemetry WHERE time > NOW() - INTERVAL '5 minutes' AND status IS NOT NULL GROUP BY status ORDER BY count DESC",
          "format": "table"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "color": { "mode": "palette-classic" }
        },
        "overrides": [
          { "matcher": { "id": "byName", "options": "running" }, "properties": [{ "id": "color", "value": { "fixedColor": "green", "mode": "fixed" } }] },
          { "matcher": { "id": "byName", "options": "idle" }, "properties": [{ "id": "color", "value": { "fixedColor": "blue", "mode": "fixed" } }] },
          { "matcher": { "id": "byName", "options": "fault" }, "properties": [{ "id": "color", "value": { "fixedColor": "red", "mode": "fixed" } }] },
          { "matcher": { "id": "byName", "options": "maintenance" }, "properties": [{ "id": "color", "value": { "fixedColor": "orange", "mode": "fixed" } }] }
        ]
      }
    },
    {
      "title": "Fleet Average Temperature",
      "type": "timeseries",
      "gridPos": { "h": 8, "w": 16, "x": 8, "y": 0 },
      "datasource": { "type": "grafana-postgresql-datasource", "uid": "timescaledb" },
      "targets": [
        {
          "rawSql": "SELECT time_bucket('1 minute', time) AS time, equipment_id, AVG(value) AS temperature FROM telemetry WHERE metric_name = 'temperature' AND $__timeFilter(time) GROUP BY 1, 2 ORDER BY 1",
          "format": "time_series"
        }
      ]
    },
    {
      "title": "Fleet Throughput (units/hr)",
      "type": "timeseries",
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 8 },
      "datasource": { "type": "grafana-postgresql-datasource", "uid": "timescaledb" },
      "targets": [
        {
          "rawSql": "SELECT time_bucket('1 minute', time) AS time, equipment_id, AVG(value) AS throughput FROM telemetry WHERE metric_name = 'throughput' AND $__timeFilter(time) GROUP BY 1, 2 ORDER BY 1",
          "format": "time_series"
        }
      ]
    },
    {
      "title": "Fault Events",
      "type": "table",
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 8 },
      "datasource": { "type": "grafana-postgresql-datasource", "uid": "timescaledb" },
      "targets": [
        {
          "rawSql": "SELECT equipment_id, MIN(time) AS fault_start, MAX(time) AS fault_end, COUNT(*) AS samples FROM telemetry WHERE status = 'fault' AND $__timeFilter(time) GROUP BY equipment_id ORDER BY fault_start DESC LIMIT 20",
          "format": "table"
        }
      ]
    },
    {
      "title": "Active Batches",
      "type": "table",
      "gridPos": { "h": 8, "w": 24, "x": 0, "y": 16 },
      "datasource": { "type": "grafana-postgresql-datasource", "uid": "timescaledb" },
      "targets": [
        {
          "rawSql": "SELECT DISTINCT ON (equipment_id) equipment_id, batch_id, unit_id, status, time FROM telemetry WHERE time > NOW() - INTERVAL '5 minutes' ORDER BY equipment_id, time DESC",
          "format": "table"
        }
      ]
    }
  ],
  "schemaVersion": 39,
  "tags": ["factory-pulse"],
  "templating": { "list": [] },
  "time": { "from": "now-1h", "to": "now" },
  "timepicker": {},
  "timezone": "browser",
  "title": "Factory Health",
  "uid": "factory-health",
  "version": 1
}
```

- [ ] **Step 2: Verify in Grafana**

```bash
cd "d:/Dev/Project 1"
docker compose restart grafana
```

Open http://localhost:3000, login admin/admin, navigate to Dashboards. Verify "Factory Health" appears and panels load.

- [ ] **Step 3: Commit**

```bash
git add grafana/dashboards/factory-health.json
git commit -m "feat(grafana): add Factory Health dashboard

Fleet-wide view: equipment status distribution, temperature trends,
throughput, fault events, and active batches."
```

---

### Task 8: Grafana — System Health dashboard

**Files:**
- Create: `grafana/dashboards/system-health.json`

This dashboard monitors the internal health of the services themselves — ingest throughput, API latency, etc. It requires Prometheus as a datasource. For Phase 1b we create the dashboard JSON targeting the Prometheus metrics exposed by the services. The dashboard will show placeholder "no data" panels until a Prometheus instance is added (Phase 1c), but the panels and queries are ready.

**Alternative approach (used here):** Since we don't have Prometheus scraping yet in the compose stack, we build this dashboard using TimescaleDB queries that approximate system health using the telemetry data itself (samples per minute, data freshness, etc.).

- [ ] **Step 1: Create `grafana/dashboards/system-health.json`**

```json
{
  "annotations": { "list": [] },
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 1,
  "id": null,
  "links": [],
  "panels": [
    {
      "title": "Ingest Rate (samples/min)",
      "type": "timeseries",
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 0 },
      "datasource": { "type": "grafana-postgresql-datasource", "uid": "timescaledb" },
      "targets": [
        {
          "rawSql": "SELECT time_bucket('1 minute', time) AS time, COUNT(*) AS samples_per_min FROM telemetry WHERE $__timeFilter(time) GROUP BY 1 ORDER BY 1",
          "format": "time_series"
        }
      ],
      "fieldConfig": {
        "defaults": { "unit": "short", "custom": { "fillOpacity": 10 } },
        "overrides": []
      }
    },
    {
      "title": "Ingest Rate by Equipment",
      "type": "timeseries",
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 0 },
      "datasource": { "type": "grafana-postgresql-datasource", "uid": "timescaledb" },
      "targets": [
        {
          "rawSql": "SELECT time_bucket('1 minute', time) AS time, equipment_id, COUNT(*) AS samples FROM telemetry WHERE $__timeFilter(time) GROUP BY 1, 2 ORDER BY 1",
          "format": "time_series"
        }
      ]
    },
    {
      "title": "Data Freshness (seconds since last sample)",
      "type": "gauge",
      "gridPos": { "h": 8, "w": 8, "x": 0, "y": 8 },
      "datasource": { "type": "grafana-postgresql-datasource", "uid": "timescaledb" },
      "targets": [
        {
          "rawSql": "SELECT equipment_id, EXTRACT(EPOCH FROM NOW() - MAX(time))::int AS seconds_since_last FROM telemetry WHERE time > NOW() - INTERVAL '10 minutes' GROUP BY equipment_id ORDER BY equipment_id",
          "format": "table"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "s",
          "thresholds": {
            "mode": "absolute",
            "steps": [
              { "color": "green", "value": null },
              { "color": "yellow", "value": 5 },
              { "color": "red", "value": 30 }
            ]
          }
        },
        "overrides": []
      }
    },
    {
      "title": "DB Table Size",
      "type": "stat",
      "gridPos": { "h": 8, "w": 8, "x": 8, "y": 8 },
      "datasource": { "type": "grafana-postgresql-datasource", "uid": "timescaledb" },
      "targets": [
        {
          "rawSql": "SELECT hypertable_size('telemetry')::bigint AS bytes",
          "format": "table"
        }
      ],
      "fieldConfig": {
        "defaults": { "unit": "decbytes" },
        "overrides": []
      }
    },
    {
      "title": "Total Rows",
      "type": "stat",
      "gridPos": { "h": 8, "w": 8, "x": 16, "y": 8 },
      "datasource": { "type": "grafana-postgresql-datasource", "uid": "timescaledb" },
      "targets": [
        {
          "rawSql": "SELECT approximate_row_count('telemetry') AS rows",
          "format": "table"
        }
      ],
      "fieldConfig": {
        "defaults": { "unit": "short" },
        "overrides": []
      }
    },
    {
      "title": "Chunk Info",
      "type": "table",
      "gridPos": { "h": 8, "w": 24, "x": 0, "y": 16 },
      "datasource": { "type": "grafana-postgresql-datasource", "uid": "timescaledb" },
      "targets": [
        {
          "rawSql": "SELECT chunk_name, range_start, range_end, is_compressed, pg_size_pretty(before_compression_total_bytes) AS uncompressed, pg_size_pretty(after_compression_total_bytes) AS compressed FROM timescaledb_information.chunks WHERE hypertable_name = 'telemetry' ORDER BY range_start DESC LIMIT 10",
          "format": "table"
        }
      ]
    }
  ],
  "schemaVersion": 39,
  "tags": ["factory-pulse", "system"],
  "templating": { "list": [] },
  "time": { "from": "now-1h", "to": "now" },
  "timepicker": {},
  "timezone": "browser",
  "title": "System Health",
  "uid": "system-health",
  "version": 1
}
```

- [ ] **Step 2: Verify in Grafana**

```bash
cd "d:/Dev/Project 1"
docker compose restart grafana
```

Open http://localhost:3000, verify "System Health" dashboard appears with panels.

- [ ] **Step 3: Commit**

```bash
git add grafana/dashboards/system-health.json
git commit -m "feat(grafana): add System Health dashboard

Ingest rate, data freshness gauges, DB size, chunk info. Uses
TimescaleDB queries directly (Prometheus datasource deferred to 1c)."
```

---

### Task 9: Docker Compose dev override

**Files:**
- Create: `docker-compose.dev.yml`

- [ ] **Step 1: Create `docker-compose.dev.yml`**

```yaml
# Development overrides: mount source code for hot reload.
# Usage: docker compose -f docker-compose.yml -f docker-compose.dev.yml up
services:
  simulator:
    volumes:
      - ./services/simulator/src:/app/src:ro
      - ./config:/config:ro
    environment:
      PYTHONDONTWRITEBYTECODE: "1"

  ingest:
    volumes:
      - ./services/ingest/src:/app/src:ro
    environment:
      PYTHONDONTWRITEBYTECODE: "1"

  api:
    build:
      context: .
      dockerfile: services/api/Dockerfile
    volumes:
      - ./services/api/src:/app/src:ro
      - ./config:/config:ro
    environment:
      PYTHONDONTWRITEBYTECODE: "1"
    command: >
      sh -c "alembic upgrade head &&
             uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app/src"
```

- [ ] **Step 2: Verify it starts**

```bash
cd "d:/Dev/Project 1"
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
docker compose ps
```

Expected: All services running.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.dev.yml
git commit -m "feat: add docker-compose.dev.yml for hot-reload development

Mount source directories and enable uvicorn --reload for the API service."
```

---

### Task 10: Integration tests

**Files:**
- Create: `services/api/tests/test_integration.py`
- Create: `docker-compose.test.yml`
- Modify: `services/api/pyproject.toml`

- [ ] **Step 1: Add testcontainers dependency**

In `services/api/pyproject.toml`, add to `[project.optional-dependencies] dev`:

```toml
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
    "ruff>=0.3",
    "mypy>=1.9",
    "testcontainers[postgres]>=4.4",
]
```

- [ ] **Step 2: Write integration tests**

Create `services/api/tests/test_integration.py`:

```python
"""Integration tests using testcontainers.

These tests spin up real TimescaleDB and Redis containers and test the
full API stack. Skip if Docker is not available.

Run: pytest tests/test_integration.py -v -m integration
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone, timedelta

import asyncpg
import pytest

# Mark all tests in this module
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def timescaledb():
    """Start a real TimescaleDB container for testing."""
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers not installed")

    # Use the same image as production
    with PostgresContainer(
        image="timescale/timescaledb:latest-pg16",
        user="factory",
        password="test_password",
        dbname="factory_pulse_test",
    ) as pg:
        yield pg


@pytest.fixture(scope="module")
def db_url(timescaledb):
    host = timescaledb.get_container_host_ip()
    port = timescaledb.get_exposed_port(5432)
    return f"postgresql://factory:test_password@{host}:{port}/factory_pulse_test"


@pytest.fixture(scope="module")
def _run_migrations(db_url, event_loop):
    """Run Alembic migrations against the test database."""
    import subprocess
    env = os.environ.copy()
    # Override DB connection for alembic
    env["POSTGRES_USER"] = "factory"
    env["POSTGRES_PASSWORD"] = "test_password"
    # Parse host/port from url
    from urllib.parse import urlparse
    parsed = urlparse(db_url)
    env["POSTGRES_HOST"] = parsed.hostname
    env["POSTGRES_PORT"] = str(parsed.port)
    env["POSTGRES_DB"] = "factory_pulse_test"

    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"Alembic migration failed:\n{result.stderr}")


@pytest.fixture(scope="module")
def pool(db_url, _run_migrations, event_loop):
    """Create an asyncpg pool connected to the test database."""
    _pool = event_loop.run_until_complete(
        asyncpg.create_pool(dsn=db_url, min_size=1, max_size=3)
    )
    yield _pool
    event_loop.run_until_complete(_pool.close())


async def test_equipment_table_exists(pool):
    """Migration creates the equipment table."""
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'equipment'"
        )
        assert result == 1


async def test_telemetry_is_hypertable(pool):
    """Telemetry table is a TimescaleDB hypertable."""
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM timescaledb_information.hypertables WHERE hypertable_name = 'telemetry'"
        )
        assert result == 1


async def test_continuous_aggregates_exist(pool):
    """Both continuous aggregates are created."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT view_name FROM timescaledb_information.continuous_aggregates ORDER BY view_name"
        )
        names = [r["view_name"] for r in rows]
        assert "telemetry_1hour" in names
        assert "telemetry_1min" in names


async def test_insert_and_query_telemetry(pool):
    """Insert telemetry rows and query them back."""
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        # Seed an equipment row
        await conn.execute(
            "INSERT INTO equipment (id, name, type, location) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
            "TEST-01", "Test Equipment", "test_type", "Test Location",
        )
        # Insert telemetry
        await conn.executemany(
            "INSERT INTO telemetry (time, equipment_id, metric_name, value, status) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
            [
                (now - timedelta(seconds=i), "TEST-01", "temperature", 25.0 + i, "running")
                for i in range(10)
            ],
        )
        # Query back
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM telemetry WHERE equipment_id = 'TEST-01'"
        )
        assert count == 10

        # Verify ordering
        rows = await conn.fetch(
            "SELECT value FROM telemetry WHERE equipment_id = 'TEST-01' ORDER BY time DESC LIMIT 3"
        )
        values = [r["value"] for r in rows]
        assert values == [25.0, 26.0, 27.0]


async def test_compression_policy_exists(pool):
    """Compression policy is configured."""
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM timescaledb_information.jobs WHERE proc_name = 'policy_compression' AND hypertable_name = 'telemetry'"
        )
        assert result == 1


async def test_retention_policy_exists(pool):
    """Retention policy is configured."""
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM timescaledb_information.jobs WHERE proc_name = 'policy_retention' AND hypertable_name = 'telemetry'"
        )
        assert result == 1
```

- [ ] **Step 3: Add integration marker to pytest config**

In `services/api/pyproject.toml`, update the pytest config:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "integration: integration tests requiring Docker (testcontainers)",
]
```

- [ ] **Step 4: Run integration tests locally**

```bash
cd "d:/Dev/Project 1/services/api"
pip install -e ".[dev]"
python -m pytest tests/test_integration.py -v -m integration
```

Expected: All 6 integration tests pass (requires Docker running).

- [ ] **Step 5: Run all tests (unit + integration) together**

```bash
cd "d:/Dev/Project 1/services/api"
python -m pytest tests/ -v
```

Expected: All tests pass (17 unit + 6 integration = 23 total).

- [ ] **Step 6: Create `docker-compose.test.yml`**

```yaml
# Minimal compose for CI integration tests.
# Usage: docker compose -f docker-compose.test.yml up -d
services:
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_USER: factory
      POSTGRES_PASSWORD: test_password
      POSTGRES_DB: factory_pulse_test
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U factory -d factory_pulse_test"]
      interval: 3s
      timeout: 3s
      retries: 10
      start_period: 5s

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

- [ ] **Step 7: Commit**

```bash
git add services/api/pyproject.toml services/api/tests/test_integration.py docker-compose.test.yml
git commit -m "feat: add integration tests with testcontainers

Test migrations, hypertable creation, continuous aggregates, insert/query,
compression and retention policies against real TimescaleDB."
```

---

### Task 11: Frontend test verification

**Files:**
- Verify: `frontend/tests/EquipmentCard.test.tsx`

- [ ] **Step 1: Run existing frontend tests**

```bash
cd "d:/Dev/Project 1/frontend"
npm install
npm test
```

Expected: 4 tests pass.

- [ ] **Step 2: If tests fail, fix them. If tests pass, no commit needed.**

---

### Task 12: GitHub Actions CI pipeline

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main]

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install ruff
        run: pip install ruff

      - name: Lint simulator
        run: ruff check services/simulator/src/

      - name: Lint ingest
        run: ruff check services/ingest/src/

      - name: Lint API
        run: ruff check services/api/src/

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: TypeScript check
        run: |
          cd frontend
          npm ci
          npx tsc --noEmit

  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Simulator tests
        run: |
          cd services/simulator
          pip install -e ".[dev]"
          pytest tests/ -v

      - name: Ingest tests
        run: |
          cd services/ingest
          pip install -e ".[dev]"
          pytest tests/ -v --ignore=tests/test_integration.py

      - name: API tests
        run: |
          cd services/api
          pip install -e ".[dev]"
          pytest tests/ -v --ignore=tests/test_integration.py -m "not integration"

      - name: Frontend tests
        run: |
          cd frontend
          npm ci
          npm test

  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    services:
      timescaledb:
        image: timescale/timescaledb:latest-pg16
        env:
          POSTGRES_USER: factory
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: factory_pulse_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U factory -d factory_pulse_test"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
          --health-start-period 10s

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install API with dev deps
        run: |
          cd services/api
          pip install -e ".[dev]"

      - name: Run Alembic migrations
        env:
          POSTGRES_HOST: localhost
          POSTGRES_USER: factory
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: factory_pulse_test
        run: |
          cd services/api
          alembic upgrade head

      - name: Run integration tests
        env:
          POSTGRES_HOST: localhost
          POSTGRES_USER: factory
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: factory_pulse_test
          REDIS_HOST: localhost
        run: |
          cd services/api
          pytest tests/test_integration.py -v -m integration

  docker-build:
    name: Docker Build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build simulator image
        run: docker build -t factory-pulse-simulator services/simulator

      - name: Build ingest image
        run: docker build -t factory-pulse-ingest services/ingest

      - name: Build API image (includes frontend)
        run: docker build -t factory-pulse-api -f services/api/Dockerfile .
```

- [ ] **Step 2: Verify CI config syntax**

```bash
cd "d:/Dev/Project 1"
# Basic YAML validation
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "feat: add GitHub Actions CI pipeline

Four parallel jobs: lint (ruff + tsc), unit tests (simulator + ingest +
api + frontend), integration tests (real TimescaleDB + Redis), and
Docker image builds."
```

---

### Task 13: ADR — Two-service split

**Files:**
- Create: `docs/adr/001-two-service-split.md`

- [ ] **Step 1: Create `docs/adr/001-two-service-split.md`**

```markdown
# ADR 001: Two-Service Architecture (Ingest + API)

**Status:** Accepted
**Date:** 2026-04-05

## Context

We need to choose how to structure the backend: a single monolith, two services (ingest + API), or three services (ingest + API + WebSocket).

## Decision

Split into two services:
- **ingest-service:** OPC-UA subscription, batch buffering, DB writes, Redis publishing
- **api-service:** REST API, WebSocket forwarding, Alembic migrations, static frontend serving

## Rationale

- **Decoupled failure domains:** Ingest can continue writing to the DB even if the API is down for deployment or crashes. API can serve cached data even if ingest is temporarily disconnected from OPC-UA.
- **Different scaling characteristics:** Ingest is IO-bound (OPC-UA + DB writes); API is request-driven. In a production scenario they'd scale differently.
- **Clear service boundary story:** Demonstrates real distributed-systems thinking without over-engineering into microservices.
- **Not three services:** A separate WebSocket service adds deployment complexity without meaningful benefit at this scale. The API service handles both REST and WebSocket since they share the same Redis subscription.

## Consequences

- Services communicate through Redis pub/sub (not direct calls), which adds a dependency but provides natural decoupling.
- Equipment config (`equipment.yaml`) must be shared between simulator and API — mounted as a read-only volume.
- Database migrations run only in the API service (single owner of the schema).
```

- [ ] **Step 2: Commit**

```bash
git add docs/adr/001-two-service-split.md
git commit -m "docs: ADR 001 — two-service split (ingest + API)"
```

---

### Task 14: ADR — TimescaleDB over InfluxDB

**Files:**
- Create: `docs/adr/002-timescaledb-over-influxdb.md`

- [ ] **Step 1: Create `docs/adr/002-timescaledb-over-influxdb.md`**

```markdown
# ADR 002: TimescaleDB Over InfluxDB

**Status:** Accepted
**Date:** 2026-04-05

## Context

We need a time-series database for equipment telemetry. The main candidates are TimescaleDB (PostgreSQL extension) and InfluxDB (purpose-built TSDB).

## Decision

Use TimescaleDB.

## Rationale

- **SQL + time-series in one database:** Equipment metadata (relational) and telemetry (time-series) live in the same database. No need for a separate Postgres instance for relational data.
- **Continuous aggregates:** Built-in materialized views that auto-refresh, giving us 1-minute and 1-hour rollups without a separate ETL pipeline.
- **Compression + retention policies:** Native, declarative — just `add_compression_policy` and `add_retention_policy`.
- **Enterprise credibility:** TimescaleDB is used in manufacturing, energy, and industrial IoT at scale. Target audience (APAC manufacturing engineers) will recognize it as a serious choice.
- **Ecosystem:** Standard PostgreSQL tooling works — `psql`, Alembic, asyncpg, Grafana's built-in PostgreSQL datasource.

## Alternatives considered

- **InfluxDB:** Purpose-built TSDB with Flux query language. Strong for pure time-series workloads. Downside: separate query language (not SQL), requires a separate relational DB for equipment metadata, less familiar to enterprise teams.
- **Plain PostgreSQL:** Would work at our scale but lacks hypertables, continuous aggregates, and compression. We'd need to build rollup logic manually.

## Consequences

- Requires the TimescaleDB Docker image instead of vanilla Postgres.
- Alembic migrations use raw SQL for TimescaleDB-specific DDL (`create_hypertable`, `add_continuous_aggregate_policy`).
- Grafana connects via the standard PostgreSQL datasource, using TimescaleDB-specific functions like `time_bucket()` in queries.
```

- [ ] **Step 2: Commit**

```bash
git add docs/adr/002-timescaledb-over-influxdb.md
git commit -m "docs: ADR 002 — TimescaleDB over InfluxDB"
```

---

### Task 15: ADR — OPC-UA only

**Files:**
- Create: `docs/adr/003-opc-ua-only.md`

- [ ] **Step 1: Create `docs/adr/003-opc-ua-only.md`**

```markdown
# ADR 003: OPC-UA Only (No MQTT in Phase 1)

**Status:** Accepted
**Date:** 2026-04-05

## Context

Industrial IoT systems commonly use OPC-UA, MQTT, or both. We need to decide which protocol(s) the ingest service supports.

## Decision

Support only OPC-UA in Phase 1. MQTT adapter deferred to Phase 2.

## Rationale

- **Domain differentiator:** OPC-UA is the dominant protocol in manufacturing automation (especially APAC automotive/battery). It signals genuine factory-floor experience that MQTT alone does not.
- **Complexity budget:** Supporting one protocol well (with subscriptions, reconnection, namespace browsing) is better than two protocols partially.
- **Architecture is protocol-agnostic internally:** The ingest service's internal pipeline (buffer → DB write → Redis publish) doesn't depend on OPC-UA. Adding an MQTT adapter in Phase 2 means creating a new subscription frontend that feeds the same pipeline.

## Consequences

- The simulator exposes an OPC-UA server only.
- The ingest service uses `asyncua` for OPC-UA client + subscription.
- Phase 2 will add an MQTT adapter, demonstrating the protocol-agnostic architecture.
```

- [ ] **Step 2: Commit**

```bash
git add docs/adr/003-opc-ua-only.md
git commit -m "docs: ADR 003 — OPC-UA only for Phase 1"
```

---

### Task 16: ADR — Narrow EAV telemetry schema

**Files:**
- Create: `docs/adr/004-narrow-eav-telemetry-schema.md`

- [ ] **Step 1: Create `docs/adr/004-narrow-eav-telemetry-schema.md`**

```markdown
# ADR 004: Narrow EAV Telemetry Schema

**Status:** Accepted
**Date:** 2026-04-05

## Context

We need to store telemetry data for equipment that has different metrics (temperature, voltage, throughput, pressure, thickness, cycle_count). Options: wide table (one column per metric), narrow EAV (entity-attribute-value with `metric_name` + `value` columns), or JSONB per row.

## Decision

Use narrow EAV: each row is `(time, equipment_id, metric_name, value)`.

## Rationale

- **Flexible ingest:** New equipment types with new metrics require zero schema changes. The simulator can emit any metric name and ingest writes it directly.
- **Simple batching:** All metrics use the same INSERT statement regardless of type. No column mapping logic.
- **Natural time-series queries:** `WHERE equipment_id = X AND metric_name = 'temperature'` maps cleanly to TimescaleDB continuous aggregates grouped by `(equipment_id, metric_name)`.
- **Compression-friendly:** TimescaleDB `compress_segmentby = 'equipment_id, metric_name'` produces excellent compression ratios because each segment is a homogeneous time-series.

## Trade-offs

- **More rows:** 5 metrics per sample = 5 rows instead of 1 wide row. At our scale (8 machines, 1s interval) this is ~40 rows/second — trivial for TimescaleDB.
- **Denormalized context:** We store `status`, `batch_id`, `unit_id` on every telemetry row. This trades storage for query simplicity — no joins needed to correlate telemetry with equipment state.
- **No type safety on metric values:** All values are `DOUBLE PRECISION`. String metrics (status, fault_code) are stored in separate columns, not in `value`.

## Alternatives considered

- **Wide table:** One column per metric. Simpler queries for single-equipment views, but requires schema changes for new metric types and makes batch inserts harder when equipment have different metric sets.
- **JSONB blob:** Maximum flexibility but poor query performance and no continuous aggregates.
```

- [ ] **Step 2: Commit**

```bash
git add docs/adr/004-narrow-eav-telemetry-schema.md
git commit -m "docs: ADR 004 — narrow EAV telemetry schema"
```

---

### Task 17: README polish

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README.md**

The current README is already good. The key additions for 1b:

1. Replace the "Phase 1b (Upcoming)" section at the bottom with the actual new features.
2. Add "Key Engineering Decisions" section linking to ADRs.
3. Add CI badge placeholder.
4. Add Grafana dashboard descriptions.

Read the current `README.md` first, then apply these edits:

Replace the last section:

```markdown
## Phase 1b (Upcoming)

Prometheus metrics, structured JSON logging, integration tests with Testcontainers, CI/CD pipeline, Caddy/HTTPS, ADRs, README polish.
```

With:

```markdown
## Key Engineering Decisions

| # | Decision | ADR |
|---|---|---|
| 1 | Two-service architecture (ingest + API) | [ADR 001](docs/adr/001-two-service-split.md) |
| 2 | TimescaleDB over InfluxDB | [ADR 002](docs/adr/002-timescaledb-over-influxdb.md) |
| 3 | OPC-UA only for Phase 1 | [ADR 003](docs/adr/003-opc-ua-only.md) |
| 4 | Narrow EAV telemetry schema | [ADR 004](docs/adr/004-narrow-eav-telemetry-schema.md) |

## Observability

### Grafana Dashboards — http://localhost:3000

| Dashboard | Description |
|---|---|
| **Equipment Telemetry** | Per-equipment drill-down: temperature, voltage, throughput over time |
| **Factory Health** | Fleet-wide view: status distribution, temperature trends, fault events, active batches |
| **System Health** | Self-monitoring: ingest rate, data freshness, DB size, chunk compression |

### Prometheus Metrics

| Service | Endpoint | Key Metrics |
|---|---|---|
| Ingest | `http://localhost:9090/metrics` | `ingest_messages_total`, `ingest_batch_latency_seconds`, `opcua_subscription_active` |
| API | `http://localhost:8000/metrics` | `http_requests_total`, `http_request_duration_seconds`, `websocket_connections_active` |

### Structured Logging

All services emit JSON-formatted logs to stdout:

```bash
docker compose logs api --tail=5
# {"timestamp": "2026-04-10T...", "level": "INFO", "service": "api", "message": "..."}
```

## CI/CD

GitHub Actions runs on every push: lint (ruff + tsc), unit tests, integration tests (real TimescaleDB), Docker builds.

## Roadmap

- **Phase 1a** (complete): Core pipeline — OPC-UA simulator, ingest, TimescaleDB, Redis, API, React dashboard, Grafana
- **Phase 1b** (complete): Observability, testing, CI, documentation
- **Phase 1c** (next): Production deployment — Caddy/HTTPS, VM deploy, GitHub Actions deploy workflow
- **Phase 2** (future): MQTT adapter, Redis Streams, alerting, OEE calculation
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: polish README with ADR links, observability section, roadmap

Add engineering decisions table, Grafana dashboard descriptions,
Prometheus metrics reference, structured logging examples, and updated
roadmap."
```

---

### Task 18: Final verification

- [ ] **Step 1: Run all unit tests**

```bash
cd "d:/Dev/Project 1/services/simulator" && python -m pytest tests/ -v
cd "d:/Dev/Project 1/services/ingest" && python -m pytest tests/ -v
cd "d:/Dev/Project 1/services/api" && python -m pytest tests/ -v -m "not integration"
cd "d:/Dev/Project 1/frontend" && npm test
```

Expected: All pass.

- [ ] **Step 2: Run integration tests**

```bash
cd "d:/Dev/Project 1/services/api"
python -m pytest tests/test_integration.py -v -m integration
```

Expected: All pass.

- [ ] **Step 3: Full stack verification**

```bash
cd "d:/Dev/Project 1"
docker compose down
docker compose up -d --build
docker compose ps -a
```

Expected: All 6 services running, API on 8000, Grafana on 3000, ingest metrics on 9090.

- [ ] **Step 4: Verify endpoints**

```bash
curl -s http://localhost:8000/api/equipment | python -m json.tool | head -10
curl -s http://localhost:8000/api/health | python -m json.tool
curl -s http://localhost:8000/metrics | head -10
curl -s http://localhost:9090/metrics | head -10
```

Expected: All return data. Health shows `"status": "healthy"`. Metrics show Prometheus format.

- [ ] **Step 5: Verify Grafana dashboards**

Open http://localhost:3000, login admin/admin. Navigate to Dashboards. Verify all three dashboards exist and load:
- Equipment Telemetry
- Factory Health
- System Health

- [ ] **Step 6: Verify structured logs**

```bash
docker compose logs --tail=3 api
docker compose logs --tail=3 ingest
docker compose logs --tail=3 simulator
```

Expected: All output JSON-formatted log lines.

**Deferred to Plan 1c:** Production VM deployment, Caddy/HTTPS, deploy workflow, `scripts/deploy.sh`, `DEPLOY.md`.
