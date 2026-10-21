#!/usr/bin/env bash
set -euo pipefail

: "${RESOURCE_GROUP:?Set RESOURCE_GROUP to the dedicated PoC resource group}"
if [[ "${DELETE_ASSET_HEALTH_POC:-}" != "YES" ]]; then
  echo "Set DELETE_ASSET_HEALTH_POC=YES only after confirming this dedicated resource group can be deleted." >&2
  exit 2
fi
az account show --only-show-errors >/dev/null
tag="$(az group show --name "$RESOURCE_GROUP" --query "tags.assetHealthPoc" -o tsv)"
if [[ "$tag" != "true" ]]; then
  echo "Refusing to delete an untagged resource group: $RESOURCE_GROUP" >&2
  exit 2
fi
az group delete --name "$RESOURCE_GROUP" --yes --no-wait --only-show-errors
echo "Deletion requested for the dedicated Asset Health PoC resource group."
