# Plan review

Initially reviewed on October 12, 2026 against `plan.md` at commit `3e88cc1`. Updated the same day for the project owner's selected React, FastAPI, PostgreSQL, and Azure stack. References below use task or section identifiers so they remain usable as the plan changes.

The roadmap has useful safeguards: explicit user approval, private storage, row-level security tests, parser confirmation, AI output validation, and failure recovery. Its main weakness is that it describes decisions to make without resolving the decisions needed to execute the first release. The repository contains the roadmap, README, and this review; the PRD, ADRs, and task tracker are still future deliverables. The core stack is now fixed, while authentication and individual Azure services remain decisions to resolve.

These findings concern planning and acceptance criteria. They are not claims about defects in an implementation. P1 findings should be resolved before the affected implementation begins; P2 findings should be resolved before beta.

## 1. P1 — Freeze a concrete MVP and resolve contradictory feature placement

**Evidence:** Task 00.3 asks for a feature inventory, but none exists. Section 1.1 promises tailored cover letters, while Phase 17 places cover-letter generation after the MVP. Gmail has a full pre-release phase, and the decision about mailbox-based tracking is delayed until Task 13.8. Local/cloud sync is also built before first browser functionality.

**Impact:** Developers cannot determine the smallest releasable product, and a working application tracker could be delayed by optional integrations and synchronization.

**Add:** A feature table with one release assignment per feature, the primary user, explicit exclusions, and decision ownership. Resolve cover letters, Gmail, managed AI, multiple storage modes, and synchronization in Phase 00. Link each included requirement to its implementation and verification tasks.

**Acceptance:** Every feature has exactly one release assignment. A complete first-release journey can be demonstrated without any deferred feature.

## 2. P1 — Validate browser feasibility before building the full foundation

**Evidence:** Extension detection and autofill arrive in Phases 09–10, after database, authentication, resume processing, synchronization, and dashboard work. No target hiring platform or supported browser version is named. File inputs and radios are detected in Task 09.2, but the filling tasks explicitly cover inputs, textareas, selects, and checkboxes. Iframes, shadow roots, multi-step forms, and CAPTCHA handoff have no explicit supported/unsupported decision.

**Impact:** The product can accumulate substantial infrastructure before proving it can complete a useful real application flow. Detection may also be mistaken for fill support.

**Add:** An early feasibility task using a small fake profile and representative permitted test forms. Create a compatibility matrix covering site/form variant, control type, inspect/fill support, browser version, unsupported behavior, and manual fallback. Decide whether resume attachment is included; distinguish selecting a file from a site uploading it after a change event.

**Acceptance:** Demonstrate inspect → review → fill → verify on a declared target flow. Confirm that unsupported controls fail visibly and that any site upload caused by filling is disclosed before approval. Turn this demonstration into a fixture for regression testing.

## 3. P1 — Select the storage and authentication contract before schema implementation

**Evidence:** Task 06.1 defines local/cloud modes after the cloud database, account lifecycle, profile persistence, and resume features have been implemented. It acknowledges that an extension-local profile needs an explicit path to the web dashboard, but no such path is selected. The updated stack section and Task 11.2 move credential-model selection into Phase 01; the corresponding ADR and mode decision still need to be written.

**Impact:** Account requirements, identifiers, profile access, resume processing, provider calls, and dashboard behavior may all need to change when the mode is chosen.

**Add:** Resolve these decisions in Phase 01. Specify the initial authoritative store, whether local mode requires an account, which UI owns local data, and whether and how dashboard/extension communication works. The updated plan places initial AI calls behind FastAPI; select the per-user credential mechanism and explain any remote processing of locally stored facts. Describe cloud opt-in and return-to-local behavior.

**Acceptance:** A mode/feature table identifies every network dependency and data transmission. No core feature depends on a storage or session mechanism that has not been selected.

## 4. P1 — Bind approval to the exact answer, field, and page state

**Evidence:** Tasks 10.1–10.4 allow editing, approval, and target validation. Task 09.8 allows dynamic reinspection, and Task 08.5 validates messages. None specifies when approval expires or how a privileged fill request is bound to its original sender and document.

**Impact:** A delayed request could fill an edited answer, a different field, or a replacement form using an earlier approval. A structurally valid message may still originate from the wrong tab/frame.

**Add:** An approval contract containing answer revision, profile revision where relevant, tab/frame/document identity, field identity, and the expected field state. Validate message sender and allowed operation independently of schema validity. Invalidate approval when the answer or relevant context changes, after navigation, or when the field has been replaced. Give each sensitive declaration its own confirmation.

**Acceptance:** Reject or request renewed approval when the user edits an approved answer, the page navigates, the DOM replaces a field, the user manually changes its value, or another tab attempts to replay a request. Preserve manual edits on retry.

## 5. P1 — Correct the Gmail permission assumption and include verification work

**Evidence:** Tasks 13.2 and 13.7 aim for narrow permissions and permission-boundary tests, but do not specify the actual scope. The release plan omits Gmail OAuth verification as a dependency.

**External constraint:** The standard Gmail `users.drafts.create` endpoint accepts `gmail.compose`, `gmail.modify`, or the full mail scope. The narrowest of these, `gmail.compose`, permits draft management and email sending and is classified as restricted. Consequently, a drafts-only product cannot rely on this OAuth scope to prohibit sending. Public-release verification and the applicability of a security assessment must be evaluated for the chosen data flow. See [draft creation authorization](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.drafts/create) and [scope classification and verification](https://developers.google.com/workspace/gmail/api/auth/scopes).

**Add:** An ADR choosing API draft creation, a user-operated compose handoff, or deferral. If API drafts are included, restrict the application interface and backend to authorized draft operations, protect tokens, and test that no application path invokes a send operation. Record verification prerequisites and an owner before scheduling the launch.

**Acceptance:** The product explains the actual requested capability accurately. Its draft workflow does not invoke sending, and applicable external verification prerequisites are satisfied before public release.

## 6. P2 — Specify durable provenance and verification state for profile facts

**Evidence:** Task 05.9 already requires confirmation of parsed facts; Tasks 10.3 and 11.7 require attribution. However, the proposed data model does not specify source identifiers, verification state, revisions, or how conflicting facts are resolved.

**Impact:** “Verified” can become a UI label with no enforceable data meaning. Two resumes can disagree about a date, or a generated answer can reference a source that has since changed.

**Add:** A fact model or equivalent metadata recording source, source revision, confirmation state/time, and user edits. Distinguish user-confirmed facts from extracted candidates and generated prose. Validate returned source references against the facts actually supplied to the model; define conflict resolution and staleness behavior. Preserve application snapshots as Task 12.3 already proposes.

**Acceptance:** Unconfirmed parser output is excluded from verified generation context. Contradictory sources require resolution, invalid source references are rejected, and changed facts invalidate dependent pending suggestions.

## 7. P2 — Define how job context reaches the generation pipeline

**Evidence:** Task 11.6 includes “Why are you interested in this role?” The request in Task 11.5 lists the question and profile/resume context but does not define employer, role, job description, or their capture and review flow. Task 12.3 saves employer and role after browser and AI implementation.

**Impact:** Role-specific answers may become generic or invent employer details. Developers must infer how and when to capture job information.

**Add:** A job-context contract with employer, role, source URL, selected relevant description text, provenance, and missing-context flags. Specify extension extraction versus manual input, user review, size limits, and the minimum information required for each generation operation. Keep page text untrusted as the existing threat model requires.

**Acceptance:** A role-specific answer uses reviewed context. Missing employer or role details produce a request for information or an explicitly limited draft. Malicious description text cannot change the operation or authorize additional data access.

## 8. P2 — Define application identity and when an application counts as submitted

**Evidence:** Task 12.1 lists statuses, Task 12.2 creates records manually or through the extension, and Task 12.4 supports manual status updates. There is no matching rule between a job posting and an application attempt or a default status for a saved form.

**Impact:** Reopening a form or retrying a save can create duplicates. Saving filled answers can be confused with successful submission even though the extension deliberately does not submit.

**Add:** A posting/application identity rule, retry idempotency, duplicate review behavior, and an explicit transition contract. Decide how to handle the same role advertised through several URLs and legitimate reapplications. Save prepared forms as Preparing unless the user confirms submission; record the source and time of an Applied transition. Define date/timezone behavior for follow-ups.

**Acceptance:** Retrying the same save does not duplicate the record. Reapplication is possible deliberately. Filling or saving a form alone never marks it Applied.

## 9. P2 — Add sync invariants for account switching and offline deletion

**Evidence:** Tasks 06.6–06.8 already address revisions, deletion markers, conflicts, and sign-out with pending changes. They do not state queue ownership, the account-switch contract, or how long deletion markers survive disconnected devices.

**Impact:** An offline operation can be replayed against the wrong account, or a stale device can recreate a deleted record after its deletion marker has expired.

**Add:** Account-scoped local stores and pending operations, server-authorized ownership, optimistic concurrency, and explicit replay semantics. Specify sign-out retention/purge behavior, cloud opt-out, tombstone retention, and what happens when a device returns after the permitted offline interval. Make account deletion cancel or permanently reject outstanding writes.

**Acceptance:** Queue a write as user A, sign out, and sign in as B: the write never enters B's account. A stale device cannot silently resurrect a deleted record. Replayed requests remain idempotent.

## 10. P2 — Make export, deletion, and retention implementable

**Evidence:** Account deletion is introduced as planning in Phase 04; Task 12.8 specifies application export; Task 14.10 verifies deletion across caches, queues, integrations, and backups. No single task specifies a complete export schema, retention periods, deletion completion state, or token-revocation ownership.

**Impact:** Separate features may implement incompatible deletion semantics. A user may receive a success message while files, tokens, or queued work remain active.

**Add:** A lifecycle matrix per data category with retention, export inclusion, deletion owner, retry behavior, and completion evidence. Include profile data, original resumes, saved answers, application history, credentials, local copies, and operational records. Define the boundary for disconnected devices and backup retention. Define a portable, versioned complete export rather than only an application list.

**Acceptance:** A full export contains the documented user data. Partial cleanup is visible and retried. Revoked/deleted integrations cannot run pending work. A deletion report distinguishes completed cleanup from explicitly documented retention.

## 11. P2 — Specify extension distribution and version compatibility

**Evidence:** Tasks 15.4–15.5 define a release build and development-mode installation. Task 15.10 publishes an MVP but does not choose store versus unpacked distribution or specify compatibility with deployed API changes. The roadmap separately mentions a later expansion to site-specific adapters.

**Impact:** A beta may depend on undocumented installation steps, and old installed extensions can break when the backend or shared schemas change.

**Add:** A distribution decision, production/development extension identities, an API/message version contract, minimum supported versions, upgrade UX, and a rollback procedure. Declare store submission prerequisites if store distribution is chosen. Package any extension-side adapter logic according to Manifest V3 requirements; remote data must not be treated as executable adapter code. See [Chrome Manifest V3 requirements](https://developer.chrome.com/docs/webstore/program-policies/mv3-requirements).

**Acceptance:** Install the chosen beta build from the documented channel. An older supported extension still works after a compatible backend deployment; an incompatible version fails with an actionable upgrade message. A rollback preserves usable data.

## 12. P2 — Turn quality and operations into owned release gates

**Evidence:** Task 00.6 lists metrics, Task 11.10 lists AI evaluation dimensions, and Phase 14 has extensive tests. Numeric targets are intentionally deferred until baselines exist, but no task requires a baseline and approved thresholds before beta. Recovery procedures and costs are mentioned without owners, restore evidence, or budgets.

**Impact:** “Important workflows pass” can mean different things to each reviewer. The team can declare completion without proving useful accuracy, latency, affordability, or recovery.

**Add:** A baseline milestone and release gate with a declared representative corpus, measurement denominator, supported-form coverage, acceptable failure limits, generation latency, and expected cost per application. Test wrong-field fills and unsupported factual claims separately from schema validity. Assign owners to risks, decisions, release work, incidents, and recovery; estimate milestones after the feasibility task. Include upload size/count limits and a restore exercise appropriate to the selected storage mode.

**Acceptance:** The release checklist links measured evidence for each agreed threshold. Costs and service limits have an owner and budget. A documented recovery exercise demonstrates restoration of both records and relevant resume files. Unresolved critical findings prevent release.

## Recommended first release and execution sequence

This is a proposed scope for the PRD, not an existing product decision.

Start with one primary user: a recent graduate repeatedly applying to technology roles. Include a user-confirmed profile, resume selection with manual attachment unless the feasibility task proves attachment support, a basic application tracker, a declared Chrome/form compatibility set, review and approved filling, one provider and one credential model, and complete export/deletion behavior.

Choose one initial storage mode. Cloud storage with an account would fit the current dashboard stack; local-first would require an explicit local management UI and processing contract. Defer bidirectional synchronization, Gmail OAuth, mailbox scanning, managed AI billing, cover letters, and additional providers until the first complete application flow works.

Recommended order:

1. Freeze the PRD, feature assignments, and privacy/storage/credential decisions.
2. Prove one inspect → review → fill flow and document the compatibility matrix.
3. Implement the selected persistence, authentication where needed, profile, and basic tracker.
4. Implement approval validity and the full extension-to-tracker flow.
5. Add one AI generation operation with reviewed job context and fact provenance.
6. Measure quality, exercise failure/deletion/upgrade paths, and release a limited beta.

Retain the roadmap's incremental implementation and verification rules. Reorder tasks around these milestones and move planning decisions ahead of the components that depend on them.

## Stack-specific decisions added to the roadmap

The selected architecture is React dashboard and extension → FastAPI → PostgreSQL/private storage/AI providers. The plan now adds Python setup, backend tests, migrations, API startup, OpenAPI client generation, explicit origins, and Azure deployment work.

These additions identify required work; they do not constitute implemented controls or completed architecture decisions:

- **Authentication:** Select the identity provider and dashboard/extension session contract. FastAPI validates identity and enforces ownership; Azure hosting does not supply this contract automatically.
- **Database isolation:** Specify runtime and migration roles. If RLS is used, define transaction-scoped user context and test pooled connections; database owners and elevated roles can bypass policies unless the role/policy design accounts for them. See [PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html).
- **Cross-language contracts:** Keep authoritative Pydantic schemas in Python and generate the browser API client from OpenAPI. Add drift checks rather than assuming TypeScript packages can be imported by FastAPI.
- **Azure topology:** Confirm the proposed Static Web Apps, App Service, PostgreSQL, Blob Storage, Key Vault, and monitoring choices, including region, service plans, cost, networking, and deployment identity. The specific service choices remain recommendations.
- **Credential lifecycle:** Distinguish service secrets from encrypted per-user BYOK and OAuth tokens. Define authorization, rotation, revocation, and deletion for each.
- **Processing:** Decide whether resume parsing fits bounded API requests or requires durable jobs. Define restart and retry behavior appropriate to the selected Azure runtime.
- **Client security:** Define separate dashboard and extension origins and authorization behavior. CORS allows browser access; it does not authenticate callers. See [FastAPI CORS guidance](https://fastapi.tiangolo.com/tutorial/cors/).
