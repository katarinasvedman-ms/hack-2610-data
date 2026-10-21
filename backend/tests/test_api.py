import base64
import json
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from app.main import ChatRequest, health, investigate, station_detail, station_history, stations


def request_with_headers(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/chat",
            "headers": headers or [],
            "query_string": b"",
        }
    )


class ApiTests(unittest.TestCase):
    def test_station_list_is_summary_and_detail_includes_history(self):
        result = stations()
        self.assertEqual(len(result["stations"]), 12)
        self.assertNotIn("history", result["stations"][0])
        self.assertEqual(len(station_detail("SE-001")["history"]), 30)
        self.assertEqual(len(station_history("SE-001", 7)["history"]), 7)

    def test_unknown_station_returns_not_found(self):
        with self.assertRaises(HTTPException) as raised:
            station_detail("SE-999")
        self.assertEqual(raised.exception.status_code, 404)

    def test_chat_does_not_return_a_canned_answer_when_not_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as raised:
                investigate(
                    ChatRequest(station_id="SE-001", question="Why is this score low?"),
                    request_with_headers(),
                )
        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("no demo answer", raised.exception.detail)

    def test_chat_requires_an_authenticated_identity_when_configured(self):
        with patch.dict(os.environ, {"AUTH_REQUIRED": "true"}, clear=True):
            with self.assertRaises(HTTPException) as raised:
                investigate(
                    ChatRequest(station_id="SE-001", question="Why is this score low?"),
                    request_with_headers(),
                )
        self.assertEqual(raised.exception.status_code, 401)

    def test_authenticated_principal_is_validated_before_foundry_configuration(self):
        principal = base64.b64encode(json.dumps({"userDetails": "operator"}).encode()).decode()
        headers = [(b"x-ms-client-principal", principal.encode())]
        with patch.dict(os.environ, {"AUTH_REQUIRED": "true"}, clear=True):
            with self.assertRaises(HTTPException) as raised:
                investigate(
                    ChatRequest(station_id="SE-001", question="Why is this score low?"),
                    request_with_headers(headers),
                )
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(health()["data_classification"], "MOCK")


if __name__ == "__main__":
    unittest.main()
