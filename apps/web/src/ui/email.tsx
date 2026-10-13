import { useCallback, useEffect, useState } from "react";

const GMAIL_COMPOSE = "https://mail.google.com/mail/?view=cm&fs=1";
const MAX_PREFILL_URL = 6000;

type Draft = {
  id: string;
  recipient_email: string;
  employer: string;
  role: string;
  subject: string;
  body: string;
  state: string;
  revision: number;
  application_id: string | null;
};

const STATE_LABELS: Record<string, string> = {
  DRAFT: "Draft",
  READY_FOR_REVIEW: "Ready for review",
  COMPOSE_OPENED: "Compose opened",
  USER_CONFIRMED_SENT: "Sent (confirmed)",
  CANCELED: "Canceled",
};

async function api<T>(
  path: string,
  csrf: string,
  options: RequestInit = {},
): Promise<T> {
  const { headers: extra, ...rest } = options;
  const response = await fetch(path, {
    credentials: "include",
    ...rest,
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrf,
      ...(extra ?? {}),
    },
  });
  if (!response.ok) {
    const detail = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(detail?.detail ?? `request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

export function gmailComposeUrl(draft: {
  recipient_email: string;
  subject: string;
  body: string;
}): string {
  const params = new URLSearchParams({
    to: draft.recipient_email,
    su: draft.subject,
    body: draft.body,
  });
  return `${GMAIL_COMPOSE}&${params.toString()}`;
}

export function mailtoUrl(draft: {
  recipient_email: string;
  subject: string;
  body: string;
}): string {
  const params = new URLSearchParams({
    subject: draft.subject,
    body: draft.body,
  });
  return `mailto:${encodeURIComponent(draft.recipient_email)}?${params.toString()}`;
}

export function EmailPage({
  csrf,
  signedIn,
}: {
  csrf: string;
  signedIn: boolean;
}) {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [selected, setSelected] = useState<Draft | null>(null);
  const [edit, setEdit] = useState({ subject: "", body: "" });
  const [sentDate, setSentDate] = useState("");
  const [form, setForm] = useState({
    recipient_email: "",
    employer: "",
    role: "",
    job_description: "",
  });
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api<{ drafts: Draft[] }>("/api/v1/email-drafts", csrf);
      setDrafts(data.drafts);
    } catch {
      setError("Email drafts could not be loaded.");
    }
  }, [csrf]);

  useEffect(() => {
    if (signedIn) void load();
  }, [signedIn, load]);

  function openDraft(draft: Draft) {
    setSelected(draft);
    setEdit({ subject: draft.subject, body: draft.body });
    setSentDate("");
    setError("");
    setNotice("");
  }

  async function createDraft() {
    setBusy(true);
    setError("");
    try {
      const draft = await api<Draft>("/api/v1/email-drafts", csrf, {
        method: "POST",
        body: JSON.stringify({
          recipient_email: form.recipient_email,
          employer: form.employer,
          role: form.role,
          job_description: form.job_description || null,
        }),
      });
      setDrafts((current) => [draft, ...current]);
      openDraft(draft);
      setNotice("Draft created. Generate or write the message yourself.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function generate() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<{
        revision: number;
        subject: string;
        body: string;
      }>(`/api/v1/email-drafts/${selected.id}/generate`, csrf, {
        method: "POST",
        body: JSON.stringify({ expected_revision: selected.revision }),
      });
      setEdit({ subject: result.subject, body: result.body });
      setSelected({ ...selected, ...result });
      setNotice("Draft generated. Review every line before sending.");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function persistEdits(): Promise<Draft | null> {
    if (!selected) return null;
    if (edit.subject === selected.subject && edit.body === selected.body) {
      return selected;
    }
    const updated = await api<Draft>(
      `/api/v1/email-drafts/${selected.id}`,
      csrf,
      {
        method: "PATCH",
        headers: { "If-Match": `"${selected.revision}"` },
        body: JSON.stringify(edit),
      },
    );
    setSelected(updated);
    return updated;
  }

  async function saveEdits() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const updated = await persistEdits();
      if (updated) setSelected(updated);
      setNotice("Edits saved as a new revision.");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function copy(label: string, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setNotice(`${label} copied.`);
    } catch {
      setError(`${label} could not be copied; select and copy it manually.`);
    }
  }

  async function openInGmail() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      // Persist first so the tracked revision always matches what is sent.
      const current = await persistEdits();
      if (!current) return;
      await api<Draft>(
        `/api/v1/email-drafts/${current.id}/compose-opened`,
        csrf,
        {
          method: "POST",
          body: JSON.stringify({
            event_idempotency_key: crypto.randomUUID(),
          }),
        },
      );
      const url = gmailComposeUrl(current);
      if (url.length > MAX_PREFILL_URL) {
        setError(
          "This message is too long to prefill in Gmail. Use the copy buttons instead — nothing was truncated.",
        );
      } else {
        window.open(url, "_blank", "noopener,noreferrer");
        setNotice(
          "Compose opened in Gmail with the reviewed revision. Come back to confirm only after you actually send.",
        );
      }
      setSelected({ ...current, state: "COMPOSE_OPENED" });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function confirmSent() {
    if (!selected || !sentDate) return;
    setBusy(true);
    setError("");
    try {
      const current = await persistEdits();
      if (!current) return;
      const result = await api<{ application_id: string; replayed: boolean }>(
        `/api/v1/email-drafts/${current.id}/confirm-sent`,
        csrf,
        {
          method: "POST",
          body: JSON.stringify({
            sent_date: sentDate,
            event_idempotency_key: crypto.randomUUID(),
          }),
        },
      );
      setNotice(
        result.replayed
          ? "Already recorded — no duplicate application was created."
          : "Recorded as Applied with your confirmation. The draft is now locked.",
      );
      setSelected({ ...current, state: "USER_CONFIRMED_SENT" });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const composeUrl = selected ? gmailComposeUrl({ ...selected, ...edit }) : "";
  const tooLong = composeUrl.length > MAX_PREFILL_URL;
  const editable =
    selected !== null &&
    !["USER_CONFIRMED_SENT", "CANCELED"].includes(selected.state);

  return (
    <section aria-labelledby="email-title">
      <h1 id="email-title">Email applications</h1>
      <p className="section-intro">
        Draft a message, review the exact recipient, subject, and body, then
        open it in Gmail yourself. Rolevo never sends email. Marking “sent” is
        your explicit confirmation and records the application as Applied.
      </p>

      <h2>New draft</h2>
      <div className="toolbar">
        <div className="field">
          <label htmlFor="email-to">Recipient</label>
          <input
            id="email-to"
            className="control"
            type="email"
            required
            value={form.recipient_email}
            onChange={(event) =>
              setForm((f) => ({ ...f, recipient_email: event.target.value }))
            }
          />
        </div>
        <div className="field">
          <label htmlFor="email-employer">Employer</label>
          <input
            id="email-employer"
            className="control"
            required
            value={form.employer}
            onChange={(event) =>
              setForm((f) => ({ ...f, employer: event.target.value }))
            }
          />
        </div>
        <div className="field">
          <label htmlFor="email-role">Role</label>
          <input
            id="email-role"
            className="control"
            required
            value={form.role}
            onChange={(event) =>
              setForm((f) => ({ ...f, role: event.target.value }))
            }
          />
        </div>
      </div>
      <div className="field" style={{ maxWidth: 560 }}>
        <label htmlFor="email-jd">Job description excerpt (optional)</label>
        <textarea
          id="email-jd"
          className="control"
          rows={3}
          value={form.job_description}
          onChange={(event) =>
            setForm((f) => ({ ...f, job_description: event.target.value }))
          }
        />
      </div>
      <button
        type="button"
        className="preview-pill"
        disabled={busy || !form.recipient_email || !form.employer || !form.role}
        onClick={() => void createDraft()}
      >
        Create draft
      </button>

      <p aria-live="polite" className="status-line">
        {notice}
      </p>
      {error && (
        <p role="alert" className="error-line">
          {error}
        </p>
      )}

      <h2>Drafts</h2>
      {drafts.length === 0 ? (
        <p>No email drafts yet.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Recipient</th>
              <th scope="col">Employer</th>
              <th scope="col">Role</th>
              <th scope="col">State</th>
              <th scope="col" aria-label="Open" />
            </tr>
          </thead>
          <tbody>
            {drafts.map((draft) => (
              <tr key={draft.id}>
                <td>{draft.recipient_email}</td>
                <td>{draft.employer}</td>
                <td>{draft.role}</td>
                <td>{STATE_LABELS[draft.state] ?? draft.state}</td>
                <td>
                  <button
                    type="button"
                    className="text-link as-button"
                    onClick={() => openDraft(draft)}
                  >
                    Review
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {selected && (
        <section className="notice-card" aria-labelledby="review-title">
          <h2 id="review-title">
            Review — revision {selected.revision} (
            {STATE_LABELS[selected.state]})
          </h2>
          <p>
            To: <strong>{selected.recipient_email}</strong> ·{" "}
            {selected.employer} — {selected.role}
          </p>
          {editable ? (
            <>
              <div className="field">
                <label htmlFor="edit-subject">Subject</label>
                <input
                  id="edit-subject"
                  className="control"
                  maxLength={200}
                  value={edit.subject}
                  onChange={(event) =>
                    setEdit((e) => ({ ...e, subject: event.target.value }))
                  }
                />
              </div>
              <div className="field">
                <label htmlFor="edit-body">Message</label>
                <textarea
                  id="edit-body"
                  className="control"
                  rows={10}
                  maxLength={10000}
                  value={edit.body}
                  onChange={(event) =>
                    setEdit((e) => ({ ...e, body: event.target.value }))
                  }
                />
              </div>
              <div className="toolbar">
                <button
                  type="button"
                  className="preview-pill"
                  disabled={busy}
                  onClick={() => void saveEdits()}
                >
                  Save edits
                </button>
                <button
                  type="button"
                  className="preview-pill"
                  disabled={busy}
                  onClick={() => void generate()}
                >
                  Generate with AI
                </button>
              </div>
            </>
          ) : (
            <>
              <p>
                <strong>Subject:</strong> {selected.subject}
              </p>
              <p style={{ whiteSpace: "pre-wrap" }}>{selected.body}</p>
            </>
          )}

          <h3>Send through Gmail (you always press Send)</h3>
          <p className="section-intro">
            Opening Gmail places the reviewed text into your browser and Gmail.
            If prefill is too long, use the copy buttons — nothing is truncated.
            Attach your files inside Gmail.
          </p>
          {tooLong && (
            <p role="alert" className="error-line">
              This message is too long for a Gmail prefill link. Use copy.
            </p>
          )}
          <div className="toolbar">
            <button
              type="button"
              className="preview-pill"
              disabled={busy || tooLong || !editable || !edit.subject}
              onClick={() => void openInGmail()}
            >
              Open in Gmail
            </button>
            <button
              type="button"
              className="preview-pill"
              onClick={() => void copy("Recipient", selected.recipient_email)}
            >
              Copy recipient
            </button>
            <button
              type="button"
              className="preview-pill"
              onClick={() => void copy("Subject", edit.subject)}
            >
              Copy subject
            </button>
            <button
              type="button"
              className="preview-pill"
              onClick={() => void copy("Message", edit.body)}
            >
              Copy message
            </button>
            <a
              className="text-link"
              href={mailtoUrl({ ...selected, ...edit })}
              rel="noreferrer"
            >
              Open mailto instead
            </a>
          </div>

          {selected.state !== "USER_CONFIRMED_SENT" && (
            <div className="toolbar">
              <div className="field">
                <label htmlFor="sent-date">I sent this email on</label>
                <input
                  id="sent-date"
                  className="control"
                  type="date"
                  value={sentDate}
                  onChange={(event) => setSentDate(event.target.value)}
                />
              </div>
              <button
                type="button"
                className="preview-pill"
                disabled={busy || !sentDate}
                onClick={() => void confirmSent()}
              >
                I sent this email
              </button>
            </div>
          )}
        </section>
      )}
    </section>
  );
}
