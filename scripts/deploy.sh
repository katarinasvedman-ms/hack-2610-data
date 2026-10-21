#!/usr/bin/env bash
set -euo pipefail

required=(RESOURCE_GROUP LOCATION ACR_NAME APP_NAME SEARCH_SERVICE_NAME STORAGE_ACCOUNT_NAME TENANT_ID ENTRA_CLIENT_ID ENTRA_CLIENT_SECRET FOUNDRY_PROJECT_ENDPOINT FOUNDRY_AGENT_NAME FOUNDRY_PRINCIPAL_ID)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Required environment variable is missing: $name" >&2
    exit 2
  fi
done

if [[ "$FOUNDRY_PROJECT_ENDPOINT" != https://* ]]; then
  echo "FOUNDRY_PROJECT_ENDPOINT must be the HTTPS Foundry project endpoint." >&2
  exit 2
fi

az account show --only-show-errors >/dev/null
if az group show --name "$RESOURCE_GROUP" --query "tags.assetHealthPoc" -o tsv 2>/dev/null | grep -qx true; then
  echo "Using the previously tagged Asset Health PoC resource group."
elif az group show --name "$RESOURCE_GROUP" >/dev/null 2>&1; then
  echo "Refusing to deploy into an existing untagged resource group: $RESOURCE_GROUP" >&2
  exit 2
else
  az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --tags assetHealthPoc=true purpose=asset-health-demo --only-show-errors >/dev/null
fi

if az acr show --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --query "tags.assetHealthPoc" -o tsv 2>/dev/null | grep -qx true; then
  echo "Using the previously tagged dedicated registry."
elif az acr show --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" >/dev/null 2>&1; then
  echo "Refusing to reuse an untagged registry: $ACR_NAME" >&2
  exit 2
else
  az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --sku Basic --admin-enabled false --tags assetHealthPoc=true purpose=asset-health-demo --only-show-errors >/dev/null
fi

registry_server="$(az acr show --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --query loginServer -o tsv)"
image_tag="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
image="$registry_server/asset-health:$image_tag"
az acr login --name "$ACR_NAME" --only-show-errors
docker build --pull --tag "$image" --file Dockerfile .
docker push "$image"

parameter_file="$(mktemp)"
chmod 600 "$parameter_file"
trap 'rm -f "$parameter_file"' EXIT
export RESOURCE_GROUP LOCATION APP_NAME ACR_NAME IMAGE="$image" TENANT_ID ENTRA_CLIENT_ID ENTRA_CLIENT_SECRET FOUNDRY_PROJECT_ENDPOINT FOUNDRY_AGENT_NAME FOUNDRY_AGENT_VERSION="${FOUNDRY_AGENT_VERSION:-1}" SEARCH_SERVICE_NAME STORAGE_ACCOUNT_NAME FOUNDRY_PRINCIPAL_ID SEARCH_SKU="${SEARCH_SKU:-basic}"
python - "$parameter_file" <<'PY'
import json
import os
import sys

names = {
    "appName": "APP_NAME",
    "location": "LOCATION",
    "registryName": "ACR_NAME",
    "image": "IMAGE",
    "tenantId": "TENANT_ID",
    "entraClientId": "ENTRA_CLIENT_ID",
    "entraClientSecret": "ENTRA_CLIENT_SECRET",
    "foundryProjectEndpoint": "FOUNDRY_PROJECT_ENDPOINT",
    "foundryAgentName": "FOUNDRY_AGENT_NAME",
    "foundryAgentVersion": "FOUNDRY_AGENT_VERSION",
    "searchServiceName": "SEARCH_SERVICE_NAME",
    "storageAccountName": "STORAGE_ACCOUNT_NAME",
    "foundryPrincipalId": "FOUNDRY_PRINCIPAL_ID",
    "searchSku": "SEARCH_SKU",
}
parameters = {name: {"value": os.environ[key]} for name, key in names.items()}
with open(sys.argv[1], "w", encoding="utf-8") as output:
    json.dump({"$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#", "contentVersion": "1.0.0.0", "parameters": parameters}, output)
PY

deployment_name="asset-health-$(date -u +%Y%m%d%H%M%S)"
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$deployment_name" \
  --template-file infra/main.bicep \
  --parameters "@$parameter_file" \
  --only-show-errors \
  --output none

app_url="$(az deployment group show --resource-group "$RESOURCE_GROUP" --name "$deployment_name" --query "properties.outputs.appUrl.value" -o tsv)"
echo "Deployment submitted. App URL: $app_url"
echo "Add $app_url/.auth/login/aad/callback as the Entra app registration redirect URI before sign-in verification."
