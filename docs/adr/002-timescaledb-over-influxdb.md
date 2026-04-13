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
