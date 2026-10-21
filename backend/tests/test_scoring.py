from datetime import datetime, timezone
import pytest

from app.fixture import build_snapshot
from app.models import AttemptCounts, DailyObservation, Snapshot, Station
from app.scoring import history, ranked_health, station_health


def test_scoring_uses_documented_weighted_formula():
    snapshot = build_snapshot()
    station = snapshot.stations[0]
    result = station_health(station, snapshot)
    components = result["components"]
    expected = sum(
        components[name]["score"] * weight / 100
        for name, weight in (("availability", 40), ("charging_success", 40), ("station_faults", 20))
    )
    assert result["health_score"] == round(expected, 1)
    assert all(components[name]["weight"] == weight for name, weight in (
        ("availability", 40), ("charging_success", 40), ("station_faults", 20)
    ))


def test_authentication_failures_are_not_station_faults():
    snapshot = build_snapshot()
    station = next(item for item in snapshot.stations if item.station_id == "ST-002")
    result = station_health(station, snapshot)
    assert result["components"]["station_faults"]["score"] == 100


def test_insufficient_evidence_never_receives_perfect_score():
    snapshot = build_snapshot()
    station = next(item for item in snapshot.stations if item.station_id == "ST-012")
    result = station_health(station, snapshot)
    assert result["status"] == "insufficient_data"
    assert result["health_score"] is None
    assert result["components"]["charging_success"]["score"] is None


def test_recurring_fault_code_counts_affected_days_once():
    snapshot = build_snapshot()
    station = next(item for item in snapshot.stations if item.station_id == "ST-003")
    result = station_health(station, snapshot)
    assert result["components"]["station_faults"]["score"] == pytest.approx(round(100 * (1 - 4 / 30), 1))


def test_priority_order_keeps_insufficient_stations_separate_and_stable():
    rows = ranked_health(build_snapshot())
    scores = [row["health_score"] for row in rows if row["health_score"] is not None]
    assert scores == sorted(scores)
    assert rows[-1]["status"] == "insufficient_data"
    assert [row["station_id"] for row in rows] == [
        row["station_id"] for row in ranked_health(build_snapshot())
    ]


def test_connector_scope_is_validated():
    snapshot = build_snapshot()
    station = snapshot.stations[0]
    try:
        history(station, "unknown")
    except ValueError as error:
        assert "unknown connector" in str(error)
    else:
        raise AssertionError("unknown connector was accepted")


def test_fixture_relationship_validation_rejects_unknown_fault_connector():
    snapshot = build_snapshot()
    invalid = snapshot.model_dump()
    invalid["stations"][0]["daily"][0]["faults"] = [{
        "fault_id": "bad",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "code": "DEMO",
        "category": "station_side",
        "scope": "connector",
        "connector_id": "missing",
        "description": "Invalid relationship",
    }]
    try:
        Snapshot.model_validate(invalid)
    except Exception:
        return
    raise AssertionError("invalid connector reference was accepted")
