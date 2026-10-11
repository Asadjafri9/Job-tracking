# Azure deployment specification — planning only

The owner requested planning only and no use of connected Azure. This document describes future configuration; no subscription/tenant has been inspected, no Azure tool has been connected and no resources/spend have been provisioned by this work.

## Selected topology

React static assets plus FastAPI share one HTTPS origin in a non-root App Service Linux B1 container, one instance initially, with Always On enabled and verified in future preflight. A separate supervised Python worker/scheduler handles parsing, source scans, export/deletion/cleanup. PostgreSQL jobs/leases are durable; no Redis/Kubernetes or deployment-slot assumption. Always On prevents idle unloading; its configuration is described in [App Service settings](https://learn.microsoft.com/en-us/azure/app-service/configure-common).

| Resource | Future default |
| --- | --- |
| Region | East US (`eastus`), disclosed; vendor AI processing policy separate |
| Runtime | App Service Linux B1, pinned Python 3.12 container, pinned Node 22 build |
| Registry | ACR Basic, immutable image digest/prior rollback image |
| Database | Azure PostgreSQL Flexible Server 17, Burstable B1ms/32 GiB, private delegated VNet subnet |
| Network | separate App Service integration/database subnets/private DNS; source-fetch transport refuses internal/metadata destinations |
| Files | Standard LRS private documents/exports/deletion-journal containers, managed identity |
| Secrets/crypto | Standard Key Vault service secrets and versioned credential-wrapping KEK; scoped wrap/unwrap role |
| Identity | dedicated External ID tenant/hosted flow; exact dashboard/extension redirects |
| Monitoring | redacted Azure Monitor/Application Insights, bounded ingestion/retention |

Azure SDK identity/database clients need their legitimate private paths; user-controlled source fetching has a separate pinned-public destination policy, never arbitrary access through those clients. Blob/Key Vault access remains authenticated even if service endpoint is public. Runtime/auth/worker/migration permissions are distinct and narrowly scoped.

USD 150/month is an initial planning envelope, not a quote, availability check or authorization. Future deployment preflight must price registry/compute/DB/storage/logs/identity/egress and transient staging, verify SKU/region/quota, and revise configuration if it doesn't fit. Ten-user/fixed-instance/document/source/request limits constrain usage; budget alerts at 80%/100% alone do not stop billing.

## Environments/build

Local: PostgreSQL 17/Azurite, fake OIDC/provider/source servers, distinct dev extension ID, local test KEK. Staging: future isolated Azure resource group/config, synthetic accounts/data only. Beta: future isolated production group/tenant, ten allowlisted adults. Never reuse real beta credentials/data in local tests.

Multistage image builds React, installs locked Python packages and includes assets. Supervisor starts API plus restartable worker/scheduler. One API worker, database pool five/max overflow five initially; worker small separate pool. Four bounded network/provider tasks, one 256 MiB parser subprocess; claim/heartbeat leases in DB. Runtime startup rejects fake production providers/issuer/origins/missing keys/incompatible schema. Health path `/health/ready`, separate worker/scheduler heartbeat alerts. API path errors never fall through to React HTML.

## Configuration interfaces

| Setting | Meaning |
| --- | --- |
| APP_ENV / PUBLIC_APP_URL / API_CONTRACT_VERSION | shared origin and contract |
| DATABASE_URL / MIGRATION_DATABASE_URL | distinct secret role connections |
| OIDC_ISSUER / CLIENT_ID / CLIENT_SECRET / REDIRECT_URI | fixed dedicated tenant confidential client |
| APP_HASH_KEY / AUTH_TRANSACTION_ENCRYPTION_KEY | secret hashes and short-lived verifier/identity-payload encryption |
| KEY_VAULT_CREDENTIAL_KEK_ID | versioned wrapping-key reference; key material never browser config |
| EXTENSION_ALLOWED_IDS / BETA_EMAIL_ALLOWLIST | exact IDs and private enrollment config |
| AZURE_STORAGE_ACCOUNT_URL / container names | owner-controlled documents/exports/journal |
| PROVIDER_MODEL_CATALOG / privacy routing policy / limits | evaluated OpenRouter/Grok/Gemini models and fallback caps; no managed user AI key env |
| WORKER_CONCURRENCY / PARSER_LIMITS / schedule defaults | bounded queue/scheduler; schedule timezone per user |
| APPLICATIONINSIGHTS_CONNECTION_STRING | protected redacted telemetry configuration |

Future `.env.example` has placeholders only. Local crypto is an explicit test adapter, refused in production. Saved user keys live encrypted in PostgreSQL; runtime managed identity wraps/unwraps through Key Vault. Client builds get public URLs/version values only. GitHub deployment uses protected OIDC, not long-lived subscription credentials.

## Future rollout and recovery tasks

1. AZ-001 prepares Bicep/parameters/what-if reviewable plan, current quote and exact identity/network/crypto roles. These are future tasks; no what-if/API call is executed now.
2. Build immutable image/extension checksums/SBOM. Apply migrations with separate migrator identity; backend runtime never owns schema. Expand/contract changes permit prior compatible image/client.
3. Deploy isolated staging, configure actual tenant redirects/keys, verify actual-provider/browser/source flows, monitoring schedule, encryption and redacted telemetry. Only explicitly authorized controlled sites/testing operations are used later.
4. Exercise prior-image rollback and isolated DB/blob recovery. Basic App Service rollback uses saved image digest rather than slots; never destructive automatic migration downgrade.
5. Restore DB into a new isolated server, reapply policies/parameters, replay independent deletion/revocation journal, invalidate sessions/grants and reconcile document hashes. Cancel restored in-flight AI operations as UNKNOWN without redispatch; reconcile daily-run identities and leases, cancel stale scheduled jobs and rebuild only future eligible schedules. Only then repoint runtime. Target measured RPO ≤15 min/RTO ≤4 h; seven-day DB/blob recovery window is disclosed.
6. Release private beta only after RELEASE_CHECKLIST evidence, exact unpacked extension installation and operator coverage. Source scanning/cost/model access must be verified at that time.

Alerts: scheduler/worker stale >2 minutes, pending scan beyond 09:30 local, repeated source/provider errors, no enabled key, cleanup >1 hour, deletion >24 hours, limits/budget/readiness/5xx. Hourly cleanup handles expired uploads/grants/exports and retention. Notifications about jobs are in-app; no background outgoing email integration.

References supporting service defaults: [App Service/FastAPI](https://learn.microsoft.com/en-us/azure/app-service/quickstart-python), [VNet integration](https://learn.microsoft.com/en-us/azure/app-service/overview-vnet-integration), [PostgreSQL recovery](https://learn.microsoft.com/en-us/azure/postgresql/backup-restore/concepts-backup-restore), [Key Vault keys](https://learn.microsoft.com/en-us/azure/key-vault/keys/about-keys). These were public documentation, not connected account inspection.
