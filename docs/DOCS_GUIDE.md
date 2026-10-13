# Guide to this documentation set

This folder is the planning and implementation reference for the Job Application Copilot. The documents turn the product idea into requirements, technical contracts, implementation work, and evidence needed to decide whether it is ready to release. They describe a plan; they do not prove that the software has been implemented or verified.

## How the documents fit together

```text
Product idea and user needs
        ↓
PRD + DECISIONS
        ↓
ARCHITECTURE + feature contracts + SECURITY_PRIVACY
        ↓
DATABASE/API contracts + COMPATIBILITY
        ↓
TASKS + TESTING
        ↓
PROGRESS + RISKS + RELEASE_CHECKLIST
```

The PRD states what the product should do. DECISIONS records choices and their rationale. Architecture and the more detailed contracts explain how important parts should behave. TASKS turns the plan into ordered work. TESTING and RELEASE_CHECKLIST define what evidence will show that work is complete. PROGRESS and RISKS track the current state. Keep these documents consistent when a decision or requirement changes.

## File inventory

| File | Purpose |
| --- | --- |
| [PRD.md](PRD.md) | Product scope, users, functional requirements, and acceptance criteria. |
| [DECISIONS.md](DECISIONS.md) | Accepted technical and product decisions, defaults, and recorded changes. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System components, boundaries, and how data or requests move between them. |
| [DESIGN_BRIEF.md](DESIGN_BRIEF.md) | Rolevo visual direction, information architecture, screen behavior, accessibility, and design validation; public trademark clearance is not claimed. |
| [DESIGN_RECONCILIATION.md](DESIGN_RECONCILIATION.md) | DGN-001 comparison of the Rolevo design with active product/security contracts and the owner decisions still open. |
| [API.md](API.md) | HTTP and browser-client routes, payloads, errors, authentication, and compatibility contracts. |
| [DATABASE.md](DATABASE.md) | Data entities, ownership, constraints, indexes, revisions, and migration expectations. |
| [SECURITY_PRIVACY.md](SECURITY_PRIVACY.md) | Threats, privacy boundaries, controls, consent, and the evidence needed to validate them. |
| [COMPATIBILITY.md](COMPATIBILITY.md) | Supported browsers, platforms, inputs, integrations, and explicit unsupported cases. |
| [ONBOARDING.md](ONBOARDING.md) | Account setup, initial data collection, imports, user review, and configuration. |
| [AUTOFILL_TRACKING.md](AUTOFILL_TRACKING.md) | Browser autofill, review, and application-submission evidence workflow. |
| [EMAIL_APPLICATIONS.md](EMAIL_APPLICATIONS.md) | Email-draft creation, validation, review, and handoff behavior. |
| [JOB_MONITORING.md](JOB_MONITORING.md) | Scheduled source checks, consent, worker behavior, and notification rules. |
| [PROVIDERS.md](PROVIDERS.md) | AI provider adapters, model selection, key handling, fallback, and output validation. |
| [TASKS.md](TASKS.md) | Ordered implementation backlog with dependencies and acceptance evidence. |
| [GITHUB_ISSUE_DRAFTS.md](GITHUB_ISSUE_DRAFTS.md) | Draft issue text for every backlog task, organized by milestone and ready for duplicate review and GitHub import. |
| [design-exploration/README.md](../design-exploration/README.md) | How to view the browser-only visual prototype and what it does not implement. |
| [TESTING.md](TESTING.md) | Verification plan, checks, and evidence expectations; planned commands are labeled as such. |
| [RISKS.md](RISKS.md) | Open risks, planned controls, owners, and the work that will verify mitigations. |
| [PROGRESS.md](PROGRESS.md) | Current planning, implementation, and verification status. |
| [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) | Release gates to complete with observed evidence. |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Intended hosting topology and deployment configuration; currently planning only. |
| [PLAN_REVIEW.md](PLAN_REVIEW.md) | Current planning review, readiness conclusion, and resolved gaps. |
| [REFERENCE_PLAN_REVIEW.md](REFERENCE_PLAN_REVIEW.md) | Historical review material retained for traceability. |
| [REFERENCE_ROADMAP.md](REFERENCE_ROADMAP.md) | Historical source roadmap retained for traceability, not the active implementation contract. |

## Reuse guidance

The reusable pattern is the relationship between the documents, not their contents. For another project, start from its actual users, goals, constraints, and risks. Select a small document set appropriate to its size. Add feature-specific contracts only for substantial features or external integrations. Mark decisions, assumptions, open questions, planned checks, and observed results distinctly. Remove or archive obsolete reference material so there is one clear active source of truth.

Use [REUSABLE_PROJECT_DOCS_PROMPT.md](REUSABLE_PROJECT_DOCS_PROMPT.md) in a new repository to generate a tailored documentation set.
