# Design reconciliation

**Task:** DGN-001  
**Status:** Prepared for owner review; not complete until open product choices are resolved.  
**Authority:** `DESIGN_BRIEF.md` is a proposed design direction. `PRD.md`, `DECISIONS.md`, `SECURITY_PRIVACY.md`, and the feature contracts remain the active product and behavior contracts.

## Areas that align

- The calm task workspace, progressive disclosure, and one clear primary action support the three product flows in `PRD.md` without making AI chat the main interface.
- Showing sources, missing facts, uncertainty, and user edits matches the confirmed-fact and provenance rules in `ONBOARDING.md`, `PROVIDERS.md`, and `AUTOFILL_TRACKING.md`.
- Keeping submit, attestations, attachments, Gmail sending, and application confirmation with the user matches `DECISIONS.md`, `SECURITY_PRIVACY.md`, `AUTOFILL_TRACKING.md`, and `EMAIL_APPLICATIONS.md`.
- Separating discovered jobs, prepared drafts, attempted submissions, and confirmed applications matches `PRD.md` and `JOB_MONITORING.md`.
- Just-in-time data-use notices, manual sensitive answers, and visible partial/failure states match the existing privacy and feature contracts.
- The design's WCAG 2.2 AA goal and narrow-screen behavior match the accessibility target in `PRD.md` and the evidence gate in `TASKS.md`/`TESTING.md`.
- The browser prototype is explicitly labeled as sample-only and disconnected from persistence or external actions, consistent with the current planning-only implementation status.

## Decisions still needed

| Topic | Design brief | Active contract | Recommendation for review | State |
| --- | --- | --- | --- | --- |
| Product name and visual identity | Aster and “Sage & ink” are proposed; the logo/name need distinctiveness and availability checks. | `DECISIONS.md` selects product technology and behavior but does not accept the Aster brand. | Keep Aster, the tagline, palette, and logo as prototype-only proposals until the owner accepts them; preserve a rename path. | Open owner decision; DGN-006 covers pre-public-use checks. |
| Age/DOB onboarding | Omit age/DOB unless a supported use case exists. | `PRD.md` and `ONBOARDING.md` allow these as optional, separate-purpose facts and prohibit inference. | Do not place age/DOB in the default onboarding flow. Add an explicit purpose-specific control only after the owner confirms a real use case. | Open owner decision before those fields appear in production UI. |
| Application status wording | The design proposes concise labels such as “Ready to review,” “Submission attempted,” “Applied,” and “Closed.” | `PRD.md` defines canonical states including Interested, Preparing, SubmissionAttempted, Applied, Assessment, Interview, Offer, Rejected, and Withdrawn; evidence determines when Applied is valid. | Keep canonical states and evidence rules in storage/API. Before UI implementation, define a reviewed copy mapping; never collapse an unconfirmed attempt into Applied or imply that “Ready to review” is a submitted application. | Open mapping; include in DGN-003 screen handoff. |
| Accessibility palette | Starting colors are candidates; the brief explicitly says pairings have not yet been verified. | `PRD.md` and `TESTING.md` require WCAG 2.2 AA evidence for core paths. | Treat the palette as provisional until semantic text, control, focus, selection, and status pairs pass contrast and interaction review. | Open verification; DGN-002 and DGN-005. |

## Implementation boundary

The prototype can continue as a design artifact. Production UI should follow the reviewed handoff in DGN-005. API, data, and backend foundation work may proceed independently, while feature behavior continues to follow the active contracts listed above. Do not treat any proposal in this review as an accepted product decision without the owner's confirmation.

## Review record

This comparison found no conflict in the core safety boundaries: Aster does not submit applications, send email, infer attestations, or report success without evidence. The product-name/identity choice, the conditions for exposing age/DOB, and the user-facing application-status mapping remain owner decisions. Resolve these before the relevant production screens are finalized.
