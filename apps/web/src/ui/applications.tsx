import { useCallback, useEffect, useState } from "react";

const STATUS_LABELS: Record<string, string> = {
  SUBMISSION_ATTEMPTED: "Submission attempted",
  APPLIED: "Applied",
  NEEDS_FOLLOW_UP: "Needs follow-up",
  CLOSED: "Closed",
};
const STATUS_ORDER = [
  "SUBMISSION_ATTEMPTED",
  "APPLIED",
  "NEEDS_FOLLOW_UP",
  "CLOSED",
];

type ApplicationView = {
  id: string;
  channel: string;
  employer: string;
  role: string;
  status: string;
  attempt_number: number;
  applied_date: string | null;
  follow_up_date: string | null;
  revision: number;
  updated_at: string;
};

type StatusEventView = {
  id: string;
  old_status: string | null;
  new_status: string;
  source: string;
  occurred_at: string;
};

type ApplicationDetail = ApplicationView & {
  status_events: StatusEventView[];
};

type Dashboard = {
  prepared_sessions: number;
  applications_by_status: Record<string, number>;
  upcoming_follow_ups: ApplicationView[];
};

async function api<T>(
  path: string,
  csrf: string,
  options: RequestInit = {},
): Promise<T> {
  const { headers: extraHeaders, ...rest } = options;
  const response = await fetch(path, {
    credentials: "include",
    ...rest,
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrf,
      ...(extraHeaders ?? {}),
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

export function ApplicationsPage({
  csrf,
  signedIn,
}: {
  csrf: string;
  signedIn: boolean;
}) {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [applications, setApplications] = useState<ApplicationView[]>([]);
  const [detail, setDetail] = useState<ApplicationDetail | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [query, setQuery] = useState("");
  const [form, setForm] = useState({ employer: "", role: "", url: "" });
  const [confirmDate, setConfirmDate] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoadState("loading");
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set("status", statusFilter);
      if (query.trim()) params.set("q", query.trim());
      const [dash, list] = await Promise.all([
        api<Dashboard>("/api/v1/dashboard", csrf),
        api<{ applications: ApplicationView[] }>(
          `/api/v1/applications?${params.toString()}`,
          csrf,
        ),
      ]);
      setDashboard(dash);
      setApplications(list.applications);
      setLoadState("ready");
    } catch {
      setLoadState("error");
    }
  }, [csrf, statusFilter, query]);

  useEffect(() => {
    if (signedIn) void load();
  }, [signedIn, load]);

  async function openDetail(id: string) {
    try {
      setDetail(
        await api<ApplicationDetail>(`/api/v1/applications/${id}`, csrf),
      );
      setConfirmDate("");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function createManual() {
    setBusy(true);
    setNotice("");
    setError("");
    try {
      await api<ApplicationView>("/api/v1/applications", csrf, {
        method: "POST",
        body: JSON.stringify({
          employer: form.employer,
          role: form.role,
          ...(form.url ? { raw_job_url: form.url } : {}),
        }),
      });
      setForm({ employer: "", role: "", url: "" });
      setNotice("Application tracked.");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(row: ApplicationView, status: string) {
    setBusy(true);
    setError("");
    try {
      await api<ApplicationView>(`/api/v1/applications/${row.id}`, csrf, {
        method: "PATCH",
        headers: { "If-Match": `"${row.revision}"` },
        body: JSON.stringify({ status }),
      });
      await load();
      if (detail?.id === row.id) await openDetail(row.id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function confirmApplied() {
    if (!detail || !confirmDate) return;
    setBusy(true);
    setError("");
    try {
      await api<ApplicationView>(
        `/api/v1/applications/${detail.id}/confirm`,
        csrf,
        {
          method: "POST",
          headers: { "If-Match": `"${detail.revision}"` },
          body: JSON.stringify({ applied_date: confirmDate }),
        },
      );
      await openDetail(detail.id);
      await load();
      setNotice("Marked applied.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (loadState === "loading" && applications.length === 0) {
    return (
      <section aria-label="Loading applications">
        <p>Loading applications…</p>
      </section>
    );
  }
  if (loadState === "error") {
    return (
      <section aria-label="Applications unavailable" role="alert">
        <h1>Applications could not be loaded</h1>
        <p>Check your connection, then refresh.</p>
        <button
          type="button"
          className="preview-pill"
          onClick={() => void load()}
        >
          Try again
        </button>
      </section>
    );
  }

  return (
    <section aria-labelledby="applications-title">
      <h1 id="applications-title">Applications</h1>
      <p className="section-intro">
        Prepared sessions never count as applications. A trusted submit
        observation is tracked as an attempt; you confirm when it is applied.
      </p>

      <div className="stat-grid" role="list" aria-label="Tracking summary">
        <div className="stat-card" role="listitem">
          <strong>{dashboard?.prepared_sessions ?? 0}</strong>
          <span>Prepared sessions</span>
        </div>
        {STATUS_ORDER.map((status) => (
          <div className="stat-card" role="listitem" key={status}>
            <strong>{dashboard?.applications_by_status[status] ?? 0}</strong>
            <span>{STATUS_LABELS[status]}</span>
          </div>
        ))}
      </div>

      {(dashboard?.upcoming_follow_ups.length ?? 0) > 0 && (
        <div className="notice-card" role="note">
          <strong>Follow-ups due within 7 days:</strong>{" "}
          {dashboard!.upcoming_follow_ups
            .map((row) => `${row.employer} (${row.follow_up_date})`)
            .join(" · ")}
        </div>
      )}

      <div className="toolbar">
        <div className="field">
          <label htmlFor="app-filter-status">Status</label>
          <select
            id="app-filter-status"
            className="control"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="">All statuses</option>
            {STATUS_ORDER.map((status) => (
              <option key={status} value={status}>
                {STATUS_LABELS[status]}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="app-filter-query">Search</label>
          <input
            id="app-filter-query"
            className="control"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Employer or role"
          />
        </div>
      </div>

      <h2>Track a manual application</h2>
      <div className="toolbar">
        <div className="field">
          <label htmlFor="app-new-employer">Employer</label>
          <input
            id="app-new-employer"
            className="control"
            required
            value={form.employer}
            onChange={(event) =>
              setForm((f) => ({ ...f, employer: event.target.value }))
            }
          />
        </div>
        <div className="field">
          <label htmlFor="app-new-role">Role</label>
          <input
            id="app-new-role"
            className="control"
            required
            value={form.role}
            onChange={(event) =>
              setForm((f) => ({ ...f, role: event.target.value }))
            }
          />
        </div>
        <div className="field">
          <label htmlFor="app-new-url">Job URL (optional)</label>
          <input
            id="app-new-url"
            className="control"
            type="url"
            value={form.url}
            onChange={(event) =>
              setForm((f) => ({ ...f, url: event.target.value }))
            }
          />
        </div>
        <button
          type="button"
          className="preview-pill"
          disabled={busy || !form.employer || !form.role}
          onClick={() => void createManual()}
        >
          Track application
        </button>
      </div>

      <p aria-live="polite" className="status-line">
        {notice}
      </p>
      {error && (
        <p role="alert" className="error-line">
          {error}
        </p>
      )}

      {applications.length === 0 ? (
        <p>
          No applications yet. Prepared sessions and manual entries appear here.
        </p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Employer</th>
              <th scope="col">Role</th>
              <th scope="col">Channel</th>
              <th scope="col">Status</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {applications.map((row) => (
              <tr key={row.id}>
                <td>{row.employer}</td>
                <td>{row.role}</td>
                <td>{row.channel === "WEB_FORM" ? "Web form" : row.channel}</td>
                <td>{STATUS_LABELS[row.status] ?? row.status}</td>
                <td>
                  <button
                    type="button"
                    className="text-link as-button"
                    onClick={() => void openDetail(row.id)}
                  >
                    History
                  </button>{" "}
                  {row.status !== "CLOSED" && row.status !== "APPLIED" && (
                    <button
                      type="button"
                      className="text-link as-button"
                      disabled={busy}
                      onClick={() => void setStatus(row, "CLOSED")}
                    >
                      Close
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {detail && (
        <section className="notice-card" aria-labelledby="detail-title">
          <h2 id="detail-title">
            {detail.employer} — {detail.role}
          </h2>
          <p>
            Status: <strong>{STATUS_LABELS[detail.status]}</strong> · attempt #
            {detail.attempt_number} · revision {detail.revision}
          </p>
          <h3>Status history</h3>
          <ul>
            {detail.status_events.map((event) => (
              <li key={event.id}>
                {event.old_status ?? "(created)"} →{" "}
                {STATUS_LABELS[event.new_status] ?? event.new_status} via{" "}
                {event.source} · {new Date(event.occurred_at).toLocaleString()}
              </li>
            ))}
          </ul>
          {detail.status !== "APPLIED" && detail.status !== "CLOSED" && (
            <div className="toolbar">
              <div className="field">
                <label htmlFor="app-confirm-date">Confirm applied date</label>
                <input
                  id="app-confirm-date"
                  className="control"
                  type="date"
                  value={confirmDate}
                  onChange={(event) => setConfirmDate(event.target.value)}
                />
              </div>
              <button
                type="button"
                className="preview-pill"
                disabled={busy || !confirmDate}
                onClick={() => void confirmApplied()}
              >
                Confirm applied
              </button>
            </div>
          )}
        </section>
      )}
    </section>
  );
}
