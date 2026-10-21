import base64
import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.staticfiles import StaticFiles

from .data import DATA_CLASSIFICATION, SNAPSHOT_AT, get_station, list_stations


logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    station_id: str = Field(min_length=1, max_length=32)
    question: str = Field(min_length=3, max_length=1500)


app = FastAPI(title="Asset Health PoC", docs_url=None, redoc_url=None)
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


def _authenticated_identity(request: Request) -> str | None:
    if os.getenv("AUTH_REQUIRED", "false").lower() != "true":
        return "local-developer"
    principal = request.headers.get("x-ms-client-principal")
    if not principal:
        raise HTTPException(status_code=401, detail="Sign in with your organizational account.")
    try:
        claims = json.loads(base64.b64decode(principal, validate=True))
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Invalid authenticated identity.") from None
    if not isinstance(claims, dict):
        raise HTTPException(status_code=401, detail="Invalid authenticated identity.")
    identity = claims.get("userId") or claims.get("userDetails")
    if not identity:
        raise HTTPException(status_code=401, detail="Authenticated identity is missing.")
    return str(identity)


@app.get("/api/health")
def health(_identity: str | None = Depends(_authenticated_identity)) -> dict[str, Any]:
    project_configured = bool(os.getenv("AZURE_AI_PROJECT_ENDPOINT") and os.getenv("AZURE_AI_AGENT_NAME"))
    iq_configured = bool(os.getenv("FOUNDRY_IQ_MCP_URL") and os.getenv("FOUNDRY_IQ_PROJECT_CONNECTION_ID"))
    return {
        "status": "ok",
        "data_classification": DATA_CLASSIFICATION,
        "snapshot_at": SNAPSHOT_AT,
        "foundry_agent_configured": project_configured,
        "foundry_iq_configured": iq_configured,
    }


@app.get("/api/stations")
def stations(_identity: str | None = Depends(_authenticated_identity)) -> dict[str, Any]:
    summaries = [
        {key: value for key, value in station.items() if key not in {"history", "maintenance_records", "safety_reports"}}
        for station in list_stations()
    ]
    return {
        "snapshot_at": SNAPSHOT_AT,
        "data_classification": DATA_CLASSIFICATION,
        "stations": summaries,
    }


@app.get("/api/stations/{station_id}")
def station_detail(
    station_id: str,
    _identity: str | None = Depends(_authenticated_identity),
) -> dict[str, Any]:
    station = get_station(station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found.")
    return station


@app.get("/api/stations/{station_id}/history")
def station_history(
    station_id: str,
    days: int = 30,
    _identity: str | None = Depends(_authenticated_identity),
) -> dict[str, Any]:
    station = get_station(station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found.")
    if days < 1 or days > 30:
        raise HTTPException(status_code=422, detail="days must be between 1 and 30.")
    return {"station_id": station_id, "history": station["history"][-days:]}


@app.post("/api/chat")
def investigate(body: ChatRequest, request: Request) -> dict[str, Any]:
    identity = _authenticated_identity(request)
    station = get_station(body.station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found.")
    foundry_configured = all(
        os.getenv(name)
        for name in (
            "AZURE_AI_PROJECT_ENDPOINT",
            "AZURE_AI_AGENT_NAME",
            "FOUNDRY_IQ_MCP_URL",
            "FOUNDRY_IQ_PROJECT_CONNECTION_ID",
        )
    )
    if not foundry_configured:
        raise HTTPException(
            status_code=503,
            detail="Foundry agent and Foundry IQ are not configured. Chat is unavailable; no demo answer was substituted.",
        )
    try:
        from .foundry import run_investigation

        answer = run_investigation(body.question, station, str(identity))
    except Exception as error:
        logger.exception("Foundry investigation failed")
        raise HTTPException(
            status_code=502,
            detail="The Foundry investigation could not be completed. Dashboard data remains available.",
        ) from error
    return answer


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str) -> FileResponse:
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found.")
    index = FRONTEND_DIST / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="Frontend is not built.")
    requested = FRONTEND_DIST / path
    if path and requested.is_file() and requested.resolve().is_relative_to(FRONTEND_DIST.resolve()):
        return FileResponse(requested)
    return FileResponse(index)
