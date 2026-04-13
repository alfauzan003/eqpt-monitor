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
pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="module")]


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
        username="factory",
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
def _run_migrations(db_url):
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
async def pool(db_url, _run_migrations):
    """Create an asyncpg pool connected to the test database."""
    _pool = await asyncpg.create_pool(dsn=db_url, min_size=1, max_size=3)
    yield _pool
    await _pool.close()


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
