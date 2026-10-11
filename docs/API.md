# HTTP and browser contracts — version 2

FastAPI Pydantic/OpenAPI is authoritative; generate browser client and fail CI drift. Prefix `/api/v1`, snake_case JSON, UUIDs, RFC3339 UTC instants, ISO dates. Unknown writable fields rejected. Protected requests derive owner from app session, require ACTIVE account and CSRF/exact Origin for cookie mutations. Extension uses opaque bearer token plus exact Origin/version. Owner-scoped resources return 404 for another user.

## Shared response behavior

Errors: `{error:{code,message,request_id,field_errors:[]}}`, with no secrets/raw personal content. 401 auth, 403 blocked/CSRF/consent, 404 foreign/missing, 409 revision/idempotency/in-flight/duplicate, 410 deleted, 413 bytes, 422 validation/missing facts, 429 quota, 502 provider/source outcome, 503 dependency unavailable. Protected responses no-store; API failures never redirect to HTML. GET ETag quoted revision, update If-Match. Creates/operations/events use stable Idempotency-Key. Cursor pagination limit 1–50.

`X-Copilot-Client-Version` and `X-Copilot-Contract-Version:1` identify extension contract. `/meta` returns limits/minimum compatible extension, not secrets. Support current/previous compatible beta release; incompatible major gets 426. Added fields are compatible; removals/meaning changes require new contract and migration.

## Routes

| Route | Contract |
| --- | --- |
| GET `/health/live`, `/health/ready`, `/api/v1/meta` | safe process/config/schema/version status |
| GET `/auth/login`, `/auth/callback` | fixed OIDC transaction/state/nonce/PKCE, exact web/extension redirect |
| GET `/api/v1/auth/session`; POST `/api/v1/auth/logout` | account/revisions/timezone/CSRF/expiry; revoke all sessions |
| POST `/api/v1/auth/extension/exchange` | one-use grant/verifier/extension ID → opaque app token/expiry |
| GET/PATCH `/api/v1/profile` | grouped facts/purpose/confirmed sources; optimistic confirmation/update |
| GET/POST `/api/v1/documents`; PATCH/DELETE `/documents/{id}`; GET `/documents/{id}/download` | private metadata/bounded multipart/revision/removal/attachment stream |
| POST `/api/v1/documents/{id}/extract`; GET `/documents/{id}/candidates`; POST `/documents/{id}/confirm` | private parse/extract operation, candidate preview/conflict choices, explicit fact confirmation |
| GET/POST `/api/v1/provider-credentials`; PATCH/DELETE `/{id}`; POST `/{id}/validate` | masked metadata/create-replace-purpose flags/delete/minimal capability check; full keys never GET |
| GET/PATCH `/api/v1/provider-settings` | evaluated model/order/fallback/background consents/limits |
| POST `/api/v1/ai-operations`; GET `/ai-operations/{id}` | typed profile_extract/job_analyze/form_answers/email_draft/job_classify request/state/result ref; purpose/source revisions/consent enforced |
| POST `/api/v1/application-sessions`; GET/PATCH `/{id}` | extracted context/form schema/draft snapshots/bindings; prepared session only |
| POST `/api/v1/application-sessions/{id}/submission-events` | stable UUID/evidence/time/ref → idempotent tracking record/status |
| GET/POST `/api/v1/applications`; GET/PATCH/DELETE `/{id}`; POST `/{id}/status-events` | owner CRUD/filter/history/correct status/explicit Applied confirmation |
| GET/POST `/api/v1/email-drafts`; GET/PATCH/DELETE `/{id}`; POST `/{id}/generate` | recipient/context/subject/body/revision/style/facts/doc refs |
| POST `/api/v1/email-drafts/{id}/compose-events`; POST `/{id}/sent-confirmation` | record reviewed compose-open revision only; explicit sent/date → USER_CONFIRMED_EMAIL Applied |
| GET/POST `/api/v1/monitored-sources`; GET/PATCH/DELETE `/{id}`; POST `/{id}/check` | public URL/preferences/09:00 timezone/support state/pause/remove/check-now |
| GET `/api/v1/monitoring-runs`; GET `/api/v1/discovered-jobs` | owner run completeness/errors and matched vacancies, separate from applications |
| GET `/api/v1/notifications`; GET `/notifications/unread-count`; PATCH `/{id}`; POST `/notifications/read-all` | list/badge/read states, no unchanged duplicate alert |
| POST `/api/v1/exports`; GET `/api/v1/operations/{id}`; GET `/exports/{id}/download` | fresh-auth all-data snapshot, scoped progress, private expiring ZIP |
| POST `/api/v1/account/deletion` | fresh-auth typed confirmation → blocked account/canceled jobs/deletion receipt; independent journal before acknowledgement |

For routes abbreviated `/{id}`, use the immediately preceding collection path. IDs cannot be caller-supplied owner selectors. Secret input uses SecretStr and request-body/APM logging is disabled. A session-only key may accompany an interactive operation; saved-key requests use an owner/purpose-validated credential ID. Monitoring never takes an arbitrary browser secret or key from a source URL. Public source URLs are validated server-side including safe redirects/DNS, not merely by Pydantic URL syntax.

String limits: recipient valid single address, subject 200 chars/no CRLF, email body/notes 10,000, question 2,000, per-answer 5,000 or field's lower limit, job excerpt 12,000. AI normalized token/output caps are in PROVIDERS. Source fetch has independent byte/page/time limits. Unknown source content isn't a successful no-jobs result.

## Extension messages

Envelope `{contract_version:1, request_id, operation, document_token?, payload}` with discriminated schemas. Validate sender extension/tab/frame/document using browser metadata, not page assertions. No externally_connectable/page postMessage command bridge/eval/remote adapter code.

| Operation | Authorized initiator | Meaning |
| --- | --- | --- |
| INSPECT_FORM / FORM_CHANGED | panel via worker / isolated script report | bounded selected-form metadata, invalidate affected bindings |
| ANALYZE_AND_AUTOFILL | trusted panel user action | context/profile/credential consent, prepare operation and write eligible values |
| APPLY_EDITED_VALUES | trusted panel user action | current exact edited revisions and field state |
| REPORT_FILL_RESULTS | isolated script | per-field verified result, no privileged commands |
| OBSERVE_SUBMISSION | isolated script → worker | bounded selected-session trusted user observation, idempotent metadata |
| FLUSH_TRACKING_OUTBOX | trusted worker | same ACTIVE account only; metadata replay, never fill/submit/generate |
| CONFIRM_SUBMITTED | trusted panel/dashboard user action | explicit date/source confirmation |

Scripts receive only target values, not keys/full profiles/private documents. Submission evidence is browser-reported observation, not independently verified delivery. Service restart clears write intent, retains only properly scoped session metadata/outbox. Poll AI/operations/run state or bounded dashboard polling; no websocket requirement in MVP. Badge refreshes on page load and at most every minute while visible.
