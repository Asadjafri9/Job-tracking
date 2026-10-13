import { useCallback, useEffect, useState } from "react";

import {
  credentialFor,
  PROVIDERS,
  providerLabel,
  settingsWrite,
  type Credential,
  type ProviderId,
  type ProviderSettings,
  type Route,
} from "./provider-utils";

function purposes(credential: Credential): string {
  const allowed = [
    credential.allow_interactive ? "interactive" : null,
    credential.allow_background ? "background" : null,
  ].filter(Boolean);
  return allowed.length ? allowed.join(" + ") : "no purposes consented";
}

interface KeyFormState {
  apiKey: string;
  allowInteractive: boolean;
  allowBackground: boolean;
}

const emptyKeyForm: KeyFormState = {
  apiKey: "",
  allowInteractive: true,
  allowBackground: false,
};

export function ProvidersPage({
  csrf,
  signedIn,
}: {
  csrf: string;
  signedIn: boolean;
}) {
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [settings, setSettings] = useState<ProviderSettings | null>(null);
  const [routeDrafts, setRouteDrafts] = useState<Route[]>([]);
  const [keyForms, setKeyForms] = useState<Record<string, KeyFormState>>({});
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoadState("loading");
    try {
      const [credentialsResponse, settingsResponse] = await Promise.all([
        fetch("/api/v1/provider-credentials", { credentials: "include" }),
        fetch("/api/v1/provider-settings", { credentials: "include" }),
      ]);
      if (!credentialsResponse.ok || !settingsResponse.ok) {
        throw new Error("load failed");
      }
      const credentialsBody = (await credentialsResponse.json()) as {
        credentials: Credential[];
      };
      const settingsBody = (await settingsResponse.json()) as ProviderSettings;
      setCredentials(credentialsBody.credentials);
      setSettings(settingsBody);
      setRouteDrafts(settingsBody.routes);
      setLoadState("ready");
    } catch {
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    if (signedIn) void load();
  }, [signedIn, load]);

  function keyForm(provider: ProviderId): KeyFormState {
    return keyForms[provider] ?? emptyKeyForm;
  }

  function updateKeyForm(provider: ProviderId, patch: Partial<KeyFormState>) {
    setKeyForms((current) => ({
      ...current,
      [provider]: { ...keyForm(provider), ...patch },
    }));
  }

  async function saveKey(provider: ProviderId) {
    const form = keyForm(provider);
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch(`/api/v1/provider-credentials/${provider}`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({
          api_key: form.apiKey,
          allow_interactive: form.allowInteractive,
          allow_background: form.allowBackground,
        }),
      });
      if (!response.ok) {
        const message =
          response.status === 403
            ? "Your session needs a fresh sign-in before saving a key."
            : "The key could not be saved. Check the key and try again.";
        throw new Error(message);
      }
      updateKeyForm(provider, { apiKey: "" });
      setNotice(
        `${providerLabel(provider)} key saved. Only the last characters are kept visible.`,
      );
      await load();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function removeCredential(credential: Credential) {
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch(
        `/api/v1/provider-credentials/${credential.id}`,
        {
          method: "DELETE",
          credentials: "include",
          headers: { "X-CSRF-Token": csrf },
        },
      );
      if (!response.ok) {
        throw new Error(
          response.status === 403
            ? "Your session needs a fresh sign-in before removing a key."
            : "The key could not be removed.",
        );
      }
      setNotice(`${providerLabel(credential.provider)} key removed.`);
      await load();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Remove failed");
    } finally {
      setBusy(false);
    }
  }

  function updateSettings(patch: Partial<ProviderSettings>) {
    setSettings((current) => (current ? { ...current, ...patch } : current));
  }

  function updateRoute(credentialId: string, patch: Partial<Route>) {
    setRouteDrafts((current) =>
      current.map((route) =>
        route.credential_id === credentialId ? { ...route, ...patch } : route,
      ),
    );
  }

  function addRoute() {
    const used = new Set(routeDrafts.map((route) => route.credential_id));
    const available = credentials.find(
      (credential) => credential.enabled && !used.has(credential.id),
    );
    if (!available || routeDrafts.length >= 3) return;
    setRouteDrafts((current) => [
      ...current,
      {
        credential_id: available.id,
        model_id: "",
        enabled: true,
        interactive_enabled: true,
        background_enabled: false,
      },
    ]);
  }

  function removeRoute(credentialId: string) {
    setRouteDrafts((current) =>
      current.filter((route) => route.credential_id !== credentialId),
    );
  }

  async function saveSettings() {
    if (!settings) return;
    setBusy(true);
    setNotice("");
    const { body, headers } = settingsWrite({
      ...settings,
      routes: routeDrafts,
    });
    try {
      const response = await fetch("/api/v1/provider-settings", {
        method: "PUT",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrf,
          ...headers,
        },
        body: JSON.stringify(body),
      });
      if (response.status === 409) {
        await load();
        throw new Error(
          "Provider settings changed elsewhere. The latest version was reloaded; review and save again.",
        );
      }
      if (!response.ok) {
        const detail = (await response.json().catch(() => null)) as {
          detail?: string;
        } | null;
        throw new Error(
          detail?.detail ?? "Provider settings could not be saved.",
        );
      }
      const saved = (await response.json()) as ProviderSettings;
      setSettings(saved);
      setRouteDrafts(saved.routes);
      setNotice("Provider settings saved.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  if (!signedIn) {
    return (
      <section className="placeholder" aria-labelledby="providers-signed-out">
        <p className="eyebrow">AI PROVIDERS</p>
        <h1 id="providers-signed-out">Sign in to manage providers</h1>
        <p>Saved keys and routing consent belong to your account.</p>
        <a className="text-link" href="/auth/login">
          Sign in
        </a>
      </section>
    );
  }

  const routedIds = new Set(routeDrafts.map((route) => route.credential_id));
  const unroutes = credentials.filter(
    (credential) => credential.enabled && !routedIds.has(credential.id),
  );

  return (
    <div className="providers" aria-labelledby="providers-title">
      <p className="eyebrow">AI PROVIDERS</p>
      <h1 id="providers-title">Provider keys and routing</h1>
      <p className="intro">
        Keys are optional. A saved key is used only after you choose a provider
        and approve the data routing below.
      </p>

      <p className="form-status" role="status" aria-live="polite">
        {loadState === "loading" ? "Loading provider settings…" : notice}
      </p>
      {loadState === "error" && (
        <p className="form-status is-error" role="alert">
          Provider settings could not be loaded. Check your connection and try
          again.
        </p>
      )}

      <section aria-labelledby="saved-keys-title">
        <h2 id="saved-keys-title">Saved keys</h2>
        <p className="data-notice">
          Credentials are masked and never shown in full again. Saving a key
          replaces any existing key for that provider.
        </p>
        <div className="provider-grid">
          {PROVIDERS.map((provider) => {
            const credential = credentialFor(credentials, provider.id);
            const form = keyForm(provider.id);
            return (
              <div className="key-card" key={provider.id}>
                <div className="key-card-head">
                  <strong>{provider.label}</strong>
                  {credential ? (
                    <span className="status-badge">{credential.status}</span>
                  ) : (
                    <span className="status-badge is-muted">Not saved</span>
                  )}
                </div>
                {credential ? (
                  <>
                    <p className="masked-key">
                      Key ending in <code>{credential.last4}</code>
                    </p>
                    <p className="key-purposes">{purposes(credential)}</p>
                    <button
                      className="text-link danger-action"
                      type="button"
                      disabled={busy}
                      onClick={() => void removeCredential(credential)}
                    >
                      Remove key
                    </button>
                  </>
                ) : (
                  <>
                    <div className="field">
                      <label htmlFor={`key-${provider.id}`}>API key</label>
                      <input
                        id={`key-${provider.id}`}
                        className="control"
                        type="password"
                        autoComplete="off"
                        value={form.apiKey}
                        onChange={(event) =>
                          updateKeyForm(provider.id, {
                            apiKey: event.target.value,
                          })
                        }
                      />
                    </div>
                    <label className="checkline">
                      <input
                        type="checkbox"
                        checked={form.allowInteractive}
                        onChange={(event) =>
                          updateKeyForm(provider.id, {
                            allowInteractive: event.target.checked,
                          })
                        }
                      />
                      <span>Allow interactive use while I am present</span>
                    </label>
                    <label className="checkline">
                      <input
                        type="checkbox"
                        checked={form.allowBackground}
                        onChange={(event) =>
                          updateKeyForm(provider.id, {
                            allowBackground: event.target.checked,
                          })
                        }
                      />
                      <span>
                        Allow scheduled background checks to use this key
                      </span>
                    </label>
                    <button
                      className="primary-action"
                      type="button"
                      disabled={
                        busy ||
                        !form.apiKey ||
                        (!form.allowInteractive && !form.allowBackground)
                      }
                      onClick={() => void saveKey(provider.id)}
                    >
                      Save key
                    </button>
                  </>
                )}
              </div>
            );
          })}
        </div>
      </section>

      <section aria-labelledby="routing-title">
        <h2 id="routing-title">Routing and consent</h2>
        <p className="data-notice">
          Before each analysis, Rolevo shows which job text and profile facts go
          to the selected provider. Unrelated personal details are never sent.
        </p>
        {settings && (
          <>
            <label className="checkline">
              <input
                type="checkbox"
                checked={settings.interactive_consent}
                onChange={(event) =>
                  updateSettings({ interactive_consent: event.target.checked })
                }
              />
              <span>
                I allow interactive requests to send selected job text and
                profile facts to my chosen provider.
              </span>
            </label>
            <label className="checkline">
              <input
                type="checkbox"
                checked={settings.fallback_consent}
                onChange={(event) =>
                  updateSettings({ fallback_consent: event.target.checked })
                }
              />
              <span>
                If my first provider is unavailable, try the next enabled
                provider in order.
              </span>
            </label>
            <label className="checkline">
              <input
                type="checkbox"
                checked={settings.background_consent}
                onChange={(event) =>
                  updateSettings({ background_consent: event.target.checked })
                }
              />
              <span>
                I allow scheduled checks to use a saved key for background
                matching.
              </span>
            </label>

            <h3>Provider order</h3>
            {routeDrafts.length === 0 && (
              <p className="key-purposes">
                No providers selected yet. Save a key above, then add it here.
              </p>
            )}
            {routeDrafts.map((route, index) => {
              const credential = credentials.find(
                (entry) => entry.id === route.credential_id,
              );
              return (
                <div className="route-row" key={route.credential_id}>
                  <span
                    className="route-order"
                    aria-label={`Position ${index + 1}`}
                  >
                    {index + 1}.
                  </span>
                  <div className="field">
                    <label htmlFor={`route-provider-${route.credential_id}`}>
                      Provider
                    </label>
                    <select
                      id={`route-provider-${route.credential_id}`}
                      className="control"
                      value={route.credential_id}
                      onChange={(event) =>
                        updateRoute(route.credential_id, {
                          credential_id: event.target.value,
                        })
                      }
                    >
                      {credential && (
                        <option value={credential.id}>
                          {providerLabel(credential.provider)}
                        </option>
                      )}
                      {unroutes.map((entry) => (
                        <option value={entry.id} key={entry.id}>
                          {providerLabel(entry.provider)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor={`route-model-${route.credential_id}`}>
                      Model
                    </label>
                    <input
                      id={`route-model-${route.credential_id}`}
                      className="control"
                      type="text"
                      placeholder={
                        PROVIDERS.find(
                          (entry) => entry.id === credential?.provider,
                        )?.modelHint ?? "provider model id"
                      }
                      value={route.model_id}
                      onChange={(event) =>
                        updateRoute(route.credential_id, {
                          model_id: event.target.value,
                        })
                      }
                    />
                  </div>
                  <label className="checkline">
                    <input
                      type="checkbox"
                      checked={route.enabled}
                      onChange={(event) =>
                        updateRoute(route.credential_id, {
                          enabled: event.target.checked,
                        })
                      }
                    />
                    <span>Enabled</span>
                  </label>
                  <label className="checkline">
                    <input
                      type="checkbox"
                      checked={route.interactive_enabled}
                      onChange={(event) =>
                        updateRoute(route.credential_id, {
                          interactive_enabled: event.target.checked,
                        })
                      }
                    />
                    <span>Interactive</span>
                  </label>
                  <label className="checkline">
                    <input
                      type="checkbox"
                      checked={route.background_enabled}
                      onChange={(event) =>
                        updateRoute(route.credential_id, {
                          background_enabled: event.target.checked,
                        })
                      }
                    />
                    <span>Background</span>
                  </label>
                  <button
                    className="text-link danger-action"
                    type="button"
                    disabled={busy}
                    onClick={() => removeRoute(route.credential_id)}
                  >
                    Remove
                  </button>
                </div>
              );
            })}
            <div className="button-row">
              <button
                className="text-link"
                type="button"
                disabled={
                  busy || unroutes.length === 0 || routeDrafts.length >= 3
                }
                onClick={addRoute}
              >
                Add provider to order
              </button>
              <button
                className="primary-action"
                type="button"
                disabled={busy}
                onClick={() => void saveSettings()}
              >
                Save routing and consent
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
