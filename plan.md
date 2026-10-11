# AI Job Application Copilot — implementation plan

Version 2.0 · October 12, 2026 · Status: READY_FOR_IMPLEMENTATION

The owner's product scope has three pillars: **autofill and application tracking, personalized email applications, and daily career-page monitoring**. The selected stack is **React + FastAPI + PostgreSQL + Azure**. This version incorporates the owner's detailed workflow and supersedes the earlier narrow MVP defaults. Other concrete defaults are maintainer-selected planning decisions, editable through DECISIONS.

Implementation is NOT_STARTED. Readiness means the decisions, contracts, backlog and gates are defined; it does not claim working software, provider access, live-site compatibility or deployed Azure resources.

## Read these documents

| Document | Responsibility |
| --- | --- |
| [Design brief](docs/DESIGN_BRIEF.md) | Proposed brand, visual language, information architecture, screens, interaction behavior, and design-validation plan |
| [PRD](docs/PRD.md) | Exact three-pillar scope, requirements and user journeys |
| [Decisions](docs/DECISIONS.md) | Accepted defaults and change conditions |
| [Architecture](docs/ARCHITECTURE.md) | Components, sessions, trusted contexts, durable workers |
| [Onboarding](docs/ONBOARDING.md) | Personal details, resumes, LinkedIn PDF, cover letter, parsing/confirmation |
| [Autofill and tracking](docs/AUTOFILL_TRACKING.md) | Extract → fill → review → user submits → dashboard record |
| [Providers](docs/PROVIDERS.md) | OpenRouter/DeepSeek, Grok, Gemini; encrypted BYOK and fallback |
| [Email applications](docs/EMAIL_APPLICATIONS.md) | Profile-based writing and Gmail compose handoff |
| [Job monitoring](docs/JOB_MONITORING.md) | User URLs, 9 a.m. timezone scheduling, discovery and notifications |
| [Database](docs/DATABASE.md) | Ownership, schemas, revisions, idempotency and lifecycle |
| [API](docs/API.md) | HTTP and extension message contracts |
| [Compatibility](docs/COMPATIBILITY.md) | Supported controls/source types and graceful fallback |
| [Security/privacy](docs/SECURITY_PRIVACY.md) | Consent, keys, fetch boundaries, retention/export/deletion |
| [Testing](docs/TESTING.md) | Verification interfaces, corpora and measurable gates |
| [Deployment](docs/DEPLOYMENT.md) | Azure topology, identities, worker/scheduler, budget and recovery |
| [Tasks](docs/TASKS.md), [Progress](docs/PROGRESS.md) | Dependencies, files, acceptance, next work and evidence |
| [Risks](docs/RISKS.md), [Release checklist](docs/RELEASE_CHECKLIST.md) | Owned risks and blocker evidence |

The [earlier broad roadmap](docs/REFERENCE_ROADMAP.md) and [original findings](docs/REFERENCE_PLAN_REVIEW.md) are historical context. [The active review](docs/PLAN_REVIEW.md) maps those findings to current resolutions. Current contracts above take precedence.

## Pillar 1 — Profile-based autofill and automatic tracking

User signs up, enters personal/professional details, uploads a resume, LinkedIn-export PDF and current cover letter, and adds useful preferences/tips. Originals are private; parsed facts are previewed and confirmed before becoming usable profile facts. Optional personal data is separately controlled and sent to providers only when needed and permitted.

User opens a job form and clicks **Analyze and autofill**. The extension extracts the visible job/form context, the backend selects relevant confirmed facts and generates constrained answers, and the extension fills supported ordinary fields and factual options. It chooses select/radio/checkbox options only when confirmed facts resolve them. The user then reviews/edit values and presses the hiring site's submit button themselves. Attestations/consent and unresolved sensitive declarations remain manual. Resume attachment is manual in the initial release.

The extension records a trusted submit click/native submit event for the selected application session and creates/updates the dashboard record automatically. **A click means Submission attempted, not proven success.** Tested site success signals or explicit user confirmation can mark Applied; validation errors/rejections remain visible. Prepared form sessions and jobs discovered by monitoring do not count as applications.

## Pillar 2 — Personalized email applications

User supplies recipient, employer, role, job text and optional starting message. AI uses confirmed profile facts/projects and the current cover letter's reviewed writing preferences to draft subject/body. User edits/reviews and clicks **Open in Gmail**. The app opens a compose URL with recipient/subject/body; attachments and Send remain the user's actions in Gmail. Copy controls and a standard mailto fallback are always available.

Do not prompt users to connect Gmail. Gmail OAuth/direct sending/mailbox scanning are deferred. Opening compose is tracked as Compose opened; Applied requires the user's **I sent this email** confirmation. No send confirmation is fabricated from an opened tab.

## Pillar 3 — Daily job monitoring

User adds up to five public career/job-listing URLs and role/location preferences. A server-side scheduler queues scans at **9:00 a.m. in the user's IANA timezone**, even while the dashboard/browser is closed. The timezone comes from onboarding/browser preference and is editable; a Karachi user uses Asia/Karachi.

Worker fetches bounded permitted public HTML/feeds/APIs, extracts openings, uses the configured providers to classify changed content and match preferences, deduplicates listings, and writes in-app notifications. Navbar bell/unread count and a Notifications page show results, failures and last/next run. No unchanged-state alert spam. Source authentication/CAPTCHA and JavaScript-only sites are marked unsupported; no bypass/unbounded crawling.

## Fixed decisions

| Area | Decision |
| --- | --- |
| Frontend/API/database | React 19/TypeScript/Vite; Python 3.12/FastAPI/Pydantic; PostgreSQL 17/SQLAlchemy/Alembic |
| Identity | Microsoft Entra External ID hosted email/password/reset flow; opaque FastAPI web/extension sessions |
| Storage | PostgreSQL and private Azure blobs authoritative; encrypted provider credentials stored owner-scoped |
| Documents | PDF/DOCX resume/cover letter, LinkedIn PDF, optional supporting docs; ten 5 MiB files/account |
| Provider 1 | OpenRouter, default `deepseek/deepseek-v4-flash` |
| Provider 2 | xAI Grok, default `grok-4.7`; Grok is interpreted as xAI, not Groq |
| Provider 3 | Gemini, default `gemini-3.8-flash` |
| Fallback | User orders/enables supplied providers; switch on defined quota/rate/unavailability outcomes with consent and bounded attempts |
| Credentials | Encrypted saved-key option for background monitoring; session-only option for interactive use |
| Hosting | Same-origin React assets plus FastAPI on Azure App Service Linux; PostgreSQL, blobs, Key Vault, ACR and monitoring |
| Scheduling | Durable PostgreSQL jobs; supervised worker/scheduler; default 09:00 local; idempotent daily runs |
| Beta | Up to ten invited adults; unpacked Chrome MV3 extension, current/previous stable tested |
| Offline tracking | Minimal account-bound submission-event outbox; no offline provider calls or form-action replay |

Model IDs were checked against primary provider documentation during planning. Revalidate capabilities/account availability before the adapter task; version changes require updated evaluation evidence. No “free unlimited AI” or provider spending guarantee is promised.

**Deferred:** Gmail OAuth/send integration, mailbox status inference, fully automatic job submission, automatic file attachment, scanned-document OCR, LinkedIn account scraping, browser automation for authenticated/JS-only monitoring pages, Firefox, local-only profile storage, bidirectional offline sync, managed AI billing, public extension-store release and paid plans. Public licensing remains a separate owner decision; no license is invented.

## Invariants

1. User initiates autofill; the extension never clicks Submit, Next, Send, or accepts final attestations for the user.
2. User-confirmed facts drive factual text and option choices. Missing/ambiguous facts remain unresolved; AI prose cannot silently become profile truth.
3. Exact account/document/field/revision bindings are checked immediately before writes; manual edits and late responses are preserved/rejected appropriately.
4. Submit clicks, native submit events, site success signals and email confirmation have distinct evidence types. Tracking records reality without claiming delivery from intent.
5. API owner checks, composite-owner FKs and RLS isolate profiles, keys, documents, drafts, jobs and notifications.
6. Saved keys are encrypted, masked in UI, never returned in full, never included in prompts/logs/exports. Scheduled work requires explicit saved-key/monitoring consent.
7. Automatic fallback uses only enabled, consented providers and the same authorized context. Unknown completion stops automatic retries/fallback to avoid duplicate charges.
8. Monitoring fetches public permitted URLs with SSRF controls and bounded budgets; model output cannot trigger additional network or account actions.
9. Sign-out/account switch purges trusted local state/outbox; deletion revokes sessions, disables monitoring, cancels jobs and destroys credentials before reporting complete.
10. Completion and release claims require measured evidence, separately from this planning baseline.

## Milestones and order

| Milestone | Work | Exit gate | Initial effort |
| --- | --- | --- | --- |
| M0 | Foundation/browser feasibility | locked setup, contracts, inspect/fill/selection/submit observation fixtures | 5–8 working days |
| M1 | Identity/database/durable jobs | two-user isolation, web/extension sessions, worker/scheduler/key encryption | 7–11 days |
| M2 | Rich onboarding/provider layer | private docs parse/confirm; three adapters and fallback evidence | 8–13 days |
| M3 | Autofill/tracking/dashboard | analyze → fill → review → user submit → automatic honest dashboard event | 8–13 days |
| M4 | Email applications | personalized editable draft → Gmail compose → explicit sent confirmation | 4–7 days |
| M5 | Daily monitoring | timezone schedule, safe fetching, dedupe/matching, notification/error states | 7–11 days |
| M6 | Privacy/quality | complete export/deletion and three-pillar regression/quality/performance gates | 6–10 days |
| M7 | Azure/beta | deployed actual-provider/identity/source smoke, recovery/rollback, fresh install | 5–8 days plus provisioning wait |

These are initial single-developer estimates, not delivery promises. Re-estimate after M0. Product owner owns scope/budget; implementing maintainer owns technical tasks and operations until reassigned. Exact IDs/dependencies/files/verification are in TASKS.

## Release gates

- Form corpus ≥100 controls: ≥95% supported detection/fill success; zero wrong-field writes, manual-edit overwrites, unauthorized submissions or guessed sensitive selections.
- Submit evidence corpus: clicks with validation failures never become Applied; keyboard submit, SPA/native success/failure, duplicate events and offline replay are correctly distinguished.
- Each enabled provider passes the versioned factuality/option/email/job-extraction corpus; zero surfaced unsupported objective claims/invalid references. Fallback tests exercise quota, outage, invalid key and unknown completion.
- Email handoff preserves reviewed recipient/subject/body or explicitly uses copy fallback; no silent truncation, attachment/send claim or false Applied status.
- Monitoring dispatch p95 ≤5 minutes after 09:00 local, completion target ≤30 minutes for the beta dataset with working sources/providers; timezone/DST/restart tests produce one daily run, no duplicate new-job notifications. Failures are visible.
- Two-user/key/SSRF/RLS tests, parsing/resource limits, full export/deletion/job cancellation and restore-journal checks pass.
- Non-provider JSON API p95 <500 ms at ten concurrent users; inspection p95 <1 second for 100 controls; interactive AI/fallback total deadline 60 seconds with measured p95 target <30 seconds.
- RELEASE_CHECKLIST has actual evidence and no P0/P1 defects. Gates are targets, not existing measurements or platform guarantees.

## First task

Start **SET-001** in [TASKS](docs/TASKS.md). Build the locked frontend/Python shells and local services, then prove browser control/event behavior before expanding compatibility. The product decisions are written; do not restart Phase 00 from the historical roadmap. This request changes documentation only and does not authorize cloud provisioning or sending messages.
