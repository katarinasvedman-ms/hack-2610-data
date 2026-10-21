from collections import defaultdict
from typing import Any


WEIGHTS = {"availability": 0.4, "charging_success": 0.4, "recurring_faults": 0.2}


def calculate_health(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Score a station only when every required component has usable evidence."""
    gaps: list[str] = []
    observed_days = len(history)
    eligible = sum(day["eligible_minutes"] for day in history if day.get("eligible_minutes") is not None)
    available = sum(day["available_minutes"] for day in history if day.get("available_minutes") is not None)
    has_complete_availability = observed_days > 0 and all(
        day.get("eligible_minutes") is not None and day.get("available_minutes") is not None
        for day in history
    )
    availability = (
        round(100 * available / eligible, 1)
        if has_complete_availability and eligible > 0
        else None
    )
    if availability is None:
        gaps.append("Availability needs complete eligible and available-minute observations.")

    attempts_complete = observed_days > 0 and all(day.get("start_attempts") is not None for day in history)
    attempts = sum(day["start_attempts"] for day in history if day.get("start_attempts") is not None)
    successes = sum(day["successful_starts"] for day in history if day.get("successful_starts") is not None)
    successes_complete = all(day.get("successful_starts") is not None for day in history)
    charging_success = (
        round(100 * successes / attempts, 1)
        if attempts_complete and successes_complete and attempts > 0
        else None
    )
    if charging_success is None:
        gaps.append("Charging success needs recorded starts and at least one start attempt.")

    faults_complete = observed_days > 0 and all(day.get("fault_codes") is not None for day in history)
    recurring_dates: dict[str, set[str]] = defaultdict(set)
    if faults_complete:
        for day in history:
            for code in set(day["fault_codes"]):
                recurring_dates[code].add(day["date"])
    recurring_codes = sorted(code for code, dates in recurring_dates.items() if len(dates) >= 2)
    affected_days = {
        date
        for code in recurring_codes
        for date in recurring_dates[code]
    }
    recurring_faults = (
        round(100 * (1 - len(affected_days) / observed_days), 1)
        if faults_complete
        else None
    )
    if recurring_faults is None:
        gaps.append("Recurring-fault scoring needs fault observations for every observed day.")

    components = {
        "availability": {"score": availability, "weight": WEIGHTS["availability"]},
        "charging_success": {"score": charging_success, "weight": WEIGHTS["charging_success"]},
        "recurring_faults": {"score": recurring_faults, "weight": WEIGHTS["recurring_faults"]},
    }
    is_scored = not gaps
    total = (
        round(sum(component["score"] * component["weight"] for component in components.values()), 1)
        if is_scored
        else None
    )
    return {
        "score": total,
        "status": "scored" if is_scored else "insufficient_data",
        "components": components,
        "observed_days": observed_days,
        "recurring_fault_codes": recurring_codes,
        "recurring_fault_days": len(affected_days),
        "data_gaps": gaps,
    }
