# Azure plan — AZ-001 reviewable deployment blueprint

PLANNING ARTIFACT ONLY. No Azure CLI, what-if, pricing API, or credential
was used. Nothing in `infra/azure/` has been applied. Every value marked
REPLACE-* and every identity/network/role decision below requires owner
review before any provisioning.

**Owner constraint (2026-10-14): free tier only — no paid SKUs.** The
topology below predates that constraint and is NOT free-tier compliant:
App Service Linux containers require B1+ (~USD 13/mo), ACR Basic is
~USD 5/mo, and PostgreSQL Flexible B1ms is only free inside the
12-month new-account grant (750 h/mo). Before any provisioning the
plan must be reworked to zero-cost components (e.g. F1 code-deploy,
Container Apps free grant, or an external free Postgres) or the
deployment stays local-only. The USD 150/mo envelope is superseded
by this constraint.

## Resources (`infra/azure/main.bicep`, `parameters.staging.json`)

| Resource | Planned shape | Review before apply |
| --- | --- | --- |
| VNet `rolevo-{env}-vnet` | `10.30.0.0/16`; `/24` subnets for App Service delegation and PostgreSQL delegation | CIDR collision with owner networks |
| Private DNS zone | `privatelink.postgres.database.azure.com` linked to VNet | none |
| PostgreSQL Flexible Server | v17, `Standard_B1ms`, 32 GiB, private-only (`publicNetworkAccess: Disabled`), 7-day backup | region availability of Burstable SKU; `postgresAdminPassword` is a `@secure()` param — the operator supplies it at deploy time (never committed); the migrator login doubles as migration identity until AZ-003 splits roles |
| ACR | `Basic`, admin disabled | immutable tag policy review |
| Key Vault | Standard, RBAC mode, soft-delete 7 days | purge protection decision; publicNetworkAccess currently `Enabled` — AZ-003 must tighten to private endpoints |
| KEK `credential-kek` | RSA-2048, `wrapKey`/`unwrapKey` only | key rotation procedure |
| Storage | `Standard_LRS`, private `user-documents` container (exports live under the `exports/` key prefix), `allowSharedKeyAccess: false`, no public access | container split for exports deferred to recovery plan; shared-key break-glass decision |
| App Service | Linux `B1`, one instance, Always On, system managed identity, `/health/ready` check, container `kind`, `acrUseManagedIdentityCreds`, `WEBSITES_PORT=8080` | scaling envelope under the ten-user beta cap |
| App Insights | 30-day retention, redacted telemetry only | ingestion cap/budget alert |
| RBAC | app identity: `AcrPull` (on ACR), Key Vault Crypto User (on KEK), Key Vault Secrets User, Storage Blob Data Contributor | least-privilege review — Blob Data Contributor is account-scoped; narrow to containers at AZ-003 |

## App settings mapping

The template emits only names the API actually reads
(`apps/api/app/config.py`): `APP_ENV`, `WEB_APP_ORIGIN`, `LOCAL_MOCKS_ENABLED=false`,
`CREDENTIAL_KEK_PROVIDER=key_vault`, `WEB_DIST_DIR`, OIDC issuer/client/redirect,
the five database role URLs, `BLOB_ENDPOINT_URL`,
`KEY_VAULT_CREDENTIAL_KEK_ID`, `APP_HASH_KEY`,
`AUTH_TRANSACTION_ENCRYPTION_KEY`, `BETA_ALLOWED_EMAILS`,
`CHROME_EXTENSION_IDS` — secrets sourced from Key Vault references,
never literal values (`CHROME_EXTENSION_IDS` is a public identifier
and arrives as a deployment parameter).

## Managed-identity wiring (implemented, unverified against Azure)

`app/storage/blob.py` selects a managed-identity `TokenCredential`
(via `app/security/managed_identity.py`, shared with the Key Vault KEK
adapter) when `APP_ENV` is not local/test, so the Blob Data Contributor
role is the only data-plane path — matching `allowSharedKeyAccess: false`.
This has not been exercised against a real IMDS endpoint; AZ-003 must
verify token acquisition and blob/KV auth inside staging.

## Quote

USD 150/month is the planning envelope (DEPLOYMENT.md), not a quote.
Before provisioning, the owner must run:

```
az deployment sub what-if --location eastus \
  --template-file infra/azure/main.bicep \
  --parameters infra/azure/parameters.staging.json
az consumption ... # plus the Azure pricing calculator for the listed SKUs
```

and record the real quote, quota checks (Burstable B1ms, App Service B1,
ACR Basic in `eastus`) and any SKU substitutions in this file.

## Apply sequence (future)

1. Operator creates the resource group and the Key Vault secrets listed
   above (database role URLs, OIDC secret, hash/encryption keys, beta
   allowlist).
2. `az deployment sub create` for staging only.
3. Build + push image via `.github/workflows/deploy-image.yml`
   (federated OIDC; operator must create the Entra app registration and
   federated credential first).
4. Run migrations with the migrator-role connection before first traffic:
   `docker run --rm <image> /srv/api/.venv/bin/alembic -c alembic.ini upgrade head`.
5. Verify `/health/ready`, auth redirect, then enable the beta allowlist.

## Recovery/rollback skeleton (AZ-004 prerequisites)

- Rollback = re-point `linuxFxVersion` to the previous recorded image
  digest (the deploy workflow records pushed digests in the step summary).
- DB restore: create a NEW isolated flexible server from the 7-day
  restore window, reapply role grants via migrations, replay the
  `deletion_journal` rows for any user deleted inside the window, revoke
  all sessions/grants, cancel in-flight jobs, then repoint runtime.
- Measured RPO ≤15 min / RTO ≤4 h targets are unverified until the drill.
