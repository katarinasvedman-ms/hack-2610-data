import unittest

from app.data import list_stations
from app.scoring import calculate_health


class HealthScoringTests(unittest.TestCase):
    def test_weighted_score_uses_the_documented_components(self):
        history = [
            {
                "date": f"2026-10-{day:02d}",
                "eligible_minutes": 100,
                "available_minutes": 80,
                "start_attempts": 10,
                "successful_starts": 9,
                "fault_codes": [],
            }
            for day in (1, 2)
        ]
        result = calculate_health(history)
        self.assertEqual(result["score"], 88.0)
        self.assertEqual(result["status"], "scored")

    def test_recurring_fault_days_are_counted_once_across_codes(self):
        history = [
            {
                "date": f"2026-10-{day:02d}",
                "eligible_minutes": 100,
                "available_minutes": 100,
                "start_attempts": 1,
                "successful_starts": 1,
                "fault_codes": codes,
            }
            for day, codes in ((1, ["A", "B"]), (2, ["A"]), (3, []))
        ]
        result = calculate_health(history)
        self.assertEqual(result["recurring_fault_codes"], ["A"])
        self.assertEqual(result["recurring_fault_days"], 2)
        self.assertEqual(result["components"]["recurring_faults"]["score"], 33.3)

    def test_zero_attempts_and_missing_required_data_are_not_reweighted(self):
        history = [
            {
                "date": "2026-10-01",
                "eligible_minutes": 100,
                "available_minutes": None,
                "start_attempts": 0,
                "successful_starts": 0,
                "fault_codes": [],
            }
        ]
        result = calculate_health(history)
        self.assertIsNone(result["score"])
        self.assertEqual(result["status"], "insufficient_data")
        self.assertIsNone(result["components"]["availability"]["score"])
        self.assertIsNone(result["components"]["charging_success"]["score"])

    def test_mock_dataset_has_twelve_stations_and_separate_safety_flags(self):
        stations = list_stations()
        self.assertEqual(len(stations), 12)
        self.assertTrue(all(station["data_classification"] == "MOCK" for station in stations))
        flagged = [station for station in stations if station["safety_reports"]]
        self.assertEqual([station["station_id"] for station in flagged], ["SE-004"])
        self.assertTrue(any(station["health"]["status"] == "insufficient_data" for station in stations))


if __name__ == "__main__":
    unittest.main()
