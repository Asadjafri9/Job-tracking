# Three-pillar verification specification

This repository contains planning documents only. Commands below are future implementation interfaces to create in SET-001–004; they are not currently runnable checks and have not been executed. No live provider calls, email sending or connected Azure validation is authorized by this planning turn.

| Code | Future command | Purpose |
| --- | --- | --- |
| V-F | `pnpm verify:frontend` | formatting, ESLint, TypeScript, Vitest, dashboard/extension build |
| V-B | `pnpm verify:backend` | uv-locked Ruff/mypy/pytest unit/API checks |
| V-DB | `pnpm verify:database` | isolated PostgreSQL migrations/upgrades, roles/RLS/FKs/concurrency |
| V-C | `pnpm verify:contracts` | OpenAPI regeneration/drift and prior compatible client fixtures |
| V-X | `pnpm verify:extension` | form extraction/fill/options/submit observations/outbox/restarts |
| V-E | `pnpm verify:e2e` | three-pillar journeys with synthetic identity/provider/source/storage |
| V-A | `pnpm verify:providers` | three adapters, schema/claims/options, fallback and key secrecy |
| V-DOC | `pnpm verify:documents` | bounded parser, candidate provenance/conflicts/quota/private files |
| V-M | `pnpm verify:monitoring` | fake clock/DST/daily uniqueness, SSRF, source parsing/dedupe/notifications |
| V-S | `pnpm verify:security` | two-user/key/CSRF/secret-canary/SSRF/account lifecycle checks |
| V-P | `pnpm verify:performance` | recorded API/inspection/provider/scheduler dataset and latency |
| V-L | `pnpm verify:providers:live` | explicit opted-in staging evaluation on supplied keys; no regular PR CI |
| V-AZ | `pnpm verify:deployment` | future image/IaC and read-only selected-environment checks |

Root scripts orchestrate JS/Python; pnpm doesn't install Python packages. CI freezes locks, uses synthetic data and separate least-privilege credentials. Live evaluations are a later explicit action with key/cost consent; don't fake results or bypass production limits. Save redacted evidence under `docs/evidence/<task>.md` with commit, command, runtime/browser/model/prompt versions, denominators, result and reviewer.

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
