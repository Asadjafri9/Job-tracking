#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

env -u PYTHONPATH uv run --project apps/api python scripts/export_openapi.py \
  --output docs/openapi.json
corepack pnpm --dir apps/web exec openapi-typescript \
  ../../docs/openapi.json \
  --output src/api/generated.ts
