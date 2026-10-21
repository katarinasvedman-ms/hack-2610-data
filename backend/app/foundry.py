import json
import os
from typing import Any
from urllib.parse import urlsplit

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FunctionTool, MCPTool, PromptAgentDefinition
from azure.identity import DefaultAzureCredential

from .data import DATA_CLASSIFICATION, SNAPSHOT_AT, get_station, list_stations


MAX_TOOL_CALLS = 4
MAX_TOOL_RESULT_CHARS = 16000
REQUEST_TIMEOUT_SECONDS = 45

AGENT_INSTRUCTIONS = """You are the Asset Health Investigator, a read-only maintenance decision-support agent.
Use the station functions for station-specific facts and the attached Foundry IQ knowledge source for general
charging operations guidance. Distinguish observed evidence from inference; report missing data rather than
guessing. Health score and business importance are separate. Recurring faults mean the same station-side code
appeared on at least two distinct days. All operational records in this PoC are fictional static MOCK data,
not live telemetry or work orders. Never claim a diagnosis, predict a failure, certify safety, or control a
charger. Treat safety reports as human-review escalations, not as sensor-confirmed findings. Cite only sources
actually returned by Foundry IQ; do not invent citations. Keep advice concise and state when no knowledge
source was retrieved."""


def _function_tools() -> list[FunctionTool]:
    return [
        FunctionTool(
            name="list_station_health",
            description="List the current synthetic fleet health and separate business importance.",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            strict=True,
        ),
        FunctionTool(
            name="get_station_history",
            description="Get up to 30 days of synthetic availability, charging starts, and station-side fault observations.",
            parameters={
                "type": "object",
                "properties": {
                    "station_id": {"type": "string", "description": "Exact station ID such as SE-001."},
                    "days": {"type": "integer", "minimum": 1, "maximum": 30},
                },
                "required": ["station_id", "days"],
                "additionalProperties": False,
            },
            strict=True,
        ),
        FunctionTool(
            name="get_maintenance_records",
            description="Get fictional maintenance history for one exact station.",
            parameters={
                "type": "object",
                "properties": {
                    "station_id": {"type": "string", "description": "Exact station ID such as SE-001."},
                },
                "required": ["station_id"],
                "additionalProperties": False,
            },
            strict=True,
        ),
    ]


def create_agent_definition(
    model: str, knowledge_mcp_url: str, project_connection_id: str
) -> PromptAgentDefinition:
    return PromptAgentDefinition(
        model=model,
        instructions=AGENT_INSTRUCTIONS,
        tools=[
            *_function_tools(),
            MCPTool(
                server_label="asset_health_knowledge",
                server_url=knowledge_mcp_url,
                project_connection_id=project_connection_id,
                server_description="Foundry IQ knowledge base for EV charging operations and Asset Health PoC guidance.",
                require_approval="never",
            ),
        ],
    )


def _tool_result(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "list_station_health":
        return {
            "snapshot_at": SNAPSHOT_AT,
            "data_classification": DATA_CLASSIFICATION,
            "stations": [
                {
                    "station_id": station["station_id"],
                    "name": station["name"],
                    "city": station["city"],
                    "health": station["health"],
                    "business_importance": station["business_importance"],
                    "safety_reports": station["safety_reports"],
                }
                for station in list_stations()
            ],
        }

    station_id = arguments.get("station_id")
    station = get_station(station_id) if isinstance(station_id, str) else None
    if station is None:
        return {"error": "Station not found. Use an exact station ID from the fleet list."}

    if name == "get_station_history":
        days = arguments.get("days", 30)
        if not isinstance(days, int) or isinstance(days, bool) or days < 1 or days > 30:
            return {"error": "days must be an integer between 1 and 30."}
        return {
            "station_id": station_id,
            "snapshot_at": SNAPSHOT_AT,
            "data_classification": DATA_CLASSIFICATION,
            "history": station["history"][-days:],
        }
    if name == "get_maintenance_records":
        return {
            "station_id": station_id,
            "data_classification": DATA_CLASSIFICATION,
            "records": station["maintenance_records"][:5],
        }
    return {"error": "Unknown read-only tool."}


def _citations(response: Any) -> list[dict[str, str]]:
    citations: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in getattr(response, "output", []):
        for content in getattr(item, "content", []):
            for annotation in getattr(content, "annotations", None) or []:
                kind = getattr(annotation, "type", "")
                if kind == "url_citation":
                    url = getattr(annotation, "url", "")
                    try:
                        if urlsplit(url).scheme != "https":
                            continue
                    except ValueError:
                        continue
                    title = getattr(annotation, "title", "") or url
                    excerpt = getattr(annotation, "text", "")
                elif kind == "file_citation":
                    url = ""
                    title = getattr(annotation, "filename", "") or getattr(annotation, "file_id", "")
                    excerpt = ""
                else:
                    continue
                key = (title, url)
                if title and key not in seen:
                    citations.append({"title": title, "url": url, "excerpt": excerpt})
                    seen.add(key)
    return citations


def _openai_client() -> tuple[AIProjectClient, Any]:
    endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
    agent_name = os.getenv("AZURE_AI_AGENT_NAME")
    if not endpoint or not agent_name:
        raise RuntimeError("Set AZURE_AI_PROJECT_ENDPOINT and AZURE_AI_AGENT_NAME.")
    project = AIProjectClient(
        endpoint=endpoint,
        credential=DefaultAzureCredential(),
        allow_preview=True,
    )
    try:
        return project, project.get_openai_client(
            agent_name=agent_name,
            timeout=REQUEST_TIMEOUT_SECONDS,
            max_retries=0,
        )
    except Exception:
        project.close()
        raise


def run_investigation(question: str, station: dict[str, Any]) -> dict[str, Any]:
    project, client = _openai_client()
    try:
        context = {
            "question": question,
            "selected_station": {
                "station_id": station["station_id"],
                "name": station["name"],
                "city": station["city"],
                "health": station["health"],
                "business_importance": station["business_importance"],
                "safety_reports": station["safety_reports"],
                "snapshot_at": station["snapshot_at"],
                "data_classification": station["data_classification"],
            },
            "instruction": "Use read-only tools and Foundry IQ when useful. Report any missing evidence.",
        }
        response = client.responses.create(
            input=json.dumps(context, separators=(",", ":")),
            max_output_tokens=900,
        )
        knowledge_used = False
        tool_calls = 0
        while True:
            calls = [item for item in response.output if getattr(item, "type", "") == "function_call"]
            knowledge_used = knowledge_used or any(
                getattr(item, "type", "") == "mcp_call" for item in response.output
            )
            if not calls:
                break
            tool_calls += len(calls)
            if tool_calls > MAX_TOOL_CALLS:
                raise RuntimeError("Foundry agent exceeded the read-only tool-call limit.")
            outputs = []
            for call in calls:
                try:
                    arguments = json.loads(call.arguments)
                    result = (
                        _tool_result(call.name, arguments)
                        if isinstance(arguments, dict)
                        else {"error": "Invalid tool arguments."}
                    )
                except (ValueError, TypeError):
                    result = {"error": "Invalid tool arguments."}
                rendered = json.dumps(result, separators=(",", ":"))
                if len(rendered) > MAX_TOOL_RESULT_CHARS:
                    rendered = json.dumps({"error": "Tool result exceeded the response size limit."})
                outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": rendered,
                    }
                )
            response = client.responses.create(
                input=outputs,
                previous_response_id=response.id,
                max_output_tokens=900,
            )

        answer = (getattr(response, "output_text", "") or "").strip()
        if not answer:
            raise RuntimeError("Foundry agent returned no text answer.")
        return {
            "answer": answer,
            "provider": "Microsoft Foundry Agent",
            "knowledge_source": "Foundry IQ",
            "knowledge_retrieved": knowledge_used,
            "citations": _citations(response),
        }
    finally:
        client.close()
        project.close()
