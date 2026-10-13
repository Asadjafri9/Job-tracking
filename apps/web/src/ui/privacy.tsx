import { useCallback, useEffect, useState } from "react";

interface ExportItem {
  id: string;
  state: string;
  size_bytes: number;
  sha256: string | null;
  expires_at: string;
  created_at: string;
  ready: boolean;
}

async function request(
  path: string,
  csrf: string,
  init: RequestInit = {},
): Promise<Response> {
  return fetch(path, {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrf,
      ...init.headers,
    },
  });
}

function formatExpiry(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function PrivacyPage({ csrf }: { csrf: string; signedIn: boolean }) {
  const [exports, setExports] = useState<ExportItem[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    const response = await fetch("/api/v1/export-requests", {
      credentials: "include",
    });
    if (response.ok) {
      const body = (await response.json()) as { exports: ExportItem[] };
      setExports(body.exports);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createExport() {
    setBusy(true);
    setError(null);
    setStatus("Building your export…");
    const response = await request("/api/v1/export-requests", csrf, {
      method: "POST",
      body: "{}",
    });
    if (!response.ok) {
      setStatus("");
      setError("Could not start the export. Try again.");
      setBusy(false);
      return;
    }
    setStatus("Export requested. It will be ready to download shortly.");
    await load();
    setBusy(false);
  }

  async function deleteAccount() {
    if (confirmation !== "DELETE") return;
    setDeleting(true);
    setError(null);
    const response = await request("/api/v1/account/deletion", csrf, {
      method: "POST",
      body: JSON.stringify({ confirmation: "DELETE" }),
    });
    if (response.ok) {
      setStatus(
        "Your account is being deleted. All sessions have been signed out.",
      );
      setTimeout(() => {
        window.location.href = "/auth/logout";
      }, 3000);
      return;
    }
    setError(
      response.status === 403
        ? "Account deletion needs a recent sign-in. Sign out and back in, then try again."
        : "Deletion could not be started. Try again.",
    );
    setDeleting(false);
  }

  return (
    <div className="providers">
      <section className="notice-card" aria-labelledby="export-heading">
        <p className="eyebrow">YOUR DATA</p>
        <h2 id="export-heading">Export everything</h2>
        <p className="intro">
          Download a ZIP with your profile, documents, applications, email
          drafts and monitoring history. Exports stay private to you and expire
          24 hours after they are built.
        </p>
        <div className="button-row">
          <button
            className="primary-action"
            type="button"
            disabled={busy}
            onClick={() => void createExport()}
          >
            {busy ? "Requesting…" : "Request export"}
          </button>
        </div>
        {exports.length > 0 ? (
          <ul className="fact-list" aria-label="Your exports">
            {exports.map((item) => (
              <li className="key-card" key={item.id}>
                <div className="key-card-head">
                  <span className="status-badge">{item.state}</span>
                  {item.ready ? (
                    <a
                      className="text-link"
                      href={`/api/v1/export-requests/${item.id}/download`}
                    >
                      Download
                    </a>
                  ) : null}
                </div>
                <p className="control-note">
                  {item.size_bytes > 0
                    ? `${(item.size_bytes / 1024).toFixed(0)} KB · `
                    : ""}
                  expires {formatExpiry(item.expires_at)}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="control-note">No exports yet.</p>
        )}
      </section>

      <section className="notice-card" aria-labelledby="delete-heading">
        <p className="eyebrow">IRREVERSIBLE</p>
        <h2 id="delete-heading">Delete your account</h2>
        <p className="intro">
          This permanently removes your profile, documents, applications, email
          drafts, monitoring sources and exports. Provider keys are revoked and
          all sessions are signed out immediately. This cannot be undone.
        </p>
        <label className="field">
          <span>
            Type <strong>DELETE</strong> to confirm
          </span>
          <input
            className="control"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            autoComplete="off"
            aria-label="Type DELETE to confirm account deletion"
          />
        </label>
        <div className="button-row">
          <button
            className="primary-action danger-action"
            type="button"
            disabled={confirmation !== "DELETE" || deleting}
            onClick={() => void deleteAccount()}
          >
            {deleting ? "Deleting…" : "Delete my account"}
          </button>
        </div>
        <p className="control-note">
          You must have signed in within the last 10 minutes. A deletion receipt
          is issued before access ends.
        </p>
      </section>

      {status ? (
        <p className="form-status" role="status" aria-live="polite">
          {status}
        </p>
      ) : null}
      {error ? (
        <p className="form-status is-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
