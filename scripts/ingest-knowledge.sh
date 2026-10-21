#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! -f "$1" ]]; then
  echo "Primer not ingested. Usage: $0 /path/to/user-supplied-primer.pdf" >&2
  exit 2
fi
primer="$1"
if [[ "${primer##*.}" != "pdf" && "${primer##*.}" != "PDF" ]] || [[ "$(head -c 5 "$primer")" != "%PDF-" ]]; then
  echo "Input must be a readable PDF; no file was uploaded." >&2
  exit 2
fi
if [[ -z "${STORAGE_ACCOUNT_NAME:-}" ]]; then
  echo "Set STORAGE_ACCOUNT_NAME to the dedicated PoC storage account." >&2
  exit 2
fi

az account show --only-show-errors >/dev/null
container="${KNOWLEDGE_CONTAINER:-asset-health-knowledge}"
az storage container create \
  --account-name "$STORAGE_ACCOUNT_NAME" \
  --name "$container" \
  --auth-mode login \
  --public-access off \
  --only-show-errors >/dev/null

for document in knowledge/*.md; do
  title="$(sed -n 's/^title: //p' "$document" | head -n 1)"
  document_date="$(sed -n 's/^date: //p' "$document" | head -n 1)"
  section="$(sed -n 's/^section: //p' "$document" | head -n 1)"
  az storage blob upload \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --container-name "$container" \
    --name "authored/$(basename "$document")" \
    --file "$document" \
    --auth-mode login \
    --overwrite true \
    --metadata "title=$title" source=AssetHealthPoCReference version=0.1.0 "documentdate=$document_date" "section=$section" classification=DEMO_ONLY \
    --only-show-errors >/dev/null
done

az storage blob upload \
  --account-name "$STORAGE_ACCOUNT_NAME" \
  --container-name "$container" \
  --name "user-supplied/$(basename "$primer")" \
  --file "$primer" \
  --auth-mode login \
  --overwrite true \
  --metadata "title=$(basename "$primer")" source=UserSuppliedPrimer version=unverified documentdate=unknown section=source_pdf "ingestiondate=$(date -u +%F)" classification=USER_SUPPLIED \
  --only-show-errors >/dev/null

echo "Source files uploaded to the private blob container."
echo "The user-supplied primer's provenance still requires confirmation."
echo "Foundry IQ source/index configuration and retrieval/citation verification are NOT completed by this upload."
