# Factory Pulse — Design Spec

**Date:** 2026-04-05
**Status:** Design approved, pending implementation plan
**Scope:** Phase 1 MVP

---

## 1. Project Identity & Story

**Project name (working):** `factory-pulse`

**One-line pitch:**
> An open-source, end-to-end real-time telemetry platform that ingests OPC-UA data from EV battery manufacturing equipment, stores it in TimescaleDB, and streams live factory-floor state to a React dashboard and Grafana — deployed on a single VM with full CI/CD and observability.

**Positioning:** Domain-anchored generalist. The project is explicitly smart-factory (OPC-UA, EV battery equipment types, manufacturing terminology) but the underlying architecture (real-time telemetry, time-series storage, decoupled services, observability) transfers cleanly to fintech observability, logistics tracking, fleet management, and other real-time data domains.

**Target reader of the README:** Senior backend/cloud engineer or engineering manager at an APAC manufacturing HQ (e.g., Japanese automaker smart-factory divisions, Korean battery company digital groups, regional manufacturing integrators). They should finish the README thinking: *"This person has built the kind of system we actually run."*

**Story arc the repo tells a recruiter:**
1. **Domain expertise** — OPC-UA, EV battery equipment types (formation, aging, coating, calendering, assembly), realistic state machines, batch/unit traceability
2. **Distributed systems thinking** — decoupled ingest/API services via Redis, clear service boundaries
3. **Data engineering** — TimescaleDB hypertables, continuous aggregates, compression, retention policies
4. **Production-grade engineering** — tests, CI/CD, containerization, structured logging, self-monitoring
5. **Frontend competence** — live React dashboard with WebSocket streaming, plus Grafana integration

**Non-goals (explicitly out of scope for Phase 1):**
- Not a real digital twin (no electrochemistry modeling)
- Not a SCADA/MES replacement (no supervisory control, no recipe execution)
- Not multi-tenant SaaS (single factory scope)
- Not Kubernetes (single VM Docker Compose deploy)
- No load testing (system size doesn't justify it)

---

## 2. System Architecture & Components

### Architectural shape: Two services (ingest + API split)

```
┌──────────────────┐     OPC-UA       ┌──────────────────┐
│ opcua-simulator  │ ◀──────────────▶ │  ingest-service  │
│  (8 machines)    │                  │                  │
└──────────────────┘                  └────┬─────────┬───┘
                                           │         │
                                    writes │         │ publishes
                                           ▼         ▼
                                  ┌──────────────┐ ┌───────┐
                                  │ TimescaleDB  │ │ Redis │
                                  └──────┬───────┘ └───┬───┘
                                         │             │
                                    reads│             │subscribes
                                         ▼             ▼
                                  ┌──────────────────────┐
                                  │    api-service       │
                                  │  (FastAPI + React)   │
                                  └──────────┬───────────┘
                                             │
                                         HTTP/WS
                                             ▼
                                  ┌──────────────────────┐
                                  │  Browser (React UI)  │
                                  └──────────────────────┘

                                  ┌──────────────────────┐
                                  │       Grafana        │ ─── SQL ──▶ TimescaleDB
                                  └──────────────────────┘
```

### Services

#### 2.1 `opcua-simulator` (Python, `asyncua` server)

- Exposes OPC-UA server on port 4840
- Models **8 EV battery manufacturing machines** across 5 equipment types:
  - 2× **Formation Cycler** (charges/discharges new cells to activate them) — IDs `FORM-01`, `FORM-02`
  - 2× **Aging Chamber** (holds cells at controlled temp to stabilize) — IDs `AGING-01`, `AGING-02`
  - 1× **Electrode Coater** (applies slurry to foil) — ID `COAT-01`
  - 1× **Calendering Machine** (compresses coated electrodes) — ID `CAL-01`
  - 2× **Cell Assembler** (stacks/winds electrodes into cells) — IDs `ASSY-01`, `ASSY-02`
- Each machine exposes OPC-UA nodes: `Status`, `Temperature`, `Voltage` (or `Thickness`/`Pressure` per type), `Throughput`, `CycleCount`, `FaultCode`, `CurrentBatchId`, `CurrentUnitId`
- State machine per machine: `idle → running → fault → maintenance → idle` with realistic dwell times and occasional fault injection
- Update interval: configurable (default 1s)
- **Batch/unit generation:** Per-equipment-type durations (coater rolls ~10 min, formation cycler cells ~30 min, aging chambers hold batches for hours). On unit completion, generates new unit_id and emits log event.
- Runs standalone — can run on dev laptop or VM

#### 2.2 `ingest-service` (Python, `asyncua` client + asyncpg + redis-py)

- Connects to OPC-UA server, subscribes to all equipment nodes
- On each data change notification:
  - Writes sample to TimescaleDB `telemetry` hypertable (batched, ~100 rows or 1s flush)
  - Publishes event to Redis pub/sub channel `telemetry:{equipment_id}`
  - Updates Redis hash `equipment:latest:{equipment_id}` (hot cache of last-known values)
- Emits Prometheus metrics (see Observability section)
- Handles reconnection to OPC-UA with exponential backoff (1s → 60s max)
- Graceful shutdown (flush pending writes)

#### 2.3 `api-service` (FastAPI)

- REST endpoints + WebSocket endpoint (see API Contracts section)
- Serves the built React frontend as static files (single service for simplicity)
- Runs Alembic migrations on startup
- Emits Prometheus metrics

#### 2.4 `frontend` (React + Vite, built static bundle)

- Served by `api-service` (not a separate container)
- **One page:** Factory Floor Overview
  - Grid of equipment cards, one per machine
  - Each card: name, type, status pill (color-coded), key live metric, "Processing: {unit_id}" label, last-updated timestamp
  - Click → drill-down modal with sparkline + deep-link to Grafana for that equipment
  - Live updates via WebSocket
  - Connection status indicator (auto-reconnect)
- No routing library needed (single page)

### Infrastructure containers

#### 2.5 `timescaledb` (official image)
See Data Model section.

#### 2.6 `redis` (official image)
- Pub/sub channels: `telemetry:{equipment_id}`
- Hash: `equipment:latest:{equipment_id}` (hot cache)
- No persistence needed (all data flows through DB)

#### 2.7 `grafana` (official image, auto-provisioned)
- TimescaleDB configured as datasource
- Pre-provisioned dashboards (committed as JSON):
  - "Equipment Telemetry" — per-equipment drill-down
  - "Factory Health" — fleet-wide metrics
  - "System Health" — self-monitoring

#### 2.8 `caddy` (reverse proxy, auto-HTTPS)
- Routes subdomains to services, handles Let's Encrypt

### Data flow (happy path)

```
OPC-UA Simulator
    │ (1s tick, node value change)
    ▼
ingest-service (subscriber callback)
    │
    ├─▶ batch buffer (flush every 100 rows or 1s) ──▶ TimescaleDB.telemetry
    │
    ├─▶ Redis PUBLISH telemetry:{equipment_id} {payload}
    │
    └─▶ Redis HSET equipment:latest:{equipment_id} {fields}

Dashboard connects:
    WebSocket ─▶ api-service /ws/telemetry
                     │
                     └─▶ Redis SUBSCRIBE telemetry:*
                             │
                             └─▶ fan out to connected browsers
```

---

## 3. Data Model & Storage

### TimescaleDB schema

#### Table: `equipment` (relational)

```sql
CREATE TABLE equipment (
    id            TEXT PRIMARY KEY,           -- e.g., "FORM-01", "AGING-02"
    name          TEXT NOT NULL,              -- e.g., "Formation Cycler #1"
    type          TEXT NOT NULL,              -- 'formation_cycler' | 'aging_chamber' | 'electrode_coater' | 'calendering_machine' | 'cell_assembler'
    location      TEXT NOT NULL,              -- e.g., "Line-A / Bay-3"
    metadata      JSONB NOT NULL DEFAULT '{}', -- vendor, model, install_date, rated_throughput
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_equipment_type ON equipment(type);
```

Seeded at startup from `config/equipment.yaml` — the same file drives the simulator, so they stay in sync.

#### Hypertable: `telemetry`

```sql
CREATE TABLE telemetry (
    time          TIMESTAMPTZ NOT NULL,
    equipment_id  TEXT NOT NULL REFERENCES equipment(id),
    metric_name   TEXT NOT NULL,              -- 'temperature', 'voltage', 'throughput', etc.
    value         DOUBLE PRECISION NOT NULL,
    status        TEXT,                       -- snapshot of equipment status at sample time
    batch_id      TEXT,                       -- lot/batch currently being processed
    unit_id       TEXT,                       -- individual item (coil/cell/tray) being processed
    PRIMARY KEY (time, equipment_id, metric_name)
);

SELECT create_hypertable('telemetry', 'time', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX idx_telemetry_equipment_time ON telemetry(equipment_id, time DESC);
CREATE INDEX idx_telemetry_batch ON telemetry(batch_id, time DESC) WHERE batch_id IS NOT NULL;
CREATE INDEX idx_telemetry_unit ON telemetry(unit_id, time DESC) WHERE unit_id IS NOT NULL;
```

**Design notes:**
- Narrow EAV-style schema (`metric_name` as column, not one column per metric) — simpler ingest, flexible
- `status` + `batch_id` + `unit_id` denormalized into telemetry rows — trade-off: more storage for simpler queries at Phase 1 scale
- Primary key makes writes idempotent

#### Continuous aggregates

```sql
-- 1-minute rollups, refreshed every 30s
CREATE MATERIALIZED VIEW telemetry_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    equipment_id, metric_name,
    AVG(value) AS avg_value,
    MIN(value) AS min_value,
    MAX(value) AS max_value,
    COUNT(*) AS sample_count
FROM telemetry
GROUP BY bucket, equipment_id, metric_name;

-- 1-hour rollups, refreshed every 5 min
CREATE MATERIALIZED VIEW telemetry_1hour
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    equipment_id, metric_name,
    AVG(value), MIN(value), MAX(value), COUNT(*) AS sample_count
FROM telemetry
GROUP BY bucket, equipment_id, metric_name;
```

#### Compression & retention

```sql
ALTER TABLE telemetry SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'equipment_id, metric_name'
);
SELECT add_compression_policy('telemetry', INTERVAL '7 days');
SELECT add_retention_policy('telemetry', INTERVAL '30 days');
```

Aggregates retained indefinitely at Phase 1 scale.

### Redis keys

| Key pattern | Type | Purpose | TTL |
|---|---|---|---|
| `telemetry:{equipment_id}` | pub/sub channel | Live event stream per equipment | — |
| `equipment:latest:{equipment_id}` | hash | Last-known values, status, current batch/unit | 5 min |

Hash fields: `status`, `temperature`, `voltage`, `throughput`, `current_batch_id`, `current_unit_id`, `unit_started_at`, `updated_at`.

TTL means stale equipment (ingest down) naturally disappears from the hot cache → surfaces as "no data" in UI.

### Query routing (API → storage)

| Endpoint | Data path |
|---|---|
| List equipment + current values | Redis `HGETALL equipment:latest:*` + Postgres `equipment` join |
| Equipment details | Postgres `equipment` lookup |
| Historical telemetry (< 1 hour) | `telemetry` raw table |
| Historical telemetry (1h – 7d) | `telemetry_1min` aggregate |
| Historical telemetry (> 7d) | `telemetry_1hour` aggregate |
| Live stream | Redis pub/sub subscribe |

### Migrations

Alembic for Postgres migrations. Run automatically on `api-service` startup (idempotent). Seed data (equipment rows) loaded from `equipment.yaml` on first boot.

---

## 4. API Contracts & Interfaces

### REST API

**Base URL:** `/api`. JSON format, ISO-8601 UTC timestamps, snake_case field names.

#### `GET /api/equipment`
List all equipment with current status.

```json
{
  "equipment": [
    {
      "id": "FORM-01",
      "name": "Formation Cycler #1",
      "type": "formation_cycler",
      "location": "Line-A / Bay-3",
      "status": "running",
      "current_batch_id": "BATCH-2026-04-05-001",
      "current_unit_id": "CELL-2026-04-05-0042",
      "unit_started_at": "2026-04-05T13:18:12Z",
      "latest_metrics": {"temperature": 45.2, "voltage": 3.72, "throughput": 120},
      "updated_at": "2026-04-05T13:20:01.234Z"
    }
  ]
}
```

#### `GET /api/equipment/{id}`
Equipment metadata. **404** if not found.

#### `GET /api/equipment/{id}/current`
Current processing context (from Redis).

#### `GET /api/equipment/{id}/telemetry`
Historical telemetry with auto resolution.

**Query params:**
- `from` (required), `to` (required) — ISO-8601
- `metric` (optional, repeatable) — filter to specific metrics
- `interval` (optional) — `"raw" | "1min" | "1hour"`. Default: auto (< 1h → raw, 1h–7d → 1min, > 7d → 1hour)

**Errors:** 400 if `from > to`, 400 if range > 90 days, 404 if equipment unknown.

#### `GET /api/batches/{batch_id}/telemetry`
Trace a batch across equipment timeline.

#### `GET /api/health`
Liveness + dependency checks. Returns 503 if any dependency unhealthy.

#### `GET /metrics`
Prometheus scrape endpoint.

### WebSocket API: `WS /ws/telemetry`

**Client → Server:**
```json
{"action": "subscribe", "equipment_ids": ["FORM-01", "AGING-02"]}
{"action": "unsubscribe", "equipment_ids": ["AGING-02"]}
{"action": "subscribe_all"}
```

**Server → Client:**
```json
{
  "type": "telemetry",
  "equipment_id": "FORM-01",
  "time": "2026-04-05T13:20:01.234Z",
  "status": "running",
  "batch_id": "BATCH-2026-04-05-001",
  "unit_id": "CELL-2026-04-05-0042",
  "metrics": {"temperature": 45.2, "voltage": 3.72}
}
```

Plus `{"type": "ack", ...}` and `{"type": "error", ...}` messages.

**Behavior:**
- Server pings every 30s; disconnects if no pong within 10s
- Server batches telemetry events per equipment at most every 250ms
- Bounded send queue per client (100 msgs); drops oldest if full
- On reconnect, client resubscribes (no server-side persistence)

### OPC-UA Namespace (simulator contract)

**Namespace URI:** `urn:factory-pulse:simulator`

```
Objects/
  Factory/
    Equipment/
      FORM-01/
        Status (String), Temperature (Double), Voltage (Double),
        Throughput (Double), CycleCount (Int32), FaultCode (String),
        CurrentBatchId (String), CurrentUnitId (String)
      FORM-02/ ...
      AGING-01/ ...
```

Ingest service subscribes to all variable nodes under `Objects/Factory/Equipment/*`.

---

## 5. Error Handling, Testing & Observability

### Error handling

**Ingest service:**

| Failure | Behavior |
|---|---|
| OPC-UA unreachable (startup or mid-run) | Exponential backoff (1s → 60s max), service stays alive |
| TimescaleDB write failure (batch) | Log, increment metric, retry once, drop + continue |
| TimescaleDB unreachable (persistent) | Buffer up to 10k rows, drop oldest beyond that |
| Redis unreachable | Skip publish + cache update, log WARN, continue (DB is source of truth) |
| Invalid OPC-UA value | Skip sample, increment `ingest_invalid_samples_total`, DEBUG log |

**API service:**

| Failure | Behavior |
|---|---|
| TimescaleDB unreachable | REST returns 503; equipment list falls back to Redis (flag `"stale": true`) |
| Redis unreachable | Equipment list falls back to Postgres (no live metrics); WebSocket closes gracefully with 1011 |
| Invalid query params | 400 with structured error |
| Range too large | 400 with `max_days: 90` |
| Unhandled exception | 500 with generic body; full trace logged |

**WebSocket:**

| Failure | Behavior |
|---|---|
| Malformed JSON | Error message, keep connection open |
| Unknown action | Error message, keep open |
| Redis subscribe fails | Close 1011, client reconnects |
| Slow consumer | Bounded queue, drop oldest, log |

### Structured logging

JSON logs to stdout. Fields: `timestamp`, `level`, `service`, `message`, `equipment_id`, `batch_id`, `request_id`, `error_type`. Stack traces as escaped single-line field.

### Testing strategy

**Unit tests:**
- `ingest-service`: value parsing, batch buffering, metric mapping, reconnect backoff
- `api-service`: query param validation, interval auto-selection, response serialization, WebSocket message parsing
- `simulator`: state machine transitions, batch/unit ID generation, value bounds

**Integration tests (testcontainers):**
- Real TimescaleDB: migrations, seed, write, query, aggregate refresh
- Real Redis: pub/sub round-trip, hash ops
- End-to-end: simulator + ingest + DB + Redis, assert arrival within N seconds

**API contract tests:** happy path + each error case per endpoint; WebSocket sub/recv/unsub flow.

**Frontend tests:** Vitest + React Testing Library for equipment card; one smoke test for app mount.

**CI (GitHub Actions):** lint (ruff + mypy + eslint + tsc), unit tests, integration tests, Docker image build, frontend bundle build. Badges on README.

**Non-goal:** Load testing (Phase 2).

### Observability

**Ingest metrics:**
- `ingest_messages_total{equipment_id, metric_name}`
- `ingest_batch_size` (histogram)
- `ingest_batch_latency_seconds` (histogram)
- `ingest_db_write_errors_total`
- `ingest_invalid_samples_total{reason}`
- `opcua_subscription_active` (gauge)
- `opcua_connection_attempts_total{result}`
- `redis_publish_errors_total`

**API metrics:**
- `http_requests_total{method, path, status}`
- `http_request_duration_seconds{method, path}` (histogram)
- `websocket_connections_active` (gauge)
- `websocket_messages_sent_total`
- `websocket_client_dropped_total{reason}`
- `db_query_duration_seconds{query}` (histogram)

**Grafana "System Health" dashboard:** ingest throughput + latency + errors, API request rate + errors + p99, dependency up/down, WebSocket connection count. Stored as JSON in `grafana/dashboards/system-health.json`.

**Health checks:** `/health` (liveness) + `/ready` (dependency checks) on every service. Docker Compose `healthcheck:` blocks + `depends_on` with `condition: service_healthy`.

---

## 6. Repository Structure, Deployment & Phased Roadmap

### Repository layout

```
factory-pulse/
├── README.md
├── ARCHITECTURE.md
├── docker-compose.yml
├── docker-compose.dev.yml
├── docker-compose.test.yml
├── .github/workflows/
│   ├── ci.yml
│   └── deploy.yml
├── services/
│   ├── simulator/     (src, tests, Dockerfile, pyproject.toml)
│   ├── ingest/        (src, tests, Dockerfile, pyproject.toml)
│   └── api/           (src, tests, alembic, Dockerfile, pyproject.toml)
├── frontend/          (src, tests, package.json, vite.config.ts)
├── grafana/
│   ├── provisioning/  (datasources, dashboards config)
│   └── dashboards/    (JSON files)
├── config/
│   └── equipment.yaml
├── scripts/
│   ├── deploy.sh
│   └── seed-demo-data.py
└── docs/
    ├── images/
    └── adr/
        ├── 001-two-service-split.md
        ├── 002-timescaledb-over-influxdb.md
        ├── 003-opc-ua-only.md
        └── 004-narrow-eav-telemetry-schema.md
```

**ADRs:** One-page records explaining *why* each major choice was made. Each significant decision from brainstorming becomes an ADR.

### Deployment

**Development (local):**
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```
Hot reload on Python services, Vite dev server on host.

**Production (single VM, ~2GB RAM / 2 cores / 40GB SSD):**
- VM sizing is tight-but-workable. Memory budget: TimescaleDB ~700MB (tuned: `shared_buffers=256MB`, `work_mem=16MB`), Redis ~100MB, each Python service ~150MB, OS+Docker overhead ~400MB → ~1.5–1.8GB with 200–500MB headroom.
- Simulator may run off-VM (on dev laptop) pointing at the VM's OPC-UA endpoint to save memory; configurable via env.
- Disk budget: 10 machines × 5 metrics × 1 sample/s ≈ 500MB/day uncompressed. Compression (7-day delay) → 10–20× reduction. Retention policy drops raw after 30 days. Aggregates retained indefinitely (small footprint).
- VM provisioned manually; steps documented in `docs/DEPLOY.md`
- GitHub Actions: on merge to `main`, build images tagged with git SHA, push to GHCR, SSH into VM, pull, `docker compose up -d`, poll health, rollback on failure
- `.env` on VM for secrets (`POSTGRES_PASSWORD`, `GRAFANA_ADMIN_PASSWORD`)
- TimescaleDB volume on host: `/opt/factory-pulse/data/timescaledb`
- Nightly `pg_dump` backup (7 days retention)
- Caddy container for automatic HTTPS + subdomain routing:
  - `factory-pulse.<domain>` → dashboard
  - `grafana.factory-pulse.<domain>` → Grafana

### README structure (recruiter experience)

1. Hero GIF of live dashboard
2. One-paragraph pitch
3. Live demo link + read-only credentials
4. Architecture diagram
5. Key engineering decisions (bullets linking to ADRs)
6. Tech stack table
7. Running locally (one command)
8. Deployment link
9. Roadmap (shows active project)

### Phased roadmap

**Phase 1 (this spec):** Everything above. Shippable MVP.

**Phase 2 (future):**
- MQTT ingest adapter (protocol-agnostic architecture)
- Redis Streams queue (durable ingest, backpressure)
- Alerting rules engine
- OEE calculation
- `node_exporter` for VM metrics
- Terraform for VM provisioning

**Phase 3 (future):**
- Anomaly detection (statistical, then possibly ML)
- Full product genealogy
- Multi-factory / multi-tenant
- Mobile-responsive dashboard

Each phase gets its own spec → plan → implementation cycle, visible in git history as deliberate evolution.

---

## Appendix: Key Decision Log

| # | Decision | Alternatives | Why |
|---|---|---|---|
| 1 | Domain-anchored generalist positioning | Generalist / Pure domain | Leverage rare factory experience as moat without narrowing funnel |
| 2 | Phased shipping (MVP → depth → showcase) | Deep & narrow / Broad | Ship something solid fast, evolve publicly |
| 3 | Multi-equipment MVP (8 machines) | Single machine / Full fleet | Mirrors real job ("all equipment to upper system") without overscope |
| 4 | OPC-UA only for Phase 1 | MQTT / Both | OPC-UA is the domain differentiator; MQTT adds no signal for target audience |
| 5 | TimescaleDB | InfluxDB / Postgres only | SQL + time-series + relational in one DB, enterprise-credible |
| 6 | Redis pub/sub + WebSocket | In-process / LISTEN-NOTIFY / SSE | Industry-standard decoupled pattern, tells real architecture story |
| 7 | Single VM Docker Compose | GCP Cloud Run / GKE / Hybrid | Cost-effective, honest, matches Phase 1 scope |
| 8 | Grafana + React/Vite custom frontend | HTMX / Full React SPA / Grafana only | Grafana = domain authenticity; custom UI = "I can build frontend" |
| 9 | Tests + CI/CD + observability | Minimal / Full terraform | Max signal per hour invested; self-monitoring mirrors real operations |
| 10 | Domain-flavored simulator (EV battery equipment) | Minimal / Full twin | Instant recognizability with target recruiters |
| 11 | Two-service architecture (ingest + API) | Monolith / Three-service | Real decoupling story without over-engineering |
| 12 | Lightweight traceability (batch_id + unit_id on telemetry) | None / Full genealogy | Huge domain signal at minimal scope cost |
