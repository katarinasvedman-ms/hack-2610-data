import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from app.foundry import create_agent_definition


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    endpoint = required("AZURE_AI_PROJECT_ENDPOINT")
    agent_name = required("AZURE_AI_AGENT_NAME")
    model = required("AZURE_AI_MODEL_DEPLOYMENT")
    knowledge_url = required("FOUNDRY_IQ_MCP_URL")
    connection_id = required("FOUNDRY_IQ_PROJECT_CONNECTION_ID")
    project = AIProjectClient(
        endpoint=endpoint,
        credential=DefaultAzureCredential(),
        allow_preview=True,
    )
    try:
        result = project.agents.create_version(
            agent_name=agent_name,
            definition=create_agent_definition(model, knowledge_url, connection_id),
            description="Read-only Asset Health investigator grounded by Foundry IQ.",
        )
        print(f"Created Foundry agent {agent_name!r}, version {result.version}.")
    finally:
        project.close()


if __name__ == "__main__":
    main()
