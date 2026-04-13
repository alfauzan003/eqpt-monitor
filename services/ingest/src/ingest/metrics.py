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
