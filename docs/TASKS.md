# Three-pillar implementation backlog

Every task starts NOT_STARTED. Statuses: NOT_STARTED, IN_PROGRESS, BLOCKED, IN_REVIEW, DONE. Implementing maintainer owns tasks unless marked owner/operator. Dependencies require evidenced completion; independent tasks may proceed once inputs exist. Verification codes are future scripts defined in TESTING, not checks already run; design tasks specify their manual evidence directly. Evidence: `docs/evidence/<ID>.md` with commit/files/commands/results/reviewer. Split oversized responsibilities into numbered child tasks retaining requirements/dependencies. DGN-005 gates implementation of production user-facing screens; backend, contracts, and the browser-only design preview may proceed in parallel.

## M0 — Foundation and browser feasibility

| ID | Depends | Planned files | Acceptance / verification |
| --- | --- | --- | --- |
| DGN-001 | none | docs/DESIGN_BRIEF.md, docs/DECISIONS.md | Reconcile the proposed Aster design with active product/security contracts; record unresolved conflicts and owner decisions. Brand and visual direction remain proposed until explicitly accepted. Manual evidence: reviewed decision record. |
| DGN-002 | DGN-001 | design tokens, logo assets, component library | **Status: DONE.** Define semantic color pairs, typography, spacing, focus/status tokens, Guiding A logo variants, and reusable component states; verify rendered text/control/status contrast and small-size logo legibility. Manual evidence: token/component spec and contrast results. |
| DGN-003 | DGN-002 | design frames/prototype for dashboard, onboarding, extension, email, alerts | **Status: DONE.** Deliver the DESIGN_BRIEF screen and state coverage at 1440px, 1280px, 390px, and 360–420px extension widths, including empty, populated, loading, partial, unsupported, failure, and privacy/review states. Manual evidence: reviewable frames/prototype linked from handoff. |
| DGN-004 | DGN-003 | design validation notes/prototype revisions | Test the key journeys with at least five representative job seekers; observe setup, form review without submission, application evidence, email handoff, and alert-source setup; record issues and resulting design changes. Manual evidence: anonymized findings and iteration notes. |
| DGN-005 | DGN-003, DGN-004 | design handoff, component states, accessibility/responsive review | Publish implementation notes and final design references; complete keyboard/focus, screen-reader labels/errors/status, reduced-motion, 200% zoom, touch-target, narrow-layout, and semantic contrast review with no unresolved critical core-flow issue. Manual evidence: handoff and review report. Production UI tasks wait for this gate. |
| DGN-006 (owner/operator) | DGN-001 | brand decision/release evidence | Before public brand use, record the owner's decision after name/logo/domain availability and distinctiveness checks; retain evidence and any resulting rename work. No public-launch clearance is implied by this planning task. |
| SET-001 | none | root manifests/locks, apps/web, apps/api | Node 22/Python 3.12/React/FastAPI shells, exact locked dependencies, real quality script interfaces and fresh setup. V-F, V-B |
| SET-002 | SET-001 | compose/config/health/test services | PostgreSQL/Azurite/fake identity/provider/source/test KEK work locally; production rejects fake/missing config. V-B |
| SET-003 | SET-001–002 | error/version/OpenAPI/client scripts | uniform errors, versioned schemas, generated TS client/drift, no API-to-HTML fallback. V-C |
| SET-004 | SET-001–003 | CI/workspace verification/evidence templates | frozen JS/Python setup and scoped synthetic CI; scripts do real checks, no unimplemented-feature fake success. V-F, V-B, V-C |
| EXT-001 | SET-001 | manifest/side panel/worker/build IDs | exact permissions/origins/stable dev ID; installs/accessibility/unsupported states; no broad permissions/secrets. V-F, install smoke |
| EXT-002 | EXT-001 | detector/field+option schema/fixtures | selected visible form/job extraction, bounded metadata, sensitive/unrelated exclusions, valid sender/document handles. V-X |
| EXT-003 | EXT-002, SET-004 | prototype setters/options/event observers/corpus | fake-profile native/React/options/review and passive submit observation work; manual edits/validation/unknown results preserved; permitted live inspection report. V-X |

## M1 — Identity, persistence and durable work

| ID | Depends | Planned files | Acceptance / verification |
| --- | --- | --- | --- |
| DB-001 | SET-002–003 | models/Alembic/seed | v2 entities/FKs/revisions/constraints/indexes from fresh migrations; synthetic seed. V-DB |
| DB-002 | DB-001 | RLS/roles/DB dependency | runtime non-owner/no BYPASSRLS; owner context transaction-local; two-user/pool/missing-context checks. V-DB, V-S |
| DB-003 | DB-002 | revision/idempotency/quota utilities | races handled, duplicate keys reuse entity, altered input conflicts, owner-child constraints and reservations. V-B, V-DB |
| AUTH-001 | SET-002–003, DB-002 | Authlib/OIDC/login/callback | state/nonce/issuer/audience/signature/PKCE/redirect validation, allowlisted enrollment, verified subject/directory mapping. V-B, V-S |
| AUTH-002 | AUTH-001, DB-003 | cookie/CSRF/session/logout/web UI | idle/absolute expiry, stable CSRF, account initialization, all-client revocation, no browser provider token. V-E, V-S |
| AUTH-003 | AUTH-002, EXT-001 | extension identity/grant/session store | one-use 60-sec PKCE app grant, exact ID/state, trusted storage, restart/expiry/switch behavior. V-X, V-S |
| AUTH-004 | AUTH-002–003 | fresh-auth/reset/tenant instructions | fake CI lifecycle; later actual tenant signup/reset/extension smoke; no prod fake bypass. V-E and later identity smoke |
| JOB-001 | DB-003, AUTH-002 | queue/worker/scheduler/leases | durable claims/heartbeat/cancellation/stages, bounded concurrency/retries and visible exhaustion; restart safe. V-B, V-DB |
| KEY-001 | DB-003, AUTH-002, JOB-001 | crypto adapter/credentials API | per-record AES-GCM/wrapped DEK/AAD, masked GET, owner/purpose unwrap and rotation/delete; test KEK only locally. V-B, V-S |
| KEY-002 | KEY-001, AUTH-003 | provider settings/key UI/consent | three slots/order/saved or session-only/background/fallback permissions; revoked key stops new jobs, no key plaintext persistence/export/log. V-E, V-S |

## M2 — Onboarding and three-provider routing

| ID | Depends | Planned files | Acceptance / verification |
| --- | --- | --- | --- |
| PROF-001 | AUTH-002, DB-003 | rich profile editor/schemas/retrieval | contact/history/projects/links/tips/optional purpose-scoped facts; confirmations/revisions, unknowns and conflicts. V-B, V-E |
| DOC-001 | PROF-001, JOB-001 | upload/private storage/download/UI | ten 5 MiB docs/50 MiB reservation, types/versions/defaults/hash/private downloads and orphan failure cleanup. V-DOC, V-S |
| DOC-002 | DOC-001 | bounded subprocess/parser/anchors | PDF/DOCX/LinkedIn/cover-letter text parsing, memory/time/ZIP limits, unsupported/scanned paths and restart safe. V-DOC |
| AI-001 | KEY-002, PROF-001, SET-003 | provider contract/router/consent | typed operations/capability catalog/source references/limits; minimum relevant facts; no tools or secret prompt input. V-A |
| AI-002 | AI-001 | OpenRouter/Grok/Gemini adapters | exact model/schema mode verified, normalized outcomes/usage, stubbed success/refusal/error, authoritative validation. V-A, V-B |
| AI-003 | AI-002, DB-003 | fallback/request/attempt/quota state | definitive exhausted/rate/outage fallback only consented keys; bad input/refusal/unknown stops; deadlines/idempotency/circuit status correct. V-A, V-S |
| DOC-003 | DOC-002, AI-003 | candidate extraction/review/conflict UI | AI candidates consented, anchors/versioned source, explicit confirmation, cover-letter style distinct from claims, changes invalidate pending work. V-DOC, V-E |
| AI-004 | AI-003, DOC-003 | quality/source/claim/options corpus | every enabled adapter passes factuality/schema/reference/option/email/job cases with recorded prompt/model evidence; later opted-in live eval. V-A, V-L later |

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
