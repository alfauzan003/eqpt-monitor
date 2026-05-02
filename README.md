# EQPT MONITOR

> Real-time telemetry platform for EV battery manufacturing — built to demonstrate industrial IoT, streaming data pipelines, and cloud-native backend engineering.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![TimescaleDB](https://img.shields.io/badge/TimescaleDB-PG16-FDB515?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-10-F46800?logo=grafana&logoColor=white)

---

## What It Does

Simulates 8 industrial machines across 3 production lines and streams live sensor data end-to-end:

```
OPC-UA Simulator → Ingest Service → TimescaleDB + Redis → FastAPI → React Dashboard + Grafana
```

Each machine runs a state machine (`idle → running → fault → maintenance → idle`) and emits metrics like temperature, voltage, pressure, and throughput at 1 Hz. The full stack runs locally in Docker with a single command.

---

## Architecture

```
┌─────────────────┐
│  OPC-UA         │  opc.tcp://simulator:4840
│  Simulator      │  8 machines, 1 Hz ticks, state machine
└────────┬────────┘
         │ asyncua subscription
┌────────▼────────┐
│  Ingest         │  Python worker
│  Service        │  • Buffers → batch-inserts (size=100 or 1s flush)
└──┬──────────┬───┘  • Publishes to Redis pub/sub
   │ asyncpg  │ redis-py
   ▼          ▼
TimescaleDB  Redis 7
• hypertable  • telemetry:{id} pub/sub channels
• 1-min agg   • equipment:latest:{id} hot cache (HSET, 5m TTL)
• 1-hr agg
• 7d compress
• 30d retain
   │          │
   └────┬─────┘
        │
┌───────▼────────┐     ┌──────────────┐
│  FastAPI       │◄────│  Grafana :3000│
│  API :8000     │     │  (direct DB)  │
│  • REST        │     └──────────────┘
│  • WebSocket   │
│  • Serves SPA  │
└───────┬────────┘
        │ WS + HTTP
┌───────▼────────┐
│  React         │
│  Dashboard     │
│  live updates  │
└────────────────┘
```

---

## Tech Stack

| Layer           | Technology                                | Purpose                                                    |
| --------------- | ----------------------------------------- | ---------------------------------------------------------- |
| Protocol        | OPC-UA (`asyncua`)                        | Industry-standard machine comms                            |
| Ingest          | Python 3.12, asyncpg, redis-py            | Async pipeline, buffered batch writes                      |
| Database        | TimescaleDB (PostgreSQL 16)               | Time-series hypertable, continuous aggregates, compression |
| Cache / Pub-Sub | Redis 7                                   | Hot cache for latest readings, real-time fan-out           |
| API             | FastAPI, uvicorn, Alembic                 | REST + WebSocket, DB migrations                            |
| Frontend        | React 18, TypeScript, Vite                | Live dashboard, auto-reconnect WS                          |
| Observability   | Grafana 10, Prometheus metrics, JSON logs | 3 dashboards, structured logging                           |
| Infra           | Docker Compose                            | 6-service local stack, one command                         |
| Testing         | pytest, pytest-asyncio, Vitest            | Unit + integration tests per service                       |

---

## Equipment Fleet

Defined in [`config/equipment.yaml`](config/equipment.yaml) — single source of truth for all services.

| ID          | Equipment           | Line | Metrics                                       |
| ----------- | ------------------- | ---- | --------------------------------------------- |
| FORM-01/02  | Formation Cycler    | A    | temperature, voltage, throughput, cycle_count |
| AGING-01/02 | Aging Chamber       | A    | temperature, throughput                       |
| COAT-01     | Electrode Coater    | B    | temperature, thickness, throughput            |
| CAL-01      | Calendering Machine | B    | pressure, thickness, throughput               |
| ASSY-01/02  | Cell Assembler      | C    | temperature, throughput, cycle_count          |

---

## Quick Start

**Prerequisites:** Docker Desktop only. No Python or Node needed.

```bash
# 1. Clone
git clone <repo-url>
cd factory-pulse

# 2. Set up env (defaults work as-is)
cp .env.example .env

# 3. Start the full stack
docker compose up -d --build
```

First run: ~2–3 min to pull and build. Wait ~15 s for services to initialize, then:

| URL                        | What                                   |
| -------------------------- | -------------------------------------- |
| http://localhost:8000      | React dashboard (live equipment cards) |
| http://localhost:8000/docs | Swagger UI (all REST endpoints)        |
| http://localhost:3000      | Grafana (`admin` / `admin`)            |

```bash
# Verify all 6 services are running
docker compose ps

# Tear down (keeps data)
docker compose down

# Full reset (wipes volumes)
docker compose down -v
```

---

## API

| Method | Endpoint                            | Description                                                 |
| ------ | ----------------------------------- | ----------------------------------------------------------- |
| `GET`  | `/api/health`                       | DB + Redis health check                                     |
| `GET`  | `/api/equipment`                    | All equipment with latest metrics (Redis cache)             |
| `GET`  | `/api/equipment/{id}/telemetry`     | Historical data — auto-selects raw / 1-min / 1-hr aggregate |
| `GET`  | `/api/batches/{batch_id}/telemetry` | Batch traceability across equipment timeline                |
| `WS`   | `/ws/telemetry`                     | Subscribe to live readings for one or all machines          |

---

## Observability

**Grafana dashboards** (http://localhost:3000 → Dashboards):

- **Equipment Telemetry** — per-machine drill-down: metrics over time
- **Factory Health** — fleet-wide: status distribution, fault events, active batches
- **System Health** — self-monitoring: ingest rate, data freshness, DB size, chunk compression

**Prometheus metrics** exposed at:

- Ingest: `http://localhost:9090/metrics` — `ingest_messages_total`, `ingest_batch_latency_seconds`
- API: `http://localhost:8000/metrics` — `http_requests_total`, `websocket_connections_active`

**Structured logging** — all services emit JSON to stdout:

```bash
docker compose logs api --tail=5
# {"timestamp": "...", "level": "INFO", "service": "api", "message": "..."}
```

---

## Running Tests

Each service has an isolated test suite (no external dependencies for unit tests).

```bash
# Simulator — 17 tests
cd services/simulator && pip install -e ".[dev]" && pytest tests/ -v

# Ingest — 8 tests
cd services/ingest && pip install -e ".[dev]" && pytest tests/ -v

# API — unit (17 tests) + integration (6 tests, requires Docker)
cd services/api && pip install -e ".[dev]"
pytest tests/ -v -m "not integration"
pytest tests/test_integration.py -v -m integration

# Frontend — 4 tests
cd frontend && npm install && npm test
```

---

## Project Structure

```
factory-pulse/
├── config/equipment.yaml       # Fleet definition (shared by all services)
├── services/
│   ├── simulator/              # OPC-UA server, state machine, sensor simulation
│   ├── ingest/                 # OPC-UA client → TimescaleDB + Redis pipeline
│   └── api/                    # FastAPI REST + WebSocket + SPA host
│       └── alembic/            # DB migrations (hypertable, aggregates, compression)
├── frontend/                   # React + TypeScript live dashboard
├── grafana/                    # Provisioned datasource + 3 dashboards
├── docker-compose.yml          # Full 6-service stack
└── .env.example                # All configurable variables with defaults
```

---

## Key Design Decisions

| #   | Decision                            | Rationale                                                                               |
| --- | ----------------------------------- | --------------------------------------------------------------------------------------- |
| 1   | Ingest and API as separate services | Ingest can fall behind under load without blocking API reads                            |
| 2   | TimescaleDB over InfluxDB           | Full SQL, native PostgreSQL tooling, continuous aggregates eliminate query-time rollups |
| 3   | OPC-UA for Phase 1                  | Industry standard for machine connectivity; realistic for IIoT portfolio                |
| 4   | Narrow EAV telemetry schema         | One row per metric enables flexible querying without schema changes per equipment type  |

---
