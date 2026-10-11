# Three-pillar product requirements

Version 2.0 · October 12, 2026. This incorporates the owner's detailed flow: autofill, email applications and daily job updates.

## User and outcome

Primary user: technology student/recent graduate/professional repeatedly applying to jobs. Private beta: ten invited adults, English UI/questions, desktop Chrome extension and responsive dashboard. Build a reusable professional knowledge profile, prepare truthful applications quickly, record submission evidence and discover new matching openings from chosen sources.

## Functional requirements

| ID | Requirement | Acceptance | Tasks |
| --- | --- | --- | --- |
| FR-001 | Managed signup/login/reset/logout | Same identity on web/extension; immediate application-session revocation | AUTH-001–004 |
| FR-002 | Rich profile and private documents | Manual details plus resume/LinkedIn PDF/cover letter; parse preview/confirmation/conflicts/provenance; optional personal data controls | PROF-001, DOC-001–003 |
| FR-003 | Three-provider BYOK/fallback | OpenRouter DeepSeek V4 Flash, xAI Grok and Gemini; one or several keys; masked/encrypted saved keys; ordered consented fallback and visible outcomes | KEY-001–002, AI-001–004 |
| FR-004 | Extract current job/form context | User-invoked inspection selects one form; captures employer/role/description/questions/options; ambiguous context editable | EXT-001–004 |
| FR-005 | Autofill text and factual options | Analyze and autofill writes supported answers/options from confirmed facts; review afterwards; unresolved/attestation fields stay manual | EXT-005–006 |
| FR-006 | Observe user's submission and record dashboard | Trusted click/submit recorded automatically; validate failure/unknown/site signal distinguished; retries and offline observations deduplicated | TRACK-001–003 |
| FR-007 | Dashboard/history/reminders | Empty application state at signup; prepared drafts/discovered jobs separate; statuses, evidence, filters, date-based follow-ups | APP-001–003 |
| FR-008 | Personalized email draft | Recipient/job text/starting message → subject/body from confirmed profile/projects/style; editable and versioned | MAIL-001 |
| FR-009 | Gmail compose handoff | No connection prompt; Open in Gmail prefill or explicit copy fallback; manual attachments/Send; user-confirmed sent record | MAIL-002–003 |
| FR-010 | Saved-source daily monitoring | Up to five public sources; 09:00 user timezone, server-side while clients closed; safe extraction/matching and run status | MON-001–003 |
| FR-011 | New-job notifications | Navbar badge/Notifications page; deduplicated source-linked openings; readable failure/paused status, no unchanged spam | MON-004 |
| FR-012 | Complete export and deletion | Versioned all-data export with original documents; key plaintext excluded; account cleanup stops jobs/keys/session access and reports retained boundaries | DATA-001–003 |
| FR-013 | Accessible/reliable operations | Keyboard paths, visible offline/unsupported/partial results, provider/source recovery, bounded resource usage | QA-001–003 and feature tasks |

## Onboarding journey

1. Sign up through managed identity; choose timezone and cloud-data disclosure.
2. Enter full/contact details, education/experience/skills/projects, links, preferences and useful writing/application notes. Age/DOB and other optional personal facts have separate controls; missing fields remain unknown.
3. Upload resume, LinkedIn-export PDF, current cover letter and optional supporting document. Originals are private. Preview parsed candidates, resolve contradictory dates/claims and confirm useful facts. Cover-letter wording is style context, not automatic proof of achievements.
4. Add one or more provider keys; choose provider/model order and consent to fallback. Save encrypted keys if daily background checks are desired; session-only keys support interactive use.
5. Dashboard initially shows “No applications yet,” setup progress and optional empty email/source/notification states. Do not populate fake applications or count discovered vacancies as applications.

## Autofill journey

User opens a job form and clicks Analyze and autofill. Extractor identifies visible job context/questions/options; user can correct ambiguous employer/role or selected form. Backend maps confirmed facts and drafts answer batches. Supported ordinary text and factual choices are filled without a separate approval click for every field. The side panel shows filled values/sources, unanswered questions and errors, and asks the user to review before submitting.

If the user edits a value, no later response overwrites it. Generated or confirmed fact changes require fresh context binding. The extension never submits. On the user's trusted submit action, record the attempt and automatically create/update a dashboard application. A failed validation click is an attempted event and returns the record to Preparing with the failure noted. Generic uncertain submission appears “Submitted — unconfirmed.” A tested site-success signal or explicit user confirmation records Applied with its evidence source. The form's review state is not itself evidence of submission.

Normal factual yes/no/select/multi-select/checkbox questions may be chosen only when their meaning and confirmed answer are known. Unknown work authorization/salary/personal questions are not guessed. Final certifications/terms/consent and sensitive demographic answers require manual completion. No automatic resume upload in this release; selected resume is available to download/attach manually.

## Email journey

User opens Email applications, enters a valid recipient, employer/role/job description and optionally an existing message. AI customizes the subject/body using confirmed facts, projects, selected resume facts and reviewed cover-letter style. User reviews/edits the message and opens Gmail compose. There is no Gmail connection prompt or token.

Copy recipient/subject/body is always available, including long-message fallback. User attaches the selected document and sends in Gmail. On return, “I sent this email” creates/updates the tracked application as Applied with USER_CONFIRMED_EMAIL/date. Opening Gmail remains Compose opened and cannot prove delivery.

## Monitoring journey

User saves public career URLs and role/location/remote preferences, explicitly enables daily checks and background provider-key use. Show timezone, next 09:00 local run, source support/last result and pause/remove controls. Worker runs with browser closed. First scan shows a summary of current matching jobs and seeds deduplication; later scans notify new matches/changed matching conditions without duplicates. A failed/unsupported source is visible and never reported as “no jobs.” Opening a notification can lead to a job page/autofill session; it does not create an application until a submission/email confirmation event.

## Records, status and dates

Channels: WEB_FORM and EMAIL. Statuses: Interested, Preparing, SubmissionAttempted, Applied, Assessment, Interview, Offer, Rejected, Withdrawn. UI distinguishes prepared form sessions/email drafts/discovered openings from actual tracked application records. Applied evidence is SITE_REPORTED_SUCCESS, USER_CONFIRMED_FORM or USER_CONFIRMED_EMAIL, never a compose open or bare click.

Per-user canonical posting URL + attempt number identifies a form application. Without a URL, use explicit user selection/creation key; never merge by employer/title alone. Preserve job-identifying query parameters; strip fragments/known trackers/secrets. Reapplications and linking alternate URLs require explicit user action. Retries/events have stable keys; status corrections append history rather than rewrite evidence.

Instants are UTC. Application/follow-up dates use the user's IANA timezone and date-only format. Monitor schedule is 09:00 local, independent of host timezone. Timezone edits recompute the next strictly future run and do not replay an already completed local-day run.

## Release boundaries

Documents are text-based PDF/DOCX; OCR deferred. Public rendered HTML/feed/ATS APIs are monitorable; authenticated, CAPTCHA and JS-only sources are unsupported unless a later approved adapter exists. “Any job form” means user-initiated best-effort inspection with explicit supported-control coverage, not guaranteed compatibility with every site/widget.

Gmail OAuth/direct send, mailbox scanning, automated submission, auto attachments, broad authenticated scraping, local-only profiles/sync, managed billing, Firefox and public store release are deferred. The requested three pillars and three providers are included in the first complete product release.

Accessibility target: first-party WCAG 2.2 AA, keyboard-only and screen-reader core paths, dashboard ≥360 px. Learning metric: median preparation-time reduction compared with manual baseline across five beta users; track with consented content-free counters, not personal answers.
