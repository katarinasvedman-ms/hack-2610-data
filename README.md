# Asset Health PoC

A small maintenance decision-support demo for identifying synthetic charging
stations that may deserve investigation. It is not automatic diagnosis, live
charger control, a safety assessment, or a validated failure-prediction system.
The repository intentionally replaces the unrelated station-mock-data files
with a separately generated fixture for this PoC.

## Current verification status

| Area | Status |
| --- | --- |
| Deterministic 12-station, 30-day fixture and shared score implementation | Implemented and locally tested |
| Dashboard, station detail, and API-backed chat/error UI | Implemented; local production build and browser check pending |
| Foundry Responses API client, bounded tool dispatch, Entra middleware | Implemented; not tested against a real Foundry project |
| Azure Container Apps, Entra, Search, and Blob deployment definitions | Added; Bicep and Azure deployment are not cloud-validated |
| Foundry IQ knowledge base, MCP connection, agent creation, source indexing | Not provisioned or verified |
| Public EV-Charging-E-Mobility primer | **Not ingested.** It was not available in this checkout. |
| Internal idea PDF | Not included or uploaded |
| Azure identity and permissions | Not available in this checkout; no provisioning was attempted |

No deployment, agent invocation, IQ retrieval, citation, or Azure resource creation
is claimed as successful. The chat endpoint returns an explicit service error
until the configured Foundry agent is reachable; it has no canned-answer fallback.

## Run locally

Requirements: Python 3.12, Node.js 24, and npm.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements-dev.txt
REQUIRE_AUTH=false PYTHONPATH=backend python -m uvicorn app.main:app --app-dir backend --reload
```

In another terminal:

```bash
npm ci --prefix frontend
npm run dev --prefix frontend
```

Open <http://localhost:5173>. Vite proxies `/api` and `/healthz` to the local
FastAPI server at port 8000. Local auth is disabled by default for development;
never expose this local server as a deployed application. Chat returns HTTP 503
until Foundry is configured.

Run the complete local verification set:

```bash
./scripts/verify.sh
```

Focused selectors:

```bash
PYTHONPATH=backend python -m pytest backend/tests/test_scoring.py -q
PYTHONPATH=backend python -m pytest backend/tests/test_api.py -q
npm test --prefix frontend -- src/format.test.ts
npm run typecheck --prefix frontend
npm run build --prefix frontend
```

Regenerate the fixed fixture with:

```bash
PYTHONPATH=backend python backend/data/generate_fixture.py
```

The generator is deterministic. The checked-in JSON snapshot is loaded and
validated at application start; all data and tool responses are labelled
`MOCK`, with snapshot time `2026-10-21T00:00:00Z`.

## Architecture

```text
Browser -- same-origin --> Entra-protected Azure Container App
                                |-- built React/Vite dashboard
                                |-- FastAPI, shared fixture and scorer
                                `-- Foundry Responses API (server-side identity)
                                      |-- read-only app-side function tools
                                      `-- Foundry IQ knowledge-base MCP tool
```

The browser never receives a provider token. The deployed Container App uses a
dedicated user-assigned managed identity for ACR image pulls and server-side
Foundry calls. Grant that app identity the minimum Foundry project role needed
to invoke the configured agent. Foundry calls use `DefaultAzureCredential` and
the `https://ai.azure.com/.default` scope. In local development, Azure Identity's
normal developer credential chain is used only when a Foundry request is made.

`GET /api/health` and station detail use the same `station_health` and
`ranked_health` functions used by the agent's operational tools:

- `list_station_health`
- `get_station_history`
- `get_maintenance_records`

`/api/status` reports only whether Entra enforcement and Foundry configuration
are set; it does not claim provider or IQ connectivity. The UI checks the
provider when a user submits a question and reports failures directly.

The function definitions and schemas to configure on the Foundry agent are in
[`infra/agent-tools.json`](infra/agent-tools.json). Tool dispatch accepts exact
station IDs, bounds arguments, rounds, provider response size and request time,
and rejects unknown station/connector identifiers. Tool results contain
operational record IDs; document citations are mapped only from returned
Foundry reference annotations or structured MCP citations. No arbitrary
filesystem paths are rendered as links. Known authored PoC references can be
opened through a fixed, allowlisted same-origin Markdown endpoint (protected by
the deployed Entra ingress). Other links are used only when returned as HTTPS
citations by Foundry; the private user-supplied primer is not copied to the app.

Conversation response IDs are keyed by authenticated principal ID plus caller
conversation ID, capped at 1,000 in-memory conversations, and are not persisted.
The deployment deliberately uses one replica because that state is process-local.
Restarting the app clears conversations. A production replacement should use a
durable encrypted store partitioned by the verified Entra subject.

## Synthetic score and prioritization

One fixed 30-day window is used everywhere. The illustrative, unvalidated score:

1. **Availability (40%)** = observed available minutes / observed eligible
   minutes × 100. A day missing either value is excluded from this component's
   denominator, not treated as zero availability.
2. **Charging success (40%)** = successful starts / recorded successful plus
   failed starts × 100. Failed attempts are included. Zero attempts means no
   score for this component.
3. **Recurring station-side faults (20%)** = 100 × (1 − affected observed
   days / days with known fault observations). A code is recurring when it is
   observed on at least two distinct days; each affected day counts once.

Missing component evidence is not silently reweighted: if any component cannot
be computed, the station is shown in an **Assessment needed** group with no
health score. Each component shows its weight, contribution, and coverage.
Authorization, roaming, and payment failures are distinct from station-side
faults. Business importance (1–5, with a scenario explanation) is an independent
demo input. Default order is lowest scored health, highest importance, then
station ID; unscored rows are grouped separately. Health-only and importance-
first sorting are available. Safety escalation is a separate flag, never
averaged into the score.

The fixture includes stable, declining, recurring-fault, connectivity,
repeated-repair, high-use, low-volume, incomplete-evidence, and separate
escalation scenarios. Some observations are deliberately missing. The fixture
does not represent live OCPP/OCPI, payment, roaming, or monitoring systems.

## Foundry and Foundry IQ setup boundary

The backend calls the configured project endpoint's OpenAI-compatible Responses
route (`/openai/v1/responses`) with an `agent_reference` containing the
configured agent name and version. It expects an agent named
`asset-health-investigator` (or the configured equivalent) with the three
function schemas in `infra/agent-tools.json` and an approved Foundry IQ MCP
knowledge-base tool. Function calls are executed by the backend against the
same snapshot and scorer as the dashboard. The backend never interprets retrieved
document text as executable instructions.

The setup tasks below require a separately authorized Foundry operator. They
cannot be completed or claimed from this source checkout:

1. Confirm the selected project, model, Responses API, agent function calling,
   and knowledge-base MCP support in the target region and deployment.
2. Create a new versioned prompt agent; do not modify another demo's agent.
   Apply [`infra/agent-instructions.md`](infra/agent-instructions.md),
   `infra/agent-tools.json`, the `knowledge/` evidence-handling rules, and
   an MCP connection for the dedicated `asset-health-knowledge` knowledge base.
3. Create the Azure AI Search data source, index, and Foundry IQ knowledge base
   using the current supported workflow for the selected Foundry project. Use
   the dedicated storage container and only the Foundry project identity with
   the least roles required. The Bicep deployment can assign the Foundry project
   identity Search service/index contributor and Blob reader roles scoped to the
   dedicated PoC resources; confirm these permissions meet current service
   requirements before deployment.
   Map the authored-source title, source, version, date, and section metadata,
   plus extraction-generated page references, into the IQ index and citation
   schema. Verify the mapping against retrieved results.
4. Run authenticated real-agent tests for a station question, a comparison,
   unknown IDs, missing evidence, a source-backed scoring question, and an IQ
   retrieval. Verify actual record references, source titles, sections/pages,
   and citation links. A blob upload is not proof of indexing or retrieval.

Once the agent, knowledge base, app, and identity permissions are configured,
run the real-cloud smoke check from an authorized developer environment:

```bash
FOUNDRY_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project> \
FOUNDRY_AGENT_NAME=asset-health-investigator \
FOUNDRY_AGENT_VERSION=1 \
python scripts/smoke-foundry.py
```

The check fails unless it observes the station-history function call, a
completed IQ MCP call, a returned title plus source location/link, and a response
that explicitly labels the fixture `MOCK`. It was not run in this checkout.

The project-specific API shape and tool wiring have not been validated against
Azure from this environment. Microsoft Learn links for the operator to confirm
current integration details:

- [Foundry Responses API](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/responses?view=foundry-classic)
- [Foundry Agent Service](https://learn.microsoft.com/azure/ai-foundry/agents/overview)
- [Azure Container Apps authentication](https://learn.microsoft.com/azure/container-apps/authentication)
- [Azure AI Search role-based access control](https://learn.microsoft.com/azure/search/search-security-rbac)
- [Authorize Blob access with Microsoft Entra ID](https://learn.microsoft.com/azure/storage/blobs/authorize-access-azure-active-directory)

## Public primer ingestion

The public primer was absent and remains **not ingested**. The implementation
does not invent its contents. If an authorized user supplies the approved PDF,
upload the authored PoC references and that PDF to the private Blob container:

```bash
STORAGE_ACCOUNT_NAME=<dedicated-storage-account> \
  ./scripts/ingest-knowledge.sh /path/to/EV-Charging-E-Mobility-Primer.pdf
```

The script requires an Azure CLI login with Blob upload rights and a PDF file.
It uploads no other local files and does not upload the internal idea PDF. It
does not configure an IQ index, knowledge base, MCP connection, or claim
successful retrieval. Confirm the source and its provenance, then complete the
Foundry setup and citation verification above. The three authored references in
[`knowledge/`](knowledge/) are explicitly demo-only, versioned PoC material;
they are not manufacturer-approved service guidance.

## Azure deployment

Deployment requires Docker, Azure CLI, an active subscription, a dedicated
resource group, permission to provision resources and role assignments, a
configured Entra application, and an already configured Foundry project/agent.
No deployment was attempted here.

Set the required deployment values in the shell; do not commit them:

```bash
export RESOURCE_GROUP=rg-asset-health-poc
export LOCATION=<supported-region>
export ACR_NAME=<globally-unique-dedicated-registry>
export APP_NAME=asset-health-poc
export SEARCH_SERVICE_NAME=<globally-unique-search-name>
export STORAGE_ACCOUNT_NAME=<globally-unique-storage-name>
export TENANT_ID=<tenant-id>
export ENTRA_CLIENT_ID=<app-registration-client-id>
export ENTRA_CLIENT_SECRET=<app-registration-secret>
export FOUNDRY_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
export FOUNDRY_AGENT_NAME=asset-health-investigator
export FOUNDRY_AGENT_VERSION=1
export FOUNDRY_PRINCIPAL_ID=<foundry-project-managed-identity-object-id>
./scripts/deploy.sh
```

`scripts/deploy.sh` refuses an existing untagged resource group or registry,
creates a dedicated basic ACR if needed, builds/pushes the image, and deploys
[`infra/main.bicep`](infra/main.bicep). The deployment creates a Container Apps
environment, app, Entra authentication config, Log Analytics workspace, private
Blob container, and dedicated Azure AI Search service. `SEARCH_SKU` defaults
to `basic` as a proposed small tier, **not as a confirmed Foundry IQ-compatible
SKU or region**; validate current regional/model/indexing requirements before
running. Search public networking is enabled for service connectivity but uses
Entra/RBAC authentication; no search key is sent to the browser. Review the
effective network rules and roles before using real data.

The app requires Entra sign-in and returns 401 for unauthenticated requests.
The Bicep output includes the app identity object ID. Assign that identity the
minimum supported Foundry project invoke role before chat is expected to work.
After deployment, add the reported
`https://<app-host>/.auth/login/aad/callback` URI to the app registration and
verify tenant/audience restrictions. Do not make the app anonymous to work
around missing consent or permissions. The API's `REQUIRE_AUTH=true` check is
an additional guard for Container Apps' trusted Easy Auth identity headers.

Cost categories are the dedicated ACR Basic registry, Search service tier,
Blob Storage LRS capacity/transactions, Container Apps CPU/memory/ingress, and
Log Analytics ingestion/retention. Region, quota, Search tier, telemetry
volume, and pricing have not been checked; use the Azure Pricing Calculator
before deployment. The only cleanup script, `scripts/cleanup.sh`, refuses to
operate without explicit confirmation and the `assetHealthPoc=true` resource
group tag. It deletes the entire dedicated resource group; do not use it for a
shared group. It never targets the unrelated demo resources.

## Real-versus-demo matrix

| Area | This PoC | Production replacement / verification |
| --- | --- | --- |
| Station health, fault, connector, attempt and maintenance data | Fixed generated synthetic records | Approved station management, telemetry, charging attempt and work-order systems with validated identity/time mappings |
| Health formula and importance values | Illustrative rules and hand-authored demo context | Calibrated, reviewed metric definitions; validate against representative operational history |
| Dashboard/API | Local code; intended same-origin Container App | Complete Azure deployment, Entra sign-in and permission verification |
| Identity | Local development bypass; deployed Bicep requires Entra and app-side auth guard | Confirm correct tenant/app consent, callback, allowed audience, managed identity and RBAC |
| Agent and IQ | Real client code and tool manifest; no agent, IQ KB, index or MCP connection verified | Create and smoke-test a versioned Foundry agent and dedicated IQ/Search/Blob grounding |
| Knowledge documents | Three authored demo-only references | User-supplied, approved public primer plus authorized operational references and manufacturer material |
| Citations | Only returned HTTPS annotations or structured MCP source citations are mapped | Verify source/page resolution against actual retrieval; empty citations are surfaced honestly |
| Charger actions, diagnosis, safety, prediction | Not implemented; no claims | Out of PoC scope |

## Tests and support boundaries

Automated coverage validates score arithmetic and recurrence, zero-attempt and
missing evidence, connector/station boundaries, identifier relationships,
priority ordering, API errors/authentication, tool argument validation, citation
mapping, and per-user conversation isolation. Frontend tests cover score labels
and snapshot formatting. These tests use synthetic fixtures and narrowly scoped
test doubles; they do not validate Azure APIs, deployment, Foundry behavior,
knowledge indexing, or real citations.
