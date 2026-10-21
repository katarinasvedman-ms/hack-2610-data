import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

os.environ["REQUIRE_AUTH"] = "false"
from app import main


client = TestClient(main.app)


def test_health_api_exposes_mock_snapshot_and_common_ranking():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["classification"] == "MOCK"
    assert body["window_days"] == 30
    assert len(body["stations"]) == 12
    assert body["stations"][-1]["status"] == "insufficient_data"


def test_health_api_validates_sort_and_importance_filters():
    assert client.get("/api/health?sort=unexpected").status_code == 400
    assert client.get("/api/health?importance=6").status_code == 400
    filtered = client.get("/api/health?importance=5").json()["stations"]
    assert filtered
    assert all(row["importance"] == 5 for row in filtered)


def test_status_reports_auth_and_foundry_configuration_without_claiming_connectivity(monkeypatch):
    monkeypatch.setattr(main, "REQUIRE_AUTH", False)
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("FOUNDRY_AGENT_NAME", raising=False)
    assert client.get("/api/status").json() == {
        "auth_required": False,
        "foundry_configured": False,
    }
    monkeypatch.setattr(main, "REQUIRE_AUTH", True)
    assert client.get("/api/status").status_code == 401
def test_station_history_is_exact_and_connector_bounded():
    station = client.get("/api/stations/ST-001/history").json()
    connector = client.get("/api/stations/ST-001/history?connector_id=1").json()
    assert station["station_id"] == connector["station_id"] == "ST-001"
    assert station["days"][0]["attempts"] != connector["days"][0]["attempts"]
    assert connector["days"][0]["available_minutes"] is None
    assert client.get("/api/stations/ST-001/history?connector_id=99").status_code == 404
    assert client.get("/api/stations/UNKNOWN/history").status_code == 404
    assert client.get("/api/stations/../history").status_code in (400, 404)


def test_tool_dispatch_rejects_unknown_ids_and_malformed_arguments():
    with pytest.raises(HTTPException) as error:
        main._dispatch_tool("get_station_history", '{"station_id":"UNKNOWN"}')
    assert error.value.status_code == 404
    with pytest.raises(ValueError):
        main._dispatch_tool("list_station_health", '{"station_id":"ST-001"}')
    with pytest.raises(ValueError):
        main._dispatch_tool("get_station_history", "[]")
    with pytest.raises(ValueError):
        main._dispatch_tool("get_station_history", '{"station_id":"ST-001","sort":"health"}')


def test_chat_reports_missing_foundry_instead_of_using_a_fallback(monkeypatch):
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("FOUNDRY_AGENT_NAME", raising=False)
    response = client.post("/api/chat", json={"message": "What should I inspect?"})
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_chat_requires_container_app_identity_when_enabled(monkeypatch):
    monkeypatch.setattr(main, "REQUIRE_AUTH", True)
    assert client.get("/api/health").status_code == 401
    assert client.get(
        "/api/health",
        headers={"x-ms-client-principal-id": "operator-1", "x-ms-client-principal": "{}"},
    ).status_code == 200
    assert client.get("/api/sources/scoring").status_code == 401


def test_approved_source_access_is_allowlisted_and_returns_reference_text():
    source = client.get("/api/sources/scoring")
    assert source.status_code == 200
    assert source.headers["content-type"].startswith("text/markdown")
    assert "illustrative" in source.text.lower()
    assert client.get("/api/sources/not-approved").status_code == 404


def test_conversation_response_ids_are_isolated_by_signed_in_user(monkeypatch):
    monkeypatch.setattr(main, "REQUIRE_AUTH", True)
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.test/api/projects/asset")
    monkeypatch.setenv("FOUNDRY_AGENT_NAME", "asset-health-investigator")
    main._conversations.clear()
    calls = []

    def fake_foundry(payload, previous):
        calls.append(previous)
        return f"response-{len(calls)}", "Test-only response", [], []

    monkeypatch.setattr(main, "_invoke_foundry", fake_foundry)
    conversation_id = str(uuid4())
    body = {"message": "Explain this station", "conversation_id": conversation_id}
    alice = {"x-ms-client-principal-id": "alice", "x-ms-client-principal": "{}"}
    bob = {"x-ms-client-principal-id": "bob", "x-ms-client-principal": "{}"}
    assert client.post("/api/chat", json=body, headers=alice).status_code == 200
    assert client.post("/api/chat", json=body, headers=alice).status_code == 200
    assert client.post("/api/chat", json=body, headers=bob).status_code == 200
    assert calls == [None, "response-1", None]


def test_foundry_citations_only_include_resolvable_http_urls():
    answer, citations = main._extract_text_and_citations([
        {
            "type": "message",
            "content": [{
                "type": "output_text",
                "text": "See the reference.",
                "annotations": [
                    {"url_citation": {"title": "Approved guide", "url": "https://example.test/guide"}},
                    {"url_citation": {"title": "Local file", "url": "file:///etc/passwd"}},
                ],
            }],
        }
    ])
    assert answer == "See the reference."
    assert citations == [{"title": "Approved guide", "url": "https://example.test/guide"}]


def test_mcp_citations_keep_only_actual_traceable_metadata():
    citations = main._extract_mcp_citations([{
        "type": "mcp_call",
        "status": "completed",
        "result": {
            "citations": [
                {
                    "title": "Scoring definition",
                    "section": "Formula",
                    "page": 2,
                    "source": "AssetHealthPoCReference",
                    "version": "0.1.0",
                    "date": "2026-10-21",
                },
                {"title": "Untrusted path", "url": "file:///etc/passwd"},
                {"url": "https://example.test/no-title"},
            ]
        },
    }])
    assert citations == [{
        "title": "Scoring definition",
        "section": "Formula",
        "page": 2,
        "source": "AssetHealthPoCReference",
        "version": "0.1.0",
        "date": "2026-10-21",
    }]


def test_failed_iq_retrieval_is_reported_as_a_service_failure(monkeypatch):
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.test/api/projects/asset")
    monkeypatch.setenv("FOUNDRY_AGENT_NAME", "asset-health-investigator")

    class Credential:
        def get_token(self, scope):
            return type("Token", (), {"token": "test-token"})()

    monkeypatch.setattr("azure.identity.DefaultAzureCredential", lambda: Credential())
    monkeypatch.setattr(main, "_post_json", lambda *args: {
        "id": "response-1",
        "output": [
            {"type": "mcp_call", "status": "failed"},
            {"type": "message", "content": [{"type": "output_text", "text": "Fallback text"}]},
        ],
    })
    with pytest.raises(HTTPException) as error:
        main._invoke_foundry(main.ChatRequest(message="Explain the rules"), None)
    assert error.value.status_code == 503
    assert "knowledge retrieval did not complete" in error.value.detail


def test_foundry_tool_rounds_are_capped(monkeypatch):
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.test/api/projects/asset")
    monkeypatch.setenv("FOUNDRY_AGENT_NAME", "asset-health-investigator")

    class Credential:
        def get_token(self, scope):
            assert scope == "https://ai.azure.com/.default"
            return type("Token", (), {"token": "test-token"})()

    monkeypatch.setattr("azure.identity.DefaultAzureCredential", lambda: Credential())
    requests = []

    def function_call(url, body, token):
        requests.append(body)
        return {
            "id": f"response-{len(requests)}",
            "output": [{
                "type": "function_call",
                "name": "get_station_history",
                "arguments": '{"station_id":"ST-001"}',
                "call_id": str(len(requests)),
            }],
        }

    monkeypatch.setattr(main, "_post_json", function_call)
    with pytest.raises(HTTPException) as error:
        main._invoke_foundry(main.ChatRequest(message="Explain ST-001"), None)
    assert error.value.status_code == 503
    assert "round limit" in error.value.detail
    assert len(requests) == 4
