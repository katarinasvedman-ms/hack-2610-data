# Charging operations PoC reference

Classification: PoC-authored educational reference. This is not manufacturer
repair guidance, a protocol conformance statement, or a substitute for current
official documentation.

Charging-network operations commonly span the charging station, its
management system, network operators, mobility-service providers, and the
vehicle. Telemetry and work-order records describe different parts of that
system and should be joined using stable station identifiers and trustworthy
timestamps before drawing operational conclusions.

The Open Charge Point Protocol (OCPP) is used between a charging station and a
charging-station management system. ISO 15118 concerns communication between
an electric vehicle and charging equipment. OCPI is used for information
exchange between e-mobility service providers and charge-point operators.
Implementations, versions, vendor extensions, and available fields vary.

An availability observation or a successful start metric cannot, by itself,
establish the physical condition of a connector or cable. Fault observations
can identify a pattern to investigate but do not prove a root cause. Work-order
completion and physical inspection should be checked in their source systems
before taking action.

The Asset Health PoC uses synthetic, static data and exposes no charger-control
operations. Confirm protocol-specific behavior with current official standards
and vendor documentation before using it outside this demonstration.
