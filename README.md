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

**Repository status:** product implementation has not started. The interactive design preview is static HTML/CSS/JavaScript for design review only; it is not the planned React application. First implementation task: SET-001. Authentication, storage, provider routing and the future Azure topology have planning defaults; runtime checks and deployment remain future work. No Azure services were used or provisioned for the prototype.

The [reference roadmap](docs/REFERENCE_ROADMAP.md) and [original review](docs/REFERENCE_PLAN_REVIEW.md) are historical. Active documents linked from `plan.md` govern implementation.
