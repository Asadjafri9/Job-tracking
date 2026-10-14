import { useCallback, useEffect, useState } from "react";

const VALUE_TYPES = [
  "TEXT",
  "NUMBER",
  "DATE",
  "BOOLEAN",
  "URL",
  "JSON",
] as const;
const PURPOSES = ["AUTOFILL", "EMAIL", "MONITORING"] as const;

interface Fact {
  id: string;
  fact_key: string;
  value_type: string;
  value: unknown;
  sensitivity: string;
  allowed_purposes: string[];
  current_revision: number;
  confirmation_state: string;
  source_type: string;
}

interface ProfileResponse {
  revision: number;
  facts: Fact[];
}

interface FactForm {
  fact_key: string;
  value_type: (typeof VALUE_TYPES)[number];
  value: string;
  sensitivity: "NORMAL" | "SENSITIVE" | "SPECIAL_CATEGORY";
  allowed_purposes: string[];
  editing_id: string | null;
  expected_revision: number | null;
}

const emptyForm: FactForm = {
  fact_key: "",
  value_type: "TEXT",
  value: "",
  sensitivity: "NORMAL",
  allowed_purposes: [],
  editing_id: null,
  expected_revision: null,
};

function encodeValue(valueType: string, raw: string): unknown {
  if (valueType === "NUMBER") return Number(raw);
  if (valueType === "BOOLEAN") return raw === "true";
  if (valueType === "JSON") return JSON.parse(raw);
  return raw;
}

export function ProfilePage({
  csrf,
  signedIn,
}: {
  csrf: string;
  signedIn: boolean;
}) {
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [form, setForm] = useState<FactForm>(emptyForm);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoadState("loading");
    try {
      const response = await fetch("/api/v1/profile", {
        credentials: "include",
      });
      if (!response.ok) throw new Error("load failed");
      setProfile((await response.json()) as ProfileResponse);
      setLoadState("ready");
    } catch {
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    if (signedIn) void load();
  }, [signedIn, load]);

  function updateForm(patch: Partial<FactForm>) {
    setForm((current) => ({ ...current, ...patch }));
  }

  async function saveFact() {
    setBusy(true);
    setNotice("");
    try {
      const payload = {
        fact_key: form.fact_key,
        value_type: form.value_type,
        value: encodeValue(form.value_type, form.value),
        sensitivity: form.sensitivity,
        allowed_purposes: form.allowed_purposes,
        ...(form.editing_id
          ? { expected_revision: form.expected_revision }
          : {}),
      };
      const editing = Boolean(form.editing_id);
      const response = await fetch(
        editing
          ? `/api/v1/profile/facts/${form.editing_id}`
          : "/api/v1/profile/facts",
        {
          method: editing ? "POST" : "PUT",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf,
            ...(editing ? { "If-Match": `"${form.expected_revision}"` } : {}),
          },
          body: JSON.stringify(payload),
        },
      );
      if (response.status === 409) {
        await load();
        throw new Error(
          "The profile changed elsewhere. Latest data was reloaded; try again.",
        );
      }
      if (!response.ok) {
        const detail = (await response.json().catch(() => null)) as {
          detail?: string;
        } | null;
        throw new Error(detail?.detail ?? "The fact could not be saved.");
      }
      setForm(emptyForm);
      setNotice(editing ? "Fact updated." : "Fact added to your profile.");
      await load();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function removeFact(fact: Fact) {
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch(`/api/v1/profile/facts/${fact.id}`, {
        method: "DELETE",
        credentials: "include",
        headers: { "X-CSRF-Token": csrf },
      });
      if (!response.ok) throw new Error("The fact could not be removed.");
      setNotice(`Removed ${fact.fact_key}.`);
      await load();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Remove failed");
    } finally {
      setBusy(false);
    }
  }

  function editFact(fact: Fact) {
    setForm({
      fact_key: fact.fact_key,
      value_type: fact.value_type as FactForm["value_type"],
      value:
        typeof fact.value === "string"
          ? fact.value
          : JSON.stringify(fact.value ?? ""),
      sensitivity: fact.sensitivity as FactForm["sensitivity"],
      allowed_purposes: fact.allowed_purposes,
      editing_id: fact.id,
      expected_revision: fact.current_revision,
    });
  }

  if (!signedIn) {
    return (
      <section className="placeholder" aria-labelledby="profile-signed-out">
        <p className="eyebrow">PROFILE</p>
        <h1 id="profile-signed-out">Sign in to manage your profile</h1>
      </section>
    );
  }

  return (
    <div className="providers" aria-labelledby="profile-title">
      <p className="eyebrow">PROFILE</p>
      <h1 id="profile-title">Your professional profile</h1>
      <p className="intro">
        Confirmed facts power autofill and email drafts. Facts marked for a
        purpose are the only ones shared with a provider.
      </p>

      <p className="form-status" role="status" aria-live="polite">
        {loadState === "loading" ? "Loading profile…" : notice}
      </p>
      {loadState === "error" && (
        <p className="form-status is-error" role="alert">
          Your profile could not be loaded. Check your connection and try again.
        </p>
      )}

      <section aria-labelledby="facts-title">
        <h2 id="facts-title">Confirmed facts</h2>
        {profile && profile.facts.length === 0 && (
          <p className="data-notice">
            No facts yet. Add your first detail below.
          </p>
        )}
        <div className="fact-list">
          {profile?.facts.map((fact) => (
            <div className="fact-row" key={fact.id}>
              <div className="fact-main">
                <strong>{fact.fact_key}</strong>
                <span className="fact-value">
                  {typeof fact.value === "string"
                    ? fact.value
                    : JSON.stringify(fact.value)}
                </span>
                <span className="key-purposes">
                  {fact.confirmation_state} · {fact.source_type.toLowerCase()} ·{" "}
                  {fact.allowed_purposes.length
                    ? fact.allowed_purposes.join(" + ").toLowerCase()
                    : "not shared with providers"}
                  {fact.sensitivity !== "NORMAL"
                    ? ` · ${fact.sensitivity.toLowerCase()}`
                    : ""}
                </span>
              </div>
              <div className="fact-actions">
                <button
                  className="text-link"
                  type="button"
                  disabled={busy}
                  onClick={() => editFact(fact)}
                >
                  Edit
                </button>
                <button
                  className="text-link danger-action"
                  type="button"
                  disabled={busy}
                  onClick={() => void removeFact(fact)}
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="fact-form-title">
        <h2 id="fact-form-title">
          {form.editing_id ? "Edit fact" : "Add a fact"}
        </h2>
        <div className="fact-form">
          <div className="field">
            <label htmlFor="fact-key">Fact key</label>
            <input
              id="fact-key"
              className="control"
              type="text"
              placeholder="contact.email, skills.primary, links.linkedin"
              value={form.fact_key}
              onChange={(event) => updateForm({ fact_key: event.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="fact-type">Type</label>
            <select
              id="fact-type"
              className="control"
              value={form.value_type}
              onChange={(event) =>
                updateForm({
                  value_type: event.target.value as FactForm["value_type"],
                })
              }
            >
              {VALUE_TYPES.map((type) => (
                <option value={type} key={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="fact-value">Value</label>
            <textarea
              id="fact-value"
              className="control"
              rows={2}
              value={form.value}
              onChange={(event) => updateForm({ value: event.target.value })}
            />
          </div>
          <fieldset className="purpose-group">
            <legend>Share with providers for</legend>
            {PURPOSES.map((purpose) => (
              <label className="checkline" key={purpose}>
                <input
                  type="checkbox"
                  checked={form.allowed_purposes.includes(purpose)}
                  onChange={(event) =>
                    updateForm({
                      allowed_purposes: event.target.checked
                        ? [...form.allowed_purposes, purpose]
                        : form.allowed_purposes.filter(
                            (entry) => entry !== purpose,
                          ),
                    })
                  }
                />
                <span>{purpose.toLowerCase()}</span>
              </label>
            ))}
          </fieldset>
          <div className="button-row">
            <button
              className="primary-action"
              type="button"
              disabled={busy || !form.fact_key || !form.value}
              onClick={() => void saveFact()}
            >
              {form.editing_id ? "Save changes" : "Add fact"}
            </button>
            {form.editing_id && (
              <button
                className="text-link"
                type="button"
                onClick={() => setForm(emptyForm)}
              >
                Cancel
              </button>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
