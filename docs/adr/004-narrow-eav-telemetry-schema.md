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
