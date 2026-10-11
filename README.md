# Job-tracking

An application copilot planned with **React + FastAPI + PostgreSQL + Azure**.

The first complete release covers three flows:

1. **Autofill:** build a confirmed profile from personal details, resume, LinkedIn PDF and cover letter; fill supported job-form answers/options; ask the user to review; record their submission evidence in the dashboard.
2. **Email applications:** personalize an editable message and open Gmail compose, with copy fallback and manual attachments/send. No Gmail connection prompt.
3. **Job updates:** check up to five saved public career sources at 09:00 in the user's timezone and show deduplicated in-app notifications.

Users can supply OpenRouter/DeepSeek, xAI Grok and Gemini keys, with encrypted saved credentials and an explicitly enabled fallback order. A submit click records an attempt; opening Gmail records a compose event. Confirmed application status requires the evidence defined in the plan.

## Start here

- [Implementation plan](plan.md): scope, decisions, milestone order and release gates.
- [Implementation tasks](docs/TASKS.md): dependencies, acceptance and future verification for each task.
- [Requirements](docs/PRD.md), [architecture](docs/ARCHITECTURE.md), [review resolutions](docs/PLAN_REVIEW.md) and [progress](docs/PROGRESS.md).

**Repository status:** documentation only; application implementation has not started. First task: SET-001. Authentication, storage, provider routing and the future Azure topology now have selected planning defaults. Runtime checks and deployment remain future work. This planning work uses no connected Azure services and provisions no resources.

The [reference roadmap](docs/REFERENCE_ROADMAP.md) and [original review](docs/REFERENCE_PLAN_REVIEW.md) are historical. Active documents linked from `plan.md` govern implementation.
