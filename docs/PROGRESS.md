# Project progress

Updated October 13, 2026 · planning version 2.0.

| Area | Status |
| --- | --- |
| Planning baseline | READY_FOR_IMPLEMENTATION |
| Application implementation | IN_PROGRESS |
| Runtime verification / live provider evaluation | NOT_RUN |
| Azure / identity provisioning | NOT_STARTED |

Planning readiness means a maintainer can start the ordered backlog with selected scope and contracts. It does not mean the features exist, the models have passed evaluations or the product can be deployed today.

Completed documentation: three-pillar PRD, rich onboarding/document confirmation, OpenRouter/Grok/Gemini encrypted BYOK and fallback, autofill/review/submission evidence, Gmail handoff, local-time monitoring/notifications, architecture/authentication, database/API contracts, compatibility/security/lifecycle, task dependencies, verification gates, future Azure configuration and original-gap resolution mapping.

The planning work used no connected Azure services, live provider calls or outgoing email. Application foundation work is now underway locally; no cloud resource has been provisioned.

## M0 completion

**M0 is complete under the owner-approved scope.** SET-001–004, DGN-001–003, DGN-005–006, and EXT-001–003 are complete for their M0 acceptance criteria. The owner explicitly waived the five-job-seeker DGN-004 study for this milestone; it was not conducted and no research findings or user-validation claim are made. The brand is Rolevo by owner decision; legal/trademark clearance remains a public-launch check. DGN-005 records the prototype accessibility and layout audit; no manual screen-reader session or production accessibility certification is claimed. Broader site compatibility remains future work. No provider call or cloud provisioning was performed.

M1 implementation is underway in this checkout. DB-001 through DB-003 have observed migration, schema, tenant-isolation, idempotency, revision, and quota-race evidence on an isolated local PostgreSQL database. The full API suite passes (90 tests plus the env-gated compose/fake-service and web/extension OIDC lifecycle checks), as do Ruff and mypy; OpenAPI/client drift checks, web checks, and extension tests pass. Authlib authorization-code/PKCE and Joserfc JWT validation back the OIDC flow; local fake OIDC web/extension lifecycle and provider-key consent/revocation checks pass. `JOB-001` now includes the one-minute scheduler tick (unique daily runs, six-hour catch-up, skipped-slot recording, dedicated `copilot_scheduler` role) and registered workload handlers verified by isolated-PostgreSQL dispatch tests and a live scheduler→worker smoke; the scan handler records an honest pending outcome until the M5 fetch pipeline lands. The production provider-settings UI is implemented under KEY-002 with masked keys, purpose consent, and revision-checked routing saves; manual browser/assistive-technology review is still unrecorded. Independent review and real tenant/Chrome/Key Vault smoke remain open. Keep M1 **IN_PROGRESS**. See [M1 evidence](evidence/M1.md), [DB-002 evidence](evidence/DB-002.md), and [DB-003 evidence](evidence/DB-003.md). Do not treat code presence or synthetic checks as live tenant completion.

Local foundation has no known external prerequisite. Later tasks need actual External ID configuration, extension IDs, opted-in provider keys/live evaluation, permitted source/form checks and future Azure subscription/region/SKU/quota/cost review. Those prerequisites remain unverified; record a blocker when it affects a task.

## M2 progress

**M2 is IN_PROGRESS with all eight tasks implemented and locally verified.** The profile editor (versioned fact CRUD, confirmations, purpose tags, `If-Match` concurrency), private document upload/download (Azurite, 10-file/5 MiB/50 MiB quotas, signature checks, idempotent upload, parse-job enqueue), the bounded subprocess parser (PDF/DOCX, page/block anchors, 15 s CPU, ≤50 pages, ≤100k chars, ≤25 MiB ZIP expansion; `RLIMIT_AS` 256 MiB on POSIX with documented macOS fallback), the typed provider contract and capability catalog, the three stub-verified adapters, the consent-gated fallback router (outcome state machine, daily quotas, idempotent replay), the durable `document.extract_candidates` job with one-shot confirm/reject review UI, and the nine-case offline corpus all pass on the loopback stack (145 API tests, plus web lint/typecheck/tests/build and `alembic check` clean). **No live provider call, real Key Vault operation, or Chrome/tenant validation was performed** — provider checks are `httpx.MockTransport`-only and extraction candidates require explicit background consent. Keep M2 **IN_PROGRESS** pending live provider evaluation (V-L), manual UI review, and independent review. See [M2 evidence](evidence/M2.md).

Task owner: implementing maintainer. Release/scope/budget owner: project owner. Operator owns identity cleanup and deployment/recovery coverage.

## M3 progress

**M3 is IN_PROGRESS with the application/tracking spine implemented and locally verified.** Prepared application sessions (canonical HTTPS URL identity, fact/document revision snapshots, open-session bounds) stay strictly separate from applications; a trusted submit event idempotently creates exactly one `SUBMISSION_ATTEMPTED` record and never counts as Applied; status history is append-only with site-vs-user evidence; applied-answer snapshots record what was actually filled under context-revision binding; the Applications page renders dashboard counts, filters, history, and the confirm-applied flow; the extension gained a durable 24 h account-bound metadata-only outbox with idempotent replay and sign-out purge, plus panel wiring for prepare-tracking, AI draft answers, and passive submit observation. Verified: 12 PostgreSQL-backed API tests, 22 extension tests, 141 total API tests, web lint/typecheck/12 tests/build, `alembic check` clean. **No real Chrome lifecycle, live hiring site, or provider call was performed** — keep M3 **IN_PROGRESS** pending live-form gates (V-X), manual UI review, and independent review. See [M3 evidence](evidence/M3.md).

Task owner: implementing maintainer. Release/scope/budget owner: project owner. Operator owns identity cleanup and deployment/recovery coverage.

## M4 progress

**M4 is IN_PROGRESS with the email application workflow implemented and locally verified.** Owner-scoped versioned email drafts (recipient/header validation, confirmed EMAIL-purpose fact snapshots, consent-gated generation, `If-Match` edits), the Gmail compose handoff (fixed origin, verified encoding, 6,000-char copy fallback, no OAuth/send), and honest send tracking (compose-opened is never Applied; explicit dated confirmation idempotently creates one EMAIL application with an immutable snapshot) all pass: 7 new API tests, 149 total API tests, 15 web tests, contracts regenerated. **No Gmail OAuth, real sending, or live provider call was performed.** See [M4 evidence](evidence/M4.md).

## M5 progress

**M5 is IN_PROGRESS with the monitoring pipeline implemented and locally verified.** Monitored-source CRUD with ≤five cap, consent-revision scheduling, pause/resume/remove and 3/day check-now; the bounded public fetch boundary (SSRF/DNS-pinning/redirect/robots/byte/time guards); JSON-LD/RSS/Atom/anchor extraction; the claim→fetch→apply scan pipeline with canonical-URL dedupe, meaningful-revision diffs and two-complete-scan closure; and the Job alerts UI with notifications badge/list and run history all pass: 48 monitoring unit tests, 17 PostgreSQL API/pipeline tests, 214 total API tests, contracts regenerated. **No live career page, ATS endpoint, DNS/TLS fetch, or AI matching call was performed; deterministic matching only.** See [M5 evidence](evidence/M5.md).

## M6 progress

**M6 is IN_PROGRESS with the privacy lifecycle implemented and locally verified.** DATA-001/002/003 are done locally: cleanup now expires application sessions, stale drafts, expired jobs and export artifacts; `privacy.export` builds a manifest/checksum ZIP inside one owner transaction with a double secret deny-list, formula-safe CSV, sanitized member names and a private 24-hour download; account deletion requires fresh auth + typed consent, revokes sessions/keys/schedules/jobs and writes the independent journal before acknowledging, then a durable stage-2 job erases owned data and tombstones identity through self-scoped view/SECURITY DEFINER functions (users stays outside tenant RLS for auth bootstrap). The new `#privacy` page covers exports and the deletion flow. Verified: 14 new tests (5 unit + 9 role-backed), 245 total API tests, web checks, `alembic check`, regenerated contracts. QA-001–003 are partially evidenced — key-canary/live-provider adversarial runs, formal perf gates, fresh assistive-tech review and beta runbooks remain open. **No Azure, provider, Gmail or Chrome contact.** See [M6 evidence](evidence/M6.md).

Task owner: implementing maintainer. Release/scope/budget owner: project owner. Operator owns identity cleanup and deployment/recovery coverage.

## Next implementation action

Proceed to M7 — future Azure private beta — following the dependency order in [`TASKS.md`](TASKS.md). M6 implementation does not mean the product is ready to deploy.

## Evidence ledger

| Item | Status | Evidence | Reviewer/date |
| --- | --- | --- | --- |
| v2 planning documents | DONE (documentation only) | plan.md and linked contracts/tasks; local document checks below | Codex, October 12, 2026 |
| SET-001 | DONE | [SET-001 evidence](evidence/SET-001.md): clean locked setup; V-F passed; V-B passed with host ROS `PYTHONPATH` isolated | Codex, independent review passed October 12, 2026 |
| SET-002 | DONE | [SET-002 evidence](evidence/SET-002.md): PostgreSQL/Azurite healthy on loopback; runtime and migration roles checked; API readiness and fake OIDC/provider/source integration passed; production fake/missing config rejected | Codex, independent review passed October 12, 2026 |
| SET-003 | DONE | [SET-003 evidence](evidence/SET-003.md): V-C OpenAPI/client generation and drift; shared error response, compatibility and no-HTML-fallback checks; V-F/V-B passed | Codex, independent review passed October 12, 2026 |
| SET-004 | DONE | [SET-004 evidence](evidence/SET-004.md): frozen workspace setup, synthetic foundation CI, real V-F/V-B/V-C aggregate, and evidence templates | Codex, independent review passed October 12, 2026 |
| DB-001 | DONE | [DB-001 evidence](evidence/DB-001.md): fresh and idempotent PostgreSQL migration, seed, drift check, nine schema checks, API suite, Ruff, and mypy | Codex, independent review passed October 12, 2026 |
| DB-002 | DONE | [DB-002 evidence](evidence/DB-002.md): fresh isolated migration, no drift, nine DB-001 schema checks and eight tenant RLS/role checks passed | Codex, October 13, 2026 |
| DB-003 | DONE | [DB-003 evidence](evidence/DB-003.md): concurrent idempotency reuse, altered-input conflict, stale revision rejection, and quota race passed; owner-child constraints passed | Codex, October 13, 2026 |
| M5 implementation | IN_PROGRESS | [M5 evidence](evidence/M5.md): sources/schedule/consent API+UI, safe fetch/extract boundary, scan dedupe/closure/match pipeline, notifications; 65 new tests, 214 API tests; no live fetch or AI matching | pending review |
| M1 implementation | IN_PROGRESS | [M1 evidence](evidence/M1.md): full API suite 90 passed plus opt-in lifecycle checks; Authlib/Joserfc local auth checks, scheduler dispatch + registered handlers, provider-settings UI, worker shutdown checks, frontend, extension, contracts, and static checks pass; independent review and tenant/Chrome/Key Vault smoke remain | Codex, October 14, 2026 |
| DGN-001 | DONE | [DGN-001 evidence](evidence/DGN-001.md): design/contract reconciliation, proposed defaults and explicit unresolved owner decisions | Codex, independent review passed October 12, 2026 |
| DGN-002 | DONE | [DGN-002 evidence](evidence/DGN-002.md): proposed tokens/components, all 16 rendered contrast pairs, and small-size/full-lockup SVG review | Codex, independent review passed October 12, 2026 |
| DGN-003 | DONE | [DGN-003 evidence](evidence/DGN-003.md): prototype; latest render has 46 desktop/mobile/extension viewport screens including 320px reflow; accessibility audit in DGN-005 | Codex, reviewed October 12, 2026 |
| DGN-004 | WAIVED for M0 | [DGN-004 evidence](evidence/DGN-004.md): owner waived five-person research; no participants, sessions, observations, or findings | Owner scope decision, October 12, 2026 |
| DGN-005 | DONE | [DGN-005 evidence](evidence/DGN-005.md): 38-route keyboard, semantic, reduced-motion, control-target, contrast, and 320px reflow audit; assistive-tech limits recorded | Codex, October 12, 2026 |
| DGN-006 | DONE for internal name decision | [DGN-006 evidence](evidence/DGN-006.md): owner-selected Rolevo name and R identity applied to app, extension, prototype, and design assets; external clearance is not claimed | Owner decision; implementation review October 12, 2026 |
| EXT-001 | DONE for M0 | [EXT-001 evidence](evidence/EXT-001.md): owner screenshots/manual confirmation confirm install, side-panel launch, safe-demo fill, and local fixture inspection/fill; 17/17 tests and brand build pass | Codex, October 12, 2026 |
| EXT-002 | DONE for M0 | [EXT-002 evidence](evidence/EXT-002.md): bounded selected-form/job schemas, sensitive getter traps, opaque context handles and synthetic exclusion corpus | Codex, October 12, 2026 |
| EXT-003 | DONE for M0 | [EXT-003 evidence](evidence/EXT-003.md): reviewed fill/manual-edit protections and passive observation pass; owner-confirmed local fill; four public forms/two hosts inspected read-only | Codex, October 12, 2026 |

Local document review passed on October 12, 2026: 21 active Markdown documents, 56 existing local links, 52 unique tasks with valid references and an acyclic dependency graph, and all 13 functional requirements mapped. Active-file whitespace and `git diff --check` passed. The original reference documents are archival and excluded from active-contract checks. These checks do not replace any future runtime verification command in TESTING.

For implementation evidence use `docs/evidence/<ID>.md`: task state, files/commit, commands, observed results, denominators, limitations and reviewer. Leave failing or unchecked acceptance IN_PROGRESS/IN_REVIEW; never invent a commit, test result or deployment.
