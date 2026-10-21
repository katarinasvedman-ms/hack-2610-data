# Mock Station Diagnostic Evidence

Dataset: `station-diagnostics-demo`. Schema version: `1.0`.

**All records are fictional, static MOCK data.** This file is not connected to stations, OCPP, or a monitoring service.

Snapshot: `2026-10-21T12:45:00Z`. All timestamps are UTC.

All `DEMO_*` codes are synthetic identifiers, not official OCPP or manufacturer error codes. Their meanings are defined below.

## Scope and limitations

- Match records by exact station ID and, when supplied, connector ID. Never substitute another station.
- No user reports or incident scenarios are included. Use the current request's `user_report` as the incident description.
- These observations describe only the static snapshot, not current or real-time station conditions.
- Missing logs, healthy-looking status, or no active errors do not certify physical safety.
- An unknown fault status is not the same as an explicitly empty error list.
- Manufacturer and model are not specified for any station.
- Charging history and usage data are unavailable for every station.
- Use the separate Station Fixing Guidance Document for procedures and maintenance recommendations. This file is evidence, not maintenance policy.

## Station ST-001 - MOCK

### ST-001 station status

| Field | Value |
|---|---|
| Station ID | ST-001 |
| Classification | MOCK |
| Snapshot and status observation | 2026-10-21T12:45:00Z |
| Status source | simulated_telemetry |
| Connectivity | online |
| Last seen | 2026-10-21T12:44:55Z |
| Manufacturer / model | Not specified / Not specified |
| Charging history | Unavailable; not included in this mock dataset |
| Usage data | Unavailable; not included in this mock dataset |

### ST-001 connectors and errors

| Connector ID | Reported state | Active error codes |
|---|---|---|
| 1 | available | Explicitly empty list; no active demo errors returned |

ST-001 has no error-code records in this snapshot.

### ST-001 logs - MOCK

| Timestamp (UTC) | Source | Connector ID | Level | Event | Code | Message |
|---|---|---|---|---|---|---|
| 2026-10-21T12:44:55Z | simulated_telemetry | Station-level; none specified | info | heartbeat_received | None supplied | Simulated station heartbeat received. |
| 2026-10-21T12:44:56Z | simulated_telemetry | 1 | info | connector_state_observed | None supplied | Connector reports available with no active demo errors. |

### ST-001 limitations

- No billing or payment records are supplied; telemetry cannot establish whether a billing error occurred.
- No physical inspection evidence is supplied.
- Status and logs are static MOCK evidence, not proof of current condition or physical safety.

## Station ST-002 - MOCK

### ST-002 station status

| Field | Value |
|---|---|
| Station ID | ST-002 |
| Classification | MOCK |
| Snapshot and status observation | 2026-10-21T12:45:00Z |
| Status source | simulated_monitoring_backend |
| Connectivity | offline |
| Last seen | 2026-10-21T12:10:00Z |
| Manufacturer / model | Not specified / Not specified |
| Charging history | Unavailable; not included in this mock dataset |
| Usage data | Unavailable; not included in this mock dataset |

### ST-002 connectors

| Connector ID | Reported state at snapshot | Last reported state | Last state observation | Active connector error codes |
|---|---|---|---|---|
| 1 | unknown | available | 2026-10-21T12:10:00Z | Unknown while disconnected; not an empty list |

### ST-002 backend error - MOCK

| Field | Value |
|---|---|
| Code | DEMO_HEARTBEAT_MISSING |
| Code system | synthetic_demo; not an official OCPP/manufacturer code |
| Source | simulated_monitoring_backend |
| Connector ID | Station-level; none specified |
| First observed | 2026-10-21T12:16:00Z |
| Last observed | 2026-10-21T12:45:00Z |
| Active at snapshot | true |
| Definition | The simulated backend has not received a heartbeat within its configured demo monitoring window. |

### ST-002 logs - MOCK

| Timestamp (UTC) | Source | Connector ID | Level | Event | Code | Message |
|---|---|---|---|---|---|---|
| 2026-10-21T12:10:00Z | simulated_telemetry | 1 | info | connector_state_observed | None supplied | Last received connector state was available. |
| 2026-10-21T12:16:00Z | simulated_monitoring_backend | Station-level; none specified | warning | heartbeat_missing | DEMO_HEARTBEAT_MISSING | No heartbeat received since 12:10:00Z; backend marks station offline. |

### ST-002 limitations

- Offline is a backend observation, not proof of a power failure.
- Connector state and station-side faults at the snapshot cannot be retrieved.
- The available connector state is last-known and stale, not a current observation.
- No evidence distinguishes network failure, power loss, or station software failure.
- All records are static MOCK evidence, not current station data.

## Station ST-003 - MOCK

### ST-003 station status

| Field | Value |
|---|---|
| Station ID | ST-003 |
| Classification | MOCK |
| Snapshot and status observation | 2026-10-21T12:45:00Z |
| Status source | simulated_telemetry |
| Connectivity | online |
| Last seen | 2026-10-21T12:44:58Z |
| Manufacturer / model | Not specified / Not specified |
| Charging history | Unavailable; only the listed diagnostic log events are supplied, not full session history |
| Usage data | Unavailable; not included in this mock dataset |

### ST-003 connectors

| Connector ID | Reported state | Active error codes |
|---|---|---|
| 1 | faulted | DEMO_CONNECTOR_LOCK_TIMEOUT |
| 2 | available | Explicitly empty list; no active demo errors returned |

### ST-003 connector 1 error - MOCK

| Field | Value |
|---|---|
| Code | DEMO_CONNECTOR_LOCK_TIMEOUT |
| Code system | synthetic_demo; not an official OCPP/manufacturer code |
| Source | simulated_telemetry |
| Connector ID | 1 |
| First observed | 2026-10-21T12:30:10Z |
| Last observed | 2026-10-21T12:35:10Z |
| Active at snapshot | true |
| Definition | The simulated connector lock did not report a confirmed locked state within the demo timeout. |

### ST-003 logs - MOCK

| Timestamp (UTC) | Source | Connector ID | Level | Event | Code | Message |
|---|---|---|---|---|---|---|
| 2026-10-21T12:30:10Z | simulated_telemetry | 1 | error | lock_confirmation_timeout | DEMO_CONNECTOR_LOCK_TIMEOUT | Lock confirmation not received; charging start aborted. |
| 2026-10-21T12:35:10Z | simulated_telemetry | 1 | error | lock_confirmation_timeout | DEMO_CONNECTOR_LOCK_TIMEOUT | A second lock-confirmation timeout occurred; charging start aborted. |
| 2026-10-21T12:44:58Z | simulated_telemetry | 2 | info | connector_state_observed | None supplied | Connector 2 reports available with no active demo errors. |

### ST-003 limitations

- Lock-confirmation timeout is an observation, not a confirmed root cause.
- No inspection, vehicle comparison, or manufacturer diagnostic evidence is supplied.
- Connector 2 status is not evidence that connector 1 is safe.
- The listed diagnostic events do not supply full charging history or usage statistics.
- All records are static MOCK evidence, not current station data.

## Station ST-004 - MOCK

### ST-004 station status

| Field | Value |
|---|---|
| Station ID | ST-004 |
| Classification | MOCK |
| Snapshot and status observation | 2026-10-21T12:45:00Z |
| Status source | simulated_telemetry |
| Connectivity | online |
| Last seen | 2026-10-21T12:44:59Z |
| Manufacturer / model | Not specified / Not specified |
| Charging history | Unavailable; not included in this mock dataset |
| Usage data | Unavailable; not included in this mock dataset |

### ST-004 connectors and errors

| Connector ID | Reported state | Active error codes |
|---|---|---|
| 1 | available | Explicitly empty list; no active demo errors returned |

ST-004 has no error-code records in this snapshot.

### ST-004 logs - MOCK

| Timestamp (UTC) | Source | Connector ID | Level | Event | Code | Message |
|---|---|---|---|---|---|---|
| 2026-10-21T12:44:59Z | simulated_telemetry | Station-level; none specified | info | heartbeat_received | None supplied | Simulated station heartbeat received. |
| 2026-10-21T12:45:00Z | simulated_telemetry | 1 | info | connector_state_observed | None supplied | Connector reports available; no active demo errors were returned. |

### ST-004 limitations

- No user incident description is included. Use only the current request's report.
- No photograph or physical inspection result is supplied.
- No active error code does not disprove physical damage reported by a user.
- No de-energization, isolation, repair, or return-to-service action has been performed or verified.
- All records are static MOCK evidence, not proof of current condition or physical safety.
