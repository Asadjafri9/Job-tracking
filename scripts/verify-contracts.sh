#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

temporary_directory="$(mktemp -d)"
trap 'rm -rf "$temporary_directory"' EXIT

env -u PYTHONPATH uv run --project apps/api python scripts/export_openapi.py \
  --output "$temporary_directory/openapi.json"
corepack pnpm --dir apps/web exec openapi-typescript \
  "$temporary_directory/openapi.json" \
  --output "$temporary_directory/generated.ts"

cmp docs/openapi.json "$temporary_directory/openapi.json"
cmp apps/web/src/api/generated.ts "$temporary_directory/generated.ts"
printf 'OpenAPI and TypeScript client are current.\n'
