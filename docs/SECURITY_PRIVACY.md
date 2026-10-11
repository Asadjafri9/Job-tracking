# Three-pillar security and data lifecycle

Implementing maintainer owns security/operations; owner controls enrollment/scope/budget. Application sessions/owner checks/RLS govern every record and job. Website/document/model content is untrusted; the model has no submit/send/fetch/admin tools. See ARCHITECTURE and feature contracts for exact state/consent boundaries.

## Required controls

| Threat | Control/evidence |
| --- | --- |
| Cross-user profile/file/key/draft/source/job access | derived owner, composite FKs, actual-role RLS, owner/purpose key unwrap; two-user and pooled context tests |
| Login/open redirect/CSRF/token replay | fixed issuer/redirect/state/nonce/PKCE, opaque sessions, CSRF+Origin, one-use grant; expiry/revoke/replay tests |
| Stale fill or wrong option | exact field/value/account/source revisions, validated option IDs, manual-edit protection; adversarial control/negation tests |
| Secret exposure | authenticated encrypted keys, no full GET, no prompt/log/APM/outbox/export secret, canary scan and ciphertext AAD swap tests |
| False submission/send claim | separate click/native/site/user-confirmed evidence; validation/Gmail-open negative cases |
| Untrusted documents/prompt injection | resource-limited parser, candidate confirmation, bounded selected text, no executed macro/script/link; malicious doc/JD fixtures |
| SSRF/internal network/source abuse | safe public destination pinning/TLS/redirect/DNS checks, robots/rate/byte bounds; metadata/private/rebinding fixtures |
| Duplicate provider charges/jobs/alerts | idempotent operation/attempt/run/notification keys, bounded definitive fallback, stop UNKNOWN |
| Deleted-data resurrection | disable schedules/keys/revoke sessions/cancel jobs, independent journal, scoped cleanup receipt, pre-publish state check and restore replay |

## Consent and processing

Cloud onboarding explains private originals/confirmed facts and processing region. Optional personal facts are purpose-scoped, never required by default. Before first Analyze and autofill explain site-input transmission even before Submit; user initiates writing and reviews afterwards. Consent/attestations remain manual. Provider setup explains each vendor/downstream route, billing responsibility, saved-key/background use and fallback order. No blanket consent to unrelated profile disclosure; retrieve only relevant confirmed facts.

Parsing can send bounded selected document text for candidate extraction only after consent. Monitoring sends job text and role/location preferences, excluding contact/DOB/document originals. Gmail handoff transmits reviewed recipient/message through the browser to Gmail; attachments/Send remain manual. No Gmail token or mailbox scan. Provider retention varies; do not promise zero retention or carry OpenAI-specific store flags into unrelated APIs.

Disable production request-body/raw HTML/prompt/APM capture. Logs contain timings, counts, pseudonymous IDs, status/error codes, model/version and token usage only. Never log compose URLs, document text, email bodies, personal values, provider keys or auth codes. Synthetic fixtures alone may have asserted example content in test output. No ad/analytics SDK.

## Retention/export

| Data | Active retention | Export/deletion |
| --- | --- | --- |
| Confirmed profile/fact versions/original documents | until user removes; ten files/50 MiB limit | JSON/source refs and originals; active cleanup target 24 h |
| Parsed candidates/unconfirmed text | 30 days or user removal, max bounded extraction/file | user extraction data; delete with source/account |
| Prepared form sessions/unsent email drafts | 30 days inactivity, user-save can retain draft | JSON; immutable sent/application snapshots preserved until removed |
| Applications/evidence/answers | until removed, ≤500/account | JSON+safe CSV+history |
| Saved provider credentials | until revoked/deleted | only non-secret provider settings/status; never plaintext/ciphertext/DEK/KEK material |
| Monitoring source/preferences/current postings | until source/account removal; closed postings 90 days | JSON/source/run evidence; cancel work on removal |
| Run metadata/notifications/AI usage | 30 days runs/usage; 90 days read notifications; unread capped/aged after 90 days | user's non-secret records, never raw attempt prompts |
| Submission-event outbox | trusted local ≤24 h/100 events/512 KiB | minimal replay metadata; purge on switch/logout/deletion |
| Sessions/auth transactions/grants | ≤12 h/10 min/60 s respectively | excluded; revoke immediately, sweep hourly |
| Export artifact | private 24 h accessibility | ZIP; cleanup hourly, retained soft-deleted copies ≤7 days |
| Operational logs/audit/deletion journal | 14 days logs, 30 days content-free audit/journal | relevant user audit, not security internals |
| DB backups/blob soft-deleted copies | seven days | expire; immediate per-item backup erasure not promised |
| External identity | provider-managed until tracked operator cleanup | hosted identity procedure; no raw passwords exported |

Export v2 ZIP: manifest/schema version/timezone/checksums, profile/facts/candidates, application/evidence/answers JSON and CSV, email drafts, source/run/discovered-job/notification data, usage/audit/preferences and original documents. Never include keys, ciphertext/wrapped key bytes, sessions or secret transaction data. Consistent per-user snapshot/lifecycle lock prevents concurrent deletion partial exports; recheck ACTIVE state before publish. Safe ZIP names and CSV formula mitigation required. No import UI in this release.

## Account deletion and restoration

Fresh authentication/typed consent creates an idempotent operation/receipt, sets DELETING, revokes sessions and credentials, disables all sources/schedules and cancels queued jobs. Write independent private content-free deletion journal with 30-day immutable retention before acknowledgement; failure leaves account blocked and visibly pending repair. Scoped receipt can view only that cleanup operation for 30 days.

Workers recheck active ownership/consent before any new provider/fetch dispatch and before publishing. Already-dispatched external work cannot be recalled; late results are discarded after deletion. Destroy credential ciphertext/wrapped DEKs and active plaintext caches, remove profile/docs/candidates/sessions/apps/email/source/posting/notification/export data, then complete managed identity removal through the restricted beta operator procedure. SUCCEEDED requires active data and identity stages complete; missed 24-hour target alerts and stays pending. Keys in retained backups remain inside the disclosed seven-day window; restore always replays revocation/deletion journal before access.

Offline clients cannot be remotely erased while disconnected, but every next operation revalidates account and purges denied/switch state; outbox isn't replayed under another account. UI closing/browser restart clears session-only credentials. No trace or customer export provides decryption material.

Restore into a new isolated server, replay the independent deletion/revocation journal, revoke all restored sessions/grants, recheck RLS and reconcile original-file hashes before exposing service. Restored in-flight AI operations become UNKNOWN without redispatch; reconcile daily-run identities/leases and cancel stale jobs before rebuilding future eligible schedules. Targets RPO ≤15 minutes/RTO ≤4 hours on measured beta data; not guaranteed until drill. Incidents disable affected capability/maintenance, revoke compromised sessions/keys, preserve redacted evidence and record remediation. The authorized operator handles any user communication; no automatic outbound messaging from this planning task.

References: [Key Vault key management](https://learn.microsoft.com/en-us/azure/key-vault/keys/about-keys), [PostgreSQL backup retention](https://learn.microsoft.com/en-us/azure/postgresql/backup-restore/concepts-backup-restore), [blob soft delete](https://learn.microsoft.com/en-us/azure/storage/blobs/soft-delete-blob-overview).
