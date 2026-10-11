# Email application workflow

## UI and generation

Dashboard section `/email-applications` lists DRAFT, READY_TO_SEND, COMPOSE_OPENED and SENT_CONFIRMED items. New draft requires one valid recipient email, employer, role, job description/excerpt and optionally a starting message. A selected resume/current cover letter/project selection guides writing; only confirmed facts support factual claims. Style can come from a user-reviewed cover letter. Missing information is flagged rather than invented.

Generate subject/body with the same provider order/fallback/consent rules as autofill. Store owner-scoped versioned drafts and source/context snapshots; user can edit, regenerate or delete. Preserve edits on network/provider failures and stale revision responses. Validate recipient, subject ≤200 chars and body ≤10,000 chars. Reject CR/LF in recipient/subject and unsafe header/address injection; body remains ordinary editable text. No HTML execution.

Review screen shows the exact recipient, subject, body, selected attachment reminder and source/factuality warnings. User clicks Open in Gmail only after reviewing the current revision. No Gmail connection prompt, OAuth tokens or mailbox permission exist in this release.

## Compose handoff

Build an encoded URL with the conventional Gmail compose parameters, e.g. `https://mail.google.com/mail/?view=cm&fs=1&to=...&su=...&body=...`, using URLSearchParams. Open only from the user's explicit button action and only to the fixed Gmail origin; do not accept a target URL from AI/job content. Gmail login/account selection happens in Gmail.

This is a best-effort UI handoff, not a guaranteed Gmail API contract. Always provide Copy recipient, Copy subject, Copy message, Open Gmail without prefill, and a standard mailto option. If the generated URL exceeds the conservative 6,000-character limit or prefill is unavailable, explain the copy fallback; never truncate silently or report prefill succeeded without observation. Do not log compose URLs or include their content in analytics/referrers. Opening a compose link necessarily places reviewed content into the browser/Gmail environment; disclose this at the action.

Original resumes/cover letters remain private files. Offer Download selected resume and an attachment reminder; the user attaches files through Gmail. Do not claim URL-prefill attaches documents or sends messages.

## Tracking

Open in Gmail appends COMPOSE_OPENED only; it is not Applied or sent. On return, ask the user whether they sent the message, with a clear “I sent this email” action and date. This explicit action creates/updates the email application as Applied with USER_CONFIRMED_EMAIL, draft revision, recipient/job context and answer/body snapshot. “Not sent yet” keeps the draft. Repeat clicks/confirmations reuse keys and don't duplicate an application; another attempt requires explicit action.

Editing a compose-opened draft creates a new revision but doesn't rewrite previously confirmed-sent snapshots. The app cannot observe Gmail delivery without an authorized integration and does not infer delivery from tab closure. Direct Gmail OAuth/send may be added later through a new scope/verification decision; it isn't required for this workflow.

Acceptance: verified encoding of Unicode/newlines and `&?+#`, no header injection/truncation, long-message copy fallback, Gmail logged-out/multiple-account handoff, attachment instructions, correct draft/open/sent statuses and immutable historical snapshot. Sending live email is not part of automated testing.
