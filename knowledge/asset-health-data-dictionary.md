---
title: Asset Health PoC data dictionary
source: Authored PoC reference
version: 0.1.0
date: 2026-10-21
classification: DEMO_ONLY
section: Data fields and provenance
---

# Asset Health PoC data dictionary

**All station records are synthetic MOCK data generated for this PoC.**

| Field | Meaning |
| --- | --- |
| `station_id` | Stable exact synthetic station identifier (`ST-001` through `ST-012`). |
| `connector_id` | Connector identifier scoped to its parent station. |
| `snapshot_at` | Fixed UTC snapshot time, `2026-10-21T00:00:00Z`. |
| `daily.date` | UTC calendar date for one of 30 synthetic daily observations. |
| `eligible_minutes` | Minutes when the station was eligible to provide service. |
| `available_minutes` | Observed available minutes; never greater than eligible minutes. |
| `successful_starts` | Recorded successful charging starts. |
| `failed_starts` | Recorded failed starts, not just completed sessions. |
| `faults` | Synthetic fault list; `null` means unknown observation, `[]` means explicitly no recorded faults. |
| `fault.category` | `station_side` or `auth_roaming_payment`; these are deliberately distinct. |
| `importance` | Separate illustrative business-context value from 1 to 5. |
| `safety_escalation` | Separate demo flag; not a scored metric or safety determination. |
| `maintenance.record_id` | Synthetic work-order reference, not a real maintenance system ID. |

Daily records, fault references, connector aggregates, and maintenance references
are validated against station/connector IDs. A connector history request cannot
substitute records from another connector or station. Missing evidence remains
unknown rather than being replaced with a healthy value.

This fixture is not connected to OCPP, OCPI, roaming, payments, or live
monitoring. Production ingestion must map and validate approved source-system
identifiers and UTC timestamps before using these scoring rules.
