# Accepted decisions — version 2

October 12, 2026. The user's three-pillar flow supersedes earlier narrow-MVP assumptions. The owner explicitly selected React/FastAPI/PostgreSQL/Azure and OpenRouter/Grok/Gemini options. Other choices below are concrete maintainer defaults for implementation, revisable through a recorded decision change.

## ADR-001 — Stack and contracts

React 19/TypeScript/Vite, Chrome MV3 side panel, Node 22/pnpm; Python 3.12/FastAPI/Pydantic 2/uv; PostgreSQL 17/SQLAlchemy 2/psycopg 3/Alembic; Ruff/mypy, Vitest, pytest/HTTPX and Playwright. Resolve compatible exact dependency versions and pin locks/container digests in SET-001. Generated OpenAPI clients bridge languages; no shared Python/TypeScript implementation assumption.

## ADR-002 — Cloud data and onboarding

PostgreSQL/private Azure blobs authoritative. Resume/LinkedIn PDF/cover-letter/supporting-file originals are immutable owner-scoped documents; text parsing yields candidates that require user confirmation before factual use. Cover-letter style remains distinct from factual claims. Optional personal/sensitive facts have purpose controls. No LinkedIn account scraping or scanned-document OCR.

Only a minimal account-bound submission-event outbox persists locally when offline; no profile database or form-action/AI replay queue. Purge on logout/account switch/deletion, TTL 24 hours, ≤100 events/512 KiB. This replaces the earlier no-outbox default because automatic submission tracking must survive brief outages.

## ADR-003 — Managed identity and sessions

Microsoft Entra External ID dedicated external tenant and hosted email/password/reset flow; FastAPI confidential OIDC client/Authlib. Dashboard has same-origin HttpOnly opaque cookie/CSRF; extension uses single-use PKCE-bound app grant through Chrome identity redirect and server-revocable opaque bearer session. Idle 60 minutes/absolute 12 hours. No provider refresh tokens in browser storage. Verified `(issuer,subject)` is the stable identity; retain verified directory object ID for eventual managed identity cleanup.

References: [External ID](https://learn.microsoft.com/en-us/entra/external-id/customers/overview-customers-ciam), [Chrome identity](https://developer.chrome.com/docs/extensions/reference/api/identity).

## ADR-004 — Three providers and persistent BYOK

Initial ordered chain: OpenRouter `deepseek/deepseek-v4-flash` → xAI `grok-4.7` → Gemini `gemini-3.8-flash`, restricted to enabled configured keys. User can reorder/disable and choose an evaluated model from the server capability catalog. User-provided keys are encrypted using per-credential AES-256-GCM data keys wrapped with a versioned Azure Key Vault key. AAD binds owner/provider/credential ID. UI sees masked metadata only. Session-only interactive keys are also supported; scheduled scans require saved keys plus explicit background consent.

Quota/rate/unavailability fallback is bounded and consented; refusals/bad facts never trigger policy-evading fallback, and uncertain completion stops automatic attempts. PROVIDERS defines the state machine and budgets. Validate every adapter's schema/capabilities and model access before enablement. Provider retention/processing varies; do not apply OpenAI-specific storage fields to other vendors or promise zero retention.

References: [DeepSeek V4 Flash](https://openrouter.ai/deepseek/deepseek-v4-flash), [Grok model catalog](https://docs.x.ai/developers/models), [Gemini catalog](https://ai.google.dev/gemini-api/docs/models), [Key Vault keys](https://learn.microsoft.com/en-us/azure/key-vault/keys/about-keys).

## ADR-005 — Autofill, options and submission evidence

User's Analyze and autofill action authorizes filling supported ordinary fields/options from confirmed facts and validated drafts, followed by review. Each write binds account/document/field/source/value revisions and current field state. Ambiguous/sensitive declarations and final attestations stay manual. No extension Submit/Next action. Observe trusted user submit intent and native submit events, deduplicate and create dashboard tracking automatically. Mark Applied only with tested site-reported success or explicit user confirmation; click alone remains unconfirmed.

## ADR-006 — Email handoff

MVP generates personalized editable email subject/body and opens Gmail compose with best-effort prefill. Use encoded known compose URL, always offer copy/mailto fallback, and never truncate silently or claim attachment/send success. No Gmail OAuth/connect prompt. User sends/attaches manually and confirms sent in the app. Direct Gmail integration needs a separate permission/verification ADR after this release.

## ADR-007 — Daily monitoring

Server scheduler dispatches durable jobs for enabled public sources at 09:00 in the user's IANA timezone. Up to five sources, bounded safe public fetching, JobPosting/feed/native ATS extraction, AI classification of changed content, per-user stable posting deduplication and in-app bell/page notifications. Respect access restrictions; never bypass login/CAPTCHA/robots restrictions or crawl without bounds. Source failures remain visible. JOB_MONITORING specifies limits, catch-up and schedule uniqueness.

References: [JobPosting vocabulary](https://schema.org/JobPosting), [robots protocol](https://www.rfc-editor.org/rfc/rfc9309), [SSRF](https://community.owasp.org/attacks/Server_Side_Request_Forgery).

## ADR-008 — Azure runtime and durable work

One App Service Linux B1 container initially serves React assets/FastAPI at the same origin and supervises a separate worker/scheduler. PostgreSQL job leases survive restarts. Worker processes document parsing, monitoring, exports and deletion; parsing runs in a resource-limited subprocess. No Redis/Kubernetes. Move worker to its own Azure runtime if measured workload misses gates; do not add services without evidence.

East US defaults: PostgreSQL Flexible Server 17/Burstable B1ms/32 GiB with private VNet path; Standard LRS blobs, Standard Key Vault, Basic ACR, Azure Monitor. Bicep and protected GitHub OIDC deployment, scoped runtime/auth/migration/worker roles. USD 150/month initial infrastructure envelope is a planning cap, not a quote or spending authorization; produce actual cost/availability preflight before applying resources.

## ADR-009 — Isolation and lifecycle

API owner checks + composite-owner FKs + PostgreSQL RLS for every product record. Non-owner/no-BYPASSRLS runtime role sets transaction-local user context; separate auth/migration privileges. Worker job ownership comes from durable server records, not client assertions.

Account deletion disables schedules/revokes sessions/keys immediately and cancels queued work, then removes data/files and tracks operator identity cleanup. Seven-day database/blob retained-copy window; 24-hour active cleanup target; 30-day content-free deletion journal; 14-day logs. Export contains documents/profile/apps/email drafts/source/job/notification data, never key plaintext/ciphertext/wrapped keys. Restore replays the independent deletion journal before exposure.

## ADR-010 — Delivery and change control

Private ten-user adult beta, stable unpacked Chrome extension IDs per environment, current/previous stable Chrome evidence. No whole-ATS guarantee; controls and observed hosts are listed explicitly. Public release requires owner-selected license, store/privacy review, support and capacity decisions. Scope/key-privacy/monitoring behavior changes revise affected PRD/contracts/tasks before code. Earlier one-provider, session-only-key, no-parsing/no-monitoring and mandatory per-field preapproval defaults are superseded.
