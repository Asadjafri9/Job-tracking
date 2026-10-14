import { useCallback, useEffect, useState } from "react";

type Source = {
  id: string;
  public_url: string;
  source_kind: string;
  state: string;
  schedule: string;
  timezone: string;
  region_selector: string | null;
  revision: number;
  next_run_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  setup_required: boolean;
};

type Run = {
  id: string;
  source_id: string;
  run_kind: string;
  state: string;
  completeness: string;
  discovered_count: number;
  started_at: string | null;
  ended_at: string | null;
  redacted_error: string | null;
};

type Job = {
  id: string;
  source_id: string;
  title: string;
  employer: string | null;
  location: string | null;
  is_remote: boolean | null;
  canonical_job_url: string | null;
  match_reason: string | null;
  status: string;
};

type Notification = {
  id: string;
  kind: string;
  content: string;
  discovered_job_id: string | null;
  read_at: string | null;
  created_at: string;
};

const SOURCE_STATES: Record<string, string> = {
  ACTIVE: "Active",
  PAUSED: "Paused",
  UNSUPPORTED: "Unsupported",
  ERROR: "Error",
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
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const TIMEZONES = (() => {
  try {
    return Intl.supportedValuesOf("timeZone");
  } catch {
    return ["UTC"];
  }
})();

export function AlertsPage({
  csrf,
  signedIn,
}: {
  csrf: string;
  signedIn: boolean;
}) {
  const [sources, setSources] = useState<Source[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unread, setUnread] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  const [url, setUrl] = useState("");
  const [timezone, setTimezone] = useState(
    () => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  );
  const [consent, setConsent] = useState(false);
  const [keyConsent, setKeyConsent] = useState(false);

  const load = useCallback(async () => {
    if (!signedIn) return;
    try {
      const [sourceList, jobList, runList, noteList] = await Promise.all([
        api<{ sources: Source[] }>("/api/v1/monitored-sources", csrf),
        api<{ jobs: Job[] }>("/api/v1/discovered-jobs", csrf),
        api<{ runs: Run[] }>("/api/v1/monitoring-runs", csrf),
        api<{ notifications: Notification[]; unread_count: number }>(
          "/api/v1/notifications",
          csrf,
        ),
      ]);
      setSources(sourceList.sources);
      setJobs(jobList.jobs);
      setRuns(runList.runs);
      setNotifications(noteList.notifications);
      setUnread(noteList.unread_count);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "load failed");
    }
  }, [csrf, signedIn]);

  useEffect(() => {
    void load();
  }, [load]);

  async function addSource() {
    setBusy(true);
    setStatus("");
    try {
      await api("/api/v1/monitored-sources", csrf, {
        method: "POST",
        body: JSON.stringify({
          public_url: url,
          timezone,
          schedule: "DAILY",
          scheduled_check_consent: consent,
          saved_key_consent: keyConsent,
        }),
      });
      setUrl("");
      setConsent(false);
      setKeyConsent(false);
      setStatus("Source added");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "save failed");
    } finally {
      setBusy(false);
    }
  }

  async function patchSource(source: Source, body: Record<string, unknown>) {
    setBusy(true);
    try {
      await api(`/api/v1/monitored-sources/${source.id}`, csrf, {
        method: "PATCH",
        body: JSON.stringify({ expected_revision: source.revision, ...body }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "update failed");
    } finally {
      setBusy(false);
    }
  }

  async function checkNow(source: Source) {
    setBusy(true);
    try {
      await api(`/api/v1/monitored-sources/${source.id}/check-now`, csrf, {
        method: "POST",
      });
      setStatus("Check queued");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "check failed");
    } finally {
      setBusy(false);
    }
  }

  async function removeSource(source: Source) {
    if (!window.confirm("Remove this source and stop its checks?")) return;
    try {
      await api(`/api/v1/monitored-sources/${source.id}`, csrf, {
        method: "DELETE",
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "remove failed");
    }
  }

  async function jobAction(job: Job, action: "save" | "dismiss" | "reopen") {
    try {
      await api(`/api/v1/discovered-jobs/${job.id}`, csrf, {
        method: "PATCH",
        body: JSON.stringify({ action }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "update failed");
    }
  }

  async function markRead(note: Notification) {
    try {
      await api(`/api/v1/notifications/${note.id}/read`, csrf, {
        method: "POST",
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "update failed");
    }
  }

  async function markAllRead() {
    try {
      await api("/api/v1/notifications/read-all", csrf, { method: "POST" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "update failed");
    }
  }

  return (
    <section className="providers" aria-labelledby="alerts-title">
      <header className="intro">
        <p className="eyebrow">MONITORING</p>
        <h1 id="alerts-title">Job alerts</h1>
        <p>
          Rolevo checks your saved public career pages once a day and lists new
          or changed postings here. Discovered jobs are never counted as
          applications.
        </p>
      </header>

      {error ? (
        <p className="error-line" role="alert">
          {error}
        </p>
      ) : null}
      <p className="status-line" aria-live="polite">
        {status}
      </p>

      <section className="notice-card" aria-labelledby="sources-title">
        <h2 id="sources-title">Monitored sources</h2>
        <form
          className="providers"
          onSubmit={(event) => {
            event.preventDefault();
            void addSource();
          }}
        >
          <label className="field">
            <span>Public career page URL (https only)</span>
            <input
              className="control"
              type="url"
              required
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://company.example.com/careers"
            />
          </label>
          <label className="field">
            <span>Your timezone (checks run daily at 09:00)</span>
            <select
              className="control"
              value={timezone}
              onChange={(event) => setTimezone(event.target.value)}
            >
              {TIMEZONES.map((zone) => (
                <option key={zone} value={zone}>
                  {zone}
                </option>
              ))}
            </select>
          </label>
          <label className="checkline">
            <input
              type="checkbox"
              checked={consent}
              onChange={(event) => setConsent(event.target.checked)}
            />
            <span>
              I consent to a daily automated check of this public page at 09:00
              in my timezone.
            </span>
          </label>
          <label className="checkline">
            <input
              type="checkbox"
              checked={keyConsent}
              disabled={!consent}
              onChange={(event) => setKeyConsent(event.target.checked)}
            />
            <span>
              I consent to my saved provider key being used for background
              matching.
            </span>
          </label>
          <button
            className="primary-action"
            type="submit"
            disabled={busy || !url}
          >
            Add source
          </button>
        </form>

        {sources.length === 0 ? (
          <p className="data-notice">
            No sources yet — add up to five public pages.
          </p>
        ) : (
          <ul className="provider-grid">
            {sources.map((source) => (
              <li className="key-card" key={source.id}>
                <div className="key-card-head">
                  <strong className="masked-key">{source.public_url}</strong>
                  <span className={`badge state-${source.state.toLowerCase()}`}>
                    {SOURCE_STATES[source.state] ?? source.state}
                  </span>
                </div>
                <div className="key-purposes">
                  {source.setup_required ? (
                    <span className="status-badge">Setup required</span>
                  ) : null}
                  <span>
                    {source.schedule === "DAILY" ? "Daily 09:00" : "Manual"} ·{" "}
                    {source.timezone}
                  </span>
                  {source.next_run_at ? (
                    <span>
                      Next check {new Date(source.next_run_at).toLocaleString()}
                    </span>
                  ) : null}
                  {source.last_success_at ? (
                    <span>
                      Last success{" "}
                      {new Date(source.last_success_at).toLocaleString()}
                    </span>
                  ) : null}
                  {source.last_error ? (
                    <span className="error-line">
                      Last error: {source.last_error}
                    </span>
                  ) : null}
                </div>
                <div className="button-row">
                  <button
                    className="preview-pill"
                    type="button"
                    disabled={busy}
                    onClick={() => void checkNow(source)}
                  >
                    Check now
                  </button>
                  {source.state === "ACTIVE" ? (
                    <button
                      className="preview-pill"
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        void patchSource(source, { action: "pause" })
                      }
                    >
                      Pause
                    </button>
                  ) : (
                    <button
                      className="preview-pill"
                      type="button"
                      disabled={busy || source.setup_required}
                      onClick={() =>
                        void patchSource(source, { action: "resume" })
                      }
                    >
                      Resume
                    </button>
                  )}
                  {source.setup_required ? (
                    <button
                      className="preview-pill"
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        void patchSource(source, {
                          scheduled_check_consent: true,
                        })
                      }
                    >
                      Consent to daily checks
                    </button>
                  ) : null}
                  <button
                    className="text-link danger-action"
                    type="button"
                    onClick={() => void removeSource(source)}
                  >
                    Remove
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="notice-card" aria-labelledby="jobs-title">
        <h2 id="jobs-title">Discovered jobs</h2>
        {jobs.length === 0 ? (
          <p className="data-notice">
            Nothing discovered yet. Jobs appear after a successful check.
          </p>
        ) : (
          <ul className="provider-grid">
            {jobs.map((job) => (
              <li className="key-card" key={job.id}>
                <div className="key-card-head">
                  <strong className="masked-key">{job.title}</strong>
                  <span className={`badge state-${job.status.toLowerCase()}`}>
                    {job.status}
                  </span>
                </div>
                <div className="key-purposes">
                  {job.employer ? <span>{job.employer}</span> : null}
                  {job.location ? <span>{job.location}</span> : null}
                  {job.is_remote ? <span>Remote</span> : null}
                  {job.match_reason ? <span>{job.match_reason}</span> : null}
                </div>
                <div className="button-row">
                  {job.canonical_job_url ? (
                    <a
                      className="preview-pill"
                      href={job.canonical_job_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      View posting
                    </a>
                  ) : null}
                  {job.status !== "SAVED" && job.status !== "CLOSED" ? (
                    <button
                      className="preview-pill"
                      type="button"
                      onClick={() => void jobAction(job, "save")}
                    >
                      Save
                    </button>
                  ) : null}
                  {job.status !== "DISMISSED" && job.status !== "CLOSED" ? (
                    <button
                      className="preview-pill"
                      type="button"
                      onClick={() => void jobAction(job, "dismiss")}
                    >
                      Dismiss
                    </button>
                  ) : null}
                  {job.status === "CLOSED" ? (
                    <button
                      className="preview-pill"
                      type="button"
                      onClick={() => void jobAction(job, "reopen")}
                    >
                      Reopen
                    </button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="notice-card" aria-labelledby="notes-title">
        <div className="key-card-head">
          <h2 id="notes-title">
            Notifications{unread > 0 ? ` (${unread} unread)` : ""}
          </h2>
          {unread > 0 ? (
            <button
              className="preview-pill"
              type="button"
              onClick={() => void markAllRead()}
            >
              Mark all read
            </button>
          ) : null}
        </div>
        {notifications.length === 0 ? (
          <p className="data-notice">No notifications yet.</p>
        ) : (
          <ul className="provider-grid">
            {notifications.map((note) => (
              <li
                className={`card${note.read_at ? "" : " unread"}`}
                key={note.id}
              >
                <div className="key-card-head">
                  <span>{note.content}</span>
                  {note.read_at ? null : (
                    <button
                      className="preview-pill"
                      type="button"
                      onClick={() => void markRead(note)}
                    >
                      Mark read
                    </button>
                  )}
                </div>
                <div className="key-purposes">
                  <span>{note.kind}</span>
                  <span>{new Date(note.created_at).toLocaleString()}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="notice-card" aria-labelledby="runs-title">
        <h2 id="runs-title">Recent checks</h2>
        {runs.length === 0 ? (
          <p className="data-notice">No checks have run yet.</p>
        ) : (
          <ul className="provider-grid">
            {runs.map((run) => (
              <li className="key-card" key={run.id}>
                <div className="key-card-head">
                  <span>
                    {run.run_kind === "DAILY"
                      ? "Scheduled check"
                      : "Manual check"}
                  </span>
                  <span className={`badge state-${run.state.toLowerCase()}`}>
                    {run.state}
                    {run.completeness === "PARTIAL" ? " (partial)" : ""}
                  </span>
                </div>
                <div className="key-purposes">
                  <span>{run.discovered_count} new or updated</span>
                  {run.started_at ? (
                    <span>{new Date(run.started_at).toLocaleString()}</span>
                  ) : null}
                  {run.redacted_error ? (
                    <span className="error-line">{run.redacted_error}</span>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}
