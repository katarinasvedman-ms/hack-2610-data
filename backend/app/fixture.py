from datetime import date, datetime, time, timedelta, timezone

from .models import (
    AttemptCounts,
    Connector,
    DailyObservation,
    FaultEvent,
    MaintenanceRecord,
    Snapshot,
    Station,
)

SNAPSHOT_AT = datetime(2026, 10, 21, tzinfo=timezone.utc)
WINDOW_DAYS = 30

SCENARIOS = [
    ("ST-001", "Central Exchange", 5, "High traffic and limited nearby alternatives.", "healthy"),
    ("ST-002", "Harbor Point", 3, "Moderate traffic with nearby charging options.", "declining"),
    ("ST-003", "North Campus", 4, "Campus demand peaks during weekday hours.", "recurring"),
    ("ST-004", "Riverside Park", 2, "Several alternative sites are within the area.", "connectivity"),
    ("ST-005", "Airport West", 5, "Critical travel corridor with limited substitutes.", "repairs"),
    ("ST-006", "Market Square", 3, "Urban location with multiple nearby alternatives.", "high_use"),
    ("ST-007", "Pine Ridge", 2, "Lower-volume location with alternate capacity nearby.", "thin"),
    ("ST-008", "East Depot", 4, "High fleet dependence during overnight periods.", "mixed"),
    ("ST-009", "Lakeside", 1, "Low criticality and several nearby alternatives.", "healthy"),
    ("ST-010", "West Medical", 5, "Important destination; score is not a safety assessment.", "safety"),
    ("ST-011", "South Junction", 3, "Moderate demand and alternate public charging.", "declining"),
    ("ST-012", "Hilltop", 2, "Low demand; some telemetry is deliberately incomplete.", "incomplete"),
]


def build_snapshot() -> Snapshot:
    stations = []
    for index, (station_id, site, importance, explanation, scenario) in enumerate(SCENARIOS):
        connectors = [
            Connector(connector_id="1", rated_kw=150, state="available"),
            Connector(connector_id="2", rated_kw=150, state="available"),
        ]
        daily = []
        for offset in range(WINDOW_DAYS, 0, -1):
            day = (SNAPSHOT_AT - timedelta(days=offset)).date()
            day_index = WINDOW_DAYS - offset
            eligible = 1440
            available_ratio = 0.98
            successes = 24 + ((day_index + index) % 11)
            failures = 1 + ((day_index + index * 3) % 4)
            faults: list[FaultEvent] | None = []

            if scenario == "declining":
                available_ratio = 0.96 - day_index * 0.012
                successes, failures = max(4, 27 - day_index // 2), 2 + day_index // 3
            elif scenario == "recurring":
                available_ratio = 0.84
                if day_index in (4, 12, 20, 27):
                    faults = [_fault(station_id, day, "DEMO-COOLING", "Recurring synthetic cooling alert", day_index)]
            elif scenario == "connectivity":
                available_ratio = 0.91
                if day_index in (5, 6, 18, 19):
                    faults = [_fault(station_id, day, "DEMO-LINK", "Synthetic heartbeat interruption", day_index)]
            elif scenario == "repairs":
                available_ratio = 0.86
                if day_index in (3, 10, 17, 25):
                    faults = [_fault(station_id, day, "DEMO-POWER", "Synthetic power-module alert", day_index)]
            elif scenario == "high_use":
                successes, failures = 118 + day_index % 9, 7 + day_index % 5
                available_ratio = 0.92
            elif scenario == "thin":
                successes, failures, available_ratio = 1, 0, 0.99
            elif scenario == "mixed":
                available_ratio = 0.89
                if day_index in (7, 21):
                    faults = [_fault(station_id, day, "DEMO-DOOR", "Synthetic enclosure alert", day_index)]
            elif scenario == "incomplete":
                if day_index % 3 == 0:
                    eligible = None
                    available_ratio = None
                successes = failures = 0
                if day_index % 5 == 0:
                    faults = None
            elif scenario == "safety":
                available_ratio = 0.94

            if scenario in ("declining", "high_use") and day_index % 9 == 0:
                faults = [
                    FaultEvent(
                        fault_id=f"{station_id}-F-{day_index:02}",
                        occurred_at=datetime.combine(day, time(11), timezone.utc),
                        code="DEMO-ACCOUNT",
                        category="auth_roaming_payment",
                        scope="connector",
                        connector_id="1",
                        description="Synthetic authorization or roaming rejection; not a station-side fault.",
                    )
                ]

            available = None if available_ratio is None else round(eligible * available_ratio)
            connector_attempts = {}
            for connector_number, connector_id in enumerate(("1", "2")):
                connector_success = None if successes is None else successes // 2 + (
                    1 if connector_number == 0 and successes % 2 else 0
                )
                connector_failures = None if failures is None else failures // 2 + (
                    1 if connector_number == 0 and failures % 2 else 0
                )
                connector_attempts[connector_id] = AttemptCounts(
                    successful_starts=connector_success,
                    failed_starts=connector_failures,
                    failure_categories={"authorization": 1}
                    if connector_number == 0 and failures and day_index % 9 == 0
                    else {},
                )
            daily.append(
                DailyObservation(
                    date=day,
                    eligible_minutes=eligible,
                    available_minutes=available,
                    attempts=AttemptCounts(
                        successful_starts=successes,
                        failed_starts=failures,
                        failure_categories={"authorization": 1} if failures and day_index % 9 == 0 else {},
                    ),
                    connector_attempts=connector_attempts,
                    faults=faults,
                )
            )

        maintenance = []
        if scenario in ("repairs", "recurring", "mixed"):
            for repair_index, days_ago in enumerate((24, 12, 3), start=1):
                maintenance.append(
                    MaintenanceRecord(
                        record_id=f"{station_id}-WO-{repair_index:02}",
                        station_id=station_id,
                        occurred_at=SNAPSHOT_AT - timedelta(days=days_ago),
                        status="completed" if days_ago != 3 else "open",
                        summary="Illustrative inspection note; no confirmed cause or prescribed repair.",
                    )
                )
        stations.append(
            Station(
                station_id=station_id,
                classification="MOCK",
                site_name=site,
                region=("North" if index % 2 == 0 else "South"),
                connectors=connectors,
                importance=importance,
                importance_explanation=explanation,
                safety_escalation=scenario == "safety",
                daily=daily,
                maintenance=maintenance,
            )
        )
    return Snapshot(
        classification="MOCK",
        snapshot_at=SNAPSHOT_AT,
        window_days=WINDOW_DAYS,
        stations=stations,
    )


def _fault(station_id: str, day: date, code: str, description: str, index: int) -> FaultEvent:
    return FaultEvent(
        fault_id=f"{station_id}-F-{index:02}",
        occurred_at=datetime.combine(day, time(8), timezone.utc),
        code=code,
        category="station_side",
        scope="station",
        description=description,
    )
