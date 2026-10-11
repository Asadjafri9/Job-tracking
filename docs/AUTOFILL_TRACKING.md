# Autofill and submission tracking

## Analyze → fill → review

User invokes Analyze and autofill on a permitted HTTPS job page. `activeTab` gives temporary inspection access; choose one visible application form if ambiguous. Extract bounded employer/role/description text, labels, requirements, options and section/group metadata. Original page content is untrusted and never authorizes commands. Ask for corrections only when context is ambiguous; employer/role/description candidates have source anchors and a reviewed or explicitly accepted analysis revision.

Create a private `application_session` holding account, context revision, profile/fact revisions, document/form identity and final draft snapshots. It is a prepared session, not a submitted application. The dashboard application count stays empty until a submit observation or explicit application creation occurs.

Contact/history facts map deterministically. AI drafts open answers from selected relevant confirmed facts and the extracted job context. Batch up to ten open questions; show progress for larger forms and preserve partial results. Every proposed field has source refs, answer revision, option identifiers if relevant, support classification and needs_information reasons. Users can generate again or edit directly.

The initiating action authorizes writing eligible ordinary fields; per-field preapproval is not required for those fields. Immediately before each write, validate account/session/profile/context/document/element/current-value bindings. Fresh user edits always win; stale responses are discarded. After filling, show a review checklist, exact text/selections and unanswered/failed fields. User can correct them in the page or side panel; changing a side-panel draft requires a new explicit Apply edits action with fresh bindings.

## Text and selection rules

- Supported visible native text/email/tel/URL/number/date fields and textareas use tested setters/events and constraint validation. Date/number transforms require exact semantics and format; unsupported locale/custom widget is left manual.
- Select/radio/checkbox/multi-select answers reference only existing option IDs. Factual choices use confirmed facts or user-selected preferences with matching scope; never choose a “closest” contradictory value. A negated question reverses logic only through a tested mapping; an ambiguous Yes/No question remains manual.
- Known factual options include relocation preference, availability, selected skills and country. Work-authorization/salary answers need explicit scope-matching confirmed facts and purpose consent; uncertainty remains manual.
- Legal certifications, terms/consent/final attestations and demographic declarations are not checked automatically. They are highlighted for manual review, irrespective of AI confidence.
- Repeated native experience/education groups map only when section order/source selection is unambiguous. Do not create/remove rows or click Next/Back automatically. File controls show the selected resume and manual attachment instructions.
- Current-value fingerprint changes, element replacement, navigation, profile/context update, account switch or service-worker restart invalidate pending writes. Reinspect/review; no blind retry or submit.

Form writes may transmit values to hiring-page scripts before final submission. Explain this once before the first fill and require the initiating action; no claim that data stays private until Submit. If a site auto-submits on input, classify it unsupported.

## Submit observation

Install passive listeners only for the selected user-invoked application session. Observe a recognized submit control's trusted pointer/keyboard action and native submit events. Check selected form/document, actual browser `isTrusted`, recent user gesture and stable session ID. Do not intercept/prevent/trigger submission, read unrelated forms, or treat programmatic synthetic clicks as user intent.

| Evidence | Tracker effect |
| --- | --- |
| Autofill completed | prepared session only; review required |
| Trusted submit control clicked | create/update application as SubmissionAttempted; label intent/unconfirmed |
| Native submit event from selected form | append dispatched-submit evidence; still unconfirmed |
| Client validation blocks submission | append validation-blocked event; current status Preparing with attempt history |
| Site reports rejection/error | append failure; never mark Applied |
| Tested adapter reports success via bounded DOM/URL evidence | Applied with SITE_REPORTED_SUCCESS; disclose site-reported, not independent delivery proof |
| Generic navigation/unknown SPA result | Submitted — unconfirmed; offer user confirmation |
| User confirms application submitted | Applied with USER_CONFIRMED_FORM and selected date |

Application records preserve channel, posting/context/resume/answer snapshots, attempt number and evidence history. Stable observation UUID and native/click correlation prevent double records; one session maps to one application attempt. Form navigation may destroy the content script, so stage the event in the worker/outbox before network delivery. Success adapters require captured permitted fixtures and positive/negative regression cases; arbitrary “thank you” text is insufficient.

The server validates session ownership and stores evidence as EXTENSION_OBSERVED or USER_CONFIRMED. It does not treat browser-supplied events as cryptographically verified hiring-site receipts. Status corrections append history. Email confirmation uses a separate source defined in EMAIL_APPLICATIONS.

## Offline reliability

Persist only `{event_id, user_id, application_session_id, observation_type, observed_at, document_reference}` in a trusted account-bound extension outbox, ≤100 events/512 KiB, TTL 24 hours. No keys, profile facts, answers, full DOM or uploaded document text. On reconnect, verify the current account/session is the same ACTIVE owner, then replay event metadata with its stable idempotency key. Never replay fill, generation or submission actions.

Account switch/logout clears outbox/state and shows any discarded pending-observation count. Account deletion rejects replay and purges local state on next validation. Expired unresolved observations are reported locally, not silently counted as submitted. Server compares session/context ownership and bounded observation time; repeated events are idempotent.

Acceptance: keyboard/pointer/native/SPA cases, validation rejection, unknown navigation, tested success, manual edits, worker restart and offline replay all produce the declared evidence/status with zero unauthorized clicks or duplicate applications.
