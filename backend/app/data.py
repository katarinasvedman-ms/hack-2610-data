import random
from datetime import date, timedelta
from typing import Any

from .scoring import calculate_health


SNAPSHOT_DATE = date(2026, 10, 20)
SNAPSHOT_AT = f"{SNAPSHOT_DATE.isoformat()}T23:59:59Z"
DATA_CLASSIFICATION = "MOCK"

PROFILES = [
    ("North Quay", "Stockholm", 98, 98, 0, 2, 30),
    ("Central Market", "Stockholm", 95, 96, 8, 4, 60),
    ("Arlanda Link", "Uppsala", 93, 91, 6, 3, 55),
    ("Harbor East", "Gothenburg", 90, 84, 4, 5, 85),
    ("Forest Road", "Västerås", 88, 89, 5, 3, 45),
    ("Airport South", "Malmö", 86, 80, 3, 4, 75),
    ("Lakeview", "Örebro", 97, 95, 12, 2, 35),
    ("West Gate", "Gothenburg", 82, 86, 4, 5, 90),
    ("University", "Linköping", 94, 78, 3, 4, 65),
    ("Pine Ridge", "Umeå", 89, 92, 6, 3, 40),
    ("Old Town", "Visby", 91, 88, 5, 2, 50),
    ("South Terminal", "Malmö", 87, 83, 4, 4, 70),
]

IMPORTANCE = {1: "Low", 2: "Moderate", 3: "High", 4: "Critical", 5: "Critical"}


def _daily_history(station_number: int, profile: tuple[Any, ...]) -> list[dict[str, Any]]:
    _, _, availability_rate, success_rate, fault_interval, importance, _ = profile
    rng = random.Random(20261021 + station_number)
    history = []
    for offset in range(29, -1, -1):
        day_date = SNAPSHOT_DATE - timedelta(days=offset)
        eligible = 1440
        available = max(0, min(eligible, round(eligible * (availability_rate + rng.uniform(-5, 4)) / 100)))
        attempts = 0 if station_number == 11 else rng.randint(1, 7)
        successful = sum(rng.random() < success_rate / 100 for _ in range(attempts))
        faults: list[str] = []
        if fault_interval and (offset + station_number) % fault_interval == 0:
            faults.append(f"POC-{station_number:02d}-COMM")
        if station_number == 4 and offset in (4, 5):
            faults.append("POC-04-THERMAL")
        if station_number == 12 and offset < 5:
            available_value = None
        else:
            available_value = available
        history.append(
            {
                "date": day_date.isoformat(),
                "eligible_minutes": eligible,
                "available_minutes": available_value,
                "start_attempts": attempts,
                "successful_starts": successful,
                "fault_codes": faults,
            }
        )
    return history


def build_stations() -> list[dict[str, Any]]:
    stations = []
    for number, profile in enumerate(PROFILES, start=1):
        name, city, _, _, _, importance, impact = profile
        station_id = f"SE-{number:03d}"
        history = _daily_history(number, profile)
        health = calculate_health(history)
        stations.append(
            {
                "station_id": station_id,
                "name": name,
                "city": city,
                "region": "Sweden",
                "connector_count": 4 if number % 3 == 0 else 2,
                "power_kw": 150 if number % 2 == 0 else 300,
                "business_importance": {
                    "level": IMPORTANCE[importance],
                    "score": impact,
                    "description": "Separate business context; not included in health score.",
                },
                "health": health,
                "snapshot_at": SNAPSHOT_AT,
                "data_classification": DATA_CLASSIFICATION,
                "history": history,
                "maintenance_records": [
                    {
                        "date": (SNAPSHOT_DATE - timedelta(days=48 + number)).isoformat(),
                        "type": "Inspection",
                        "summary": "Routine connector and enclosure inspection recorded.",
                        "source": "Synthetic PoC work-order fixture",
                    },
                    {
                        "date": (SNAPSHOT_DATE - timedelta(days=110 + number)).isoformat(),
                        "type": "Service",
                        "summary": "Preventive service completed; no live work-order integration.",
                        "source": "Synthetic PoC work-order fixture",
                    },
                ],
                "safety_reports": (
                    [
                        {
                            "date": (SNAPSHOT_DATE - timedelta(days=1)).isoformat(),
                            "label": "Human review required",
                            "summary": "A fictional report noted visible cable damage. Not sensor-confirmed.",
                        }
                    ]
                    if number == 4
                    else []
                ),
            }
        )
    return stations


STATIONS = build_stations()


def list_stations() -> list[dict[str, Any]]:
    return sorted(
        STATIONS,
        key=lambda station: (
            station["health"]["status"] == "scored",
            station["health"]["score"] if station["health"]["score"] is not None else 0,
            -station["business_importance"]["score"],
            station["station_id"],
        ),
    )


def get_station(station_id: str) -> dict[str, Any] | None:
    return next((station for station in STATIONS if station["station_id"] == station_id), None)
