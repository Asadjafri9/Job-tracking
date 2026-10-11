# Planning review and gap resolutions

Version 2.0 · October 12, 2026. The [original review](REFERENCE_PLAN_REVIEW.md) of commit `3e88cc1` and [broad roadmap](REFERENCE_ROADMAP.md) are historical; active linked documents govern implementation.

## Readiness conclusion

**The planning baseline is ready to begin implementation with SET-001.** React/FastAPI/PostgreSQL/Azure, all three flows, authentication/storage, three-provider routing and boundaries are selected. Tasks specify dependencies, acceptance and future checks. No application has been built or runtime behavior verified; external identity/provider/source/cloud prerequisites remain implementation gates.

This incorporates the owner's onboarding/autofill/email/09:00-monitoring flow and instruction to plan without connected Azure. It provisions no services and sends no email.

## Original review: resolution matrix

| Gap | Planning resolution | Specification / tasks |
| --- | --- | --- |
| 1. MVP not frozen | Three pillars/three providers in first complete release; OAuth/direct send and expansion deferred | [PRD](PRD.md), [DECISIONS](DECISIONS.md); feature tasks, QA-003 |
| 2. Browser feasibility late | M0 prototype before feature foundation; explicit control/browser matrix and manual fallback | [COMPATIBILITY](COMPATIBILITY.md); EXT-001–003 |
| 3. Storage/auth unresolved | PostgreSQL/private originals authoritative; backend identity/web cookies/extension grants; no local sync MVP | [ARCHITECTURE](ARCHITECTURE.md), [DATABASE](DATABASE.md); DB-001–003, AUTH-001–004 |
| 4. Stale fill authorization | Analyze permits ordinary fill before review; exact account/document/field/revision/value binding; attestations manual | [AUTOFILL_TRACKING](AUTOFILL_TRACKING.md), [API](API.md); EXT-005–006 |
| 5. Gmail permissions unclear | Compose/copy handoff without OAuth/send API; explicit sent confirmation | [EMAIL_APPLICATIONS](EMAIL_APPLICATIONS.md); MAIL-001–003 |
| 6. Fact provenance missing | Versioned candidates/anchors, confirmation/conflicts; cover-letter style separate from proof | [ONBOARDING](ONBOARDING.md); PROF-001, DOC-001–003 |
| 7. Job context missing | Bounded extracted/manual context, corrections/missing flags and injection boundaries | [AUTOFILL_TRACKING](AUTOFILL_TRACKING.md), [EMAIL_APPLICATIONS](EMAIL_APPLICATIONS.md); EXT-004, MAIL-001 |
| 8. Application identity/status unclear | Posting/attempt identity, stable event keys, separate drafts, click/site/user evidence and immutable history | [PRD](PRD.md), [DATABASE](DATABASE.md); APP-001–003, TRACK-001–003 |
| 9. Offline/account-switch invariants missing | Minimal same-owner evidence outbox with TTL; logout/switch purge, deletion denial and no action replay; local profile sync deferred | [AUTOFILL_TRACKING](AUTOFILL_TRACKING.md), [SECURITY_PRIVACY](SECURITY_PRIVACY.md); AUTH-003, TRACK-002, DATA-003 |
| 10. Lifecycle incomplete | All-feature export, retention, immediate revocation/durable deletion/identity cleanup and independent journal | [SECURITY_PRIVACY](SECURITY_PRIVACY.md); DATA-001–003, AZ-004 |
| 11. Distribution/version compatibility missing | Stable environment extension IDs, ten-user unpacked Chrome beta, generated versioned API/current-prior clients and incompatible-version guidance | [COMPATIBILITY](COMPATIBILITY.md), [API](API.md); EXT-001, SET-003, QA-003 |
| 12. Quality/operations not owned or measurable | Declared corpora/denominators, owned gates/tasks/evidence, future Azure config/quote/rollback/recovery and unchecked release checklist | [TESTING](TESTING.md), [TASKS](TASKS.md), [PROGRESS](PROGRESS.md), [DEPLOYMENT](DEPLOYMENT.md), [RELEASE_CHECKLIST](RELEASE_CHECKLIST.md); AI-004, QA-001–003, AZ-001–004 |

These are documentation resolutions. Mitigations are proven only when implementation checks pass.

## Added requirements resolved

- Rich onboarding includes LinkedIn PDF, cover letter, projects/tips and optional personal facts with confirmation/purpose controls.
- Saved encrypted keys enable background work; session-only mode is interactive. Three adapters use evaluated models/explicit fallback consent. Unknown completion stops retries.
- Checkbox/radio/select answers use known meaning/confirmed facts; unknown questions, attestations and demographics remain manual.
- Automatic submission observation is separate from success; offline replay contains minimal event metadata only.
- Gmail opening cannot prove sending; long/failed prefill has copy fallback without truncation.
- Server checks at 09:00 local with DST/restart rules, safe public fetching and deduplicated notifications; discovery alone is not an application.

## Remaining implementation gates

Validate actual controls/event evidence, provider availability/schema/factuality on supplied keys, permitted source compatibility, real identity and future Azure cost/capacity/roles/recovery. [RISKS](RISKS.md) assigns owners/checks. Exact dependency patches are locked in SET-001. None of these external prerequisites is claimed as already tested.
