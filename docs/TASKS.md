# Three-pillar implementation backlog

Every task starts NOT_STARTED. Statuses: NOT_STARTED, IN_PROGRESS, BLOCKED, IN_REVIEW, DONE, WAIVED. WAIVED is reserved for an owner-approved scope change and must include its evidence; it does not mean the work was performed. Implementing maintainer owns tasks unless marked owner/operator. Dependencies require evidenced completion; independent tasks may proceed once inputs exist. Verification codes are future scripts defined in TESTING, not checks already run; design tasks specify their manual evidence directly. Evidence: `docs/evidence/<ID>.md` with commit/files/commands/results/reviewer. Split oversized responsibilities into numbered child tasks retaining requirements/dependencies. DGN-005 gates implementation of production user-facing screens; backend, contracts, and the browser-only design preview may proceed in parallel.

## M0 — Foundation and browser feasibility

| ID | Depends | Planned files | Acceptance / verification |
| --- | --- | --- | --- |
| DGN-001 | none | docs/DESIGN_BRIEF.md, docs/DECISIONS.md | **Status: DONE.** Reconcile the design with active product/security contracts; record unresolved conflicts and owner decisions, including the Rolevo name. Manual evidence: reviewed decision record. |
| DGN-002 | DGN-001 | design tokens, logo assets, component library | **Status: DONE.** Define semantic color pairs, typography, spacing, focus/status tokens, Rolevo R logo variants, and reusable component states; verify rendered text/control/status contrast and small-size logo legibility. Manual evidence: token/component spec and contrast results. |
| DGN-003 | DGN-002 | design frames/prototype for dashboard, onboarding, extension, email, alerts | **Status: DONE.** Deliver the DESIGN_BRIEF screen and state coverage at 1440px, 1280px, 390px, and 360–420px extension widths, including empty, populated, loading, partial, unsupported, failure, and privacy/review states. Manual evidence: reviewable frames/prototype linked from handoff. |
| DGN-004 | DGN-003 | docs/design-validation/DGN-004-STUDY-KIT.md, docs/evidence/DGN-004.md | **Status: WAIVED for M0 by owner.** Do not conduct the five-job-seeker study in M0. No sessions, observations, or findings are claimed. This waiver removes DGN-004 from M0 exit criteria and does not count as usability validation. [Scope decision](evidence/DGN-004.md) |
| DGN-005 | DGN-003 | design handoff, component states, accessibility/responsive review | **Status: DONE for the M0 prototype/design handoff audit.** Keyboard/focus, screen-reader semantics, reduced-motion, 320px reflow, 44px targets, narrow layout, and semantic contrast were checked and recorded. Manual assistive-technology output and production-screen testing remain limitations, not completed claims. DGN-004 is not a dependency under the owner-approved M0 scope. [Evidence](evidence/DGN-005.md) |
| DGN-006 (owner/operator) | DGN-001 | brand decision/release evidence | **Status: DONE for product naming/identity decision.** Owner selected Rolevo and the R identity for product work. No legal or trademark clearance is claimed; external clearance remains a public-launch gate. [Evidence](evidence/DGN-006.md) |
| SET-001 | none | root manifests/locks, apps/web, apps/api | Node 22/Python 3.12/React/FastAPI shells, exact locked dependencies, real quality script interfaces and fresh setup. V-F, V-B |
| SET-002 | SET-001 | compose/config/health/test services | PostgreSQL/Azurite/fake identity/provider/source/test KEK work locally; production rejects fake/missing config. V-B |
| SET-003 | SET-001–002 | error/version/OpenAPI/client scripts | uniform errors, versioned schemas, generated TS client/drift, no API-to-HTML fallback. V-C |
| SET-004 | SET-001–003 | CI/workspace verification/evidence templates | frozen JS/Python setup and scoped synthetic CI; scripts do real checks, no unimplemented-feature fake success. V-F, V-B, V-C |
| EXT-001 | SET-001 | manifest/side panel/worker/build IDs | **Status: DONE for M0.** Exact permissions/origins/stable dev ID, local install/side-panel/safe demo, keyboard/live-status semantics, and unsupported states; no broad permissions/secrets. V-F, install smoke. [Evidence](evidence/EXT-001.md) |
| EXT-002 | EXT-001 | detector/field+option schema/fixtures | **Status: DONE for M0.** Selected visible form/job extraction, bounded metadata, sensitive/unrelated exclusions, valid sender/document handles, synthetic corpus and local Chrome inspection. V-X. [Evidence](evidence/EXT-002.md) |
| EXT-003 | EXT-002, SET-004 | prototype setters/options/event observers/corpus | **Status: DONE for M0.** Fake-profile native/React/options/review and passive submit observation work; manual edits/validation/unknown results preserved; four permitted forms/two hosts reviewed read-only; owner-confirmed local fixture fill. V-X. [Evidence](evidence/EXT-003.md) |

## M1 — Identity, persistence and durable work

| ID | Depends | Planned files | Acceptance / verification |
| --- | --- | --- | --- |
| DB-001 | SET-002–003 | models/Alembic/seed | **Status: DONE.** v2 entities/FKs/revisions/constraints/indexes from a fresh migration; loopback-only synthetic seed. V-DB evidence: [DB-001](evidence/DB-001.md). Independent review passed October 12, 2026. |
| DB-002 | DB-001 | RLS/roles/DB dependency | **Status: DONE.** Tenant RLS, transaction-scoped verified-owner context, hash-scoped auth lookups, and jobs-only worker access passed isolated PostgreSQL role, two-user, missing-context, and pool-reset checks. [Evidence](evidence/DB-002.md). V-DB, V-S |
| DB-003 | DB-002 | revision/idempotency/quota utilities | **Status: DONE.** Optimistic revisions, HMAC idempotency, and owner-locked expiring quota reservations passed stale-write, altered-input, concurrent duplicate-key, and quota-race checks on isolated PostgreSQL. [Evidence](evidence/DB-003.md). V-B, V-DB |
| AUTH-001 | SET-002–003, DB-002 | Authlib/OIDC/login/callback | **Status: IN_PROGRESS.** Authlib authorization-code/PKCE and Joserfc JWT signature validation are integrated with strict discovery, claim checks, exact callbacks, allowlisted enrollment, and subject/directory mapping. Local fake identity and security tests pass; actual tenant smoke remains. [Evidence](evidence/M1.md). V-B, V-S |
| AUTH-002 | AUTH-001, DB-003 | cookie/CSRF/session/logout/web UI | **Status: IN_PROGRESS.** Opaque idle/absolute sessions, stable CSRF, account initialization, revocation, and web sign-in shell pass the local lifecycle check; later tenant validation remains. [Evidence](evidence/M1.md). V-E, V-S |
| AUTH-003 | AUTH-002, EXT-001 | extension identity/grant/session store | **Status: IN_PROGRESS.** One-use 60-sec PKCE grant, exact extension/state checks, and trusted session storage pass extension and local fake-flow checks; real Chrome lifecycle checks remain. [Evidence](evidence/M1.md). V-X, V-S |
| AUTH-004 | AUTH-002–003 | fresh-auth/reset/tenant instructions | **Status: IN_PROGRESS.** Fresh-auth handling, local fake lifecycle configuration, and tenant setup instructions pass the local fake-flow check; actual tenant signup/reset/extension smoke remains. [Evidence](evidence/M1.md). V-E and later identity smoke |
| JOB-001 | DB-003, AUTH-002 | queue/worker/scheduler/leases | **Status: IN_PROGRESS.** Durable claims, heartbeat, cancellation, bounded worker concurrency, retry exhaustion, concurrent claims, PostgreSQL restart/reclaim, and worker idle/graceful-shutdown checks pass. One-minute scheduler ticks now dispatch unique daily runs through the `copilot_scheduler` role with six-hour catch-up and skipped-slot recording, and `monitoring.daily_scan`/`maintenance.owner_cleanup` handlers are registered via the shared registry; verified by isolated-PostgreSQL dispatch tests and a live scheduler→worker smoke. Independent review remains. [Evidence](evidence/M1.md). V-B, V-DB |
| KEY-001 | DB-003, AUTH-002, JOB-001 | crypto adapter/credentials API | **Status: IN_PROGRESS.** Per-record AES-GCM/wrapped DEK/AAD, masked summaries, owner/purpose unwrap, local rotation/delete, and managed-identity Key Vault RSA-OAEP-256 adapter are covered by local security tests. Live Key Vault permission/rotation smoke remains. [Evidence](evidence/M1.md). V-B, V-S |
| KEY-002 | KEY-001, AUTH-003 | provider settings/key UI/consent | **Status: IN_PROGRESS.** Three-provider route and saved-key consent APIs pass local integration checks for masking, revisions, revocation, and consent reset. The production AI-providers settings UI is now implemented (masked saved keys, per-purpose consent, ordered routes with If-Match revision handling); web unit/typecheck/build checks pass and the lifecycle test exercises the same endpoints. Manual browser/assistive-technology review and real tenant validation remain. [Evidence](evidence/M1.md). V-E, V-S |

## M2 — Onboarding and three-provider routing

| ID | Depends | Planned files | Acceptance / verification |
| --- | --- | --- | --- |
| PROF-001 | AUTH-002, DB-003 | rich profile editor/schemas/retrieval | **Status: IN_PROGRESS.** Fact CRUD with unique keys, immutable versions, sensitivity/purpose tags, confirmations, `If-Match` revision handling, and the profile editor UI pass local API checks; richer onboarding field groups and manual UI review remain. [Evidence](evidence/M2.md). V-B, V-E |
| DOC-001 | PROF-001, JOB-001 | upload/private storage/download/UI | **Status: IN_PROGRESS.** Ten-document/5 MiB/50 MiB quota, signature validation, hashing, immutable keys, private downloads, soft-delete invalidation, and idempotent upload pass Azurite-backed checks; replacement-version UX and independent review remain. [Evidence](evidence/M2.md). V-DOC, V-S |
| DOC-002 | DOC-001 | bounded subprocess/parser/anchors | **Status: IN_PROGRESS.** PDF/DOCX text+anchor extraction in a resource-limited subprocess with page/character/ZIP caps and explicit malformed/password-protected/scanned outcomes passes unit checks and a live worker→Azurite smoke; the 256 MiB bound is POSIX-enforced with documented macOS fallback. [Evidence](evidence/M2.md). V-DOC |
| AI-001 | KEY-002, PROF-001, SET-003 | provider contract/router/consent | **Status: IN_PROGRESS.** Five typed operations, extra-forbidden schemas, evaluated-model catalog, token/output ceilings, JSON-Schema export, and authoritative validation implemented; no tools or secret prompt input. [Evidence](evidence/M2.md). V-A |
| AI-002 | AI-001 | OpenRouter/Grok/Gemini adapters | **Status: IN_PROGRESS.** Three pinned-endpoint adapters normalize outcomes/usage and validate content; stubbed MockTransport tests cover success and every error class. Live endpoint/schema-mode verification remains opted-in. [Evidence](evidence/M2.md). V-A, V-B |
| AI-003 | AI-002, DB-003 | fallback/request/attempt/quota state | **Status: IN_PROGRESS.** Consent-gated routing implements the outcome state machine (fallback only for exhausted/rate/outage, one bounded 429 retry, invalid-key attention+consented fallthrough, bad-input/refusal/unknown stop), daily quotas, one active interactive op, and idempotent replay; verified on PostgreSQL. Circuit cooldown and live deadline checks remain. [Evidence](evidence/M2.md). V-A, V-S |
| DOC-003 | DOC-002, AI-003 | candidate extraction/review/conflict UI | **Status: IN_PROGRESS.** Durable `document.extract_candidates` job dispatches consented BACKGROUND extraction with restart-safe idempotency; candidates keep page/block anchors, one-shot confirm/reject writes document-sourced fact versions, source deletion marks versions for review; UI and API checks pass. Conflict-choice UX and cover-letter style distinction remain. [Evidence](evidence/M2.md). V-DOC, V-E |
| AI-004 | AI-003, DOC-003 | quality/source/claim/options corpus | **Status: IN_PROGRESS.** Nine recorded corpus cases across all five operations validate schemas and source-reference rules (absent section/field/fact/option/native-id rejected); live prompt/model evidence gated on opted-in provider eval. [Evidence](evidence/M2.md). V-A, V-L later |

## M3 — Autofill, tracking and dashboard

| ID | Depends | Planned files | Acceptance / verification |
| --- | --- | --- | --- |
| APP-001 | AUTH-002, DB-003 | applications/session CRUD/URL identity | prepared sessions separate from applications, exact attempt/channel/URL matching, optimistic CRUD/duplicate handling. V-B, V-E |
| APP-002 | APP-001 | status/evidence/history/snapshots | distinct Preparing/SubmissionAttempted/Applied evidence, immutable answers/context/docs, corrections append history. V-B, V-E |
| APP-003 | APP-002, PROF-001 | dashboard overview/filter/reminder UI | real empty state, drafts/jobs separate counts, bounded filters/date/timezone and accessible offline states. V-F, V-E |
| EXT-004 | EXT-003, AUTH-003, DOC-003, AI-003, APP-001 | context/profile retrieval/autofill pipeline | extract/correct context, use confirmed facts, ordinary answer batch/option IDs, exact sources and missing facts; keys stay server/trusted UI. V-X, V-A |
| EXT-005 | EXT-004 | account/document/field revision bindings | user Analyze action allows ordinary fill; stale/edited/replaced/navigated/account-switched writes rejected; sensitive attestations manual. V-X, V-S |
| EXT-006 | EXT-005 | setters/selection/review/results | post-render verified text/radio/select/checkbox outcomes; no guessed options/manual overwrite/Submit/Next; post-fill review and manual attachments. Full form gates V-X |
| TRACK-001 | EXT-006, APP-002 | passive trusted submit/event correlation | recognized pointer/keyboard/native selected-form events; validation error/SPA unknown/success fixtures; no prevented/triggered submit. V-X |
| TRACK-002 | TRACK-001, DB-003 | trusted minimal outbox/replay | same-account 24 h metadata-only outbox/idempotent replay, restart/offline delivery, purge on logout/switch/deletion; no action replay. V-X, V-S |
| TRACK-003 | TRACK-002, APP-003 | dashboard automatic event/status/confirmation | event automatically creates/updates one application; click doesn't mean Applied; site/user confirmation/date exposed, historical snapshots stable. V-E |

## M4 — Email applications

| ID | Depends | Planned files | Acceptance / verification |
| --- | --- | --- | --- |
| MAIL-001 | DOC-003, AI-003, APP-002 | email draft routes/UI/generation | recipient/job/start message → editable source-based subject/body, current style/doc hints, version/race/header/claim validation. V-A, V-E |
| MAIL-002 | MAIL-001 | compose encoding/copy/mailto/download UI | no connect/OAuth prompt; exact reviewed revision encoded; long/failed prefill fallback no truncation; manual attachments/Send. V-F, V-E |
| MAIL-003 | MAIL-002, TRACK-003 | compose/sent events/email tracking | open isn't Applied; explicit sent/date idempotently tracks USER_CONFIRMED_EMAIL and immutable snapshot. V-E |

## M5 — Daily source monitoring and notifications

| ID | Depends | Planned files | Acceptance / verification |
| --- | --- | --- | --- |
| MON-001 | KEY-002, JOB-001, PROF-001 | sources/preferences/schedule UI/API | ≤five public URLs, 09:00/timezone/next-run/consent/support/pause/check-now; private prefs only relevant. V-M, V-E |
| MON-002 | MON-001 | safe fetch/DNS/robots/HTML/feed/ATS extraction | pinned public TLS destinations/redirect/private/DNS/byte/page/time bounds, no login/JS/CAPTCHA bypass; source completeness/evidence. V-M, V-S |
| MON-003 | MON-002, AI-003 | due scheduler/run/dedupe/match pipeline | clients closed, one daily run/local date, DST/timezone/restart/catch-up; changed-text AI/circuit/deadline; stable postings/no false closure. V-M |
| MON-004 | MON-003, APP-003 | notifications/badge/job links/run UI | first summary/new-match digest, exact dedupe/read states, failed/partial/paused/no-key visible; discovered jobs not applications. V-M, V-E |

## M6 — Privacy, reliability and quality

| ID | Depends | Planned files | Acceptance / verification |
| --- | --- | --- | --- |
| DATA-001 | JOB-001, DOC-003, KEY-002, MON-004 | lifecycle/cleanup/cancel stages | docs/keys/sources removals stop use/jobs, cleanup bounded/restart safe, expired sessions/drafts/outbox/artifacts handled. V-B, V-S |
| DATA-002 | DATA-001, MAIL-003, TRACK-003 | export v2/snapshot/ZIP/privacy UI | full three-pillar data/originals/checksums, safe CSV/ZIP, consistent concurrency, private 24 h artifact, no key material. V-E, V-S |
| DATA-003 | DATA-001–002, AUTH-004 | account delete/journal/receipt/identity operator command | fresh auth/typed consent, immediate session/key/schedule revocation, journal before ack, cancel/late-result guard, visible identity stage/completion. V-E, V-S |
| QA-001 | DATA-003, AI-004, MON-004, MAIL-003, TRACK-003 | adversarial/three-pillar E2E/security | actual-role owner isolation, key canaries, parser/source SSRF/prompt races, provider unknown/outage, submit/email false-confirm negatives. V-S, V-E |
| QA-002 | QA-001 | performance/accessibility/fake-clock reports | declared dataset/gates/denominators, worker/scheduler doesn't block API; keyboard/screenreader/360px core paths. V-P, accessibility smoke |
| QA-003 | QA-001–002 | fresh install/limitations/contracts/evidence | current+previous compatible clients, exact fallback/source limits, private beta docs/operator runbooks, no fake completion claims. V-F, V-B, V-C, V-X, V-E |

## M7 — Future Azure private beta

These tasks are specifications only. The owner requested no connected Azure use during planning; no Azure action is executed now.

| ID | Depends | Planned files | Acceptance / verification |
| --- | --- | --- | --- |
| AZ-001 | SET-004, AUTH-004, DATA-003 | Bicep/config/quote/identity/network/KEK plan | later reviewable resources/cost/quota/roles/region/tenant/IDs and actual quote before provisioning. Future Bicep/what-if/quote |
| AZ-002 | AZ-001, QA-001 | Docker/supervision/OIDC CI/immutable artifacts | locked non-root web/API/worker/scheduler image, scoped roles/KEK/private DB, migration separate, prior rollback image. Future V-AZ |
| AZ-003 | AZ-002, QA-003 | isolated staging/beta evidence | later real identity/providers/source smoke/encryption/schedule/E2E; no fake prod config/secrets, redacted monitoring/budget. Future V-AZ/V-L/V-E/V-M |
| AZ-004 | AZ-003 | recovery/rollback/runbook evidence | later image rollback/new DB restore/journal replay/revoked keys/sessions/original-file checks and measured RPO/RTO. Future recovery drill |
| BETA-001 (owner/operator) | AZ-004, QA-003, AI-004 | checklist/artifacts/invitations/feedback | actual blocker evidence, two controlled form environments, three pillars, ten-user cap, identity/deletion coverage; owner release decision. RELEASE_CHECKLIST |

## Requirement traceability

FR-001→AUTH; FR-002→PROF/DOC; FR-003→KEY/AI; FR-004→EXT-001–004; FR-005→EXT-005–006; FR-006→TRACK; FR-007→APP; FR-008→MAIL-001; FR-009→MAIL-002–003; FR-010→MON-001–003; FR-011→MON-004; FR-012→DATA; FR-013→QA and feature state checks.

M0 first, then dependencies in M1–M7. Re-estimate after browser/source feasibility. Feature/model/privacy/budget changes revise PRD/ADR/contracts and task acceptance first. DONE needs recorded observed checks; planned scripts are not evidence.
