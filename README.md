# Job-tracking

An application copilot planned with **React + FastAPI + PostgreSQL + Azure**.

The first complete release covers three flows:

1. **Autofill:** build a confirmed profile from personal details, resume, LinkedIn PDF and cover letter; fill supported job-form answers/options; ask the user to review; record their submission evidence in the dashboard.
2. **Email applications:** personalize an editable message and open Gmail compose, with copy fallback and manual attachments/send. No Gmail connection prompt.
3. **Job updates:** check up to five saved public career sources at 09:00 in the user's timezone and show deduplicated in-app notifications.

Users can supply OpenRouter/DeepSeek, xAI Grok and Gemini keys, with encrypted saved credentials and an explicitly enabled fallback order. A submit click records an attempt; opening Gmail records a compose event. Confirmed application status requires the evidence defined in the plan.

## Start here

- [Implementation plan](plan.md): scope, decisions, milestone order and release gates.
- [Product design brief](docs/DESIGN_BRIEF.md): proposed Aster logo, visual direction, UX principles, screens and accessibility/validation guidance.
- [Interactive design preview](design-exploration/README.md): browser-only implementation of the design direction; no backend or product data is connected.
- [Implementation tasks](docs/TASKS.md): dependencies, acceptance and future verification for each task.
- [Requirements](docs/PRD.md), [architecture](docs/ARCHITECTURE.md), [review resolutions](docs/PLAN_REVIEW.md) and [progress](docs/PROGRESS.md).

**Implementation status:** SET-001 has started. `apps/web` is the React application shell and `apps/api` is the FastAPI service foundation. The design preview remains a separate static HTML/CSS/JavaScript reference; it is not connected to application data. Authentication, persistence, provider routing, and deployment remain future work. No Azure services were provisioned.

## Local development

Prerequisites: Node 22, its bundled Corepack, Python 3.12, uv, and Docker Compose. The workspace pins pnpm 10.33.3, which works with the Corepack version bundled with Node 22.16.

```powershell
Copy-Item .env.example .env
docker compose up -d
corepack pnpm install
corepack pnpm dev:web
```

In another terminal, run the API:

```powershell
corepack pnpm dev:api
```

To start the loopback-only synthetic OIDC, provider, and source fixtures, use a third terminal:

```powershell
corepack pnpm dev:mocks
```

The web app serves on `http://127.0.0.1:5173`; API liveness is at `http://127.0.0.1:8000/health/live`. `/health/ready` reports TCP reachability but intentionally remains `503` until database authentication/schema and blob authorization checks are implemented. The local Compose services bind to loopback and use test-only credentials and separate admin, migration, and runtime database roles. Run `docker compose down` when you want to stop them. Run `corepack pnpm verify:frontend` or `corepack pnpm verify:backend` for the configured format, lint, type-check, test, and build commands. The full verification commands remain incomplete until feature tests and the browser extension are implemented.

The [reference roadmap](docs/REFERENCE_ROADMAP.md) and [original review](docs/REFERENCE_PLAN_REVIEW.md) are historical. Active documents linked from `plan.md` govern implementation.
