from collections import defaultdict
from typing import Literal

from .models import DailyObservation, Snapshot, Station

SortMode = Literal["priority", "health", "importance"]


def station_health(station: Station, snapshot: Snapshot) -> dict:
    days = station.daily
    eligible = sum(day.eligible_minutes or 0 for day in days)
    available = sum(day.available_minutes or 0 for day in days)
    availability_covered = sum(
        1 for day in days if day.eligible_minutes is not None and day.available_minutes is not None
    )

    attempt_days = [
        day for day in days
        if day.attempts.successful_starts is not None and day.attempts.failed_starts is not None
    ]
    successes = sum(day.attempts.successful_starts or 0 for day in attempt_days)
    attempts = sum(
        (day.attempts.successful_starts or 0) + (day.attempts.failed_starts or 0)
        for day in attempt_days
    )

    fault_days = [day for day in days if day.faults is not None]
    code_days: dict[str, set] = defaultdict(set)
    for day in fault_days:
        for fault in day.faults or []:
            if fault.category == "station_side":
                code_days[fault.code].add(day.date)
    recurring_dates = set().union(*(dates for dates in code_days.values() if len(dates) >= 2)) if code_days else set()

    components = {
        "availability": _component(
            40,
            100 * available / eligible if eligible else None,
            f"{availability_covered}/{snapshot.window_days} days observed; {available}/{eligible} eligible minutes",
        ),
        "charging_success": _component(
            40,
            100 * successes / attempts if attempts else None,
            f"{len(attempt_days)}/{snapshot.window_days} days observed; {successes}/{attempts} starts succeeded",
        ),
        "station_faults": _component(
            20,
            100 * (1 - len(recurring_dates) / len(fault_days)) if fault_days else None,
            f"{len(fault_days)}/{snapshot.window_days} days with known fault observation; "
            f"{len(recurring_dates)} days affected by recurring station-side codes",
        ),
    }
    sufficient = all(component["score"] is not None for component in components.values())
    score = (
        round(sum(component["score"] * component["weight"] / 100 for component in components.values()), 1)
        if sufficient
        else None
    )
    return {
        "station_id": station.station_id,
        "classification": station.classification,
        "snapshot_at": snapshot.snapshot_at,
        "window_days": snapshot.window_days,
        "health_score": score,
        "status": "scored" if sufficient else "insufficient_data",
        "components": components,
        "importance": station.importance,
        "importance_explanation": station.importance_explanation,
        "safety_escalation": station.safety_escalation,
    }


def _component(weight: int, score: float | None, coverage: str) -> dict:
    score = round(score, 1) if score is not None else None
    return {
        "weight": weight,
        "score": score,
        "contribution": round(score * weight / 100, 1) if score is not None else None,
        "coverage": coverage,
    }


def ranked_health(snapshot: Snapshot, sort: SortMode = "priority") -> list[dict]:
    rows = [station_health(station, snapshot) for station in snapshot.stations]

    def key(row):
        if row["health_score"] is None:
            return (row["station_id"],)
        if sort == "health":
            return (row["health_score"], row["station_id"])
        if sort == "importance":
            return (-row["importance"], row["health_score"], row["station_id"])
        return (row["health_score"], -row["importance"], row["station_id"])

    scored = sorted((row for row in rows if row["health_score"] is not None), key=key)
    insufficient = sorted((row for row in rows if row["health_score"] is None), key=lambda row: row["station_id"])
    return scored + insufficient


def history(station: Station, connector_id: str | None = None) -> list[dict]:
    if connector_id is not None and connector_id not in {c.connector_id for c in station.connectors}:
        raise ValueError("unknown connector_id for station")
    return [
        {
            "date": day.date,
            "eligible_minutes": day.eligible_minutes,
            "available_minutes": day.available_minutes,
            "attempts": (
                day.connector_attempts[connector_id].model_dump()
                if connector_id is not None
                else day.attempts.model_dump()
            ),
            "faults": [
                fault.model_dump(mode="json")
                for fault in (day.faults or [])
                if connector_id is None or fault.scope == "station" or fault.connector_id == connector_id
            ] if day.faults is not None else None,
        }
        for day in station.daily
    ]


def maintenance_records(station: Station, connector_id: str | None = None) -> list[dict]:
    if connector_id is not None and connector_id not in {c.connector_id for c in station.connectors}:
        raise ValueError("unknown connector_id for station")
    return [
        record.model_dump(mode="json")
        for record in station.maintenance
        if connector_id is None or record.connector_id in (None, connector_id)
    ]
