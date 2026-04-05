# Factory Pulse — Phase 1a: Core Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the local-dev working core pipeline: OPC-UA simulator → ingest service → TimescaleDB + Redis → FastAPI REST/WebSocket → React dashboard, plus Grafana with one equipment telemetry dashboard. After this plan, `docker compose up` produces a running system with live telemetry flowing end-to-end.

**Architecture:** Two-service split (ingest-service + api-service) with TimescaleDB for persistence, Redis for pub/sub and hot cache, OPC-UA as the ingest protocol. Monorepo with `services/` for Python services and `frontend/` for React. Single `docker-compose.yml` brings up the whole stack.

**Tech Stack:** Python 3.12, FastAPI, asyncua (OPC-UA), asyncpg, redis-py, TimescaleDB, Redis, Alembic, React 18, Vite, TypeScript, Grafana, Docker Compose, pytest, Vitest.

**Out of scope (covered in Plan 1b):** Prometheus metrics, structured logging, health endpoints, integration tests, CI/CD, production deploy, Caddy/HTTPS, ADRs, README polish.

---

## File Structure

This is what Plan 1a produces. Items marked `(1b)` are deferred to Plan 1b.

```
factory-pulse/
├── .gitignore
├── .env.example
├── docker-compose.yml
├── docker-compose.dev.yml
├── config/
│   └── equipment.yaml                  # Single source of truth for equipment
├── services/
│   ├── simulator/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/simulator/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                 # Entry point
│   │   │   ├── config.py               # Load equipment.yaml
│   │   │   ├── equipment.py            # Equipment base + subclasses
│   │   │   ├── state_machine.py        # idle→running→fault→maintenance
│   │   │   ├── batch_tracker.py        # batch/unit ID generation
│   │   │   └── opcua_server.py         # asyncua server + node publishing
│   │   └── tests/
│   │       ├── test_state_machine.py
│   │       ├── test_batch_tracker.py
│   │       └── test_equipment.py
│   ├── ingest/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/ingest/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── opcua_client.py         # Subscribe to nodes
│   │   │   ├── batch_buffer.py         # Flush on size/time
│   │   │   ├── db_writer.py            # asyncpg batch insert
│   │   │   └── redis_publisher.py      # pub/sub + hot cache
│   │   └── tests/
│   │       ├── test_batch_buffer.py
│   │       └── test_redis_publisher.py
│   └── api/
│       ├── Dockerfile
│       ├── pyproject.toml
│       ├── alembic.ini
│       ├── alembic/
│       │   ├── env.py
│       │   └── versions/
│       │       └── 0001_initial_schema.py
│       ├── src/api/
│       │   ├── __init__.py
│       │   ├── main.py                 # FastAPI app
│       │   ├── config.py
│       │   ├── db.py                   # asyncpg pool
│       │   ├── redis_client.py
│       │   ├── seed.py                 # Load equipment.yaml
│       │   ├── routes/
│       │   │   ├── equipment.py
│       │   │   ├── telemetry.py
│       │   │   ├── batches.py
│       │   │   └── health.py
│       │   ├── websocket.py
│       │   └── query_router.py         # Auto-select raw/1min/1hour
│       └── tests/
│           ├── test_query_router.py
│           ├── test_routes_equipment.py
│           └── test_websocket.py
├── frontend/
│   ├── Dockerfile                      # For production static build
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api.ts                      # REST client
│   │   ├── websocket.ts                # WS client with reconnect
│   │   ├── types.ts                    # Shared types
│   │   └── components/
│   │       ├── EquipmentGrid.tsx
│   │       ├── EquipmentCard.tsx
│   │       └── ConnectionStatus.tsx
│   └── tests/
│       └── EquipmentCard.test.tsx
└── grafana/
    ├── provisioning/
    │   ├── datasources/timescaledb.yml
    │   └── dashboards/dashboards.yml
    └── dashboards/
        └── equipment-telemetry.json
```

---

## Task List

### Task 1: Repository skeleton and Git init

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md` (placeholder, polished in Plan 1b)

- [ ] **Step 1: Initialize git repo**

```bash
cd "d:/Dev/Project 1"
git init
git config core.autocrlf false
```

- [ ] **Step 2: Create `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.venv/
venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Node
node_modules/
dist/
.vite/

# Env
.env
.env.local

# Docker volumes
data/

# IDE
.vscode/
.idea/
*.swp
.DS_Store

# OS
Thumbs.db
```

- [ ] **Step 3: Create `.env.example`**

```
POSTGRES_USER=factory
POSTGRES_PASSWORD=factory_dev_password
POSTGRES_DB=factory_pulse
POSTGRES_HOST=timescaledb
POSTGRES_PORT=5432

REDIS_HOST=redis
REDIS_PORT=6379

OPCUA_ENDPOINT=opc.tcp://simulator:4840
OPCUA_NAMESPACE=urn:factory-pulse:simulator

API_HOST=0.0.0.0
API_PORT=8000

SIMULATOR_TICK_SECONDS=1.0

GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin
```

- [ ] **Step 4: Create placeholder README.md**

```markdown
# Factory Pulse

Real-time telemetry platform for EV battery manufacturing equipment.

**Status:** Under construction (Phase 1a).

See [design spec](docs/superpowers/specs/2026-04-05-factory-pulse-design.md).
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore .env.example README.md docs/
git commit -m "chore: initial repo skeleton"
```

---

### Task 2: Equipment configuration file

**Files:**
- Create: `config/equipment.yaml`

- [ ] **Step 1: Create `config/equipment.yaml`**

```yaml
# Single source of truth for equipment fleet.
# Consumed by simulator (to create OPC-UA nodes) and api-service (seed).
equipment:
  - id: FORM-01
    name: "Formation Cycler #1"
    type: formation_cycler
    location: "Line-A / Bay-1"
    metadata:
      vendor: SimuCorp
      model: FC-2000
      rated_throughput: 150
    metrics: [temperature, voltage, throughput, cycle_count]
    unit_duration_seconds: 1800   # 30 min per cell
    unit_id_prefix: CELL

  - id: FORM-02
    name: "Formation Cycler #2"
    type: formation_cycler
    location: "Line-A / Bay-2"
    metadata:
      vendor: SimuCorp
      model: FC-2000
      rated_throughput: 150
    metrics: [temperature, voltage, throughput, cycle_count]
    unit_duration_seconds: 1800
    unit_id_prefix: CELL

  - id: AGING-01
    name: "Aging Chamber #1"
    type: aging_chamber
    location: "Line-A / Bay-3"
    metadata:
      vendor: SimuCorp
      model: AC-500
      rated_throughput: 300
    metrics: [temperature, throughput]
    unit_duration_seconds: 14400  # 4 hours per batch
    unit_id_prefix: TRAY

  - id: AGING-02
    name: "Aging Chamber #2"
    type: aging_chamber
    location: "Line-A / Bay-4"
    metadata:
      vendor: SimuCorp
      model: AC-500
      rated_throughput: 300
    metrics: [temperature, throughput]
    unit_duration_seconds: 14400
    unit_id_prefix: TRAY

  - id: COAT-01
    name: "Electrode Coater #1"
    type: electrode_coater
    location: "Line-B / Bay-1"
    metadata:
      vendor: SimuCorp
      model: EC-1000
      rated_throughput: 80
    metrics: [temperature, thickness, throughput]
    unit_duration_seconds: 600    # 10 min per roll
    unit_id_prefix: COIL

  - id: CAL-01
    name: "Calendering Machine #1"
    type: calendering_machine
    location: "Line-B / Bay-2"
    metadata:
      vendor: SimuCorp
      model: CM-800
      rated_throughput: 100
    metrics: [pressure, thickness, throughput]
    unit_duration_seconds: 420    # 7 min per roll
    unit_id_prefix: COIL

  - id: ASSY-01
    name: "Cell Assembler #1"
    type: cell_assembler
    location: "Line-C / Bay-1"
    metadata:
      vendor: SimuCorp
      model: CA-3000
      rated_throughput: 200
    metrics: [temperature, throughput, cycle_count]
    unit_duration_seconds: 60     # 1 min per cell
    unit_id_prefix: CELL

  - id: ASSY-02
    name: "Cell Assembler #2"
    type: cell_assembler
    location: "Line-C / Bay-2"
    metadata:
      vendor: SimuCorp
      model: CA-3000
      rated_throughput: 200
    metrics: [temperature, throughput, cycle_count]
    unit_duration_seconds: 60
    unit_id_prefix: CELL
```

- [ ] **Step 2: Commit**

```bash
git add config/equipment.yaml
git commit -m "feat: add equipment fleet config"
```

---

### Task 3: Simulator — pyproject.toml and package skeleton

**Files:**
- Create: `services/simulator/pyproject.toml`
- Create: `services/simulator/src/simulator/__init__.py`

- [ ] **Step 1: Create `services/simulator/pyproject.toml`**

```toml
[project]
name = "factory-pulse-simulator"
version = "0.1.0"
description = "OPC-UA simulator for EV battery manufacturing equipment"
requires-python = ">=3.12"
dependencies = [
    "asyncua>=1.1.5",
    "pyyaml>=6.0",
    "pydantic>=2.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.3",
    "mypy>=1.9",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = true

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Create `services/simulator/src/simulator/__init__.py`**

```python
"""OPC-UA simulator for EV battery manufacturing equipment."""
__version__ = "0.1.0"
```

- [ ] **Step 3: Install dev dependencies locally**

```bash
cd "services/simulator"
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
```

Expected: clean install, no errors.

- [ ] **Step 4: Commit**

```bash
git add services/simulator/pyproject.toml services/simulator/src/simulator/__init__.py
git commit -m "feat(simulator): package skeleton"
```

---

### Task 4: Simulator — state machine (TDD)

**Files:**
- Create: `services/simulator/tests/test_state_machine.py`
- Create: `services/simulator/src/simulator/state_machine.py`

- [ ] **Step 1: Write failing tests**

Create `services/simulator/tests/test_state_machine.py`:

```python
import pytest
from simulator.state_machine import EquipmentState, StateMachine


def test_initial_state_is_idle():
    sm = StateMachine(seed=42)
    assert sm.state == EquipmentState.IDLE


def test_idle_transitions_to_running():
    sm = StateMachine(seed=42)
    sm.transition_to(EquipmentState.RUNNING)
    assert sm.state == EquipmentState.RUNNING


def test_invalid_transition_raises():
    sm = StateMachine(seed=42)
    # idle -> fault is not allowed (must go through running)
    with pytest.raises(ValueError, match="invalid transition"):
        sm.transition_to(EquipmentState.FAULT)


def test_running_can_go_to_fault():
    sm = StateMachine(seed=42)
    sm.transition_to(EquipmentState.RUNNING)
    sm.transition_to(EquipmentState.FAULT)
    assert sm.state == EquipmentState.FAULT


def test_fault_can_go_to_maintenance():
    sm = StateMachine(seed=42)
    sm.transition_to(EquipmentState.RUNNING)
    sm.transition_to(EquipmentState.FAULT)
    sm.transition_to(EquipmentState.MAINTENANCE)
    assert sm.state == EquipmentState.MAINTENANCE


def test_maintenance_returns_to_idle():
    sm = StateMachine(seed=42)
    sm.transition_to(EquipmentState.RUNNING)
    sm.transition_to(EquipmentState.FAULT)
    sm.transition_to(EquipmentState.MAINTENANCE)
    sm.transition_to(EquipmentState.IDLE)
    assert sm.state == EquipmentState.IDLE


def test_auto_tick_eventually_runs():
    # With a deterministic seed, after enough ticks we should be running
    sm = StateMachine(seed=42)
    for _ in range(100):
        sm.tick()
    # Seed 42 should have entered RUNNING at some point
    assert sm.total_transitions > 0


def test_fault_code_set_in_fault_state():
    sm = StateMachine(seed=42)
    sm.transition_to(EquipmentState.RUNNING)
    sm.transition_to(EquipmentState.FAULT)
    assert sm.fault_code is not None
    assert sm.fault_code.startswith("F-")


def test_fault_code_cleared_on_idle():
    sm = StateMachine(seed=42)
    sm.transition_to(EquipmentState.RUNNING)
    sm.transition_to(EquipmentState.FAULT)
    sm.transition_to(EquipmentState.MAINTENANCE)
    sm.transition_to(EquipmentState.IDLE)
    assert sm.fault_code is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "services/simulator"
.venv/Scripts/pytest tests/test_state_machine.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'simulator.state_machine'`.

- [ ] **Step 3: Write the implementation**

Create `services/simulator/src/simulator/state_machine.py`:

```python
"""Equipment state machine: idle -> running -> fault -> maintenance -> idle."""
from __future__ import annotations

import random
from enum import Enum


class EquipmentState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    FAULT = "fault"
    MAINTENANCE = "maintenance"


# Allowed transitions.
_ALLOWED: dict[EquipmentState, set[EquipmentState]] = {
    EquipmentState.IDLE: {EquipmentState.RUNNING},
    EquipmentState.RUNNING: {EquipmentState.FAULT, EquipmentState.IDLE},
    EquipmentState.FAULT: {EquipmentState.MAINTENANCE},
    EquipmentState.MAINTENANCE: {EquipmentState.IDLE},
}

# Per-tick transition probabilities (approximate). Tuned for ~1s ticks.
_TICK_PROBABILITIES: dict[EquipmentState, list[tuple[EquipmentState, float]]] = {
    EquipmentState.IDLE: [(EquipmentState.RUNNING, 0.20)],
    EquipmentState.RUNNING: [
        (EquipmentState.FAULT, 0.002),   # rare
        (EquipmentState.IDLE, 0.005),    # occasional planned stop
    ],
    EquipmentState.FAULT: [(EquipmentState.MAINTENANCE, 0.10)],
    EquipmentState.MAINTENANCE: [(EquipmentState.IDLE, 0.05)],
}

_FAULT_CODES = ["F-001", "F-002", "F-003", "F-TEMP-HIGH", "F-COMM-LOST"]


class StateMachine:
    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)
        self.state: EquipmentState = EquipmentState.IDLE
        self.fault_code: str | None = None
        self.total_transitions: int = 0

    def transition_to(self, new_state: EquipmentState) -> None:
        if new_state not in _ALLOWED[self.state]:
            raise ValueError(
                f"invalid transition: {self.state.value} -> {new_state.value}"
            )
        self.state = new_state
        self.total_transitions += 1
        if new_state == EquipmentState.FAULT:
            self.fault_code = self._rng.choice(_FAULT_CODES)
        elif new_state == EquipmentState.IDLE:
            self.fault_code = None

    def tick(self) -> None:
        """Advance time by one tick, possibly transitioning stochastically."""
        for target, prob in _TICK_PROBABILITIES.get(self.state, []):
            if self._rng.random() < prob:
                self.transition_to(target)
                return
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/pytest tests/test_state_machine.py -v
```

Expected: 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "d:/Dev/Project 1"
git add services/simulator/tests/test_state_machine.py services/simulator/src/simulator/state_machine.py
git commit -m "feat(simulator): equipment state machine"
```

---

### Task 5: Simulator — batch/unit tracker (TDD)

**Files:**
- Create: `services/simulator/tests/test_batch_tracker.py`
- Create: `services/simulator/src/simulator/batch_tracker.py`

- [ ] **Step 1: Write failing tests**

Create `services/simulator/tests/test_batch_tracker.py`:

```python
from datetime import datetime, timezone, timedelta

from simulator.batch_tracker import BatchTracker


def _dt(seconds: int = 0) -> datetime:
    return datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=seconds)


def test_starts_with_initial_batch_and_unit():
    t = BatchTracker(unit_duration_seconds=60, unit_id_prefix="CELL", now=_dt(0))
    assert t.current_batch_id is not None
    assert t.current_unit_id is not None
    assert t.current_unit_id.startswith("CELL-")


def test_advance_before_duration_no_change():
    t = BatchTracker(unit_duration_seconds=60, unit_id_prefix="CELL", now=_dt(0))
    first_unit = t.current_unit_id
    t.advance(_dt(30))
    assert t.current_unit_id == first_unit


def test_advance_past_duration_rotates_unit():
    t = BatchTracker(unit_duration_seconds=60, unit_id_prefix="CELL", now=_dt(0))
    first_unit = t.current_unit_id
    t.advance(_dt(61))
    assert t.current_unit_id != first_unit
    assert t.current_unit_id.startswith("CELL-")


def test_batch_rotates_after_10_units():
    t = BatchTracker(unit_duration_seconds=60, unit_id_prefix="CELL", now=_dt(0))
    first_batch = t.current_batch_id
    for i in range(1, 11):
        t.advance(_dt(i * 61))
    # After 10 unit rotations, batch should have rotated
    assert t.current_batch_id != first_batch


def test_unit_started_at_updated_on_rotation():
    t = BatchTracker(unit_duration_seconds=60, unit_id_prefix="CELL", now=_dt(0))
    t.advance(_dt(61))
    assert t.unit_started_at >= _dt(60)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "services/simulator"
.venv/Scripts/pytest tests/test_batch_tracker.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

Create `services/simulator/src/simulator/batch_tracker.py`:

```python
"""Generate batch_id and unit_id per equipment over time."""
from __future__ import annotations

from datetime import datetime


_UNITS_PER_BATCH = 10


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


class BatchTracker:
    def __init__(
        self,
        unit_duration_seconds: int,
        unit_id_prefix: str,
        now: datetime,
    ) -> None:
        self._unit_duration = unit_duration_seconds
        self._prefix = unit_id_prefix
        self._unit_seq = 0
        self._batch_seq = 0
        self._units_in_current_batch = 0

        self.current_batch_id: str = self._next_batch_id(now)
        self.current_unit_id: str = self._next_unit_id(now)
        self.unit_started_at: datetime = now

    def advance(self, now: datetime) -> None:
        elapsed = (now - self.unit_started_at).total_seconds()
        if elapsed < self._unit_duration:
            return

        # Rotate unit
        self._units_in_current_batch += 1
        if self._units_in_current_batch >= _UNITS_PER_BATCH:
            self.current_batch_id = self._next_batch_id(now)
            self._units_in_current_batch = 0
        self.current_unit_id = self._next_unit_id(now)
        self.unit_started_at = now

    def _next_unit_id(self, now: datetime) -> str:
        self._unit_seq += 1
        return f"{self._prefix}-{_fmt_date(now)}-{self._unit_seq:04d}"

    def _next_batch_id(self, now: datetime) -> str:
        self._batch_seq += 1
        return f"BATCH-{_fmt_date(now)}-{self._batch_seq:03d}"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/pytest tests/test_batch_tracker.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "d:/Dev/Project 1"
git add services/simulator/tests/test_batch_tracker.py services/simulator/src/simulator/batch_tracker.py
git commit -m "feat(simulator): batch/unit id tracker"
```

---

### Task 6: Simulator — equipment config loader (TDD)

**Files:**
- Create: `services/simulator/tests/test_equipment.py`
- Create: `services/simulator/src/simulator/config.py`
- Create: `services/simulator/src/simulator/equipment.py`

- [ ] **Step 1: Write failing tests**

Create `services/simulator/tests/test_equipment.py`:

```python
from pathlib import Path

import pytest

from simulator.config import load_equipment_config, EquipmentConfig


FIXTURE = """
equipment:
  - id: FORM-01
    name: "Formation Cycler #1"
    type: formation_cycler
    location: "Line-A / Bay-1"
    metadata: {vendor: SimuCorp}
    metrics: [temperature, voltage]
    unit_duration_seconds: 1800
    unit_id_prefix: CELL
"""


def test_load_equipment_config(tmp_path: Path):
    p = tmp_path / "equipment.yaml"
    p.write_text(FIXTURE)
    configs = load_equipment_config(p)
    assert len(configs) == 1
    assert configs[0].id == "FORM-01"
    assert configs[0].type == "formation_cycler"
    assert configs[0].metrics == ["temperature", "voltage"]
    assert configs[0].unit_duration_seconds == 1800
    assert configs[0].unit_id_prefix == "CELL"


def test_load_equipment_config_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_equipment_config(tmp_path / "nope.yaml")


def test_equipment_config_round_trip():
    c = EquipmentConfig(
        id="X-01",
        name="Test",
        type="formation_cycler",
        location="A/1",
        metadata={"vendor": "Test"},
        metrics=["temperature"],
        unit_duration_seconds=60,
        unit_id_prefix="CELL",
    )
    assert c.id == "X-01"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "services/simulator"
.venv/Scripts/pytest tests/test_equipment.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write config.py**

Create `services/simulator/src/simulator/config.py`:

```python
"""Load equipment configuration from YAML."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class EquipmentConfig(BaseModel):
    id: str
    name: str
    type: str
    location: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    metrics: list[str]
    unit_duration_seconds: int
    unit_id_prefix: str


def load_equipment_config(path: Path) -> list[EquipmentConfig]:
    if not path.exists():
        raise FileNotFoundError(f"equipment config not found: {path}")
    data = yaml.safe_load(path.read_text())
    return [EquipmentConfig(**item) for item in data["equipment"]]
```

- [ ] **Step 4: Write equipment.py (metric value generation)**

Create `services/simulator/src/simulator/equipment.py`:

```python
"""Equipment model: generates metric values based on type and state."""
from __future__ import annotations

import random
from dataclasses import dataclass

from simulator.state_machine import EquipmentState


@dataclass
class MetricValue:
    name: str
    value: float


# Baseline ranges per metric, per equipment type.
# Format: (mean_running, noise_stddev, idle_value, fault_value)
_METRIC_PROFILES: dict[str, dict[str, tuple[float, float, float, float]]] = {
    "formation_cycler": {
        "temperature": (45.0, 1.5, 22.0, 85.0),
        "voltage": (3.7, 0.05, 0.0, 4.3),
        "throughput": (120.0, 10.0, 0.0, 0.0),
        "cycle_count": (1.0, 0.0, 0.0, 0.0),  # monotonic-ish counter
    },
    "aging_chamber": {
        "temperature": (55.0, 0.8, 25.0, 90.0),
        "throughput": (280.0, 15.0, 0.0, 0.0),
    },
    "electrode_coater": {
        "temperature": (80.0, 2.0, 25.0, 120.0),
        "thickness": (0.15, 0.005, 0.0, 0.0),
        "throughput": (75.0, 5.0, 0.0, 0.0),
    },
    "calendering_machine": {
        "pressure": (250.0, 8.0, 0.0, 350.0),
        "thickness": (0.10, 0.003, 0.0, 0.0),
        "throughput": (95.0, 6.0, 0.0, 0.0),
    },
    "cell_assembler": {
        "temperature": (30.0, 1.0, 22.0, 55.0),
        "throughput": (190.0, 12.0, 0.0, 0.0),
        "cycle_count": (1.0, 0.0, 0.0, 0.0),
    },
}


class EquipmentSimulator:
    def __init__(self, equipment_type: str, metrics: list[str], seed: int) -> None:
        if equipment_type not in _METRIC_PROFILES:
            raise ValueError(f"unknown equipment type: {equipment_type}")
        self._type = equipment_type
        self._metrics = metrics
        self._rng = random.Random(seed)
        self._cycle_count = 0

    def sample(self, state: EquipmentState) -> list[MetricValue]:
        profile = _METRIC_PROFILES[self._type]
        out: list[MetricValue] = []
        for metric in self._metrics:
            if metric not in profile:
                continue
            mean_run, noise, idle_val, fault_val = profile[metric]
            if metric == "cycle_count":
                if state == EquipmentState.RUNNING:
                    self._cycle_count += 1
                out.append(MetricValue(metric, float(self._cycle_count)))
                continue
            if state == EquipmentState.RUNNING:
                v = self._rng.gauss(mean_run, noise)
            elif state == EquipmentState.FAULT:
                v = fault_val if fault_val > 0 else idle_val
            else:
                v = idle_val
            out.append(MetricValue(metric, round(v, 3)))
        return out
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/Scripts/pytest tests/test_equipment.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "d:/Dev/Project 1"
git add services/simulator/tests/test_equipment.py services/simulator/src/simulator/config.py services/simulator/src/simulator/equipment.py
git commit -m "feat(simulator): equipment config loader and metric generator"
```

---

### Task 7: Simulator — OPC-UA server

**Files:**
- Create: `services/simulator/src/simulator/opcua_server.py`
- Create: `services/simulator/src/simulator/main.py`

- [ ] **Step 1: Create `opcua_server.py`**

Create `services/simulator/src/simulator/opcua_server.py`:

```python
"""OPC-UA server exposing equipment nodes."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from asyncua import Server, ua

from simulator.batch_tracker import BatchTracker
from simulator.config import EquipmentConfig
from simulator.equipment import EquipmentSimulator
from simulator.state_machine import EquipmentState, StateMachine

logger = logging.getLogger(__name__)

NAMESPACE_URI = "urn:factory-pulse:simulator"


class EquipmentNode:
    """Holds the OPC-UA node handles for a single piece of equipment."""

    def __init__(
        self,
        config: EquipmentConfig,
        state: StateMachine,
        sim: EquipmentSimulator,
        tracker: BatchTracker,
    ) -> None:
        self.config = config
        self.state = state
        self.sim = sim
        self.tracker = tracker
        # Populated during server setup
        self.status_node: ua.NodeId | None = None
        self.fault_code_node: ua.NodeId | None = None
        self.current_batch_node: ua.NodeId | None = None
        self.current_unit_node: ua.NodeId | None = None
        self.metric_nodes: dict[str, ua.NodeId] = {}


async def build_server(
    endpoint: str, equipment_configs: list[EquipmentConfig]
) -> tuple[Server, list[EquipmentNode]]:
    server = Server()
    await server.init()
    server.set_endpoint(endpoint)
    server.set_server_name("factory-pulse simulator")

    idx = await server.register_namespace(NAMESPACE_URI)

    objects = server.nodes.objects
    factory = await objects.add_object(idx, "Factory")
    equipment_folder = await factory.add_object(idx, "Equipment")

    now = datetime.now(timezone.utc)
    nodes: list[EquipmentNode] = []

    for i, cfg in enumerate(equipment_configs):
        obj = await equipment_folder.add_object(idx, cfg.id)
        status = await obj.add_variable(idx, "Status", "idle", ua.VariantType.String)
        await status.set_writable()
        fault = await obj.add_variable(idx, "FaultCode", "", ua.VariantType.String)
        await fault.set_writable()
        batch = await obj.add_variable(idx, "CurrentBatchId", "", ua.VariantType.String)
        await batch.set_writable()
        unit = await obj.add_variable(idx, "CurrentUnitId", "", ua.VariantType.String)
        await unit.set_writable()

        metric_vars: dict[str, ua.NodeId] = {}
        for metric in cfg.metrics:
            var = await obj.add_variable(idx, metric, 0.0, ua.VariantType.Double)
            await var.set_writable()
            metric_vars[metric] = var

        node = EquipmentNode(
            config=cfg,
            state=StateMachine(seed=hash(cfg.id) & 0xFFFFFFFF),
            sim=EquipmentSimulator(cfg.type, cfg.metrics, seed=i * 7919),
            tracker=BatchTracker(
                unit_duration_seconds=cfg.unit_duration_seconds,
                unit_id_prefix=cfg.unit_id_prefix,
                now=now,
            ),
        )
        node.status_node = status
        node.fault_code_node = fault
        node.current_batch_node = batch
        node.current_unit_node = unit
        node.metric_nodes = metric_vars
        nodes.append(node)

    return server, nodes


async def tick_equipment(node: EquipmentNode, now: datetime) -> None:
    node.state.tick()
    node.tracker.advance(now)
    samples = node.sim.sample(node.state.state)

    await node.status_node.write_value(node.state.state.value)  # type: ignore[union-attr]
    await node.fault_code_node.write_value(node.state.fault_code or "")  # type: ignore[union-attr]
    await node.current_batch_node.write_value(node.tracker.current_batch_id)  # type: ignore[union-attr]
    await node.current_unit_node.write_value(node.tracker.current_unit_id)  # type: ignore[union-attr]
    for s in samples:
        var = node.metric_nodes.get(s.name)
        if var is not None:
            await var.write_value(s.value)
```

- [ ] **Step 2: Create `main.py` entry point**

Create `services/simulator/src/simulator/main.py`:

```python
"""Simulator entry point."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from simulator.config import load_equipment_config
from simulator.opcua_server import build_server, tick_equipment

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("simulator")


async def run() -> None:
    endpoint = os.environ.get("OPCUA_ENDPOINT", "opc.tcp://0.0.0.0:4840")
    tick_seconds = float(os.environ.get("SIMULATOR_TICK_SECONDS", "1.0"))
    config_path = Path(os.environ.get("EQUIPMENT_CONFIG", "/config/equipment.yaml"))

    configs = load_equipment_config(config_path)
    logger.info("loaded %d equipment configs", len(configs))

    server, nodes = await build_server(endpoint, configs)
    logger.info("starting OPC-UA server on %s", endpoint)
    async with server:
        while True:
            now = datetime.now(timezone.utc)
            for node in nodes:
                try:
                    await tick_equipment(node, now)
                except Exception:
                    logger.exception("tick failed for %s", node.config.id)
            await asyncio.sleep(tick_seconds)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify it starts (smoke test)**

```bash
cd "services/simulator"
EQUIPMENT_CONFIG="../../config/equipment.yaml" OPCUA_ENDPOINT="opc.tcp://0.0.0.0:4840" .venv/Scripts/python -m simulator.main
```

Expected: log shows "loaded 8 equipment configs" and "starting OPC-UA server". Ctrl+C to stop after ~5 seconds.

- [ ] **Step 4: Commit**

```bash
cd "d:/Dev/Project 1"
git add services/simulator/src/simulator/opcua_server.py services/simulator/src/simulator/main.py
git commit -m "feat(simulator): OPC-UA server with equipment ticking"
```

---

### Task 8: Simulator — Dockerfile

**Files:**
- Create: `services/simulator/Dockerfile`

- [ ] **Step 1: Create `services/simulator/Dockerfile`**

```dockerfile
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
```

- [ ] **Step 2: Build image**

```bash
cd "d:/Dev/Project 1"
docker build -t factory-pulse-simulator services/simulator
```

Expected: image builds without errors.

- [ ] **Step 3: Commit**

```bash
git add services/simulator/Dockerfile
git commit -m "chore(simulator): add Dockerfile"
```

---

### Task 9: TimescaleDB schema — Alembic migration

**Files:**
- Create: `services/api/pyproject.toml`
- Create: `services/api/alembic.ini`
- Create: `services/api/alembic/env.py`
- Create: `services/api/alembic/versions/0001_initial_schema.py`
- Create: `services/api/src/api/__init__.py`

- [ ] **Step 1: Create `services/api/pyproject.toml`**

```toml
[project]
name = "factory-pulse-api"
version = "0.1.0"
description = "REST + WebSocket API for factory-pulse"
requires-python = ">=3.12"
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
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
    "ruff>=0.3",
    "mypy>=1.9",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = true

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Create `services/api/src/api/__init__.py`**

```python
"""Factory Pulse API service."""
__version__ = "0.1.0"
```

- [ ] **Step 3: Install dev dependencies**

```bash
cd "services/api"
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
```

- [ ] **Step 4: Create `services/api/alembic.ini`**

```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql://factory:factory_dev_password@localhost:5432/factory_pulse

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 5: Create `services/api/alembic/env.py`**

```python
"""Alembic environment. Reads URL from env var POSTGRES_URL when available."""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _url() -> str:
    env_url = os.environ.get("POSTGRES_URL")
    if env_url:
        return env_url
    user = os.environ.get("POSTGRES_USER", "factory")
    pw = os.environ.get("POSTGRES_PASSWORD", "factory_dev_password")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "factory_pulse")
    return f"postgresql://{user}:{pw}@{host}:{port}/{db}"


def run_migrations_online() -> None:
    cfg_section = config.get_section(config.config_ini_section) or {}
    cfg_section["sqlalchemy.url"] = _url()
    connectable = engine_from_config(
        cfg_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
```

- [ ] **Step 6: Create the initial migration `services/api/alembic/versions/0001_initial_schema.py`**

```python
"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-05
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")

    op.execute(
        """
        CREATE TABLE equipment (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            location TEXT NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute("CREATE INDEX idx_equipment_type ON equipment(type);")

    op.execute(
        """
        CREATE TABLE telemetry (
            time TIMESTAMPTZ NOT NULL,
            equipment_id TEXT NOT NULL REFERENCES equipment(id),
            metric_name TEXT NOT NULL,
            value DOUBLE PRECISION NOT NULL,
            status TEXT,
            batch_id TEXT,
            unit_id TEXT,
            PRIMARY KEY (time, equipment_id, metric_name)
        );
        """
    )
    op.execute(
        "SELECT create_hypertable('telemetry', 'time', "
        "chunk_time_interval => INTERVAL '1 day');"
    )
    op.execute(
        "CREATE INDEX idx_telemetry_equipment_time "
        "ON telemetry(equipment_id, time DESC);"
    )
    op.execute(
        "CREATE INDEX idx_telemetry_batch ON telemetry(batch_id, time DESC) "
        "WHERE batch_id IS NOT NULL;"
    )
    op.execute(
        "CREATE INDEX idx_telemetry_unit ON telemetry(unit_id, time DESC) "
        "WHERE unit_id IS NOT NULL;"
    )

    op.execute(
        """
        CREATE MATERIALIZED VIEW telemetry_1min
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 minute', time) AS bucket,
            equipment_id,
            metric_name,
            AVG(value) AS avg_value,
            MIN(value) AS min_value,
            MAX(value) AS max_value,
            COUNT(*) AS sample_count
        FROM telemetry
        GROUP BY bucket, equipment_id, metric_name
        WITH NO DATA;
        """
    )
    op.execute(
        "SELECT add_continuous_aggregate_policy('telemetry_1min', "
        "start_offset => INTERVAL '2 hours', "
        "end_offset => INTERVAL '1 minute', "
        "schedule_interval => INTERVAL '30 seconds');"
    )

    op.execute(
        """
        CREATE MATERIALIZED VIEW telemetry_1hour
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', time) AS bucket,
            equipment_id,
            metric_name,
            AVG(value) AS avg_value,
            MIN(value) AS min_value,
            MAX(value) AS max_value,
            COUNT(*) AS sample_count
        FROM telemetry
        GROUP BY bucket, equipment_id, metric_name
        WITH NO DATA;
        """
    )
    op.execute(
        "SELECT add_continuous_aggregate_policy('telemetry_1hour', "
        "start_offset => INTERVAL '2 days', "
        "end_offset => INTERVAL '1 hour', "
        "schedule_interval => INTERVAL '5 minutes');"
    )

    op.execute(
        "ALTER TABLE telemetry SET ("
        "timescaledb.compress, "
        "timescaledb.compress_segmentby = 'equipment_id, metric_name');"
    )
    op.execute("SELECT add_compression_policy('telemetry', INTERVAL '7 days');")
    op.execute("SELECT add_retention_policy('telemetry', INTERVAL '30 days');")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_1hour;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_1min;")
    op.execute("DROP TABLE IF EXISTS telemetry;")
    op.execute("DROP TABLE IF EXISTS equipment;")
```

- [ ] **Step 7: Commit**

```bash
cd "d:/Dev/Project 1"
git add services/api/pyproject.toml services/api/alembic.ini services/api/alembic/env.py services/api/alembic/versions/0001_initial_schema.py services/api/src/api/__init__.py
git commit -m "feat(api): initial TimescaleDB schema migration"
```

---

### Task 10: Docker Compose baseline (TimescaleDB + Redis)

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
services:
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-factory}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-factory_dev_password}
      POSTGRES_DB: ${POSTGRES_DB:-factory_pulse}
    ports:
      - "5432:5432"
    volumes:
      - timescaledb_data:/var/lib/postgresql/data
    command:
      - "postgres"
      - "-c"
      - "shared_buffers=256MB"
      - "-c"
      - "work_mem=16MB"
      - "-c"
      - "max_connections=50"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  timescaledb_data:
```

- [ ] **Step 2: Start the stack**

```bash
cd "d:/Dev/Project 1"
docker compose up -d timescaledb redis
```

Expected: both containers start. Check `docker compose ps`.

- [ ] **Step 3: Verify TimescaleDB is up**

```bash
docker compose exec timescaledb psql -U factory -d factory_pulse -c "SELECT extversion FROM pg_extension WHERE extname='timescaledb';"
```

Expected: non-empty version row returned (e.g., `2.14.2`).

- [ ] **Step 4: Run migration from host**

```bash
cd "services/api"
POSTGRES_HOST=localhost .venv/Scripts/alembic upgrade head
```

Expected: migration runs, prints `Running upgrade -> 0001`.

- [ ] **Step 5: Verify tables**

```bash
cd "d:/Dev/Project 1"
docker compose exec timescaledb psql -U factory -d factory_pulse -c "\dt"
```

Expected: `equipment` and `telemetry` tables listed.

```bash
docker compose exec timescaledb psql -U factory -d factory_pulse -c "SELECT hypertable_name FROM timescaledb_information.hypertables;"
```

Expected: `telemetry` row returned.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: docker-compose with timescaledb and redis"
```

---

### Task 11: API — equipment seed loader

**Files:**
- Create: `services/api/src/api/config.py`
- Create: `services/api/src/api/db.py`
- Create: `services/api/src/api/seed.py`
- Create: `services/api/tests/test_seed.py`

- [ ] **Step 1: Write failing test**

Create `services/api/tests/test_seed.py`:

```python
from pathlib import Path

from api.seed import parse_equipment_yaml

FIXTURE = """
equipment:
  - id: X-01
    name: "Test"
    type: formation_cycler
    location: "A/1"
    metadata: {vendor: Test}
    metrics: [temperature]
    unit_duration_seconds: 60
    unit_id_prefix: CELL
  - id: X-02
    name: "Test 2"
    type: aging_chamber
    location: "A/2"
    metadata: {}
    metrics: [temperature]
    unit_duration_seconds: 3600
    unit_id_prefix: TRAY
"""


def test_parse_equipment_yaml(tmp_path: Path):
    p = tmp_path / "equipment.yaml"
    p.write_text(FIXTURE)
    rows = parse_equipment_yaml(p)
    assert len(rows) == 2
    assert rows[0]["id"] == "X-01"
    assert rows[0]["type"] == "formation_cycler"
    assert rows[0]["metadata"] == {"vendor": "Test"}
    assert rows[1]["id"] == "X-02"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "services/api"
.venv/Scripts/pytest tests/test_seed.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `config.py`**

Create `services/api/src/api/config.py`:

```python
"""API service configuration from env."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    postgres_user: str = "factory"
    postgres_password: str = "factory_dev_password"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "factory_pulse"

    redis_host: str = "localhost"
    redis_port: int = 6379

    equipment_config_path: str = "/config/equipment.yaml"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"


settings = Settings()
```

- [ ] **Step 4: Create `db.py`**

Create `services/api/src/api/db.py`:

```python
"""asyncpg connection pool."""
from __future__ import annotations

import asyncpg

from api.config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            user=settings.postgres_user,
            password=settings.postgres_password,
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            min_size=2,
            max_size=10,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
```

- [ ] **Step 5: Create `seed.py`**

Create `services/api/src/api/seed.py`:

```python
"""Seed equipment table from equipment.yaml."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import asyncpg
import yaml

logger = logging.getLogger(__name__)


def parse_equipment_yaml(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text())
    return [
        {
            "id": item["id"],
            "name": item["name"],
            "type": item["type"],
            "location": item["location"],
            "metadata": item.get("metadata", {}),
        }
        for item in data["equipment"]
    ]


async def seed_equipment(pool: asyncpg.Pool, path: Path) -> int:
    rows = parse_equipment_yaml(path)
    async with pool.acquire() as conn:
        for row in rows:
            await conn.execute(
                """
                INSERT INTO equipment (id, name, type, location, metadata)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    type = EXCLUDED.type,
                    location = EXCLUDED.location,
                    metadata = EXCLUDED.metadata;
                """,
                row["id"],
                row["name"],
                row["type"],
                row["location"],
                json.dumps(row["metadata"]),
            )
    logger.info("seeded %d equipment rows", len(rows))
    return len(rows)
```

- [ ] **Step 6: Run test to verify it passes**

```bash
.venv/Scripts/pytest tests/test_seed.py -v
```

Expected: 1 test PASS.

- [ ] **Step 7: Commit**

```bash
cd "d:/Dev/Project 1"
git add services/api/src/api/config.py services/api/src/api/db.py services/api/src/api/seed.py services/api/tests/test_seed.py
git commit -m "feat(api): equipment seed loader and db pool"
```

---

### Task 12: API — query router (TDD)

**Files:**
- Create: `services/api/tests/test_query_router.py`
- Create: `services/api/src/api/query_router.py`

- [ ] **Step 1: Write failing tests**

Create `services/api/tests/test_query_router.py`:

```python
from datetime import datetime, timezone, timedelta

import pytest

from api.query_router import Interval, select_interval, validate_range


def _dt(offset_seconds: int) -> datetime:
    return datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc) + timedelta(
        seconds=offset_seconds
    )


def test_short_range_uses_raw():
    frm = _dt(0)
    to = _dt(1800)  # 30 min
    assert select_interval(frm, to) == Interval.RAW


def test_medium_range_uses_1min():
    frm = _dt(0)
    to = _dt(7200)  # 2 hours
    assert select_interval(frm, to) == Interval.MIN_1


def test_long_range_uses_1hour():
    frm = _dt(0)
    to = _dt(60 * 60 * 24 * 10)  # 10 days
    assert select_interval(frm, to) == Interval.HOUR_1


def test_boundary_exactly_1_hour_uses_1min():
    frm = _dt(0)
    to = _dt(3600)  # exactly 1 hour
    assert select_interval(frm, to) == Interval.MIN_1


def test_boundary_exactly_7_days_uses_1min():
    frm = _dt(0)
    to = _dt(7 * 24 * 3600)  # exactly 7 days
    assert select_interval(frm, to) == Interval.MIN_1


def test_validate_range_rejects_inverted():
    with pytest.raises(ValueError, match="from must be before to"):
        validate_range(_dt(100), _dt(0))


def test_validate_range_rejects_too_long():
    with pytest.raises(ValueError, match="range too large"):
        validate_range(_dt(0), _dt(60 * 60 * 24 * 100))  # 100 days


def test_validate_range_accepts_valid():
    validate_range(_dt(0), _dt(3600))  # no exception
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "services/api"
.venv/Scripts/pytest tests/test_query_router.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `query_router.py`**

Create `services/api/src/api/query_router.py`:

```python
"""Select raw / 1-min / 1-hour table based on time range."""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

MAX_RANGE_DAYS = 90


class Interval(str, Enum):
    RAW = "raw"
    MIN_1 = "1min"
    HOUR_1 = "1hour"


def select_interval(frm: datetime, to: datetime) -> Interval:
    span = to - frm
    if span < timedelta(hours=1):
        return Interval.RAW
    if span <= timedelta(days=7):
        return Interval.MIN_1
    return Interval.HOUR_1


def validate_range(frm: datetime, to: datetime) -> None:
    if frm >= to:
        raise ValueError("from must be before to")
    if to - frm > timedelta(days=MAX_RANGE_DAYS):
        raise ValueError(f"range too large (max {MAX_RANGE_DAYS} days)")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/pytest tests/test_query_router.py -v
```

Expected: 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "d:/Dev/Project 1"
git add services/api/tests/test_query_router.py services/api/src/api/query_router.py
git commit -m "feat(api): time-range query router"
```

---

### Task 13: API — Redis client

**Files:**
- Create: `services/api/src/api/redis_client.py`

- [ ] **Step 1: Create `redis_client.py`**

Create `services/api/src/api/redis_client.py`:

```python
"""Redis async client (shared instance)."""
from __future__ import annotations

import redis.asyncio as redis

from api.config import settings

_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
```

- [ ] **Step 2: Commit**

```bash
git add services/api/src/api/redis_client.py
git commit -m "feat(api): redis async client"
```

---

### Task 14: API — FastAPI app + health route

**Files:**
- Create: `services/api/src/api/routes/__init__.py`
- Create: `services/api/src/api/routes/health.py`
- Create: `services/api/src/api/main.py`

- [ ] **Step 1: Create `routes/__init__.py` (empty)**

```python
```

- [ ] **Step 2: Create `routes/health.py`**

Create `services/api/src/api/routes/health.py`:

```python
"""Health endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Response
from fastapi import status as http_status

from api.db import get_pool
from api.redis_client import get_client

router = APIRouter()


@router.get("/health")
async def health(response: Response) -> dict:
    deps: dict[str, str] = {}
    all_ok = True

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        deps["timescaledb"] = "ok"
    except Exception:
        deps["timescaledb"] = "error"
        all_ok = False

    try:
        client = get_client()
        await client.ping()
        deps["redis"] = "ok"
    except Exception:
        deps["redis"] = "error"
        all_ok = False

    if not all_ok:
        response.status_code = http_status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "healthy" if all_ok else "degraded",
        "dependencies": deps,
        "version": "0.1.0",
    }
```

- [ ] **Step 3: Create `main.py`**

Create `services/api/src/api/main.py`:

```python
"""FastAPI app entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from api.config import settings
from api.db import close_pool, get_pool
from api.redis_client import close_client
from api.routes.health import router as health_router
from api.seed import seed_equipment

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await get_pool()
    try:
        await seed_equipment(pool, Path(settings.equipment_config_path))
    except FileNotFoundError:
        logger.warning("equipment config not found at %s; skipping seed", settings.equipment_config_path)
    yield
    await close_pool()
    await close_client()


app = FastAPI(title="Factory Pulse API", version="0.1.0", lifespan=lifespan)
app.include_router(health_router, prefix="/api")
```

- [ ] **Step 4: Verify it starts**

```bash
cd "services/api"
POSTGRES_HOST=localhost REDIS_HOST=localhost EQUIPMENT_CONFIG_PATH="../../config/equipment.yaml" .venv/Scripts/uvicorn api.main:app --port 8000
```

In another terminal:
```bash
curl http://localhost:8000/api/health
```

Expected: `{"status":"healthy","dependencies":{"timescaledb":"ok","redis":"ok"},"version":"0.1.0"}`.

Stop uvicorn with Ctrl+C.

- [ ] **Step 5: Verify seed worked**

```bash
cd "d:/Dev/Project 1"
docker compose exec timescaledb psql -U factory -d factory_pulse -c "SELECT id, name FROM equipment ORDER BY id;"
```

Expected: 8 rows listed.

- [ ] **Step 6: Commit**

```bash
git add services/api/src/api/routes/__init__.py services/api/src/api/routes/health.py services/api/src/api/main.py
git commit -m "feat(api): FastAPI app with health endpoint and seed on startup"
```

---

### Task 15: Ingest service — pyproject + batch buffer (TDD)

**Files:**
- Create: `services/ingest/pyproject.toml`
- Create: `services/ingest/src/ingest/__init__.py`
- Create: `services/ingest/tests/test_batch_buffer.py`
- Create: `services/ingest/src/ingest/batch_buffer.py`

- [ ] **Step 1: Create `services/ingest/pyproject.toml`**

```toml
[project]
name = "factory-pulse-ingest"
version = "0.1.0"
description = "OPC-UA ingest to TimescaleDB + Redis"
requires-python = ">=3.12"
dependencies = [
    "asyncua>=1.1.5",
    "asyncpg>=0.29",
    "redis>=5.0",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.3",
    "mypy>=1.9",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = true

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Create `services/ingest/src/ingest/__init__.py`**

```python
"""Factory Pulse ingest service."""
__version__ = "0.1.0"
```

- [ ] **Step 3: Install dev deps**

```bash
cd "services/ingest"
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
```

- [ ] **Step 4: Write failing tests**

Create `services/ingest/tests/test_batch_buffer.py`:

```python
from datetime import datetime, timezone, timedelta

from ingest.batch_buffer import BatchBuffer, Sample


def _s(t: int) -> Sample:
    return Sample(
        time=datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=t),
        equipment_id="E-01",
        metric_name="temperature",
        value=45.0,
        status="running",
        batch_id="B-1",
        unit_id="U-1",
    )


def test_buffer_starts_empty():
    b = BatchBuffer(max_size=10, max_age_seconds=1.0)
    assert len(b) == 0
    assert not b.should_flush(now=_s(0).time)


def test_flush_on_size():
    b = BatchBuffer(max_size=3, max_age_seconds=10.0)
    for i in range(3):
        b.add(_s(i))
    assert b.should_flush(now=_s(0).time)


def test_flush_on_age():
    b = BatchBuffer(max_size=100, max_age_seconds=1.0)
    b.add(_s(0))
    # Same time: no flush
    assert not b.should_flush(now=_s(0).time)
    # 2 seconds later: flush
    assert b.should_flush(now=_s(2).time)


def test_drain_returns_and_clears():
    b = BatchBuffer(max_size=10, max_age_seconds=10.0)
    b.add(_s(0))
    b.add(_s(1))
    drained = b.drain()
    assert len(drained) == 2
    assert len(b) == 0


def test_bounded_drops_oldest_when_overflow():
    b = BatchBuffer(max_size=3, max_age_seconds=10.0, overflow_limit=5)
    for i in range(7):
        b.add(_s(i))
    assert len(b) == 5  # capped at overflow_limit
    drained = b.drain()
    # Oldest 2 should have been dropped
    assert drained[0].time == _s(2).time
```

- [ ] **Step 5: Run tests to verify they fail**

```bash
cd "services/ingest"
.venv/Scripts/pytest tests/test_batch_buffer.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 6: Write implementation**

Create `services/ingest/src/ingest/batch_buffer.py`:

```python
"""Buffered telemetry samples, flushed on size or age."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class Sample:
    time: datetime
    equipment_id: str
    metric_name: str
    value: float
    status: str | None
    batch_id: str | None
    unit_id: str | None


class BatchBuffer:
    def __init__(
        self,
        max_size: int,
        max_age_seconds: float,
        overflow_limit: int | None = None,
    ) -> None:
        self._max_size = max_size
        self._max_age = timedelta(seconds=max_age_seconds)
        self._overflow_limit = overflow_limit or (max_size * 100)
        self._buf: deque[Sample] = deque()
        self._oldest_time: datetime | None = None

    def add(self, sample: Sample) -> None:
        if self._oldest_time is None:
            self._oldest_time = sample.time
        self._buf.append(sample)
        while len(self._buf) > self._overflow_limit:
            self._buf.popleft()
            self._oldest_time = self._buf[0].time if self._buf else None

    def should_flush(self, now: datetime) -> bool:
        if len(self._buf) == 0:
            return False
        if len(self._buf) >= self._max_size:
            return True
        if self._oldest_time is not None and (now - self._oldest_time) >= self._max_age:
            return True
        return False

    def drain(self) -> list[Sample]:
        out = list(self._buf)
        self._buf.clear()
        self._oldest_time = None
        return out

    def __len__(self) -> int:
        return len(self._buf)
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
.venv/Scripts/pytest tests/test_batch_buffer.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 8: Commit**

```bash
cd "d:/Dev/Project 1"
git add services/ingest/pyproject.toml services/ingest/src/ingest/__init__.py services/ingest/src/ingest/batch_buffer.py services/ingest/tests/test_batch_buffer.py
git commit -m "feat(ingest): batch buffer with size/age flushing"
```

---

### Task 16: Ingest service — DB writer

**Files:**
- Create: `services/ingest/src/ingest/config.py`
- Create: `services/ingest/src/ingest/db_writer.py`

- [ ] **Step 1: Create `config.py`**

Create `services/ingest/src/ingest/config.py`:

```python
"""Ingest service config."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    postgres_user: str = "factory"
    postgres_password: str = "factory_dev_password"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "factory_pulse"

    redis_host: str = "localhost"
    redis_port: int = 6379

    opcua_endpoint: str = "opc.tcp://localhost:4840"
    opcua_namespace: str = "urn:factory-pulse:simulator"

    batch_max_size: int = 100
    batch_max_age_seconds: float = 1.0
    batch_overflow_limit: int = 10000

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"


settings = Settings()
```

- [ ] **Step 2: Create `db_writer.py`**

Create `services/ingest/src/ingest/db_writer.py`:

```python
"""Write batches to TimescaleDB."""
from __future__ import annotations

import logging

import asyncpg

from ingest.batch_buffer import Sample

logger = logging.getLogger(__name__)


class DbWriter:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def write_batch(self, samples: list[Sample]) -> None:
        if not samples:
            return
        rows = [
            (s.time, s.equipment_id, s.metric_name, s.value, s.status, s.batch_id, s.unit_id)
            for s in samples
        ]
        async with self._pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO telemetry (time, equipment_id, metric_name, value, status, batch_id, unit_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (time, equipment_id, metric_name) DO NOTHING
                """,
                rows,
            )
```

- [ ] **Step 3: Commit**

```bash
git add services/ingest/src/ingest/config.py services/ingest/src/ingest/db_writer.py
git commit -m "feat(ingest): db writer with batch insert"
```

---

### Task 17: Ingest service — Redis publisher

**Files:**
- Create: `services/ingest/tests/test_redis_publisher.py`
- Create: `services/ingest/src/ingest/redis_publisher.py`

- [ ] **Step 1: Write failing tests**

Create `services/ingest/tests/test_redis_publisher.py`:

```python
from datetime import datetime, timezone

from ingest.redis_publisher import build_publish_payload, build_hot_cache_fields


def test_build_publish_payload():
    t = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
    payload = build_publish_payload(
        equipment_id="E-01",
        time=t,
        status="running",
        batch_id="B-1",
        unit_id="U-1",
        metrics={"temperature": 45.2, "voltage": 3.7},
    )
    assert payload["equipment_id"] == "E-01"
    assert payload["time"] == "2026-04-05T12:00:00+00:00"
    assert payload["status"] == "running"
    assert payload["batch_id"] == "B-1"
    assert payload["unit_id"] == "U-1"
    assert payload["metrics"]["temperature"] == 45.2


def test_build_hot_cache_fields():
    t = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
    fields = build_hot_cache_fields(
        status="running",
        batch_id="B-1",
        unit_id="U-1",
        unit_started_at=t,
        metrics={"temperature": 45.2},
        updated_at=t,
    )
    assert fields["status"] == "running"
    assert fields["current_batch_id"] == "B-1"
    assert fields["current_unit_id"] == "U-1"
    assert fields["unit_started_at"] == "2026-04-05T12:00:00+00:00"
    assert fields["temperature"] == "45.2"
    assert fields["updated_at"] == "2026-04-05T12:00:00+00:00"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "services/ingest"
.venv/Scripts/pytest tests/test_redis_publisher.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `redis_publisher.py`**

Create `services/ingest/src/ingest/redis_publisher.py`:

```python
"""Publish telemetry events + update hot cache."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)

HOT_CACHE_TTL_SECONDS = 300


def build_publish_payload(
    *,
    equipment_id: str,
    time: datetime,
    status: str | None,
    batch_id: str | None,
    unit_id: str | None,
    metrics: dict[str, float],
) -> dict[str, Any]:
    return {
        "equipment_id": equipment_id,
        "time": time.isoformat(),
        "status": status,
        "batch_id": batch_id,
        "unit_id": unit_id,
        "metrics": metrics,
    }


def build_hot_cache_fields(
    *,
    status: str | None,
    batch_id: str | None,
    unit_id: str | None,
    unit_started_at: datetime | None,
    metrics: dict[str, float],
    updated_at: datetime,
) -> dict[str, str]:
    fields: dict[str, str] = {"updated_at": updated_at.isoformat()}
    if status is not None:
        fields["status"] = status
    if batch_id is not None:
        fields["current_batch_id"] = batch_id
    if unit_id is not None:
        fields["current_unit_id"] = unit_id
    if unit_started_at is not None:
        fields["unit_started_at"] = unit_started_at.isoformat()
    for name, value in metrics.items():
        fields[name] = str(value)
    return fields


class RedisPublisher:
    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    async def publish(self, equipment_id: str, payload: dict[str, Any]) -> None:
        channel = f"telemetry:{equipment_id}"
        try:
            await self._client.publish(channel, json.dumps(payload))
        except Exception:
            logger.warning("redis publish failed for %s", equipment_id, exc_info=True)

    async def update_hot_cache(self, equipment_id: str, fields: dict[str, str]) -> None:
        key = f"equipment:latest:{equipment_id}"
        try:
            await self._client.hset(key, mapping=fields)
            await self._client.expire(key, HOT_CACHE_TTL_SECONDS)
        except Exception:
            logger.warning("redis hot cache update failed for %s", equipment_id, exc_info=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/pytest tests/test_redis_publisher.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "d:/Dev/Project 1"
git add services/ingest/tests/test_redis_publisher.py services/ingest/src/ingest/redis_publisher.py
git commit -m "feat(ingest): redis publisher and hot cache updater"
```

---

### Task 18: Ingest service — OPC-UA client + main loop

**Files:**
- Create: `services/ingest/src/ingest/opcua_client.py`
- Create: `services/ingest/src/ingest/main.py`

- [ ] **Step 1: Create `opcua_client.py`**

Create `services/ingest/src/ingest/opcua_client.py`:

```python
"""OPC-UA client: browse equipment and subscribe to nodes."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from asyncua import Client, Node, ua

logger = logging.getLogger(__name__)


@dataclass
class EquipmentState:
    equipment_id: str
    status: str | None = None
    batch_id: str | None = None
    unit_id: str | None = None
    metrics: dict[str, float] | None = None


# Fixed names (not metrics) exposed on each equipment object.
_META_NODES = {"Status", "FaultCode", "CurrentBatchId", "CurrentUnitId"}


class _SubHandler:
    """asyncua subscription handler."""

    def __init__(
        self,
        node_index: dict[str, tuple[str, str]],
        state: dict[str, EquipmentState],
        on_update: Callable[[str], None],
    ) -> None:
        # node_index: node_id_str -> (equipment_id, field_name)
        self._idx = node_index
        self._state = state
        self._on_update = on_update

    def datachange_notification(self, node: Node, val, data) -> None:
        key = node.nodeid.to_string()
        entry = self._idx.get(key)
        if entry is None:
            return
        equipment_id, field = entry
        st = self._state.setdefault(equipment_id, EquipmentState(equipment_id=equipment_id))
        if field == "Status":
            st.status = val if val else None
        elif field == "CurrentBatchId":
            st.batch_id = val if val else None
        elif field == "CurrentUnitId":
            st.unit_id = val if val else None
        elif field == "FaultCode":
            pass  # Could propagate if desired later
        else:
            # It's a metric
            if st.metrics is None:
                st.metrics = {}
            try:
                st.metrics[field] = float(val)
            except (TypeError, ValueError):
                return
        self._on_update(equipment_id)


async def connect_and_subscribe(
    endpoint: str,
    on_update: Callable[[str, EquipmentState, datetime], None],
    state_store: dict[str, EquipmentState],
) -> Client:
    """Connect, browse equipment, subscribe to all nodes. Returns live client."""
    client = Client(url=endpoint)
    await client.connect()
    logger.info("connected to OPC-UA %s", endpoint)

    factory = await client.nodes.objects.get_child(["0:Factory"])
    equipment_folder = await factory.get_child(["0:Equipment"])
    equipment_objs = await equipment_folder.get_children()

    node_index: dict[str, tuple[str, str]] = {}
    variables_to_subscribe: list[Node] = []

    for obj in equipment_objs:
        qname = await obj.read_browse_name()
        equipment_id = qname.Name
        children = await obj.get_children()
        for child in children:
            cname = (await child.read_browse_name()).Name
            node_index[child.nodeid.to_string()] = (equipment_id, cname)
            variables_to_subscribe.append(child)

    logger.info("subscribing to %d nodes across %d equipment", len(variables_to_subscribe), len(equipment_objs))

    def _trigger(equipment_id: str) -> None:
        st = state_store.get(equipment_id)
        if st is None:
            return
        on_update(equipment_id, st, datetime.now(timezone.utc))

    handler = _SubHandler(node_index, state_store, _trigger)
    sub = await client.create_subscription(1000, handler)  # 1s publish interval
    await sub.subscribe_data_change(variables_to_subscribe)
    return client
```

- [ ] **Step 2: Create `main.py`**

Create `services/ingest/src/ingest/main.py`:

```python
"""Ingest service entry point."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as redis

from ingest.batch_buffer import BatchBuffer, Sample
from ingest.config import settings
from ingest.db_writer import DbWriter
from ingest.opcua_client import EquipmentState, connect_and_subscribe
from ingest.redis_publisher import (
    RedisPublisher,
    build_hot_cache_fields,
    build_publish_payload,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ingest")


async def _connect_db_with_retry() -> asyncpg.Pool:
    delay = 1.0
    while True:
        try:
            return await asyncpg.create_pool(
                dsn=settings.postgres_dsn, min_size=1, max_size=5
            )
        except Exception:
            logger.warning("postgres connect failed, retrying in %.1fs", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60.0)


async def _connect_opcua_with_retry(on_update, state_store):
    delay = 1.0
    while True:
        try:
            return await connect_and_subscribe(
                settings.opcua_endpoint, on_update, state_store
            )
        except Exception:
            logger.warning("opcua connect failed, retrying in %.1fs", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60.0)


async def run() -> None:
    pool = await _connect_db_with_retry()
    db_writer = DbWriter(pool)

    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    publisher = RedisPublisher(redis_client)

    buffer = BatchBuffer(
        max_size=settings.batch_max_size,
        max_age_seconds=settings.batch_max_age_seconds,
        overflow_limit=settings.batch_overflow_limit,
    )

    # Track unit_started_at per equipment (derived from batch/unit changes).
    last_unit: dict[str, tuple[str | None, datetime]] = {}

    def on_update(equipment_id: str, st: EquipmentState, now: datetime) -> None:
        if st.metrics is None:
            return
        prev = last_unit.get(equipment_id)
        if prev is None or prev[0] != st.unit_id:
            last_unit[equipment_id] = (st.unit_id, now)
        unit_started_at = last_unit[equipment_id][1]

        for metric_name, value in st.metrics.items():
            buffer.add(
                Sample(
                    time=now,
                    equipment_id=equipment_id,
                    metric_name=metric_name,
                    value=value,
                    status=st.status,
                    batch_id=st.batch_id,
                    unit_id=st.unit_id,
                )
            )

        payload = build_publish_payload(
            equipment_id=equipment_id,
            time=now,
            status=st.status,
            batch_id=st.batch_id,
            unit_id=st.unit_id,
            metrics=dict(st.metrics),
        )
        fields = build_hot_cache_fields(
            status=st.status,
            batch_id=st.batch_id,
            unit_id=st.unit_id,
            unit_started_at=unit_started_at,
            metrics=dict(st.metrics),
            updated_at=now,
        )
        asyncio.create_task(publisher.publish(equipment_id, payload))
        asyncio.create_task(publisher.update_hot_cache(equipment_id, fields))

    state_store: dict[str, EquipmentState] = {}
    opcua_client = await _connect_opcua_with_retry(on_update, state_store)

    try:
        while True:
            now = datetime.now(timezone.utc)
            if buffer.should_flush(now):
                batch = buffer.drain()
                try:
                    await db_writer.write_batch(batch)
                except Exception:
                    logger.exception("db write failed for batch of %d", len(batch))
            await asyncio.sleep(0.2)
    finally:
        await opcua_client.disconnect()
        await pool.close()
        await redis_client.aclose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Commit**

```bash
git add services/ingest/src/ingest/opcua_client.py services/ingest/src/ingest/main.py
git commit -m "feat(ingest): opcua client, subscription, main loop"
```

---

### Task 19: Ingest service — Dockerfile

**Files:**
- Create: `services/ingest/Dockerfile`

- [ ] **Step 1: Create `services/ingest/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY src/ ./src/
RUN pip install --no-cache-dir -e . --no-deps

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "ingest.main"]
```

- [ ] **Step 2: Build image**

```bash
cd "d:/Dev/Project 1"
docker build -t factory-pulse-ingest services/ingest
```

Expected: image builds.

- [ ] **Step 3: Commit**

```bash
git add services/ingest/Dockerfile
git commit -m "chore(ingest): add Dockerfile"
```

---

### Task 20: Docker Compose — add simulator + ingest + api (end-to-end)

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Create `services/api/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
RUN pip install --no-cache-dir -e . --no-deps

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
```

- [ ] **Step 2: Build api image**

```bash
cd "d:/Dev/Project 1"
docker build -t factory-pulse-api services/api
```

Expected: image builds.

- [ ] **Step 3: Extend `docker-compose.yml`**

Replace the entire file with:

```yaml
services:
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-factory}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-factory_dev_password}
      POSTGRES_DB: ${POSTGRES_DB:-factory_pulse}
    ports:
      - "5432:5432"
    volumes:
      - timescaledb_data:/var/lib/postgresql/data
    command:
      - "postgres"
      - "-c"
      - "shared_buffers=256MB"
      - "-c"
      - "work_mem=16MB"
      - "-c"
      - "max_connections=50"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  simulator:
    build: services/simulator
    environment:
      OPCUA_ENDPOINT: opc.tcp://0.0.0.0:4840
      EQUIPMENT_CONFIG: /config/equipment.yaml
      SIMULATOR_TICK_SECONDS: "1.0"
    volumes:
      - ./config:/config:ro
    ports:
      - "4840:4840"

  ingest:
    build: services/ingest
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-factory}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-factory_dev_password}
      POSTGRES_HOST: timescaledb
      POSTGRES_DB: ${POSTGRES_DB:-factory_pulse}
      REDIS_HOST: redis
      OPCUA_ENDPOINT: opc.tcp://simulator:4840
      OPCUA_NAMESPACE: urn:factory-pulse:simulator
    depends_on:
      - timescaledb
      - redis
      - simulator

  api:
    build: services/api
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-factory}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-factory_dev_password}
      POSTGRES_HOST: timescaledb
      POSTGRES_DB: ${POSTGRES_DB:-factory_pulse}
      REDIS_HOST: redis
      EQUIPMENT_CONFIG_PATH: /config/equipment.yaml
    volumes:
      - ./config:/config:ro
    ports:
      - "8000:8000"
    depends_on:
      - timescaledb
      - redis

volumes:
  timescaledb_data:
```

- [ ] **Step 4: Bring up stack**

```bash
docker compose down
docker compose up -d --build
```

Expected: all 5 services start.

- [ ] **Step 5: Verify end-to-end telemetry flow**

Wait 10 seconds, then:

```bash
curl http://localhost:8000/api/health
```

Expected: healthy status.

```bash
docker compose exec timescaledb psql -U factory -d factory_pulse -c "SELECT COUNT(*) FROM telemetry;"
```

Expected: non-zero row count (ingest is flowing).

```bash
docker compose exec redis redis-cli HGETALL equipment:latest:FORM-01
```

Expected: hash with status, metrics, updated_at fields.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml services/api/Dockerfile
git commit -m "feat: full docker-compose stack with simulator, ingest, api"
```

---

### Task 21: API — equipment list route (reads Redis + Postgres)

**Files:**
- Create: `services/api/src/api/routes/equipment.py`
- Create: `services/api/tests/test_routes_equipment.py`
- Modify: `services/api/src/api/main.py`

- [ ] **Step 1: Create `routes/equipment.py`**

```python
"""Equipment list + detail endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException

from api.db import get_pool
from api.redis_client import get_client

router = APIRouter()

_META_METRIC_FIELDS = {
    "status",
    "current_batch_id",
    "current_unit_id",
    "unit_started_at",
    "updated_at",
}


def _split_latest(h: dict[str, str]) -> tuple[dict[str, object], dict[str, float]]:
    meta: dict[str, object] = {
        "status": h.get("status"),
        "current_batch_id": h.get("current_batch_id"),
        "current_unit_id": h.get("current_unit_id"),
        "unit_started_at": h.get("unit_started_at"),
        "updated_at": h.get("updated_at"),
    }
    metrics: dict[str, float] = {}
    for k, v in h.items():
        if k in _META_METRIC_FIELDS:
            continue
        try:
            metrics[k] = float(v)
        except (TypeError, ValueError):
            continue
    return meta, metrics


@router.get("/equipment")
async def list_equipment() -> dict:
    pool = await get_pool()
    client = get_client()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, type, location FROM equipment ORDER BY id"
        )

    result = []
    for row in rows:
        try:
            h = await client.hgetall(f"equipment:latest:{row['id']}")
        except Exception:
            h = {}
        meta, metrics = _split_latest(h) if h else ({}, {})
        result.append(
            {
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "location": row["location"],
                "status": meta.get("status"),
                "current_batch_id": meta.get("current_batch_id"),
                "current_unit_id": meta.get("current_unit_id"),
                "unit_started_at": meta.get("unit_started_at"),
                "latest_metrics": metrics,
                "updated_at": meta.get("updated_at"),
            }
        )
    return {"equipment": result}


@router.get("/equipment/{equipment_id}")
async def get_equipment(equipment_id: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, type, location, metadata FROM equipment WHERE id = $1",
            equipment_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "location": row["location"],
        "metadata": row["metadata"],
    }


@router.get("/equipment/{equipment_id}/current")
async def get_equipment_current(equipment_id: str) -> dict:
    client = get_client()
    try:
        h = await client.hgetall(f"equipment:latest:{equipment_id}")
    except Exception:
        h = {}
    if not h:
        raise HTTPException(status_code=404, detail={"error": "no_current_data"})
    return {
        "equipment_id": equipment_id,
        "status": h.get("status"),
        "batch_id": h.get("current_batch_id"),
        "unit_id": h.get("current_unit_id"),
        "unit_started_at": h.get("unit_started_at"),
    }
```

- [ ] **Step 2: Write route tests**

Create `services/api/tests/test_routes_equipment.py`:

```python
from api.routes.equipment import _split_latest


def test_split_latest_separates_meta_from_metrics():
    h = {
        "status": "running",
        "current_batch_id": "B-1",
        "current_unit_id": "U-1",
        "unit_started_at": "2026-04-05T12:00:00+00:00",
        "updated_at": "2026-04-05T12:00:01+00:00",
        "temperature": "45.2",
        "voltage": "3.7",
    }
    meta, metrics = _split_latest(h)
    assert meta["status"] == "running"
    assert meta["current_batch_id"] == "B-1"
    assert metrics == {"temperature": 45.2, "voltage": 3.7}


def test_split_latest_handles_empty():
    meta, metrics = _split_latest({})
    assert meta == {
        "status": None,
        "current_batch_id": None,
        "current_unit_id": None,
        "unit_started_at": None,
        "updated_at": None,
    }
    assert metrics == {}


def test_split_latest_skips_non_numeric_metrics():
    h = {"status": "running", "temperature": "not_a_number"}
    _, metrics = _split_latest(h)
    assert metrics == {}
```

- [ ] **Step 3: Include router in `main.py`**

Edit `services/api/src/api/main.py` — add import and include router:

```python
from api.routes.equipment import router as equipment_router
```

After `app.include_router(health_router, prefix="/api")`, add:

```python
app.include_router(equipment_router, prefix="/api")
```

- [ ] **Step 4: Run tests**

```bash
cd "services/api"
.venv/Scripts/pytest tests/test_routes_equipment.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Verify end-to-end**

```bash
cd "d:/Dev/Project 1"
docker compose up -d --build api
sleep 5
curl http://localhost:8000/api/equipment
```

Expected: JSON with 8 equipment entries, each having non-null `status` and `latest_metrics`.

```bash
curl http://localhost:8000/api/equipment/FORM-01
```

Expected: JSON with id, name, type, location, metadata.

```bash
curl http://localhost:8000/api/equipment/FORM-01/current
```

Expected: JSON with status, batch_id, unit_id, unit_started_at.

- [ ] **Step 6: Commit**

```bash
git add services/api/src/api/routes/equipment.py services/api/tests/test_routes_equipment.py services/api/src/api/main.py
git commit -m "feat(api): equipment list, detail, current endpoints"
```

---

### Task 22: API — telemetry history route

**Files:**
- Create: `services/api/src/api/routes/telemetry.py`
- Modify: `services/api/src/api/main.py`

- [ ] **Step 1: Create `routes/telemetry.py`**

```python
"""Telemetry history endpoint with auto resolution."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from api.db import get_pool
from api.query_router import Interval, select_interval, validate_range

router = APIRouter()


@router.get("/equipment/{equipment_id}/telemetry")
async def get_telemetry(
    equipment_id: str,
    frm: Annotated[datetime, Query(alias="from")],
    to: Annotated[datetime, Query()],
    metric: Annotated[list[str] | None, Query()] = None,
    interval: Annotated[str | None, Query()] = None,
) -> dict:
    try:
        validate_range(frm, to)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": "invalid_range", "detail": str(e)})

    if interval is None:
        resolved = select_interval(frm, to)
    else:
        try:
            resolved = Interval(interval)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "invalid_interval"})

    pool = await get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval("SELECT 1 FROM equipment WHERE id = $1", equipment_id)
        if not exists:
            raise HTTPException(status_code=404, detail={"error": "not_found"})

        if resolved == Interval.RAW:
            rows = await _query_raw(conn, equipment_id, frm, to, metric)
            series = _group_raw(rows)
        else:
            table = "telemetry_1min" if resolved == Interval.MIN_1 else "telemetry_1hour"
            rows = await _query_agg(conn, table, equipment_id, frm, to, metric)
            series = _group_agg(rows)

    return {
        "equipment_id": equipment_id,
        "interval": resolved.value,
        "series": series,
    }


async def _query_raw(conn, equipment_id, frm, to, metric):
    sql = (
        "SELECT time, metric_name, value FROM telemetry "
        "WHERE equipment_id = $1 AND time >= $2 AND time < $3"
    )
    params = [equipment_id, frm, to]
    if metric:
        sql += " AND metric_name = ANY($4)"
        params.append(metric)
    sql += " ORDER BY time"
    return await conn.fetch(sql, *params)


async def _query_agg(conn, table, equipment_id, frm, to, metric):
    sql = (
        f"SELECT bucket, metric_name, avg_value, min_value, max_value FROM {table} "
        "WHERE equipment_id = $1 AND bucket >= $2 AND bucket < $3"
    )
    params = [equipment_id, frm, to]
    if metric:
        sql += " AND metric_name = ANY($4)"
        params.append(metric)
    sql += " ORDER BY bucket"
    return await conn.fetch(sql, *params)


def _group_raw(rows):
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["metric_name"], []).append(
            {"time": r["time"].isoformat(), "value": r["value"]}
        )
    return [{"metric": k, "points": v} for k, v in out.items()]


def _group_agg(rows):
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["metric_name"], []).append(
            {
                "time": r["bucket"].isoformat(),
                "avg": r["avg_value"],
                "min": r["min_value"],
                "max": r["max_value"],
            }
        )
    return [{"metric": k, "points": v} for k, v in out.items()]
```

- [ ] **Step 2: Include router in `main.py`**

Edit `services/api/src/api/main.py` — add import and include:

```python
from api.routes.telemetry import router as telemetry_router
```

After the equipment router include:

```python
app.include_router(telemetry_router, prefix="/api")
```

- [ ] **Step 3: Verify end-to-end**

```bash
cd "d:/Dev/Project 1"
docker compose up -d --build api
sleep 5
# Use ISO-8601 for the current UTC time minus 30 min
curl "http://localhost:8000/api/equipment/FORM-01/telemetry?from=2026-04-05T00:00:00Z&to=2026-04-05T23:59:59Z&metric=temperature"
```

Expected: JSON with `interval` and non-empty `series`.

- [ ] **Step 4: Commit**

```bash
git add services/api/src/api/routes/telemetry.py services/api/src/api/main.py
git commit -m "feat(api): telemetry history endpoint with auto-resolution"
```

---

### Task 23: API — batches route

**Files:**
- Create: `services/api/src/api/routes/batches.py`
- Modify: `services/api/src/api/main.py`

- [ ] **Step 1: Create `routes/batches.py`**

```python
"""Batch traceability endpoint."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.db import get_pool

router = APIRouter()


@router.get("/batches/{batch_id}/telemetry")
async def get_batch_timeline(batch_id: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                equipment_id,
                MIN(time) AS started_at,
                MAX(time) AS ended_at,
                ARRAY_AGG(DISTINCT unit_id) AS units
            FROM telemetry
            WHERE batch_id = $1
            GROUP BY equipment_id
            ORDER BY started_at
            """,
            batch_id,
        )
    if not rows:
        raise HTTPException(status_code=404, detail={"error": "batch_not_found"})
    return {
        "batch_id": batch_id,
        "equipment_timeline": [
            {
                "equipment_id": r["equipment_id"],
                "started_at": r["started_at"].isoformat(),
                "ended_at": r["ended_at"].isoformat(),
                "units_processed": [u for u in r["units"] if u is not None],
            }
            for r in rows
        ],
    }
```

- [ ] **Step 2: Include in `main.py`**

```python
from api.routes.batches import router as batches_router
```

```python
app.include_router(batches_router, prefix="/api")
```

- [ ] **Step 3: Verify**

```bash
cd "d:/Dev/Project 1"
docker compose up -d --build api
sleep 10
# Get a real batch_id first
BATCH=$(curl -s http://localhost:8000/api/equipment/FORM-01/current | python -c "import sys,json;print(json.load(sys.stdin)['batch_id'])")
curl "http://localhost:8000/api/batches/$BATCH/telemetry"
```

Expected: JSON with `batch_id` and at least one equipment entry.

- [ ] **Step 4: Commit**

```bash
git add services/api/src/api/routes/batches.py services/api/src/api/main.py
git commit -m "feat(api): batch traceability endpoint"
```

---

### Task 24: API — WebSocket telemetry stream

**Files:**
- Create: `services/api/src/api/websocket.py`
- Create: `services/api/tests/test_websocket.py`
- Modify: `services/api/src/api/main.py`

- [ ] **Step 1: Write failing test for message parser**

Create `services/api/tests/test_websocket.py`:

```python
import pytest

from api.websocket import parse_client_message, SubscribeAction, UnsubscribeAction, SubscribeAllAction


def test_parse_subscribe():
    msg = parse_client_message('{"action":"subscribe","equipment_ids":["E-01","E-02"]}')
    assert isinstance(msg, SubscribeAction)
    assert msg.equipment_ids == ["E-01", "E-02"]


def test_parse_unsubscribe():
    msg = parse_client_message('{"action":"unsubscribe","equipment_ids":["E-01"]}')
    assert isinstance(msg, UnsubscribeAction)
    assert msg.equipment_ids == ["E-01"]


def test_parse_subscribe_all():
    msg = parse_client_message('{"action":"subscribe_all"}')
    assert isinstance(msg, SubscribeAllAction)


def test_parse_invalid_json():
    with pytest.raises(ValueError, match="invalid json"):
        parse_client_message("not json")


def test_parse_unknown_action():
    with pytest.raises(ValueError, match="unknown action"):
        parse_client_message('{"action":"nope"}')
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "services/api"
.venv/Scripts/pytest tests/test_websocket.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Write `websocket.py`**

```python
"""WebSocket telemetry stream."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Union

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.redis_client import get_client

logger = logging.getLogger(__name__)

router = APIRouter()

SEND_QUEUE_MAX = 100
BATCH_INTERVAL_MS = 250


@dataclass
class SubscribeAction:
    equipment_ids: list[str]


@dataclass
class UnsubscribeAction:
    equipment_ids: list[str]


@dataclass
class SubscribeAllAction:
    pass


ClientMessage = Union[SubscribeAction, UnsubscribeAction, SubscribeAllAction]


def parse_client_message(raw: str) -> ClientMessage:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError("invalid json")
    action = data.get("action")
    if action == "subscribe":
        return SubscribeAction(equipment_ids=data.get("equipment_ids", []))
    if action == "unsubscribe":
        return UnsubscribeAction(equipment_ids=data.get("equipment_ids", []))
    if action == "subscribe_all":
        return SubscribeAllAction()
    raise ValueError(f"unknown action: {action}")


@router.websocket("/ws/telemetry")
async def ws_telemetry(ws: WebSocket) -> None:
    await ws.accept()
    client = get_client()
    pubsub = client.pubsub()
    subscribed: set[str] = set()
    all_mode = False

    send_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=SEND_QUEUE_MAX)

    async def reader() -> None:
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    action = parse_client_message(raw)
                except ValueError as e:
                    await ws.send_text(json.dumps({"type": "error", "message": str(e)}))
                    continue
                nonlocal all_mode
                if isinstance(action, SubscribeAction):
                    for eid in action.equipment_ids:
                        ch = f"telemetry:{eid}"
                        if ch not in subscribed:
                            await pubsub.subscribe(ch)
                            subscribed.add(ch)
                    await ws.send_text(json.dumps({"type": "ack", "action": "subscribe", "equipment_ids": action.equipment_ids}))
                elif isinstance(action, UnsubscribeAction):
                    for eid in action.equipment_ids:
                        ch = f"telemetry:{eid}"
                        if ch in subscribed:
                            await pubsub.unsubscribe(ch)
                            subscribed.discard(ch)
                    await ws.send_text(json.dumps({"type": "ack", "action": "unsubscribe", "equipment_ids": action.equipment_ids}))
                elif isinstance(action, SubscribeAllAction):
                    await pubsub.psubscribe("telemetry:*")
                    all_mode = True
                    await ws.send_text(json.dumps({"type": "ack", "action": "subscribe_all"}))
        except WebSocketDisconnect:
            pass

    async def forwarder() -> None:
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is None:
                    continue
                data = message.get("data")
                if not data:
                    continue
                try:
                    inner = json.loads(data)
                except json.JSONDecodeError:
                    continue
                out = {
                    "type": "telemetry",
                    "equipment_id": inner.get("equipment_id"),
                    "time": inner.get("time"),
                    "status": inner.get("status"),
                    "batch_id": inner.get("batch_id"),
                    "unit_id": inner.get("unit_id"),
                    "metrics": inner.get("metrics", {}),
                }
                try:
                    send_queue.put_nowait(json.dumps(out))
                except asyncio.QueueFull:
                    try:
                        send_queue.get_nowait()  # drop oldest
                    except asyncio.QueueEmpty:
                        pass
                    send_queue.put_nowait(json.dumps(out))
        except Exception:
            logger.exception("forwarder error")

    async def sender() -> None:
        try:
            while True:
                msg = await send_queue.get()
                await ws.send_text(msg)
        except WebSocketDisconnect:
            pass

    reader_task = asyncio.create_task(reader())
    forwarder_task = asyncio.create_task(forwarder())
    sender_task = asyncio.create_task(sender())

    done, pending = await asyncio.wait(
        {reader_task, forwarder_task, sender_task}, return_when=asyncio.FIRST_COMPLETED
    )
    for t in pending:
        t.cancel()
    try:
        await pubsub.close()
    except Exception:
        pass
```

- [ ] **Step 4: Include in `main.py`**

```python
from api.websocket import router as ws_router
```

```python
app.include_router(ws_router)  # no /api prefix for ws
```

- [ ] **Step 5: Run tests**

```bash
.venv/Scripts/pytest tests/test_websocket.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 6: Verify end-to-end with websocat (or Python)**

Install websocat or use this Python quick test:

```bash
cd "d:/Dev/Project 1"
docker compose up -d --build api
sleep 5
python -c "
import asyncio, websockets, json
async def main():
    async with websockets.connect('ws://localhost:8000/ws/telemetry') as ws:
        await ws.send(json.dumps({'action':'subscribe_all'}))
        for _ in range(3):
            msg = await ws.recv()
            print(msg)
asyncio.run(main())
"
```

Expected: `{"type":"ack",...}` then several `{"type":"telemetry",...}` messages within a few seconds.

(If `websockets` not installed: `pip install websockets`.)

- [ ] **Step 7: Commit**

```bash
git add services/api/src/api/websocket.py services/api/tests/test_websocket.py services/api/src/api/main.py
git commit -m "feat(api): websocket telemetry stream"
```

---

### Task 25: Frontend — Vite scaffold + types

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/types.ts`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "factory-pulse-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "lint": "eslint src --ext .ts,.tsx"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@testing-library/react": "^14.2.0",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "jsdom": "^24.0.0",
    "typescript": "^5.3.0",
    "vite": "^5.1.0",
    "vitest": "^1.3.0"
  }
}
```

- [ ] **Step 2: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "allowImportingTsExtensions": true,
    "types": ["vite/client", "vitest/globals"]
  },
  "include": ["src", "tests"]
}
```

- [ ] **Step 3: Create `frontend/vite.config.ts`**

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
});
```

- [ ] **Step 4: Create `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Factory Pulse</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Create `frontend/src/types.ts`**

```typescript
export interface Equipment {
  id: string;
  name: string;
  type: string;
  location: string;
  status: string | null;
  current_batch_id: string | null;
  current_unit_id: string | null;
  unit_started_at: string | null;
  latest_metrics: Record<string, number>;
  updated_at: string | null;
}

export interface EquipmentListResponse {
  equipment: Equipment[];
}

export interface TelemetryEvent {
  type: 'telemetry';
  equipment_id: string;
  time: string;
  status: string | null;
  batch_id: string | null;
  unit_id: string | null;
  metrics: Record<string, number>;
}
```

- [ ] **Step 6: Create `frontend/src/main.tsx`**

```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 7: Install dependencies**

```bash
cd frontend
npm install
```

Expected: clean install.

- [ ] **Step 8: Commit**

```bash
cd "d:/Dev/Project 1"
git add frontend/
git commit -m "feat(frontend): vite + react scaffold with shared types"
```

---

### Task 26: Frontend — API client + WebSocket client

**Files:**
- Create: `frontend/src/api.ts`
- Create: `frontend/src/websocket.ts`

- [ ] **Step 1: Create `frontend/src/api.ts`**

```typescript
import type { EquipmentListResponse } from './types';

export async function fetchEquipment(): Promise<EquipmentListResponse> {
  const r = await fetch('/api/equipment');
  if (!r.ok) throw new Error(`fetch equipment failed: ${r.status}`);
  return r.json();
}
```

- [ ] **Step 2: Create `frontend/src/websocket.ts`**

```typescript
import type { TelemetryEvent } from './types';

type Handler = (e: TelemetryEvent) => void;
type StatusHandler = (connected: boolean) => void;

export class TelemetryWebSocket {
  private ws: WebSocket | null = null;
  private closed = false;
  private reconnectDelay = 1000;

  constructor(
    private onTelemetry: Handler,
    private onStatus: StatusHandler,
  ) {}

  connect(): void {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${window.location.host}/ws/telemetry`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectDelay = 1000;
      this.onStatus(true);
      this.ws?.send(JSON.stringify({ action: 'subscribe_all' }));
    };

    this.ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'telemetry') {
          this.onTelemetry(msg as TelemetryEvent);
        }
      } catch {
        // ignore
      }
    };

    this.ws.onclose = () => {
      this.onStatus(false);
      if (this.closed) return;
      setTimeout(() => this.connect(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  close(): void {
    this.closed = true;
    this.ws?.close();
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.ts frontend/src/websocket.ts
git commit -m "feat(frontend): api and websocket clients"
```

---

### Task 27: Frontend — EquipmentCard component (TDD)

**Files:**
- Create: `frontend/tests/EquipmentCard.test.tsx`
- Create: `frontend/src/components/EquipmentCard.tsx`

- [ ] **Step 1: Write failing test**

Create `frontend/tests/EquipmentCard.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EquipmentCard } from '../src/components/EquipmentCard';
import type { Equipment } from '../src/types';

const base: Equipment = {
  id: 'FORM-01',
  name: 'Formation Cycler #1',
  type: 'formation_cycler',
  location: 'Line-A / Bay-1',
  status: 'running',
  current_batch_id: 'B-1',
  current_unit_id: 'CELL-2026-04-05-0001',
  unit_started_at: '2026-04-05T12:00:00Z',
  latest_metrics: { temperature: 45.2, voltage: 3.72 },
  updated_at: '2026-04-05T12:00:01Z',
};

describe('EquipmentCard', () => {
  it('renders name and status', () => {
    render(<EquipmentCard equipment={base} />);
    expect(screen.getByText('Formation Cycler #1')).toBeDefined();
    expect(screen.getByText(/running/i)).toBeDefined();
  });

  it('renders the unit id', () => {
    render(<EquipmentCard equipment={base} />);
    expect(screen.getByText(/CELL-2026-04-05-0001/)).toBeDefined();
  });

  it('renders metric values', () => {
    render(<EquipmentCard equipment={base} />);
    expect(screen.getByText(/45.2/)).toBeDefined();
  });

  it('handles missing status', () => {
    render(<EquipmentCard equipment={{ ...base, status: null }} />);
    expect(screen.getByText(/unknown/i)).toBeDefined();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend
npm test
```

Expected: FAIL with "Cannot find module".

- [ ] **Step 3: Write the component**

Create `frontend/src/components/EquipmentCard.tsx`:

```typescript
import type { Equipment } from '../types';

interface Props {
  equipment: Equipment;
}

const STATUS_COLORS: Record<string, string> = {
  running: '#22c55e',
  idle: '#94a3b8',
  fault: '#ef4444',
  maintenance: '#f59e0b',
};

export function EquipmentCard({ equipment }: Props) {
  const status = equipment.status ?? 'unknown';
  const color = STATUS_COLORS[status] ?? '#64748b';
  const metrics = Object.entries(equipment.latest_metrics);

  return (
    <div
      style={{
        border: '1px solid #e2e8f0',
        borderRadius: 8,
        padding: 16,
        minWidth: 260,
        fontFamily: 'system-ui, sans-serif',
        background: '#fff',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14 }}>{equipment.name}</div>
          <div style={{ color: '#64748b', fontSize: 12 }}>{equipment.location}</div>
        </div>
        <span
          style={{
            background: color,
            color: '#fff',
            padding: '2px 8px',
            borderRadius: 12,
            fontSize: 11,
            textTransform: 'uppercase',
          }}
        >
          {status}
        </span>
      </div>
      <div style={{ marginTop: 8, fontSize: 11, color: '#475569' }}>
        Processing: {equipment.current_unit_id ?? '—'}
      </div>
      <div style={{ marginTop: 8, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
        {metrics.map(([k, v]) => (
          <div key={k} style={{ fontSize: 12 }}>
            <span style={{ color: '#64748b' }}>{k}:</span>{' '}
            <span style={{ fontWeight: 600 }}>{v.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npm test
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "d:/Dev/Project 1"
git add frontend/tests/EquipmentCard.test.tsx frontend/src/components/EquipmentCard.tsx
git commit -m "feat(frontend): EquipmentCard component"
```

---

### Task 28: Frontend — EquipmentGrid + ConnectionStatus + App

**Files:**
- Create: `frontend/src/components/EquipmentGrid.tsx`
- Create: `frontend/src/components/ConnectionStatus.tsx`
- Create: `frontend/src/App.tsx`

- [ ] **Step 1: Create `EquipmentGrid.tsx`**

```typescript
import type { Equipment } from '../types';
import { EquipmentCard } from './EquipmentCard';

interface Props {
  equipment: Equipment[];
}

export function EquipmentGrid({ equipment }: Props) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
        gap: 12,
      }}
    >
      {equipment.map((e) => (
        <EquipmentCard key={e.id} equipment={e} />
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create `ConnectionStatus.tsx`**

```typescript
interface Props {
  connected: boolean;
}

export function ConnectionStatus({ connected }: Props) {
  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 12,
        color: connected ? '#16a34a' : '#dc2626',
      }}
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: connected ? '#22c55e' : '#ef4444',
        }}
      />
      {connected ? 'Live' : 'Reconnecting…'}
    </div>
  );
}
```

- [ ] **Step 3: Create `App.tsx`**

```typescript
import { useEffect, useRef, useState } from 'react';
import { fetchEquipment } from './api';
import { TelemetryWebSocket } from './websocket';
import { EquipmentGrid } from './components/EquipmentGrid';
import { ConnectionStatus } from './components/ConnectionStatus';
import type { Equipment, TelemetryEvent } from './types';

export default function App() {
  const [equipment, setEquipment] = useState<Record<string, Equipment>>({});
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<TelemetryWebSocket | null>(null);

  useEffect(() => {
    fetchEquipment()
      .then((res) => {
        const map: Record<string, Equipment> = {};
        for (const e of res.equipment) map[e.id] = e;
        setEquipment(map);
      })
      .catch((err) => console.error('fetch equipment', err));

    const ws = new TelemetryWebSocket(
      (ev: TelemetryEvent) => {
        setEquipment((prev) => {
          const cur = prev[ev.equipment_id];
          if (!cur) return prev;
          return {
            ...prev,
            [ev.equipment_id]: {
              ...cur,
              status: ev.status,
              current_batch_id: ev.batch_id,
              current_unit_id: ev.unit_id,
              latest_metrics: { ...cur.latest_metrics, ...ev.metrics },
              updated_at: ev.time,
            },
          };
        });
      },
      (ok) => setConnected(ok),
    );
    wsRef.current = ws;
    ws.connect();
    return () => ws.close();
  }, []);

  const list = Object.values(equipment).sort((a, b) => a.id.localeCompare(b.id));

  return (
    <div style={{ padding: 16, fontFamily: 'system-ui, sans-serif', background: '#f8fafc', minHeight: '100vh' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h1 style={{ margin: 0, fontSize: 20 }}>Factory Pulse — Floor Overview</h1>
        <ConnectionStatus connected={connected} />
      </header>
      <EquipmentGrid equipment={list} />
    </div>
  );
}
```

- [ ] **Step 4: Run dev server and verify**

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. Expected: grid of 8 equipment cards, Live indicator green, status pills updating in real time, metric values changing every second.

Stop with Ctrl+C.

- [ ] **Step 5: Commit**

```bash
cd "d:/Dev/Project 1"
git add frontend/src/components/EquipmentGrid.tsx frontend/src/components/ConnectionStatus.tsx frontend/src/App.tsx
git commit -m "feat(frontend): equipment grid with live websocket updates"
```

---

### Task 29: Frontend — Dockerfile + serve from API

**Files:**
- Create: `frontend/Dockerfile`
- Modify: `services/api/src/api/main.py`
- Modify: `services/api/Dockerfile`

- [ ] **Step 1: Create `frontend/Dockerfile` (multi-stage build)**

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY . .
RUN npm run build

# Output is /app/dist — consumed by api service via shared volume or COPY
```

- [ ] **Step 2: Update `services/api/Dockerfile` to embed frontend**

Replace `services/api/Dockerfile` with:

```dockerfile
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

COPY services/api/pyproject.toml ./
RUN pip install --no-cache-dir .

COPY services/api/src/ ./src/
COPY services/api/alembic/ ./alembic/
COPY services/api/alembic.ini ./
RUN pip install --no-cache-dir -e . --no-deps

COPY --from=frontend-build /frontend/dist ./static

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
```

- [ ] **Step 3: Update `docker-compose.yml` api service to build from root**

Replace the `api:` service block with:

```yaml
  api:
    build:
      context: .
      dockerfile: services/api/Dockerfile
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-factory}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-factory_dev_password}
      POSTGRES_HOST: timescaledb
      POSTGRES_DB: ${POSTGRES_DB:-factory_pulse}
      REDIS_HOST: redis
      EQUIPMENT_CONFIG_PATH: /config/equipment.yaml
    volumes:
      - ./config:/config:ro
    ports:
      - "8000:8000"
    depends_on:
      - timescaledb
      - redis
```

- [ ] **Step 4: Update `services/api/src/api/main.py` to serve static files**

Replace the app setup section (after `app = FastAPI(...)`) with:

```python
from pathlib import Path as _P
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Factory Pulse API", version="0.1.0", lifespan=lifespan)
app.include_router(health_router, prefix="/api")
app.include_router(equipment_router, prefix="/api")
app.include_router(telemetry_router, prefix="/api")
app.include_router(batches_router, prefix="/api")
app.include_router(ws_router)

_static_dir = _P(__file__).parent.parent.parent / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
```

- [ ] **Step 5: Build and verify**

```bash
cd "d:/Dev/Project 1"
docker compose up -d --build api
sleep 10
curl -I http://localhost:8000/
```

Expected: `HTTP/1.1 200 OK` with `content-type: text/html`.

Open `http://localhost:8000/` in a browser. Expected: live dashboard (same as dev server).

- [ ] **Step 6: Commit**

```bash
git add frontend/Dockerfile services/api/Dockerfile docker-compose.yml services/api/src/api/main.py
git commit -m "feat: serve built frontend from api container"
```

---

### Task 30: Grafana datasource + equipment telemetry dashboard

**Files:**
- Create: `grafana/provisioning/datasources/timescaledb.yml`
- Create: `grafana/provisioning/dashboards/dashboards.yml`
- Create: `grafana/dashboards/equipment-telemetry.json`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Create `grafana/provisioning/datasources/timescaledb.yml`**

```yaml
apiVersion: 1
datasources:
  - name: TimescaleDB
    type: postgres
    access: proxy
    url: timescaledb:5432
    user: ${POSTGRES_USER}
    secureJsonData:
      password: ${POSTGRES_PASSWORD}
    jsonData:
      database: ${POSTGRES_DB}
      sslmode: disable
      postgresVersion: 1600
      timescaledb: true
    isDefault: true
```

- [ ] **Step 2: Create `grafana/provisioning/dashboards/dashboards.yml`**

```yaml
apiVersion: 1
providers:
  - name: factory-pulse
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards
```

- [ ] **Step 3: Create `grafana/dashboards/equipment-telemetry.json`**

```json
{
  "title": "Equipment Telemetry",
  "uid": "equipment-telemetry",
  "schemaVersion": 38,
  "version": 1,
  "refresh": "5s",
  "time": { "from": "now-15m", "to": "now" },
  "templating": {
    "list": [
      {
        "name": "equipment_id",
        "type": "query",
        "datasource": { "type": "postgres", "uid": "TimescaleDB" },
        "query": "SELECT id FROM equipment ORDER BY id",
        "refresh": 1,
        "includeAll": false
      }
    ]
  },
  "panels": [
    {
      "id": 1,
      "title": "Metrics for $equipment_id",
      "type": "timeseries",
      "datasource": { "type": "postgres", "uid": "TimescaleDB" },
      "targets": [
        {
          "refId": "A",
          "rawSql": "SELECT time AS \"time\", metric_name, value FROM telemetry WHERE equipment_id = '$equipment_id' AND $__timeFilter(time) ORDER BY time",
          "format": "time_series"
        }
      ],
      "gridPos": { "x": 0, "y": 0, "w": 24, "h": 12 }
    }
  ]
}
```

- [ ] **Step 4: Add Grafana to `docker-compose.yml`**

Add under services:

```yaml
  grafana:
    image: grafana/grafana:10.4.0
    environment:
      GF_SECURITY_ADMIN_USER: ${GRAFANA_ADMIN_USER:-admin}
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD:-admin}
      POSTGRES_USER: ${POSTGRES_USER:-factory}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-factory_dev_password}
      POSTGRES_DB: ${POSTGRES_DB:-factory_pulse}
    ports:
      - "3000:3000"
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana/dashboards:/var/lib/grafana/dashboards:ro
      - grafana_data:/var/lib/grafana
    depends_on:
      - timescaledb
```

And add to volumes section:

```yaml
  grafana_data:
```

- [ ] **Step 5: Start Grafana and verify**

```bash
docker compose up -d grafana
sleep 10
```

Open `http://localhost:3000`. Login with admin / admin. Navigate to Dashboards → "Equipment Telemetry". Pick an equipment ID from the variable dropdown. Expected: live-updating time series chart with metric lines.

- [ ] **Step 6: Commit**

```bash
git add grafana/ docker-compose.yml
git commit -m "feat(grafana): datasource + equipment telemetry dashboard"
```

---

### Task 31: Full-stack smoke test

- [ ] **Step 1: Fresh full-stack startup**

```bash
cd "d:/Dev/Project 1"
docker compose down -v
docker compose up -d --build
sleep 20
```

- [ ] **Step 2: Verify all services healthy**

```bash
docker compose ps
```

Expected: all services in "running" state.

- [ ] **Step 3: Verify ingest is flowing**

```bash
docker compose exec timescaledb psql -U factory -d factory_pulse -c "SELECT COUNT(*) FROM telemetry;"
```

Expected: row count > 100 within 30 seconds.

- [ ] **Step 4: Verify API endpoints**

```bash
curl -s http://localhost:8000/api/health | python -m json.tool
curl -s http://localhost:8000/api/equipment | python -m json.tool | head -40
```

Expected: healthy + equipment listed with live metrics.

- [ ] **Step 5: Verify dashboard**

Open `http://localhost:8000/` — expect live equipment grid updating.
Open `http://localhost:3000/` — expect Grafana dashboard.

- [ ] **Step 6: Tag release**

```bash
git tag -a v0.1.0-phase1a -m "Phase 1a: core pipeline complete"
```

- [ ] **Step 7: Commit final state**

```bash
git add -A
git commit --allow-empty -m "chore: phase 1a complete"
```

---

## Self-Review Checklist (filled in by plan author)

**1. Spec coverage:**
- ✅ OPC-UA simulator with 8 machines across 5 types — Tasks 3-8
- ✅ State machine with idle/running/fault/maintenance — Task 4
- ✅ Batch/unit traceability — Task 5, Task 9 (schema), all API endpoints
- ✅ TimescaleDB schema with hypertable, continuous aggregates, compression, retention — Task 9
- ✅ Ingest service with batch buffer, DB writer, Redis publisher + hot cache — Tasks 15-18
- ✅ OPC-UA reconnection with backoff — Task 18 (`_connect_opcua_with_retry`)
- ✅ API: equipment list, detail, current, telemetry history, batches, health — Tasks 14, 21, 22, 23
- ✅ Time-range query routing (raw/1min/1hour) — Task 12, 22
- ✅ WebSocket with subscribe/unsubscribe/subscribe_all, bounded queue — Task 24
- ✅ React dashboard with live grid, WebSocket reconnect, connection status — Tasks 25-28
- ✅ Grafana datasource + equipment dashboard — Task 30
- ✅ Docker Compose full stack — Tasks 10, 20, 29, 30

**Deferred to Plan 1b (per scope):** Prometheus metrics, structured JSON logging, integration testcontainers tests, health/ready endpoints on ingest service, CI/CD, Caddy/HTTPS, ADRs, README polish.

**2. Placeholders:** None found.

**3. Type consistency:**
- `Sample` dataclass used consistently across ingest (Task 15 definition, Task 16 + 18 usage)
- `Equipment` TypeScript type used consistently across frontend (Task 25 definition, Tasks 26-28 usage)
- `EquipmentState` enum used consistently (Task 4 definition, Task 6 + 7 usage)
- `Interval` enum used consistently (Task 12 definition, Task 22 usage)
- `BatchBuffer` interface: `add`, `should_flush`, `drain`, `__len__` — match between Task 15 tests, Task 15 impl, Task 18 usage

**Confidence:** High. Plan produces a working end-to-end local-dev system.
