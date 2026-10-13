# Identity and local account setup

## Local synthetic identity

The loopback mock at `http://127.0.0.1:18101/oidc` implements a short-lived authorization-code flow with S256 PKCE. It signs synthetic ID tokens with the local-only `OIDC_CLIENT_SECRET`; this HS256 mode is accepted only when `APP_ENV=local` or `test`. It is not suitable for staging or production.

Set these local values in `.env`:

- `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, and `OIDC_REDIRECT_URI` must match the loopback mock and API callback. `WEB_APP_ORIGIN` is the fixed dashboard origin used after sign-in.
- `BETA_ALLOWED_EMAILS` is a comma-separated list of synthetic identities admitted to the local workspace.
- `AUTH_DATABASE_URL`, `DATABASE_URL`, `WORKER_DATABASE_URL`, and `MIGRATION_DATABASE_URL` must use their separate PostgreSQL roles and target the same loopback database.
- `CHROME_EXTENSION_IDS` must include the ID derived from the extension's pinned development manifest key. The current development ID is `digpnmcecpkodggeieillcjpfgpokgnk`.

Start PostgreSQL/Azurite, then the mock identity service and API. Open `/auth/login` from the web origin or sign in from the extension panel. The dashboard receives an HttpOnly session cookie. The extension receives a one-use grant bound to its ID, state, and PKCE challenge, then keeps its bearer token in `chrome.storage.session`.

## Configuring a real Entra External ID tenant

Before a nonlocal environment can accept sign-in, an operator must configure a dedicated External ID tenant and confidential web app registration. Record the exact issuer, client ID, secret reference, tenant directory-object claim mapping, and callback URI. Register only the deployed HTTPS callback and the exact extension redirect `https://<extension-id>.chromiumapp.org/auth`. Populate a beta enrollment allowlist and `CHROME_EXTENSION_IDS`; do not enable local mocks or HS256 outside local/test.

The provider must return a verified email, stable `sub`, directory object `oid`, and signed ID token using RS256 with a published JWKS. Confirm issuer, audience, nonce, `auth_time`, email-verification, PKCE, sign-up/reset policy, and account deletion procedure in the actual tenant before beta. Keep client secrets and application hash/transaction-encryption keys in the configured secret store. This repository does not provision a tenant, create real identities, or claim a live-provider smoke test.

## Session operations

Web sessions store only a SHA-256 token digest; the cookie is Secure, HttpOnly, SameSite=Lax, and host-only. Idle expiry is 60 minutes and absolute expiry is 12 hours. Cookie mutations require the session CSRF token and exact request Origin. `/auth/login?fresh=true` requests a fresh provider authentication for sensitive actions. Logout revokes all sessions for the account.

Provider keys are encrypted with a fresh AES-GCM DEK per saved record. Local/test wraps each DEK with the local test KEK; nonlocal settings use the versioned Key Vault RSA key through the App Service managed-identity endpoint with RSA-OAEP-256. Grant the configured App Service identity Key Vault wrap/unwrap permissions and configure `KEY_VAULT_CREDENTIAL_KEK_ID` with the versioned HTTPS key URI. To rotate, deploy the new versioned URI and run the credential rewrap operation while retaining access to the prior key version for unwrap. Key management endpoints deliberately return only masked key metadata. The adapter still needs a live tenant permission, storage, and rotation smoke test before release.
