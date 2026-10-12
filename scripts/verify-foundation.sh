#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

expected_node="v$(tr -d '\r\n' < .node-version)"
actual_node="$(node --version)"
if [[ "$actual_node" != "$expected_node" ]]; then
  printf 'Expected Node.js %s from .node-version, found %s.\n' "$expected_node" "$actual_node" >&2
  exit 1
fi

expected_pnpm="$(node -e 'process.stdout.write(require("./package.json").packageManager.split("@")[1])')"
actual_pnpm="$(corepack pnpm --version)"
if [[ "$actual_pnpm" != "$expected_pnpm" ]]; then
  printf 'Expected pnpm %s from package.json, found %s.\n' "$expected_pnpm" "$actual_pnpm" >&2
  exit 1
fi

expected_uv="$(tr -d '\r\n' < .uv-version)"
actual_uv="$(uv --version | awk '{print $2}')"
if [[ "$actual_uv" != "$expected_uv" ]]; then
  printf 'Expected uv %s from .uv-version, found %s.\n' "$expected_uv" "$actual_uv" >&2
  exit 1
fi

expected_python="$(tr -d '\r\n' < .python-version)"
actual_python="$(uv run --locked --project apps/api python --version | awk '{print $2}' | cut -d. -f1-2)"
if [[ "$actual_python" != "$expected_python" ]]; then
  printf 'Expected Python %s from .python-version, found %s.\n' "$expected_python" "$actual_python" >&2
  exit 1
fi

corepack pnpm verify:frontend
env -u PYTHONPATH corepack pnpm verify:backend
corepack pnpm verify:contracts
