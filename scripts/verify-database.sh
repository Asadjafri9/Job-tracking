#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${MIGRATION_DATABASE_URL:-}" ]]; then
  echo "Set MIGRATION_DATABASE_URL to the local copilot_migrator PostgreSQL URL." >&2
  exit 2
fi

python3 - "$MIGRATION_DATABASE_URL" <<'PY'
import sys
from urllib.parse import urlparse

if urlparse(sys.argv[1]).hostname not in {"localhost", "127.0.0.1", "::1"}:
    raise SystemExit("V-DB refuses non-loopback database URLs")
PY

export DB001_DATABASE_URL="$MIGRATION_DATABASE_URL"
export DB001_LOCAL_SEED=1
export PYTHONPATH="apps/api${PYTHONPATH:+:$PYTHONPATH}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

uv run --locked --project apps/api alembic -c apps/api/alembic.ini upgrade head
uv run --locked --project apps/api python -m app.db.seed
uv run --locked --project apps/api alembic -c apps/api/alembic.ini check
uv run --locked --project apps/api pytest -c apps/api/pyproject.toml --rootdir apps/api apps/api/tests/test_db001_schema.py -q
