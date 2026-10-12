#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

docker compose up -d --wait --wait-timeout 120
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d postgres \
  < infra/local/postgres/init.sql

printf '%s\n' \
  'PostgreSQL and Azurite are running on loopback ports from .env or docker-compose defaults.' \
  'Database roles are provisioned idempotently. Run `pnpm local:services:status` to inspect health.'
