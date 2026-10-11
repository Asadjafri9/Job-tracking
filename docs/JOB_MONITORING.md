# Daily job monitoring contract

## Setup and schedule

User saves up to five public career/job-listing URLs and role/location/remote/experience preferences. Show source support status, next check, last success/error, Pause, Remove and Check now. Explicitly enable scheduled checks and saved-key background use; no API key or consent means the source can be saved but AI monitoring shows setup_required. Role/location preferences may be sent; contact email/phone/DOB/private documents are excluded.

Default daily time is 09:00 in the user's IANA timezone, chosen at onboarding; Asia/Karachi is used for a Karachi user. Store timezone/local time and computed next_run_at UTC. Scheduler checks due sources every minute, atomically queues unique `(source_id, scheduled_local_date)` runs and advances the schedule. Workers validate source/account/saved-key/consent state again at claim and before publishing.

Timezone/time edits cancel unclaimed future jobs, increment schedule revision and choose the next strictly future local slot; no already-completed local date is repeated. DST uses timezone library rules (earliest occurrence for repeated local time, next valid instant for nonexistent time). Server restarts catch up at most one missed daily run within six hours; older slots become SKIPPED with reason, then advance. Unique run keys and leases prevent duplicate daily scans or notifications across replicas/restarts. Check now is separate, rate-limited to three/source/day, and doesn't duplicate existing job alerts.

This is an application scheduler specification; do not create a Codex chat automation for it.

## Public fetch boundary

Fetch only HTTP data required for the explicit public source, using HTTPS/port 443. Reject credentials in URL, IP-literal/private/reserved/loopback/link-local/metadata targets, non-HTTP schemes and unsafe redirects. Resolve all A/AAAA answers and require global addresses; pin the validated destination for the connection with correct TLS hostname/SNI verification. Validate each redirect hop, max three. Tests must cover DNS rebinding, mixed public/private records and IPv4-mapped IPv6.

Respect robots/access limits and site terms; identify the crawler, cache robots for ≤24 hours, honor Retry-After and per-host throttling. Login, CAPTCHA or explicit denial yields UNSUPPORTED/DENIED, not bypass. Network controls independently deny private/metadata egress where practical; public URL validation is not sufficient alone. See [robots protocol](https://www.rfc-editor.org/rfc/rfc9309) and [SSRF](https://community.owasp.org/attacks/Server_Side_Request_Forgery).

Limits per source/run: three content requests plus cached robots lookup, ≤2 MiB response/request, ≤30-second fetch deadline, ≤200 candidate listings, no unbounded following of links. At most four worker network/provider tasks simultaneously and one document-parsing subprocess; throttle same host to one fetch per two seconds. Conditional ETag/Last-Modified and normalized content hashes avoid redundant processing. No JavaScript execution/browser scraping or arbitrary model-selected URL fetch.

## Extraction and matching

Prefer structured JobPosting JSON-LD, public RSS/Atom and explicitly supported native ATS public endpoints. For rendered HTML, extract bounded text/cards and source anchors, then use the selected model to return listing candidates referencing observed links/text only. User can select a listing region during source setup when page structure is ambiguous. A JS-only page or unparseable listing shows unsupported with manual-source guidance.

Normalize `{source_id, external_job_id?, title, employer, public_url, location?, remote?, posted_at?, evidence_anchors, content_hash}`. AI cannot invent unseen jobs/URLs/publication dates. Match confirmed role/location preferences; missing location/remote data remains unknown, not a guessed match. Show why a job matched and link to the source. URL expansion is bounded by the source and fetch rules.

Per-user posting identity is native stable job ID with host namespace, otherwise canonical public posting URL. Deduplicate across that user's sources; use title/employer only as a review hint, never automatic identity. Initial scan seeds records and shows one current-matches summary; subsequent scans notify new matches and important changed matching conditions. Notification key is `(user_id, posting_id, event_kind, meaningful_revision)`; reruns/duplicate sources can't spam.

Do not mark a posting closed merely because a request fails or a partial page lacks it. Require explicit source closure evidence or absence from two complete successful scans. Store completeness on each run. Unchanged source/unchanged match yields no job alert. Preference changes can cause a first new match, labeled preferences_changed; previously notified unchanged jobs remain deduplicated.

## Notifications and failure handling

Navbar bell/unread count and `/notifications` show title/employer/location/source, discovery time, match reason and Open job. Group new jobs into a daily digest with individual links; mark read/all read. Job discoveries are vacancies, not applications. Opening one can start an autofill session but never marks Applied.

Source state: SETUP_REQUIRED, ACTIVE, PAUSED, UNSUPPORTED, DENIED, ERROR. Run state: QUEUED/RUNNING/SUCCEEDED/PARTIAL/FAILED/SKIPPED/CANCELED. UI shows last successful check separately from last attempted run and the next schedule. AI/provider outage leaves deterministic extracted jobs available but matching incomplete; show that reason rather than “no jobs found.” All exhausted keys pause AI work and create one actionable settings notification, deduplicated until the condition changes.

Provider fallback follows PROVIDERS; no unknown-result replay. Definitive temporary fetch/provider failures can retry twice within the current run window. Remove/pause/account deletion cancels unclaimed jobs, and active jobs must recheck before making provider calls/publishing. Sources and notifications are owner-scoped and included in export/deletion.

Acceptance: clients closed at 09:00; dispatch p95 ≤5 minutes and target finish ≤30 minutes on five sources ×ten users with healthy dependencies; exact daily uniqueness through restart/DST/timezone edits; zero invented jobs/private-network fetches; no duplicate notifications on reruns; failures and partial coverage remain visible.
