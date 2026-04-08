# Factory Pulse

Real-time telemetry platform for EV battery manufacturing equipment. Simulates 8 machines across 5 equipment types (formation cyclers, aging chambers, electrode coaters, calendering machines, cell assemblers) and streams live sensor data end-to-end: OPC-UA → ingest service → TimescaleDB + Redis → REST/WebSocket API → React dashboard + Grafana.

Built as a portfolio project demonstrating industrial IoT systems design, real-time data pipelines, and cloud-native backend engineering.

---

## Architecture

```
OPC-UA Simulator
      │  opc.tcp://4840
      ▼
Ingest Service  ──────────────────────────────────────────────────┐
  - Subscribes to all equipment nodes via asyncua                 │
  - Buffers samples (flush on size=100 or age=1s)                │
  - Batch-inserts into TimescaleDB                               │
  - Publishes to Redis pub/sub + updates hot cache (HSET)        │
      │ asyncpg                         │ redis pub/sub           │
      ▼                                 ▼                         │
TimescaleDB                         Redis                         │
  - telemetry hypertable              - telemetry:{id} channels   │
  - 1-min continuous aggregate        - equipment:latest:{id}     │
  - 1-hour continuous aggregate         hot cache (HSET, 5m TTL) │
  - 7-day compression policy                  │                   │
  - 30-day retention policy                   ▼                   │
      │                               API Service ◄───────────────┘
      └──────────────────────────────►  - FastAPI + uvicorn
                                        - Seeds equipment on startup
                                        - REST: equipment, telemetry, batches
                                        - WebSocket: /ws/telemetry (Redis sub)
                                        - Serves built React frontend at /
                                              │ HTTP :8000
                                              ▼
                                       React Dashboard
                                        - Fetches equipment list on load
                                        - Subscribes to all via WS
                                        - Live status + metric updates
                                        - Auto-reconnect with backoff

TimescaleDB ◄── Grafana :3000
  (separate direct connection)
```

## Tech Stack

| Layer | Technology |
|---|---|
| Simulator | Python 3.12, asyncua (OPC-UA server) |
| Ingest | Python 3.12, asyncua (OPC-UA client), asyncpg, redis-py |
| Database | TimescaleDB (PostgreSQL 16) — hypertable, continuous aggregates, compression |
| Cache / Pub-Sub | Redis 7 |
| API | FastAPI, uvicorn, asyncpg, redis-py, Alembic |
| Frontend | React 18, TypeScript, Vite |
| Observability | Grafana 10 |
| Packaging | Docker, Docker Compose |
| Testing | pytest, pytest-asyncio, Vitest, @testing-library/react |

## Equipment Fleet

8 machines across 3 production lines defined in [`config/equipment.yaml`](config/equipment.yaml):

| ID | Name | Line | Metrics |
|---|---|---|---|
| FORM-01/02 | Formation Cycler | A | temperature, voltage, throughput, cycle_count |
| AGING-01/02 | Aging Chamber | A | temperature, throughput |
| COAT-01 | Electrode Coater | B | temperature, thickness, throughput |
| CAL-01 | Calendering Machine | B | pressure, thickness, throughput |
| ASSY-01/02 | Cell Assembler | C | temperature, throughput, cycle_count |

Each machine runs a state machine: **idle → running → fault → maintenance → idle**.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- That's it. No Python or Node installation needed to run.

---

## Running the Project

### 1. Clone and enter the repo

```bash
git clone <repo-url>
cd "factory-pulse"
```

### 2. Create your `.env` (copy from example)

```bash
cp .env.example .env
```

The defaults work as-is for local development. No changes needed.

### 3. Start the full stack

```bash
docker compose up -d --build
```

First run takes ~2–3 minutes to pull images and build containers. Subsequent starts are fast.

### 4. Wait ~15 seconds for services to initialize

TimescaleDB needs a moment to start, then Alembic migrations run, then the ingest service connects to the OPC-UA simulator.

### 5. Check everything is running

```bash
docker compose ps
```

Expected: all 6 services in `running` state.

---

## What You'll See

### Live Dashboard — http://localhost:8000

React dashboard served directly from the API container.

- **8 equipment cards** — one per machine
- **Colored status pill** — green (running), grey (idle), red (fault), amber (maintenance)
- **Live metric values** — updating every ~1 second as OPC-UA data flows through
- **Processing unit ID** — current batch/unit being processed
- **Connection indicator** — green "Live" dot when WebSocket is connected, red "Reconnecting…" when not

### REST API — http://localhost:8000/api

| Endpoint | Description |
|---|---|
| `GET /api/health` | Service health check (DB + Redis status) |
| `GET /api/equipment` | All equipment with latest metrics from Redis hot cache |
| `GET /api/equipment/{id}` | Single equipment detail |
| `GET /api/equipment/{id}/current` | Current status, batch, unit from Redis |
| `GET /api/equipment/{id}/telemetry?from=&to=` | Historical telemetry — auto-selects raw / 1-min / 1-hour based on time range |
| `GET /api/batches/{batch_id}/telemetry` | Batch traceability — equipment timeline for a batch |
| `WS /ws/telemetry` | WebSocket stream — subscribe to specific equipment or all |

Auto-documentation at **http://localhost:8000/docs** (Swagger UI).

### Grafana — http://localhost:3000

Login: `admin` / `admin`

- Navigate to **Dashboards → Equipment Telemetry**
- Pick any equipment from the dropdown
- Live-updating time series chart of all metrics for that machine

### TimescaleDB (direct access)

```bash
docker compose exec timescaledb psql -U factory -d factory_pulse
```

```sql
-- Row count (should be growing every second)
SELECT COUNT(*) FROM telemetry;

-- Latest reading per equipment
SELECT equipment_id, metric_name, value, time
FROM telemetry
ORDER BY time DESC
LIMIT 20;

-- Check continuous aggregate is populated
SELECT * FROM telemetry_1min LIMIT 10;
```

### Redis (direct access)

```bash
docker compose exec redis redis-cli

# Hot cache for a machine
HGETALL equipment:latest:FORM-01

# Subscribe to live telemetry stream
SUBSCRIBE telemetry:FORM-01
```

---

## Stopping the Stack

```bash
# Stop containers (keeps data)
docker compose down

# Stop and wipe all data (full reset)
docker compose down -v
```

---

## Development

### Running tests

Each service has its own isolated test suite with no external dependencies.

```bash
# Simulator (17 tests)
cd services/simulator
pip install -e ".[dev]"
pytest tests/ -v

# Ingest (7 tests)
cd services/ingest
pip install -e ".[dev]"
pytest tests/ -v

# API (17 tests)
cd services/api
pip install -e ".[dev]"
pytest tests/ -v

# Frontend (4 tests)
cd frontend
npm install
npm test
```

### Project structure

```
factory-pulse/
├── config/
│   └── equipment.yaml          # Single source of truth for the equipment fleet
├── services/
│   ├── simulator/              # OPC-UA server — publishes fake sensor data
│   ├── ingest/                 # OPC-UA client → TimescaleDB + Redis
│   └── api/                    # FastAPI — REST + WebSocket + static frontend
│       └── alembic/            # DB migrations (TimescaleDB schema)
├── frontend/                   # React + TypeScript dashboard (Vite)
├── grafana/                    # Grafana provisioning (datasource + dashboard)
├── docker-compose.yml          # Full 6-service stack
└── .env.example                # Environment variable reference
```

---

## Environment Variables

All variables have working defaults. Only override if needed.

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_USER` | `factory` | DB username |
| `POSTGRES_PASSWORD` | `factory_dev_password` | DB password |
| `POSTGRES_DB` | `factory_pulse` | Database name |
| `REDIS_HOST` | `redis` | Redis hostname (Docker service name) |
| `OPCUA_ENDPOINT` | `opc.tcp://simulator:4840` | OPC-UA server address |
| `SIMULATOR_TICK_SECONDS` | `1.0` | How often simulator updates nodes |
| `INGEST_BATCH_SIZE` | `100` | Flush buffer after N samples |
| `INGEST_FLUSH_SECONDS` | `1.0` | Flush buffer after N seconds |
| `GRAFANA_ADMIN_PASSWORD` | `admin` | Change before any public deployment |

---

## Phase 1b (Upcoming)

Prometheus metrics, structured JSON logging, integration tests with Testcontainers, CI/CD pipeline, Caddy/HTTPS, ADRs, README polish.
