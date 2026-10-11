# GitHub issue drafts for the implementation and design backlog

Target repository: `Asadjafri9/Job-tracking` (`origin`). These drafts map every task row in [`TASKS.md`](TASKS.md) to one GitHub issue. They preserve task IDs, dependencies, design/implementation areas, and acceptance criteria. The design tasks were added after reviewing [`DESIGN_BRIEF.md`](DESIGN_BRIEF.md) and the browser-only prototype.

## Import and assignment notes

- Create one milestone for each M0–M7 section in `TASKS.md`; each draft names its milestone.
- Keep task IDs in issue titles so code, commits, and evidence can refer back to the plan.
- Preserve dependency links as GitHub issue references after issue numbers are created.
- Leave drafts unassigned until the repository owner confirms the maintainer and owner/operator GitHub usernames.
- The design preview is not the product UI. DGN-005 is the gate for production user-facing screen implementation; foundational backend/contracts can proceed in parallel.

## Coverage

This file contains 58 issue drafts for all task rows. It covers the three product pillars, design direction and validation, database/API/security/deployment plans, verification gates, and future Azure private-beta work. Historical reference documents are context, not new implementation tasks.

---

### [DGN-001] Reconcile the proposed design with product contracts

- **Milestone:** M0 — Foundation and browser feasibility
- **Backlog dependency:** none
- **Planned files/areas:** docs/DESIGN_BRIEF.md, docs/DECISIONS.md
- **Acceptance / verification:** Reconcile the proposed Aster design with active product/security contracts; record unresolved conflicts and owner decisions. Brand and visual direction remain proposed until explicitly accepted. Manual evidence: reviewed decision record.
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [DGN-002] Define accessible visual tokens and component foundations

- **Milestone:** M0 — Foundation and browser feasibility
- **Backlog dependency:** DGN-001
- **Planned files/areas:** design tokens, logo assets, component library
- **Acceptance / verification:** Define semantic color pairs, typography, spacing, focus/status tokens, Guiding A logo variants, and reusable component states; verify rendered text/control/status contrast and small-size logo legibility. Manual evidence: token/component spec and contrast results.
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [DGN-003] Create responsive frames for core screens and states

- **Milestone:** M0 — Foundation and browser feasibility
- **Backlog dependency:** DGN-002
- **Planned files/areas:** design frames/prototype for dashboard, onboarding, extension, email, alerts
- **Acceptance / verification:** Deliver the DESIGN_BRIEF screen and state coverage at 1440px, 1280px, 390px, and 360–420px extension widths, including empty, populated, loading, partial, unsupported, failure, and privacy/review states. Manual evidence: reviewable frames/prototype linked from handoff.
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [DGN-004] Validate the prototype with five representative users

- **Milestone:** M0 — Foundation and browser feasibility
- **Backlog dependency:** DGN-003
- **Planned files/areas:** design validation notes/prototype revisions
- **Acceptance / verification:** Test the key journeys with at least five representative job seekers; observe setup, form review without submission, application evidence, email handoff, and alert-source setup; record issues and resulting design changes. Manual evidence: anonymized findings and iteration notes.
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [DGN-005] Complete design handoff and accessibility review

- **Milestone:** M0 — Foundation and browser feasibility
- **Backlog dependency:** DGN-003, DGN-004
- **Planned files/areas:** design handoff, component states, accessibility/responsive review
- **Acceptance / verification:** Publish implementation notes and final design references; complete keyboard/focus, screen-reader labels/errors/status, reduced-motion, 200% zoom, touch-target, narrow-layout, and semantic contrast review with no unresolved critical core-flow issue. Manual evidence: handoff and review report. Production UI tasks wait for this gate.
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [DGN-006] Record owner decision on brand availability before public use

- **Milestone:** M0 — Foundation and browser feasibility
- **Backlog dependency:** DGN-001
- **Planned files/areas:** brand decision/release evidence
- **Acceptance / verification:** Before public brand use, record the owner's decision after name/logo/domain availability and distinctiveness checks; retain evidence and any resulting rename work. No public-launch clearance is implied by this planning task.
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [SET-001] Implement root manifests/locks, apps/web, apps/api

- **Milestone:** M0 — Foundation and browser feasibility
- **Backlog dependency:** none
- **Planned files/areas:** root manifests/locks, apps/web, apps/api
- **Acceptance / verification:** Node 22/Python 3.12/React/FastAPI shells, exact locked dependencies, real quality script interfaces and fresh setup. V-F, V-B
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [SET-002] Implement compose/config/health/test services

- **Milestone:** M0 — Foundation and browser feasibility
- **Backlog dependency:** SET-001
- **Planned files/areas:** compose/config/health/test services
- **Acceptance / verification:** PostgreSQL/Azurite/fake identity/provider/source/test KEK work locally; production rejects fake/missing config. V-B
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [SET-003] Implement error/version/OpenAPI/client scripts

- **Milestone:** M0 — Foundation and browser feasibility
- **Backlog dependency:** SET-001
- **Planned files/areas:** error/version/OpenAPI/client scripts
- **Acceptance / verification:** uniform errors, versioned schemas, generated TS client/drift, no API-to-HTML fallback. V-C
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [SET-004] Implement CI/workspace verification/evidence templates

- **Milestone:** M0 — Foundation and browser feasibility
- **Backlog dependency:** SET-001–003
- **Planned files/areas:** CI/workspace verification/evidence templates
- **Acceptance / verification:** frozen JS/Python setup and scoped synthetic CI; scripts do real checks, no unimplemented-feature fake success. V-F, V-B, V-C
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [EXT-001] Implement manifest/side panel/worker/build IDs

- **Milestone:** M0 — Foundation and browser feasibility
- **Backlog dependency:** SET-001
- **Planned files/areas:** manifest/side panel/worker/build IDs
- **Acceptance / verification:** exact permissions/origins/stable dev ID; installs/accessibility/unsupported states; no broad permissions/secrets. V-F, install smoke
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [EXT-002] Implement detector/field+option schema/fixtures

- **Milestone:** M0 — Foundation and browser feasibility
- **Backlog dependency:** EXT-001
- **Planned files/areas:** detector/field+option schema/fixtures
- **Acceptance / verification:** selected visible form/job extraction, bounded metadata, sensitive/unrelated exclusions, valid sender/document handles. V-X
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [EXT-003] Implement prototype setters/options/event observers/corpus

- **Milestone:** M0 — Foundation and browser feasibility
- **Backlog dependency:** EXT-002, SET-004
- **Planned files/areas:** prototype setters/options/event observers/corpus
- **Acceptance / verification:** fake-profile native/React/options/review and passive submit observation work; manual edits/validation/unknown results preserved; permitted live inspection report. V-X
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [DB-001] Implement models/Alembic/seed

- **Milestone:** M1 — Identity, persistence and durable work
- **Backlog dependency:** SET-002–003
- **Planned files/areas:** models/Alembic/seed
- **Acceptance / verification:** v2 entities/FKs/revisions/constraints/indexes from fresh migrations; synthetic seed. V-DB
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [DB-002] Implement RLS/roles/DB dependency

- **Milestone:** M1 — Identity, persistence and durable work
- **Backlog dependency:** DB-001
- **Planned files/areas:** RLS/roles/DB dependency
- **Acceptance / verification:** runtime non-owner/no BYPASSRLS; owner context transaction-local; two-user/pool/missing-context checks. V-DB, V-S
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [DB-003] Implement revision/idempotency/quota utilities

- **Milestone:** M1 — Identity, persistence and durable work
- **Backlog dependency:** DB-002
- **Planned files/areas:** revision/idempotency/quota utilities
- **Acceptance / verification:** races handled, duplicate keys reuse entity, altered input conflicts, owner-child constraints and reservations. V-B, V-DB
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [AUTH-001] Implement Authlib/OIDC/login/callback

- **Milestone:** M1 — Identity, persistence and durable work
- **Backlog dependency:** SET-002–003, DB-002
- **Planned files/areas:** Authlib/OIDC/login/callback
- **Acceptance / verification:** state/nonce/issuer/audience/signature/PKCE/redirect validation, allowlisted enrollment, verified subject/directory mapping. V-B, V-S
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [AUTH-002] Implement cookie/CSRF/session/logout/web UI

- **Milestone:** M1 — Identity, persistence and durable work
- **Backlog dependency:** AUTH-001, DB-003
- **Planned files/areas:** cookie/CSRF/session/logout/web UI
- **Acceptance / verification:** idle/absolute expiry, stable CSRF, account initialization, all-client revocation, no browser provider token. V-E, V-S
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [AUTH-003] Implement extension identity/grant/session store

- **Milestone:** M1 — Identity, persistence and durable work
- **Backlog dependency:** AUTH-002, EXT-001
- **Planned files/areas:** extension identity/grant/session store
- **Acceptance / verification:** one-use 60-sec PKCE app grant, exact ID/state, trusted storage, restart/expiry/switch behavior. V-X, V-S
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [AUTH-004] Implement fresh-auth/reset/tenant instructions

- **Milestone:** M1 — Identity, persistence and durable work
- **Backlog dependency:** AUTH-002–003
- **Planned files/areas:** fresh-auth/reset/tenant instructions
- **Acceptance / verification:** fake CI lifecycle; later actual tenant signup/reset/extension smoke; no prod fake bypass. V-E and later identity smoke
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [JOB-001] Implement queue/worker/scheduler/leases

- **Milestone:** M1 — Identity, persistence and durable work
- **Backlog dependency:** DB-003, AUTH-002
- **Planned files/areas:** queue/worker/scheduler/leases
- **Acceptance / verification:** durable claims/heartbeat/cancellation/stages, bounded concurrency/retries and visible exhaustion; restart safe. V-B, V-DB
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [KEY-001] Implement crypto adapter/credentials API

- **Milestone:** M1 — Identity, persistence and durable work
- **Backlog dependency:** DB-003, AUTH-002, JOB-001
- **Planned files/areas:** crypto adapter/credentials API
- **Acceptance / verification:** per-record AES-GCM/wrapped DEK/AAD, masked GET, owner/purpose unwrap and rotation/delete; test KEK only locally. V-B, V-S
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [KEY-002] Implement provider settings/key UI/consent

- **Milestone:** M1 — Identity, persistence and durable work
- **Backlog dependency:** KEY-001, AUTH-003
- **Planned files/areas:** provider settings/key UI/consent
- **Acceptance / verification:** three slots/order/saved or session-only/background/fallback permissions; revoked key stops new jobs, no key plaintext persistence/export/log. V-E, V-S
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [PROF-001] Implement rich profile editor/schemas/retrieval

- **Milestone:** M2 — Onboarding and three-provider routing
- **Backlog dependency:** AUTH-002, DB-003
- **Planned files/areas:** rich profile editor/schemas/retrieval
- **Acceptance / verification:** contact/history/projects/links/tips/optional purpose-scoped facts; confirmations/revisions, unknowns and conflicts. V-B, V-E
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [DOC-001] Implement upload/private storage/download/UI

- **Milestone:** M2 — Onboarding and three-provider routing
- **Backlog dependency:** PROF-001, JOB-001
- **Planned files/areas:** upload/private storage/download/UI
- **Acceptance / verification:** ten 5 MiB docs/50 MiB reservation, types/versions/defaults/hash/private downloads and orphan failure cleanup. V-DOC, V-S
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [DOC-002] Implement bounded subprocess/parser/anchors

- **Milestone:** M2 — Onboarding and three-provider routing
- **Backlog dependency:** DOC-001
- **Planned files/areas:** bounded subprocess/parser/anchors
- **Acceptance / verification:** PDF/DOCX/LinkedIn/cover-letter text parsing, memory/time/ZIP limits, unsupported/scanned paths and restart safe. V-DOC
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [AI-001] Implement provider contract/router/consent

- **Milestone:** M2 — Onboarding and three-provider routing
- **Backlog dependency:** KEY-002, PROF-001, SET-003
- **Planned files/areas:** provider contract/router/consent
- **Acceptance / verification:** typed operations/capability catalog/source references/limits; minimum relevant facts; no tools or secret prompt input. V-A
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [AI-002] Implement OpenRouter/Grok/Gemini adapters

- **Milestone:** M2 — Onboarding and three-provider routing
- **Backlog dependency:** AI-001
- **Planned files/areas:** OpenRouter/Grok/Gemini adapters
- **Acceptance / verification:** exact model/schema mode verified, normalized outcomes/usage, stubbed success/refusal/error, authoritative validation. V-A, V-B
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [AI-003] Implement fallback/request/attempt/quota state

- **Milestone:** M2 — Onboarding and three-provider routing
- **Backlog dependency:** AI-002, DB-003
- **Planned files/areas:** fallback/request/attempt/quota state
- **Acceptance / verification:** definitive exhausted/rate/outage fallback only consented keys; bad input/refusal/unknown stops; deadlines/idempotency/circuit status correct. V-A, V-S
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [DOC-003] Implement candidate extraction/review/conflict UI

- **Milestone:** M2 — Onboarding and three-provider routing
- **Backlog dependency:** DOC-002, AI-003
- **Planned files/areas:** candidate extraction/review/conflict UI
- **Acceptance / verification:** AI candidates consented, anchors/versioned source, explicit confirmation, cover-letter style distinct from claims, changes invalidate pending work. V-DOC, V-E
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [AI-004] Implement quality/source/claim/options corpus

- **Milestone:** M2 — Onboarding and three-provider routing
- **Backlog dependency:** AI-003, DOC-003
- **Planned files/areas:** quality/source/claim/options corpus
- **Acceptance / verification:** every enabled adapter passes factuality/schema/reference/option/email/job cases with recorded prompt/model evidence; later opted-in live eval. V-A, V-L later
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [APP-001] Implement applications/session CRUD/URL identity

- **Milestone:** M3 — Autofill, tracking and dashboard
- **Backlog dependency:** AUTH-002, DB-003
- **Planned files/areas:** applications/session CRUD/URL identity
- **Acceptance / verification:** prepared sessions separate from applications, exact attempt/channel/URL matching, optimistic CRUD/duplicate handling. V-B, V-E
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [APP-002] Implement status/evidence/history/snapshots

- **Milestone:** M3 — Autofill, tracking and dashboard
- **Backlog dependency:** APP-001
- **Planned files/areas:** status/evidence/history/snapshots
- **Acceptance / verification:** distinct Preparing/SubmissionAttempted/Applied evidence, immutable answers/context/docs, corrections append history. V-B, V-E
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [APP-003] Implement dashboard overview/filter/reminder UI

- **Milestone:** M3 — Autofill, tracking and dashboard
- **Backlog dependency:** APP-002, PROF-001
- **Planned files/areas:** dashboard overview/filter/reminder UI
- **Acceptance / verification:** real empty state, drafts/jobs separate counts, bounded filters/date/timezone and accessible offline states. V-F, V-E
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [EXT-004] Implement context/profile retrieval/autofill pipeline

- **Milestone:** M3 — Autofill, tracking and dashboard
- **Backlog dependency:** EXT-003, AUTH-003, DOC-003, AI-003, APP-001
- **Planned files/areas:** context/profile retrieval/autofill pipeline
- **Acceptance / verification:** extract/correct context, use confirmed facts, ordinary answer batch/option IDs, exact sources and missing facts; keys stay server/trusted UI. V-X, V-A
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [EXT-005] Implement account/document/field revision bindings

- **Milestone:** M3 — Autofill, tracking and dashboard
- **Backlog dependency:** EXT-004
- **Planned files/areas:** account/document/field revision bindings
- **Acceptance / verification:** user Analyze action allows ordinary fill; stale/edited/replaced/navigated/account-switched writes rejected; sensitive attestations manual. V-X, V-S
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [EXT-006] Implement setters/selection/review/results

- **Milestone:** M3 — Autofill, tracking and dashboard
- **Backlog dependency:** EXT-005
- **Planned files/areas:** setters/selection/review/results
- **Acceptance / verification:** post-render verified text/radio/select/checkbox outcomes; no guessed options/manual overwrite/Submit/Next; post-fill review and manual attachments. Full form gates V-X
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [TRACK-001] Implement passive trusted submit/event correlation

- **Milestone:** M3 — Autofill, tracking and dashboard
- **Backlog dependency:** EXT-006, APP-002
- **Planned files/areas:** passive trusted submit/event correlation
- **Acceptance / verification:** recognized pointer/keyboard/native selected-form events; validation error/SPA unknown/success fixtures; no prevented/triggered submit. V-X
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [TRACK-002] Implement trusted minimal outbox/replay

- **Milestone:** M3 — Autofill, tracking and dashboard
- **Backlog dependency:** TRACK-001, DB-003
- **Planned files/areas:** trusted minimal outbox/replay
- **Acceptance / verification:** same-account 24 h metadata-only outbox/idempotent replay, restart/offline delivery, purge on logout/switch/deletion; no action replay. V-X, V-S
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [TRACK-003] Implement dashboard automatic event/status/confirmation

- **Milestone:** M3 — Autofill, tracking and dashboard
- **Backlog dependency:** TRACK-002, APP-003
- **Planned files/areas:** dashboard automatic event/status/confirmation
- **Acceptance / verification:** event automatically creates/updates one application; click doesn't mean Applied; site/user confirmation/date exposed, historical snapshots stable. V-E
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [MAIL-001] Implement email draft routes/UI/generation

- **Milestone:** M4 — Email applications
- **Backlog dependency:** DOC-003, AI-003, APP-002
- **Planned files/areas:** email draft routes/UI/generation
- **Acceptance / verification:** recipient/job/start message → editable source-based subject/body, current style/doc hints, version/race/header/claim validation. V-A, V-E
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [MAIL-002] Implement compose encoding/copy/mailto/download UI

- **Milestone:** M4 — Email applications
- **Backlog dependency:** MAIL-001
- **Planned files/areas:** compose encoding/copy/mailto/download UI
- **Acceptance / verification:** no connect/OAuth prompt; exact reviewed revision encoded; long/failed prefill fallback no truncation; manual attachments/Send. V-F, V-E
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [MAIL-003] Implement compose/sent events/email tracking

- **Milestone:** M4 — Email applications
- **Backlog dependency:** MAIL-002, TRACK-003
- **Planned files/areas:** compose/sent events/email tracking
- **Acceptance / verification:** open isn't Applied; explicit sent/date idempotently tracks USER_CONFIRMED_EMAIL and immutable snapshot. V-E
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [MON-001] Implement sources/preferences/schedule UI/API

- **Milestone:** M5 — Daily source monitoring and notifications
- **Backlog dependency:** KEY-002, JOB-001, PROF-001
- **Planned files/areas:** sources/preferences/schedule UI/API
- **Acceptance / verification:** ≤five public URLs, 09:00/timezone/next-run/consent/support/pause/check-now; private prefs only relevant. V-M, V-E
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [MON-002] Implement safe fetch/DNS/robots/HTML/feed/ATS extraction

- **Milestone:** M5 — Daily source monitoring and notifications
- **Backlog dependency:** MON-001
- **Planned files/areas:** safe fetch/DNS/robots/HTML/feed/ATS extraction
- **Acceptance / verification:** pinned public TLS destinations/redirect/private/DNS/byte/page/time bounds, no login/JS/CAPTCHA bypass; source completeness/evidence. V-M, V-S
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [MON-003] Implement due scheduler/run/dedupe/match pipeline

- **Milestone:** M5 — Daily source monitoring and notifications
- **Backlog dependency:** MON-002, AI-003
- **Planned files/areas:** due scheduler/run/dedupe/match pipeline
- **Acceptance / verification:** clients closed, one daily run/local date, DST/timezone/restart/catch-up; changed-text AI/circuit/deadline; stable postings/no false closure. V-M
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [MON-004] Implement notifications/badge/job links/run UI

- **Milestone:** M5 — Daily source monitoring and notifications
- **Backlog dependency:** MON-003, APP-003
- **Planned files/areas:** notifications/badge/job links/run UI
- **Acceptance / verification:** first summary/new-match digest, exact dedupe/read states, failed/partial/paused/no-key visible; discovered jobs not applications. V-M, V-E
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [DATA-001] Implement lifecycle/cleanup/cancel stages

- **Milestone:** M6 — Privacy, reliability and quality
- **Backlog dependency:** JOB-001, DOC-003, KEY-002, MON-004
- **Planned files/areas:** lifecycle/cleanup/cancel stages
- **Acceptance / verification:** docs/keys/sources removals stop use/jobs, cleanup bounded/restart safe, expired sessions/drafts/outbox/artifacts handled. V-B, V-S
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [DATA-002] Implement export v2/snapshot/ZIP/privacy UI

- **Milestone:** M6 — Privacy, reliability and quality
- **Backlog dependency:** DATA-001, MAIL-003, TRACK-003
- **Planned files/areas:** export v2/snapshot/ZIP/privacy UI
- **Acceptance / verification:** full three-pillar data/originals/checksums, safe CSV/ZIP, consistent concurrency, private 24 h artifact, no key material. V-E, V-S
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [DATA-003] Implement account delete/journal/receipt/identity operator command

- **Milestone:** M6 — Privacy, reliability and quality
- **Backlog dependency:** DATA-001–002, AUTH-004
- **Planned files/areas:** account delete/journal/receipt/identity operator command
- **Acceptance / verification:** fresh auth/typed consent, immediate session/key/schedule revocation, journal before ack, cancel/late-result guard, visible identity stage/completion. V-E, V-S
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [QA-001] Implement adversarial/three-pillar E2E/security

- **Milestone:** M6 — Privacy, reliability and quality
- **Backlog dependency:** DATA-003, AI-004, MON-004, MAIL-003, TRACK-003
- **Planned files/areas:** adversarial/three-pillar E2E/security
- **Acceptance / verification:** actual-role owner isolation, key canaries, parser/source SSRF/prompt races, provider unknown/outage, submit/email false-confirm negatives. V-S, V-E
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [QA-002] Implement performance/accessibility/fake-clock reports

- **Milestone:** M6 — Privacy, reliability and quality
- **Backlog dependency:** QA-001
- **Planned files/areas:** performance/accessibility/fake-clock reports
- **Acceptance / verification:** declared dataset/gates/denominators, worker/scheduler doesn't block API; keyboard/screenreader/360px core paths. V-P, accessibility smoke
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [QA-003] Implement fresh install/limitations/contracts/evidence

- **Milestone:** M6 — Privacy, reliability and quality
- **Backlog dependency:** QA-001–002
- **Planned files/areas:** fresh install/limitations/contracts/evidence
- **Acceptance / verification:** current+previous compatible clients, exact fallback/source limits, private beta docs/operator runbooks, no fake completion claims. V-F, V-B, V-C, V-X, V-E
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [AZ-001] Implement Bicep/config/quote/identity/network/KEK plan

- **Milestone:** M7 — Future Azure private beta
- **Backlog dependency:** SET-004, AUTH-004, DATA-003
- **Planned files/areas:** Bicep/config/quote/identity/network/KEK plan
- **Acceptance / verification:** later reviewable resources/cost/quota/roles/region/tenant/IDs and actual quote before provisioning. Future Bicep/what-if/quote
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [AZ-002] Implement Docker/supervision/OIDC CI/immutable artifacts

- **Milestone:** M7 — Future Azure private beta
- **Backlog dependency:** AZ-001, QA-001
- **Planned files/areas:** Docker/supervision/OIDC CI/immutable artifacts
- **Acceptance / verification:** locked non-root web/API/worker/scheduler image, scoped roles/KEK/private DB, migration separate, prior rollback image. Future V-AZ
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [AZ-003] Implement isolated staging/beta evidence

- **Milestone:** M7 — Future Azure private beta
- **Backlog dependency:** AZ-002, QA-003
- **Planned files/areas:** isolated staging/beta evidence
- **Acceptance / verification:** later real identity/providers/source smoke/encryption/schedule/E2E; no fake prod config/secrets, redacted monitoring/budget. Future V-AZ/V-L/V-E/V-M
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [AZ-004] Implement recovery/rollback/runbook evidence

- **Milestone:** M7 — Future Azure private beta
- **Backlog dependency:** AZ-003
- **Planned files/areas:** recovery/rollback/runbook evidence
- **Acceptance / verification:** later image rollback/new DB restore/journal replay/revoked keys/sessions/original-file checks and measured RPO/RTO. Future recovery drill
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.

---

### [BETA-001] Implement checklist/artifacts/invitations/feedback

- **Milestone:** M7 — Future Azure private beta
- **Backlog dependency:** AZ-004, QA-003, AI-004
- **Planned files/areas:** checklist/artifacts/invitations/feedback
- **Acceptance / verification:** actual blocker evidence, two controlled form environments, three pillars, ten-user cap, identity/deletion coverage; owner release decision. RELEASE_CHECKLIST
- **Source:** [docs/TASKS.md](TASKS.md)
- **Assignee:** leave unassigned until the repository owner confirms the role mapping.
