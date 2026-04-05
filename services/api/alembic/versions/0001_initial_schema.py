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
