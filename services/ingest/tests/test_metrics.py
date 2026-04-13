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
