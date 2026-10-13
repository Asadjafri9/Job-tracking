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

## Next implementation action

**M0 is not complete.** SET-001–004 and DGN-001–003 are done; EXT-001–003 have passed independent code/synthetic review, and the owner confirmed local Chrome fixture inspection/fill, but accessibility and broader compatibility checks remain open. DGN-004 is **BLOCKED** awaiting five consenting representative job seekers; DGN-005 is blocked on that study; DGN-006 awaits the owner's brand/clearance decision. See the evidence below. No user study, accessibility sign-off, owner brand approval, provider call, or cloud provisioning is claimed.

M1 implementation is underway in this checkout. DB-001 through DB-003 have observed migration, schema, tenant-isolation, idempotency, revision, and quota-race evidence on an isolated local PostgreSQL database. The full API suite passes (72 tests), as do Ruff and mypy; OpenAPI/client drift checks, web checks, and extension tests also pass from the earlier run. Authlib authorization-code/PKCE and Joserfc JWT validation now back the OIDC flow; local fake OIDC web/extension lifecycle and provider-key consent/revocation checks pass. `JOB-001` worker idle and graceful shutdown checks pass; scheduler ticks and registered workload handlers remain unimplemented pending dependent feature contracts. Independent review, real tenant/Chrome/Key Vault smoke, and the DGN-005-gated production settings UI remain open. Keep M1 **IN_PROGRESS**. See [M1 evidence](evidence/M1.md), [DB-002 evidence](evidence/DB-002.md), and [DB-003 evidence](evidence/DB-003.md). Do not treat code presence or synthetic checks as live tenant completion.

Local foundation has no known external prerequisite. Later tasks need actual External ID configuration, extension IDs, opted-in provider keys/live evaluation, permitted source/form checks and future Azure subscription/region/SKU/quota/cost review. Those prerequisites remain unverified; record a blocker when it affects a task.

Task owner: implementing maintainer. Release/scope/budget owner: project owner. Operator owns identity cleanup and deployment/recovery coverage.

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
| M1 implementation | IN_PROGRESS | [M1 evidence](evidence/M1.md): full API suite 72 passed; Authlib/Joserfc local auth checks, worker shutdown checks, frontend, extension, contracts, and static checks pass; scheduler/handlers, independent review, and tenant/UI gates remain | Codex, October 13, 2026 |
| DGN-001 | DONE | [DGN-001 evidence](evidence/DGN-001.md): design/contract reconciliation, proposed defaults and explicit unresolved owner decisions | Codex, independent review passed October 12, 2026 |
| DGN-002 | DONE | [DGN-002 evidence](evidence/DGN-002.md): proposed tokens/components, all 16 rendered contrast pairs, and small-size/full-lockup SVG review | Codex, independent review passed October 12, 2026 |
| DGN-003 | DONE | [DGN-003 evidence](evidence/DGN-003.md): browser-only prototype and 42 rendered screens across 1440/1280/390 and 360/420px targets; user study and accessibility review remain outstanding | Codex, independent review passed October 12, 2026 |
| DGN-004 | BLOCKED | [DGN-004 evidence](evidence/DGN-004.md): moderator kit and templates prepared; awaiting five representative participants; no sessions or findings claimed | — |
| DGN-005 | BLOCKED | [DGN-005 evidence](evidence/DGN-005.md): awaiting DGN-004 study; no handoff/accessibility sign-off claimed | — |
| DGN-006 | BLOCKED | [DGN-006 evidence](evidence/DGN-006.md): preliminary name/domain research recorded; owner decision and appropriate clearance outstanding | — |
| EXT-001 | IN_REVIEW | [EXT-001 evidence](evidence/EXT-001.md): owner screenshots confirm manual install, side-panel launch, safe-demo fill, and owner-confirmed local regular-page inspection/fill; accessibility checks remain open | Codex, partial review October 12, 2026 |
| EXT-002 | IN_REVIEW | [EXT-002 evidence](evidence/EXT-002.md): bounded selected-form/job schemas, sensitive getter traps, opaque tab/document/form context validation and synthetic exclusion corpus; local Chrome fixture inspection confirmed | Codex, partial review October 12, 2026 |
| EXT-003 | IN_REVIEW | [EXT-003 evidence](evidence/EXT-003.md): reviewed fill/manual-edit protections and passive observation pass synthetic checks; owner confirms local Chrome fixture fill; four public form structures reviewed read-only | Codex, partial review October 12, 2026 |

Local document review passed on October 12, 2026: 21 active Markdown documents, 56 existing local links, 52 unique tasks with valid references and an acyclic dependency graph, and all 13 functional requirements mapped. Active-file whitespace and `git diff --check` passed. The original reference documents are archival and excluded from active-contract checks. These checks do not replace any future runtime verification command in TESTING.

For implementation evidence use `docs/evidence/<ID>.md`: task state, files/commit, commands, observed results, denominators, limitations and reviewer. Leave failing or unchecked acceptance IN_PROGRESS/IN_REVIEW; never invent a commit, test result or deployment.
