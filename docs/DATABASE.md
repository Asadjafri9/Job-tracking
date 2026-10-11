# Version 2 database contract

PostgreSQL 17, SQLAlchemy 2/psycopg 3/Alembic. Server UUIDs, UTC timestamptz instants, date-only application/follow-up dates, integer revisions, explicit enums/checks. Owner UUID derives from session/job, never client data. Generate migrations including tables/indexes/grants/RLS; no ad hoc cloud schema edits.

## Entities

| Table | Required fields/invariants |
| --- | --- |
| users | issuer/subject unique, verified directory object ID/login email, ACTIVE/DELETING/DELETED, IANA timezone, beta eligibility |
| auth_transactions/sessions/extension_grants | hashed state/token/grant, encrypted short-lived verifier, nonce, exact callback/client/extension/challenge, expiry/consumed/revoked, session auth_time/last_seen; no plaintext long-lived tokens |
| profiles/profile_facts/profile_fact_versions | grouped typed fact, current_revision, immutable source/confirmation versions, sensitivity/purpose tags, document/page anchors; profile revision increments atomically |
| documents | owner/type/version/private key, filename/media/size/hash, original-ready/parse states, revision, current/default flags; ≤10 files/50 MiB, each ≤5 MiB |
| document_extractions | document/version, bounded text/anchors/candidates, parse/prompt/model version, user review state; no candidate automatically confirmed |
| provider_credentials | owner/provider, ciphertext/nonce/wrapped DEK/KEK version, last4, enabled/status, revision, allowed interactive/background purposes; never raw key |
| provider_settings | ordered enabled credential/model IDs, fallback/background consent revisions, request limits |
| ai_operations/ai_attempts | operation kind/owner/input HMAC/idempotency/revisions/state, actual credential/provider/model, usage, redacted outcome, dispatch/completion time; no keys or raw prompt trace |
| application_sessions | prepared form/context/draft snapshots, selected source/doc/fact versions, document/form ref, profile/context revisions; distinct from submitted application |
| applications | owner/channel/employer/role/raw+canonical URL/attempt/status/application/follow-up dates/revision, linked form session/email draft, immutable context/document metadata snapshots |
| submission_events | UUID/idempotency key, owner/session/application, evidence type/source/observed+received time, correlated gesture ref, bounded signal code; append-only, no full DOM |
| application_status_events/application_answers | append-only history and exact historical answer/fact/context snapshots; later profile edits don't rewrite them |
| email_drafts | owner/recipient/employer/role/job context/subject/body/document refs/revision/state/current source refs; compose-open/sent events append-only |
| monitored_sources | owner/public URL/source kind/state/region selector?, schedule/timezone/revision/next_run_at/last_success/consent, bounded ETag/hash |
| monitoring_runs | partial unique (source, scheduled local date) for DAILY only; MANUAL has a distinct request UUID, schedule revision, MANUAL/DAILY, state/completeness, counts/start/end/redacted error |
| discovered_jobs | owner/source refs/native ID namespace or canonical URL identity, title/employer/location/remote/evidence anchors/first+last_seen/meaningful_revision/match reason/status; no invented URL |
| notifications | owner/type/posting/run/ref, idempotent event key, bounded content/read_at, created_at; no key/private doc content |
| jobs/operations | owner/kind/ref/status/stages/lease/heartbeat/attempts/next_run/expiry/result key/receipt digest as needed; encrypted identity-cleanup payload temporary |
| idempotency_records | unique owner/route/key, HMAC input fingerprint, entity/result status/expiry; no duplicated private payload |
| audit_events/deletion_journal | pseudonymous content-free activity, deleted account IDs and revoked credential/version IDs/time/HMAC refs; independent append-only blob journal also exists |

All children use `(user_id,parent_id)` FKs against `UNIQUE(user_id,id)` parents, including credentials/drafts/session/documents/postings/notifications. Session or draft maps to at most one application attempt; per-user canonical URL/attempt uniqueness prevents duplicate web applications. Channel/email draft identity handles email confirmations. Individual source/document deletion preserves historical application snapshots but removes live access.

## Roles and isolation

`copilot_migrator` owns schema; runtime cannot. `copilot_runtime` has no superuser/BYPASSRLS and uses transaction-local `set_config('app.user_id', verified_uuid, true)`. RLS USING/WITH CHECK compare owner to the null-safe current setting; missing context returns no access. Privileged identity/session code uses narrowly granted `copilot_auth`. Worker claims server job metadata with a scoped role, then operates on the durable job's owner in a runtime transaction. Test actual roles and pooled commit/rollback reset; never set owner session-wide or accept it from a job body.

Account state is checked before dispatch and locked/rechecked at publishing. Deletion worker has an explicit DELETING account capability, not a generic ACTIVE API bypass. Cross-owner/unknown resources return 404. Provider key unwrap is owner/purpose-checked independently of row lookup.

## Concurrency and idempotency

GET returns `ETag: "<revision>"`; updates require matching quoted If-Match and conditional revision increment; conflicts return 409. First profile row is initialized during signup so normal editor doesn't invent ownership. Atomic quota reservations prevent concurrent document/key/source/job limit bypass.

Creates use UUID Idempotency-Key plus normalized HMAC fingerprint (exclude secret key values; credential replacement uses secret-version fingerprint, never logged). Same key/input returns original result/ref; changed input conflicts. Ordinary record keys retain 24 hours and database identity constraints protect after expiry. Submission observation UUIDs stay unique for application lifetime. Daily runs unique by source/local date; notifications unique by owner/posting/event/meaningful revision. Deleted entity replay returns 410 and cannot recreate it.

AI operation metadata retains 30 days; exact replay does not redispatch an unknown/completed operation. Requests include original creation time; absent-key operations older than 24 hours are rejected rather than silently becoming new generation calls. Explicit regeneration creates a new key. Provider success results can persist in the intended private draft/session; raw prompts/keys never persist in attempt logs.

## Limits/indexes and durable lifecycle

Per account: 200 confirmed active facts, 40 selected facts/model request, ten documents/50 MiB, 500 applications, five monitored sources, three saved-provider slots, quotas from PROVIDERS. One interactive AI operation, one active export, four worker network slots globally, one parser child. Bound draft/session/notification accumulation through SECURITY_PRIVACY retention. Cursor lists ≤50 rows. Index owner/update/ID, owner/status/follow-up, canonical posting/attempt, token digests, job lease/state/next run, notification unread/time and daily run uniqueness.

Upload reservation → bounded private stream/validation → original READY → leased parse → candidates REVIEW_REQUIRED → user confirmation. Each stage has durable marker; failed metadata/blob commit triggers orphan cleanup. Reserved uploads expire after one hour, parser restarts do not duplicate facts, ZIP expansion/resource bounds apply. Keys use per-record authenticated encryption and wrapped-DEK versioning; not a plain profile field.

Deletion blocks document/key/source use immediately, cancels scheduled/queued work, checks running jobs before new dispatch/results, and queues physical cleanup. Independent deletion journal is written before acknowledging account deletion. Journal replay is mandatory after DB restore before exposure. Export takes a consistent per-owner snapshot/lifecycle lock, streams originals safely and never includes credential ciphertext/key material. Background run failures do not close absent jobs unless the completeness rule is satisfied.

CI migrates an empty DB, tests supported upgrade paths/constraints/roles and rejects incompatible runtime schema. Expand/contract changes preserve current/previous beta clients; no automatic destructive downgrade.
