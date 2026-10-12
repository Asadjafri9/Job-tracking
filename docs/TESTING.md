# Three-pillar verification specification

The repository has working foundation checks for the existing web shell, API foundation, and OpenAPI/client contract. `pnpm verify:foundation` checks pinned local runtime versions, then runs V-F, V-B, and V-C; GitHub Actions runs this same scope after frozen dependency installation. These checks do not claim product-feature acceptance. Feature UI/API/database suites, the browser extension, and later integration suites remain incomplete. CI needs no secrets, database containers, cloud resources, live identity, provider calls, or outbound messages.

| Code | State | Command | Scope |
| --- | --- | --- | --- |
| V-F | Implemented, foundation only | `pnpm verify:frontend` | formatting, ESLint, TypeScript, Vitest, and React web build. Add extension build when EXT-001 exists. |
| V-B | Implemented, foundation only | `pnpm verify:backend` | uv-locked Ruff/mypy/pytest. Local service integration is opt-in and otherwise reports a skip. |
| V-C | Implemented | `pnpm verify:contracts` | Export FastAPI OpenAPI, regenerate TS paths in a temporary directory, and compare both artifacts byte-for-byte. |
| V-DB | Planned; no script registered | Not available | PostgreSQL migrations/upgrades, roles/RLS/FKs/concurrency. |
| V-X | Planned; no script registered | Not available | Form extraction/fill/options/submit observations/outbox/restarts. |
| V-E | Planned; no script registered | Not available | Three-pillar journeys with synthetic identity/provider/source/storage. |
| V-A | Planned; no script registered | Not available | Provider schemas/claims/options, fallback, and key secrecy. |
| V-DOC | Planned; no script registered | Not available | Bounded parsing, provenance/conflicts/quota/private files. |
| V-M | Planned; no script registered | Not available | Fake clock/DST/daily uniqueness, SSRF, source parsing/dedupe/notifications. |
| V-S | Planned; no script registered | Not available | Two-user/key/CSRF/secret-canary/SSRF/account lifecycle checks. |
| V-P | Planned; no script registered | Not available | Recorded API/inspection/provider/scheduler dataset and latency. |
| V-L | Planned, explicit staging opt-in required; no script registered | Not available | Live provider evaluation; never regular PR CI. |
| V-AZ | Planned; no script registered | Not available | Future image/IaC and read-only selected-environment checks. |

Root scripts orchestrate JS/Python; pnpm does not install Python packages. The JS workspace uses `pnpm-lock.yaml`; the API uses `apps/api/uv.lock`. CI uses `corepack pnpm install --frozen-lockfile` and `uv sync --locked`. No placeholder script reports success: a planned gate is explicitly marked unavailable and running a nonexistent package script exits as an error. Only implement a gate when it can perform and report its real checks. CI is scoped to synthetic foundation verification with read-only repository permissions and no secret configuration. Live evaluations require a later explicit action with key/cost consent. Use [the task evidence template](evidence/TASK_TEMPLATE.md) and [the release evidence template](evidence/RELEASE_TEMPLATE.md); record exact commands, observed results, denominators, limitations and reviewer, and redact secrets/personal data.

For SET-002's local-services check, start PostgreSQL/Azurite with `pnpm local:services:up` and the loopback fake service with `pnpm dev:mocks`, then set `SET002_LOCAL_SERVICES=1` and the local environment values before running V-B. This enables one integration test for the runtime/migration roles, authenticated Azurite/API readiness, OIDC authorization-code PKCE, and synthetic provider/source routes. Without that opt-in flag, the integration test is skipped, keeping ordinary V-B independent of Docker.

V-C exports the OpenAPI document directly from the FastAPI app without starting a server, regenerates the browser TypeScript definitions from that document, and byte-compares both outputs against checked-in artifacts. Run `pnpm generate:contracts` after an intentional contract change; `pnpm verify:contracts` must then pass with no committed-artifact drift.

## Corpora and measurable gates

**Forms:** ≥12 fixtures/100 labeled controls across native contact/prose/number/date/options/repeated groups, negation, confirmed/missing facts, sensitive attestations, React accepted/reverted changes, dynamic/replaced fields, unrelated forms, iframe/shadow widgets and manual-edit races. Supported detection/fill ≥95%; zero wrong target, guessed sensitive choice, manual overwrite or extension-triggered submission. Verify immediate/post-render values and partial failure reporting. Unsupported cases are not successes.

**Submission evidence:** trusted pointer/keyboard clicks/native submit, validation-blocked click, SPA rejection, generic navigation/unknown outcome, tested positive/negative site signals, duplicate click/native correlation, lost network, worker restart/outbox TTL/account switch/deletion. Bare click/compose-open never marks Applied. Passive observations never prevent/trigger Submit. Stable event replay creates one attempt.

**Provider quality:** 50-case core corpus per enabled provider, three live runs each: answerable factual drafts, missing/conflicting information, objective-claim traps, prompt injection/schema/refusal. Annotate claims against ground truth independently of model self-citations. Zero surfaced unsupported objective claims/invalid source refs; ≥90% valid relevant outputs on answerable cases; missing facts blocked. Additional fixtures: 30 factual/negated option mappings, 15 personalized emails and 20 job extraction/matching cases. Evaluate model/router privacy/capability changes before enabling them. Limit live test quota only in explicit synthetic staging configuration.

**Fallback/keys:** definitive quota/rate/unavailability advances through only consented enabled keys; invalid key needs_attention; input/refusal/claim failure stops; timeout/unknown doesn't redispatch. At most configured attempts/deadline. Test encrypted key AAD swaps/rotation/delete, two-user unwrap denial, no full GET, no keys in prompts/builds/outbox/exports/logs/APM. Validate every saved/background consent revocation.

**Documents:** ≥12 text PDF/DOCX/LinkedIn/cover-letter fixtures: correct facts/anchors, contradictory dates/claims, scanned/protected/malformed/oversize/ZIP bomb/path cases. Confirmed facts must come from explicit review, no automatic cover-letter achievement proof. Limits/timeouts/restart/private download/default-version/quota reservation and orphan cleanup pass; manual profile entry survives parser/provider failure.

**Email:** Unicode/newline/query encoding, header injection, edit/revision, body-length/copy fallback, Gmail logged-out/multiple-account/open behavior, manual attachment reminder, duplicate compose/sent confirmation and snapshot preservation. No sending actual mail in automated tests, no Applied from handoff alone.

**Monitoring:** fixtures for HTML/JobPosting/RSS/ATS listings: empty/new/duplicate/changed/closed/incomplete/denied/JS-only/error, first-run summary, unchanged hash, preference changes and all providers unavailable. Zero invented jobs/URLs and duplicate alerts. DNS/private/metadata/IPv6/redirect/rebinding/size/time fixtures prove SSRF bounds. Fake clock verifies 09:00 local, DST, timezone change, lease/restart, six-hour catch-up and exactly one daily run/source/local date. With ten users/five sources each and healthy dependencies: p95 dispatch ≤5 minutes, completion target ≤30 minutes. Failures remain visible; unsuccessful scan never implies closed/no jobs.

**Data lifecycle:** two-user API/RLS/private blob/key/draft/source/notification access; real runtime roles and pooled context reset. Complete export v2 matches known profile/documents/application/email/source/job/notification checksums; safe ZIP/CSV and concurrent edits/deletes. Account deletion immediately revokes keys/session/schedule, cancels queued jobs, rejects outbox replay/late results and survives worker restart. SUCCEEDED requires operator identity stage; retained backup boundaries shown. Independent journal prevents resurrection after isolated restore.

**E2E:** signup → rich profile/docs → confirm candidates → configure ordered providers → empty application dashboard → analyze/autofill/review → user submit observation → evidence-aware dashboard; email draft/edit → compose handoff → explicit sent; public sources/preferences → simulated local 09:00 with browser closed → notifications → job opening. Include no-key/manual-fact flow, no available provider, partial fill/source results, auth expiry and account switch.

**Performance/accessibility:** beta dataset ten users, 200 facts/user, 500 applications/user, ten 5 MiB docs/user and five sources/user. JSON API p95 <500 ms at ten concurrent users; inspect 100 controls p95 <1 s; interactive provider-chain deadline 60 s/measured p95 target <30 s across ≥20 successful operations. Parser is separately bounded; worker backpressure cannot block normal API. First-party keyboard/screen-reader paths and ≥360px dashboard pass with no critical core-flow accessibility defects.

## Severity

P0: cross-user data/key exposure, unauthorized submit/send, unrecoverable loss. P1: false confirmed submission, broken core pillar/approval/factuality/deletion/isolation, unsafe network access. Both block release and cannot waive critical invariants. P2: contained defect with explicit manual fallback/impact/owner/follow-up. Measure/document rather than mark DONE from planned tests.
