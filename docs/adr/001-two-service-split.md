# ADR 001: Two-Service Architecture (Ingest + API)

**Status:** Accepted
**Date:** 2026-04-05

## Context

We need to choose how to structure the backend: a single monolith, two services (ingest + API), or three services (ingest + API + WebSocket).

## Decision

Split into two services:
- **ingest-service:** OPC-UA subscription, batch buffering, DB writes, Redis publishing
- **api-service:** REST API, WebSocket forwarding, Alembic migrations, static frontend serving

## Rationale

- **Decoupled failure domains:** Ingest can continue writing to the DB even if the API is down for deployment or crashes. API can serve cached data even if ingest is temporarily disconnected from OPC-UA.
- **Different scaling characteristics:** Ingest is IO-bound (OPC-UA + DB writes); API is request-driven. In a production scenario they'd scale differently.
- **Clear service boundary story:** Demonstrates real distributed-systems thinking without over-engineering into microservices.
- **Not three services:** A separate WebSocket service adds deployment complexity without meaningful benefit at this scale. The API service handles both REST and WebSocket since they share the same Redis subscription.

## Consequences

- Services communicate through Redis pub/sub (not direct calls), which adds a dependency but provides natural decoupling.
- Equipment config (`equipment.yaml`) must be shared between simulator and API — mounted as a read-only volume.
- Database migrations run only in the API service (single owner of the schema).
