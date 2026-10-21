import asyncio
import json
import os
import re
import threading
import urllib.error
import urllib.request
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .fixture import load_snapshot
from .models import Snapshot
from .scoring import history, maintenance_records, ranked_health, station_health

app = FastAPI(title="Asset Health PoC API", version="0.1.0")
SNAPSHOT: Snapshot = load_snapshot()
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "true").lower() == "true"
_conversation_lock = threading.Lock()
_conversations: dict[tuple[str, UUID], str] = {}
_USER_ID = re.compile(r"^[A-Za-z0-9._@:-]{1,256}$")
_ID_PATTERN = re.compile(r"^[A-Z0-9-]{1,32}$")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None
    station_id: str | None = Field(default=None, max_length=32)


@app.middleware("http")
async def require_container_app_auth(request: Request, call_next):
    if REQUIRE_AUTH and request.url.path.startswith("/api/"):
        user_id = request.headers.get("x-ms-client-principal-id", "")
        principal = request.headers.get("x-ms-client-principal")
        if not user_id or not principal or not _USER_ID.fullmatch(user_id):
            return _json_error(401, "Sign-in is required.")
        request.state.user_id = user_id
    else:
        request.state.user_id = "local-developer"
    return await call_next(request)


@app.get("/api/health")
def get_health(sort: str = "priority", importance: int | None = None):
    if sort not in {"priority", "health", "importance"}:
        raise HTTPException(400, "sort must be priority, health, or importance")
    if importance is not None and not 1 <= importance <= 5:
        raise HTTPException(400, "importance must be between 1 and 5")
    rows = ranked_health(SNAPSHOT, sort=sort)
    if importance is not None:
        rows = [row for row in rows if row["importance"] == importance]
    return {
        "classification": SNAPSHOT.classification,
        "snapshot_at": SNAPSHOT.snapshot_at,
        "window_days": SNAPSHOT.window_days,
        "stations": rows,
    }


@app.get("/api/status")
def get_status():
    return {
        "auth_required": REQUIRE_AUTH,
        "foundry_configured": bool(
            os.getenv("FOUNDRY_PROJECT_ENDPOINT") and os.getenv("FOUNDRY_AGENT_NAME")
        ),
    }


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/api/sources/{source_id}")
def get_approved_source(source_id: str):
    source = APPROVED_SOURCES.get(source_id)
    if source is None or not source.is_file():
        raise HTTPException(404, "Approved source not found.")
    return FileResponse(source, media_type="text/markdown")


@app.get("/api/stations/{station_id}")
def get_station(station_id: str):
    station = _station(station_id)
    return {
        "station": station.model_dump(mode="json", exclude={"daily", "maintenance"}),
        "health": station_health(station, SNAPSHOT),
        "maintenance": maintenance_records(station),
    }


@app.get("/api/stations/{station_id}/history")
def get_station_history(station_id: str, connector_id: str | None = None):
    station = _station(station_id)
    try:
        records = history(station, connector_id)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    return {"station_id": station_id, "connector_id": connector_id, "classification": "MOCK", "days": records}


@app.get("/api/stations/{station_id}/maintenance")
def get_station_maintenance(station_id: str, connector_id: str | None = None):
    station = _station(station_id)
    try:
        records = maintenance_records(station, connector_id)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    return {"station_id": station_id, "classification": "MOCK", "records": records}


@app.post("/api/chat")
async def chat(payload: ChatRequest, request: Request):
    if payload.station_id is not None:
        _station(payload.station_id)
    if not os.getenv("FOUNDRY_PROJECT_ENDPOINT") or not os.getenv("FOUNDRY_AGENT_NAME"):
        raise HTTPException(
            503,
            "Foundry investigation is not configured. Dashboard data remains available.",
        )
    user_id = request.state.user_id
    conversation_id = payload.conversation_id or uuid4()
    with _conversation_lock:
        previous_response_id = _conversations.get((user_id, conversation_id))
    try:
        response_id, answer, activity, citations = await asyncio.wait_for(
            asyncio.to_thread(_invoke_foundry, payload, previous_response_id),
            timeout=65,
        )
    except asyncio.TimeoutError as error:
        raise HTTPException(504, "Foundry investigation exceeded the 65-second request limit.") from error
    with _conversation_lock:
        if (user_id, conversation_id) not in _conversations and len(_conversations) >= 1000:
            _conversations.pop(next(iter(_conversations)))
        _conversations[(user_id, conversation_id)] = response_id
    return {
        "conversation_id": conversation_id,
        "answer": answer,
        "activity": activity,
        "citations": citations,
        "operational_references": _operational_references(activity),
        "classification": "MOCK",
        "notice": "Synthetic PoC records; not live telemetry or a validated diagnosis.",
    }


def _station(station_id: str):
    if not _ID_PATTERN.fullmatch(station_id):
        raise HTTPException(400, "Invalid station identifier.")
    for station in SNAPSHOT.stations:
        if station.station_id == station_id:
            return station
    raise HTTPException(404, "Station not found.")


def _invoke_foundry(payload: ChatRequest, previous_response_id: str | None):
    try:
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        token = credential.get_token("https://ai.azure.com/.default").token
        endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"].rstrip("/")
        if not endpoint.startswith("https://"):
            raise RuntimeError("FOUNDRY_PROJECT_ENDPOINT must use HTTPS.")
        agent_name = os.environ["FOUNDRY_AGENT_NAME"]
        version = os.getenv("FOUNDRY_AGENT_VERSION", "1")
        base = f"{endpoint}/openai/v1/responses"
        input_content: list[dict] = [{"role": "user", "content": payload.message}]
        if payload.station_id:
            input_content[0]["content"] = (
                f"User selected station {payload.station_id}. Use the exact station identifier "
                f"for operational lookups. User question: {payload.message}"
            )
        body: dict = {
            "agent_reference": {"name": agent_name, "version": version},
            "input": input_content,
        }
        if previous_response_id:
            body["previous_response_id"] = previous_response_id
        activity: list[dict] = []
        citations: list[dict] = []
        for _ in range(4):
            response = _post_json(base, body, token)
            response_id = response.get("id")
            if not response_id:
                raise RuntimeError("Foundry response did not contain an id.")
            output = response.get("output", [])
            mcp_calls = [
                item for item in output
                if item.get("type") == "mcp_call" and item.get("status") == "completed"
            ]
            if any(
                item.get("type") == "mcp_call" and item.get("status") in {"failed", "error"}
                for item in output
            ):
                raise RuntimeError("Foundry IQ knowledge retrieval did not complete.")
            activity.extend(
                {"type": "knowledge_retrieval", "status": "completed"}
                for _ in mcp_calls
            )
            citations.extend(_extract_mcp_citations(mcp_calls))
            _, text_citations = _extract_text_and_citations(output)
            citations.extend(text_citations)
            calls = [item for item in output if item.get("type") == "function_call"]
            if not calls:
                answer, _ = _extract_text_and_citations(output)
                if not answer:
                    raise RuntimeError("Foundry returned no answer text.")
                unique_citations = []
                seen_citations = set()
                for citation in citations:
                    key = tuple(
                        citation.get(field)
                        for field in ("title", "url", "section", "page", "source", "version", "date")
                    )
                    if key not in seen_citations:
                        seen_citations.add(key)
                        unique_citations.append(citation)
                return response_id, answer, activity, unique_citations
            results = []
            for call in calls:
                if not isinstance(call.get("call_id"), str) or not call["call_id"]:
                    raise ValueError("Foundry function call is missing call_id.")
                result = _dispatch_tool(call.get("name", ""), call.get("arguments", ""))
                activity.append({
                    "type": "data_tool",
                    "tool": call.get("name"),
                    "status": "completed",
                    "record_refs": _record_references(result),
                })
                serialized = json.dumps(result, default=str)
                if len(serialized) > 100_000:
                    raise RuntimeError("Tool result exceeds the allowed output size.")
                results.append({
                    "type": "function_call_output",
                    "call_id": call.get("call_id"),
                    "output": serialized,
                })
            body = {
                "agent_reference": {"name": agent_name, "version": version},
                "previous_response_id": response_id,
                "input": results,
            }
        raise RuntimeError("Foundry tool round limit reached.")
    except HTTPException:
        raise
    except urllib.error.HTTPError as error:
        detail = error.read(1024).decode("utf-8", "replace")
        raise HTTPException(502, f"Foundry request failed ({error.code}): {detail[:400]}") from error
    except Exception as error:
        raise HTTPException(503, f"Foundry investigation failed: {str(error)[:400]}") from error


def _post_json(url: str, body: dict, token: str) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read(2_000_000))


def _dispatch_tool(name: str, raw_arguments: str):
    if not isinstance(raw_arguments, str):
        raise ValueError("Tool arguments must be a JSON string.")
    if len(raw_arguments) > 8000:
        raise ValueError("Tool arguments exceed the allowed size.")
    arguments = json.loads(raw_arguments)
    if not isinstance(arguments, dict) or set(arguments) - {"station_id", "connector_id", "sort"}:
        raise ValueError("Unsupported tool arguments.")
    if name == "list_station_health":
        if set(arguments) - {"sort"}:
            raise ValueError("list_station_health accepts only the sort argument.")
        sort = arguments.get("sort", "priority")
        if sort not in {"priority", "health", "importance"}:
            raise ValueError("Unsupported sort.")
        return ranked_health(SNAPSHOT, sort=sort)
    if name not in {"get_station_history", "get_maintenance_records"}:
        raise ValueError("Unsupported tool.")
    if set(arguments) - {"station_id", "connector_id"}:
        raise ValueError("Unsupported station tool arguments.")
    station_id = arguments.get("station_id")
    if not isinstance(station_id, str):
        raise ValueError("station_id is required.")
    station = _station(station_id)
    connector_id = arguments.get("connector_id")
    if connector_id is not None and not isinstance(connector_id, str):
        raise ValueError("connector_id must be a string.")
    if name == "get_station_history":
        return {
            "health": station_health(station, SNAPSHOT),
            "health_scope": "station",
            "days": history(station, connector_id),
        }
    if name == "get_maintenance_records":
        return maintenance_records(station, connector_id)
    raise ValueError("Unsupported tool.")


def _extract_text_and_citations(output: list[dict]) -> tuple[str, list[dict]]:
    text = []
    citations = []
    for item in output:
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    text.append(content.get("text", ""))
                    for annotation in content.get("annotations", []):
                        reference = annotation.get("url_citation")
                        url = reference.get("url") if isinstance(reference, dict) else None
                        if isinstance(url, str) and url.startswith("https://"):
                            citations.append(
                                {
                                    "title": str(reference.get("title") or "Source"),
                                    "url": url,
                                }
                            )
    return "\n".join(text).strip(), citations


def _extract_mcp_citations(calls: list[dict]) -> list[dict]:
    citations = []
    for call in calls:
        result = call.get("result")
        if not isinstance(result, dict):
            continue
        candidates = result.get("citations", [])
        if not isinstance(candidates, list):
            continue
        for source in candidates:
            if not isinstance(source, dict):
                continue
            title = source.get("title") or source.get("name")
            if not isinstance(title, str) or not title.strip():
                continue
            citation = {"title": title[:200]}
            url = source.get("url")
            has_location = False
            if isinstance(url, str) and url.startswith("https://"):
                citation["url"] = url
                has_location = True
            section = source.get("section")
            if isinstance(section, str) and section:
                citation["section"] = section[:200]
                has_location = True
            page = source.get("page")
            if isinstance(page, (str, int)) and not isinstance(page, bool):
                citation["page"] = page
                has_location = True
            for field in ("source", "version", "date"):
                value = source.get(field)
                if isinstance(value, str) and value:
                    citation[field] = value[:200]
            if has_location:
                citations.append(citation)
    return citations


def _operational_references(activity: list[dict]) -> list[dict]:
    return [
        {
            "source": "synthetic_fixture",
            "record_type": item["tool"],
            "record_id": record_id,
            "classification": "MOCK",
        }
        for item in activity
        for record_id in item.get("record_refs", [])
    ]


def _record_references(value) -> list[str]:
    references: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in {"station_id", "fault_id", "record_id"} and isinstance(nested, str):
                references.append(nested)
            else:
                references.extend(_record_references(nested))
    elif isinstance(value, list):
        for nested in value:
            references.extend(_record_references(nested))
    return list(dict.fromkeys(references))[:100]


def _json_error(status: int, detail: str):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=status, content={"detail": detail})


STATIC_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"
KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"
APPROVED_SOURCES = {
    "scoring": KNOWLEDGE_DIR / "asset-health-scoring.md",
    "data-dictionary": KNOWLEDGE_DIR / "asset-health-data-dictionary.md",
    "investigation-guide": KNOWLEDGE_DIR / "asset-health-investigation-guide.md",
}
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "API route not found.")
        candidate = (STATIC_DIR / path).resolve()
        if candidate.is_file() and STATIC_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
