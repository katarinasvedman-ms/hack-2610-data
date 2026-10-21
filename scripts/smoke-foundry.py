#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.main import _dispatch_tool, _extract_mcp_citations, _extract_text_and_citations


def main() -> int:
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").rstrip("/")
    agent_name = os.environ.get("FOUNDRY_AGENT_NAME", "asset-health-investigator")
    version = os.environ.get("FOUNDRY_AGENT_VERSION", "1")
    if not endpoint.startswith("https://"):
        raise SystemExit("Set FOUNDRY_PROJECT_ENDPOINT to the HTTPS Foundry project endpoint.")

    from azure.identity import DefaultAzureCredential

    token = DefaultAzureCredential().get_token("https://ai.azure.com/.default").token
    url = f"{endpoint}/openai/v1/responses"
    body = {
        "agent_reference": {"name": agent_name, "version": version},
        "input": [{
            "role": "user",
            "content": (
                "Use get_station_history for the exact synthetic station ST-001, then explain "
                "the documented demo scoring rule and cite an approved knowledge source with "
                "its title and page or section. Clearly identify the data as MOCK."
            ),
        }],
    }
    tool_names: set[str] = set()
    citations: list[dict] = []
    knowledge_calls = 0
    answer = ""
    for _ in range(4):
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                result = json.loads(response.read(2_000_000))
        except urllib.error.HTTPError as error:
            detail = error.read(1024).decode("utf-8", "replace")
            raise SystemExit(f"Foundry request failed ({error.code}): {detail[:400]}") from error

        response_id = result.get("id")
        if not response_id:
            raise SystemExit("Foundry response did not contain an id.")
        output = result.get("output", [])
        completed_mcp = [
            item for item in output
            if item.get("type") == "mcp_call" and item.get("status") == "completed"
        ]
        knowledge_calls += len(completed_mcp)
        citations.extend(_extract_mcp_citations(completed_mcp))
        answer, response_citations = _extract_text_and_citations(output)
        citations.extend(response_citations)
        calls = [item for item in output if item.get("type") == "function_call"]
        if not calls:
            break
        outputs = []
        for call in calls:
            tool_name = call.get("name", "")
            call_id = call.get("call_id")
            if not isinstance(call_id, str) or not call_id:
                raise SystemExit("Foundry function call did not contain call_id.")
            tool_names.add(tool_name)
            payload = _dispatch_tool(tool_name, call.get("arguments", ""))
            serialized = json.dumps(payload, default=str)
            if len(serialized) > 100_000:
                raise SystemExit("Tool result exceeded the output-size limit.")
            outputs.append({
                "type": "function_call_output",
                "call_id": call_id,
                "output": serialized,
            })
        body = {
            "agent_reference": {"name": agent_name, "version": version},
            "previous_response_id": response_id,
            "input": outputs,
        }
    else:
        raise SystemExit("Foundry tool round limit reached.")

    traceable = [
        citation for citation in citations
        if citation.get("title") and (
            citation.get("url") or citation.get("section") or citation.get("page")
        )
    ]
    if "get_station_history" not in tool_names:
        raise SystemExit("No live get_station_history function call was observed.")
    if knowledge_calls == 0:
        raise SystemExit("No completed Foundry IQ MCP retrieval was observed.")
    if not traceable:
        raise SystemExit("No source citation with a title and traceable location was returned.")
    if "MOCK" not in answer.upper():
        raise SystemExit("The response did not identify the synthetic data as MOCK.")
    print(
        "PASS: live Foundry function call, completed IQ MCP retrieval, "
        f"and {len(traceable)} traceable citation(s) observed."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
