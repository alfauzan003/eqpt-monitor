# ADR 003: OPC-UA Only (No MQTT in Phase 1)

**Status:** Accepted
**Date:** 2026-04-05

## Context

Industrial IoT systems commonly use OPC-UA, MQTT, or both. We need to decide which protocol(s) the ingest service supports.

## Decision

Support only OPC-UA in Phase 1. MQTT adapter deferred to Phase 2.

## Rationale

- **Domain differentiator:** OPC-UA is the dominant protocol in manufacturing automation (especially APAC automotive/battery). It signals genuine factory-floor experience that MQTT alone does not.
- **Complexity budget:** Supporting one protocol well (with subscriptions, reconnection, namespace browsing) is better than two protocols partially.
- **Architecture is protocol-agnostic internally:** The ingest service's internal pipeline (buffer → DB write → Redis publish) doesn't depend on OPC-UA. Adding an MQTT adapter in Phase 2 means creating a new subscription frontend that feeds the same pipeline.

## Consequences

- The simulator exposes an OPC-UA server only.
- The ingest service uses `asyncua` for OPC-UA client + subscription.
- Phase 2 will add an MQTT adapter, demonstrating the protocol-agnostic architecture.
