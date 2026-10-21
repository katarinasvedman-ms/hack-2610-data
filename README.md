# Northstar Asset Health PoC

An evidence-led demo for prioritizing charging-station investigation. It
includes a station portfolio, station detail and history, transparent health
components, separate business importance, and a read-only Microsoft Foundry
investigator grounded through a Foundry IQ knowledge base.

This is maintenance decision support, not a live monitoring system, automatic
diagnosis, validated failure prediction, or charger-control interface.

## Current status

| Capability | PoC implementation | Production replacement |
| --- | --- | --- |
| Station telemetry and charging attempts | Deterministic fictional fixture; fixed 30-day snapshot ending 2026-10-20 | CSMS/OCPP status and fault records plus backend charging-start events |
| Maintenance history | Two synthetic work-order records per station | Work-order/CMMS integration with source IDs and timestamps |
| Business importance | Separate synthetic 0–100 context value; excluded from health score | Approved asset register, utilization, and business-impact inputs |
| Safety reports | One clearly fictional, separately displayed human-review flag | Verified support/inspection workflow; never inferred from a health score |
| Health scoring | Deterministic transparent rules in `backend/app/scoring.py` | Validate source mappings, observation windows, and thresholds with operations |
| Assistant | Real Foundry prompt agent setup script; uses read-only station tools and a Foundry IQ MCP connection when configured | Configure a supported model deployment, Foundry IQ knowledge base, and project connection |
| Grounding documents | Two clearly labelled PoC-authored references in `knowledge/` | Add approved official/vendor references and the user-supplied public primer |
| Identity | Entra authentication via Azure Container Apps built-in authentication in the deployment template | Set tenant/app registration, roles, and production access policy |

No live Azure deployment, Foundry agent invocation, IQ retrieval, or document
ingestion was performed for this repository change. The local PDF files and
Azure credentials from the planning session are not included. Chat reports an
explicit unavailable/error state rather than substituting a canned answer.

## Health score

The backend computes a score from a 30-day history:

- **Availability (40%)** = observed available minutes / eligible minutes.
- **Charging success (40%)** = successful starts / recorded start attempts.
- **Recurring faults (20%)** = `100 × (1 − recurring-fault days / observed days)`.
  A code is recurring only when the same station-side code appears on at least
  two distinct days; each affected day counts once, even if multiple codes
  recur.

All three inputs are required. Missing required observations or no recorded
start attempts yield **insufficient data**, not a reweighted score. An explicit
empty fault list is different from a missing fault observation. The dashboard
groups insufficient-data stations separately, then sorts scored stations by
lowest score, higher business importance, and station ID. Business importance
does not affect health. Safety reports remain independent escalation flags.

The score is a demo prioritization aid. It does not establish root cause,
physical safety, or future failure probability.

## Run locally

Requirements: Node.js 22 or later and Python 3.12 or later.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt

cd frontend
npm ci
npm run dev
```

In a second terminal, start the API:

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

The Vite development server proxies `/api` to `http://127.0.0.1:8000`. Open
the URL printed by Vite. Local mode permits unauthenticated read-only use;
Foundry chat remains unavailable until the agent and IQ environment variables
below are configured.

Run checks from the repository root:

```bash
cd backend && python -m unittest discover -s tests -v
cd ..
npm --prefix frontend run lint
npm --prefix frontend run build
```

## Configure Foundry and Foundry IQ

The backend uses the Azure AI Projects SDK, `DefaultAzureCredential`, and the
Foundry agent's OpenAI-compatible Responses endpoint. It does not contain a
mock chat provider. The setup script creates a versioned prompt agent with
three bounded, read-only functions (`list_station_health`,
`get_station_history`, and `get_maintenance_records`) plus an MCP tool for the
Foundry IQ knowledge base.

1. Create a dedicated Foundry IQ knowledge base backed by a dedicated Azure AI
   Search service. `infra/knowledge.bicep` can provision a small Search service,
   private Blob container, and the Search service's read role on that storage.
   This template creates the storage and Search resources, not the Foundry IQ
   knowledge-base object.
2. Upload `knowledge/asset-health-scoring.md` and
   `knowledge/charging-operations-reference.md` to the knowledge source. The
   EV charging primer from the planning session is **not in this checkout and
   has not been ingested**. If you have an approved copy, upload it yourself:

   ```bash
   az storage blob upload \
     --account-name "$ASSET_HEALTH_STORAGE_ACCOUNT" \
     --container-name knowledge-docs \
     --name EV-Charging-E-Mobility-Primer.pdf \
     --file "$EV_CHARGING_PRIMER_PDF" \
     --auth-mode login \
     --overwrite
   ```

   The signed-in uploader needs `Storage Blob Data Contributor` on the account.
   Grant the Search/knowledge-base identity only the data access required by
   the chosen Foundry IQ ingestion configuration.
3. Create the knowledge-base MCP project connection in Foundry, and obtain its
   exact MCP URL and project connection ID from that configuration. Grant the
   Container App managed identity the appropriate project/agent and knowledge
   source permissions. Do not copy an access token or credential into the
   repository.
4. Set these environment variables in the backend environment:

   ```bash
   AZURE_AI_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
   AZURE_AI_AGENT_NAME=asset-health-investigator
   AZURE_AI_MODEL_DEPLOYMENT=<available-model-deployment>
   FOUNDRY_IQ_MCP_URL=<exact-knowledge-base-MCP-URL>
   FOUNDRY_IQ_PROJECT_CONNECTION_ID=<Foundry-project-connection-ID>
   ```

   Use an authenticated Azure CLI login locally. The deployment uses the
   Container App's managed identity. Verify model availability and RBAC in the
   target Foundry project before creating the agent.
5. From `backend/`, create the prompt-agent version:

   ```bash
   python scripts/configure_agent.py
   ```

The setup script reports the created agent version, but does not create the
knowledge base or its project connection. Agent and IQ calls require real Azure
access and have not been cloud-verified here. Foundry IQ citations are returned
only when the service provides citation annotations; the application never
fabricates citations.

Official integration reference:
[Connect Foundry IQ to a Foundry agent](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/foundry-iq-connect).

## Azure deployment

The app is a single Container App serving the built React site and FastAPI API
on the same origin. `infra/main.bicep` enables Entra authentication with
Container Apps built-in authentication and uses a user-assigned managed
identity for ACR pulls and Azure SDK access. Create a single-tenant Entra app
registration and client secret separately; pass the secret as a secure Bicep
parameter, never as a checked-in file.

The first template provisions a private ACR:

```bash
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file infra/registry.bicep \
  --parameters registryName="$ACR_NAME"
```

Build and push the container image with Azure:

```bash
az acr build --registry "$ACR_NAME" --image asset-health:latest .
```

Deploy the app after setting up the Foundry agent and the Entra app registration:

```bash
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file infra/main.bicep \
  --parameters \
    appName="$APP_NAME" \
    registryName="$ACR_NAME" \
    containerImage="$ACR_LOGIN_SERVER/asset-health:latest" \
    tenantId="$TENANT_ID" \
    entraClientId="$ENTRA_CLIENT_ID" \
    entraClientSecret="$ENTRA_CLIENT_SECRET" \
    projectEndpoint="$AZURE_AI_PROJECT_ENDPOINT" \
    agentName="$AZURE_AI_AGENT_NAME" \
    iqMcpUrl="$FOUNDRY_IQ_MCP_URL" \
    iqProjectConnectionId="$FOUNDRY_IQ_PROJECT_CONNECTION_ID"
```

After deployment, add the output app URL's
`/.auth/login/aad/callback` URL as a **Web** redirect URI on the Entra app
registration. Grant the Container App identity the minimum roles needed for
Foundry agent invocation, the project MCP connection, and knowledge retrieval.
The exact Foundry and Search role assignment depends on how the target project
and knowledge base were created; verify these in Azure before enabling users.
The templates do not modify existing demo resources.

## API

- `GET /api/health` — service and provider configuration status.
- `GET /api/stations` — ranked station summary.
- `GET /api/stations/{station_id}` — station detail and synthetic records.
- `GET /api/stations/{station_id}/history?days=30` — bounded history.
- `POST /api/chat` — Foundry investigation for a station.

In Azure, Container Apps authentication protects the app, and the API checks
the authenticated principal before chat. Each question is a fresh Foundry
Responses request; prior user messages are not sent or shared across requests.
All tools are read-only and limited to the static PoC dataset.

## Limitations and next steps

- Replace synthetic telemetry, work orders, safety reports, and importance
  values with approved source integrations, retaining source IDs, event times,
  and missing-data semantics.
- Validate score definitions and review thresholds with operations; the
  synthetic distribution does not demonstrate predictive accuracy.
- Ingest and verify the user-supplied primer and approved vendor/OCPP guidance
  before relying on Foundry IQ citations.
- Verify the actual Entra callback, identity roles, Foundry agent version,
  model quota, MCP connection, IQ retrieval, and citations in the deployment
  environment.
- Add integration tests and cloud smoke tests when non-production Azure
  credentials and an approved knowledge source are available.
