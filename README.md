# Job-tracking

An application copilot planned with **React + FastAPI + PostgreSQL + Azure**.

The first complete release covers three flows:

1. **Autofill:** build a confirmed profile from personal details, resume, LinkedIn PDF and cover letter; fill supported job-form answers/options; ask the user to review; record their submission evidence in the dashboard.
2. **Email applications:** personalize an editable message and open Gmail compose, with copy fallback and manual attachments/send. No Gmail connection prompt.
3. **Job updates:** check up to five saved public career sources at 09:00 in the user's timezone and show deduplicated in-app notifications.

Users can supply OpenRouter/DeepSeek, xAI Grok and Gemini keys, with encrypted saved credentials and an explicitly enabled fallback order. A submit click records an attempt; opening Gmail records a compose event. Confirmed application status requires the evidence defined in the plan.

The browser extension assists with form filling but leaves review and final submission to the user.

## Start here

- [Implementation plan](plan.md): scope, decisions, milestone order and release gates.
- [Product design brief](docs/DESIGN_BRIEF.md): Rolevo logo, visual direction, UX principles, screens and accessibility/validation guidance.
- [Interactive design preview](design-exploration/README.md): browser-only implementation of the design direction; no backend or product data is connected.
- [Implementation tasks](docs/TASKS.md): dependencies, acceptance and future verification for each task.
- [Identity setup](docs/AUTH_SETUP.md): local synthetic OIDC, extension sign-in, and real-tenant prerequisites.
- [Requirements](docs/PRD.md), [architecture](docs/ARCHITECTURE.md), [review resolutions](docs/PLAN_REVIEW.md) and [progress](docs/PROGRESS.md).

**Implementation status:** SET-001–003 are complete; SET-004 adds frozen workspace verification and synthetic CI. `apps/web` is the React application shell and `apps/api` is the FastAPI service foundation with local-only dependency health checks and synthetic fixtures. The design preview remains a separate static HTML/CSS/JavaScript reference; it is not connected to application data. Product authentication, persistence, provider routing, and deployment remain future work. No connected Azure services were used or provisioned.

## Local development

Prerequisites: Node.js 22.16.0, its bundled Corepack, Python 3.12, uv 0.11.32, and Docker Compose. Runtime pins are in `.node-version`, `.python-version`, and `.uv-version`; pnpm 10.33.3 is pinned by the root `package.json`.

```sh
if [ ! -f .env ]; then cp .env.example .env; fi
corepack pnpm local:services:up
corepack pnpm install --frozen-lockfile
corepack pnpm dev:web
```

The local PostgreSQL/Azurite containers bind only to `127.0.0.1` on ports 55432 and 11000–11002 by default. `local:services:up` waits for both containers, then provisions the separate migration/runtime/auth/worker PostgreSQL roles through `psql` without asking Docker Desktop to mount the repository folder. Override the host ports through `.env` when needed. `local:services:down` stops the containers and preserves their named data volumes.

If `.env` already exists, preserve its secrets and update its loopback service URLs and host-port values to match the new defaults instead of replacing the file.

In another terminal, run the API:

```powershell
corepack pnpm dev:api
```

Apply the database migrations and run the database-backed acceptance checks:

```powershell
corepack pnpm verify:database
```

To start the loopback-only synthetic OIDC, provider, and source fixtures, use a third terminal:

```powershell
corepack pnpm dev:mocks
```

The web app serves on `http://127.0.0.1:5173`; API liveness and readiness are at `http://127.0.0.1:18000/health/live` and `/health/ready`. Local readiness verifies a `SELECT 1` using the restricted runtime role and authenticates to Azurite using its emulator-only account. It returns HTTP 200 when both checks pass and reports database schema compatibility as unverified until migrations are implemented. The API and fake OIDC/provider/source service bind to loopback at port 18000 and 18101 by default; both can be overridden with `API_HOST_PORT` and `MOCKS_HOST_PORT`. Local/test credentials and the test KEK must never be reused outside local/test. Production rejects fake endpoints, the test KEK adapter, missing secrets and enabled local mocks. Run `corepack pnpm verify:foundation` to check the pinned Node/pnpm/Python/uv versions and execute the implemented V-F/V-B/V-C foundation checks. GitHub Actions uses the frozen JS/Python locks and this same verification scope; it needs no secrets or connected services. For V-B's optional local-service integration, set `SET002_LOCAL_SERVICES=1` and the local settings from `.env` before running `corepack pnpm verify:backend`. The separately registered synthetic extension checks are available as `corepack pnpm verify:extension`; they are not part of foundation CI or browser/site compatibility validation. Planned product-feature gates remain future work.
The web app serves on `http://127.0.0.1:5173`; API liveness and readiness are at `http://127.0.0.1:18000/health/live` and `/health/ready`. Local readiness verifies a `SELECT 1` using the restricted runtime role and authenticates to Azurite using its emulator-only account. It returns HTTP 200 when both checks pass and reports database schema compatibility as unverified until migrations are implemented. The API and fake OIDC/provider/source service bind to loopback at port 18000 and 18101 by default; both can be overridden with `API_HOST_PORT` and `MOCKS_HOST_PORT`. Local/test credentials and the test KEK must never be reused outside local/test. Production rejects fake endpoints, the test KEK adapter, missing secrets and enabled local mocks. Run `corepack pnpm verify:foundation` to check the pinned Node/pnpm/Python/uv versions and execute the implemented V-F/V-B/V-C foundation checks. GitHub Actions uses the frozen JS/Python locks and this same verification scope; it needs no secrets or connected services. For V-B's optional local-service integration, set `SET002_LOCAL_SERVICES=1` and the local settings from `.env` before running `corepack pnpm verify:backend`. The separately registered synthetic extension checks are available as `corepack pnpm verify:extension`; they are not part of foundation CI or browser/site compatibility validation. Database schema compatibility remains unverified by readiness until the runtime schema check is added. Planned product-feature gates remain future work.

The [reference roadmap](docs/REFERENCE_ROADMAP.md) and [original review](docs/REFERENCE_PLAN_REVIEW.md) are historical. Active documents linked from `plan.md` govern implementation.
