# Agent notes

## Git

- Never add AI attribution to commits: no "Generated with Devin", no
  `Co-Authored-By` trailers, no AI tool mentions in commit messages or PRs.
- Work happens on `work`; PRs target `develop`; never commit to `main`.

## Local verification

- `~/.cache` is root-owned on this machine — set `UV_CACHE_DIR=/tmp/uv-cache`
  and `COREPACK_HOME=/tmp/corepack` before running `uv`/`corepack`.
- `pnpm` is only available via `corepack pnpm`.
- API tests: `uv run --locked --project apps/api pytest -c apps/api/pyproject.toml --rootdir apps/api`
  with `PYTHONPATH=apps/api`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, and the DB
  role URLs mapped as in `scripts/verify-database.sh` (`DB001_DATABASE_URL`,
  `DB002_RUNTIME_DATABASE_URL`, `DB002_AUTH_DATABASE_URL`,
  `DB002_WORKER_DATABASE_URL`, `JOB001_SCHEDULER_DATABASE_URL`,
  `DB001_LOCAL_SEED=1`). Async tests need `-p anyio`.
- Ruff scope is `apps/api/app` + `apps/api/tests` run from `apps/api`
  (alembic files carry pre-existing violations).
- Web checks: `corepack pnpm format:check lint typecheck test build` in `apps/web`.
- Contracts: `bash scripts/verify-contracts.sh`.

## Constraints

- Free tier only — never provision paid resources; do not touch Azure or
  GitHub credentials.
