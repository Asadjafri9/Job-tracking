#!/usr/bin/env bash
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # Local setup values are intentionally shared with the API/worker processes.
  source .env
  set +a
fi

if [[ -z "${MIGRATION_DATABASE_URL:-}" ]]; then
  echo "Set MIGRATION_DATABASE_URL to the local copilot_migrator PostgreSQL URL." >&2
  exit 2
fi
if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "Set DATABASE_URL to the local copilot_runtime PostgreSQL URL." >&2
  exit 2
fi
if [[ -z "${AUTH_DATABASE_URL:-}" || -z "${WORKER_DATABASE_URL:-}" ]]; then
  echo "Set AUTH_DATABASE_URL and WORKER_DATABASE_URL to their local PostgreSQL role URLs." >&2
  exit 2
fi

python3 - "$MIGRATION_DATABASE_URL" "$DATABASE_URL" "$AUTH_DATABASE_URL" "$WORKER_DATABASE_URL" <<'PY'
import sys
from urllib.parse import urlparse

urls = [urlparse(value) for value in sys.argv[1:]]
allowed_hosts = {"localhost", "127.0.0.1", "::1"}
if any(url.hostname not in allowed_hosts for url in urls):
    raise SystemExit("V-DB refuses non-loopback database URLs")
targets = {(url.hostname, url.port, url.path) for url in urls}
if len(targets) != 1:
    raise SystemExit("V-DB role URLs must target the same local database")
users = [url.username for url in urls]
if users != ["copilot_migrator", "copilot_runtime", "copilot_auth", "copilot_worker"]:
    raise SystemExit("V-DB URLs must use the dedicated migrator/runtime/auth/worker roles")
PY

export DB001_DATABASE_URL="$MIGRATION_DATABASE_URL"
export DB002_RUNTIME_DATABASE_URL="$DATABASE_URL"
export DB002_AUTH_DATABASE_URL="$AUTH_DATABASE_URL"
export DB002_WORKER_DATABASE_URL="$WORKER_DATABASE_URL"
export DB001_LOCAL_SEED=1
export PYTHONPATH="apps/api${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

uv run --locked --project apps/api alembic -c apps/api/alembic.ini upgrade head
uv run --locked --project apps/api python -m app.db.seed
uv run --locked --project apps/api alembic -c apps/api/alembic.ini check
uv run --locked --project apps/api pytest -c apps/api/pyproject.toml --rootdir apps/api apps/api/tests/test_db001_schema.py -q
uv run --locked --project apps/api pytest -c apps/api/pyproject.toml --rootdir apps/api apps/api/tests/test_db002_tenant_rls.py -q
