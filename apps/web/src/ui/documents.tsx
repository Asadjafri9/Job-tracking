import { useCallback, useEffect, useRef, useState } from "react";

const DOC_TYPES = [
  { value: "RESUME", label: "Resume" },
  { value: "LINKEDIN_PDF", label: "LinkedIn PDF" },
  { value: "COVER_LETTER", label: "Cover letter" },
  { value: "SUPPORTING_DOCUMENT", label: "Supporting document" },
  { value: "OTHER", label: "Other" },
] as const;

interface DocSummary {
  id: string;
  document_type: string;
  file_name: string;
  size_bytes: number;
  original_state: string;
  parse_state: string;
  is_default: boolean;
}

interface Candidate {
  index: number;
  fact_key: string;
  value_type: string;
  value: unknown;
  section_id: number;
  anchor: { page?: number | null };
  decision: string | null;
}

interface Extraction {
  id: string;
  review_state: string;
  extracted_text: string | null;
  candidates: Candidate[];
  redacted_error: string | null;
}

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KiB`;
}

export function DocumentsPage({
  csrf,
  signedIn,
}: {
  csrf: string;
  signedIn: boolean;
}) {
  const [documents, setDocuments] = useState<DocSummary[]>([]);
  const [extractions, setExtractions] = useState<Record<string, Extraction[]>>(
    {},
  );
  const [docType, setDocType] = useState<string>("RESUME");
  const fileInput = useRef<HTMLInputElement>(null);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoadState("loading");
    try {
      const response = await fetch("/api/v1/documents", {
        credentials: "include",
      });
      if (!response.ok) throw new Error("load failed");
      const body = (await response.json()) as { documents: DocSummary[] };
      setDocuments(body.documents);
      setLoadState("ready");
    } catch {
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    if (signedIn) void load();
  }, [signedIn, load]);

  async function upload() {
    const file = fileInput.current?.files?.[0];
    if (!file) return;
    setBusy(true);
    setNotice("");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("document_type", docType);
      const response = await fetch("/api/v1/documents", {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": csrf },
        body: form,
      });
      if (!response.ok) {
        const detail = (await response.json().catch(() => null)) as {
          detail?: string;
        } | null;
        throw new Error(detail?.detail ?? "Upload failed.");
      }
      if (fileInput.current) fileInput.current.value = "";
      setNotice("Document uploaded. Parsing has been queued.");
      await load();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function removeDocument(doc: DocSummary) {
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch(`/api/v1/documents/${doc.id}`, {
        method: "DELETE",
        credentials: "include",
        headers: { "X-CSRF-Token": csrf },
      });
      if (!response.ok) throw new Error("The document could not be deleted.");
      setNotice(
        `Deleted ${doc.file_name}. Facts sourced from it are marked for review.`,
      );
      await load();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  async function setDefault(doc: DocSummary) {
    setBusy(true);
    try {
      const response = await fetch(`/api/v1/documents/${doc.id}/default`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ is_default: true }),
      });
      if (!response.ok) throw new Error("Default could not be updated.");
      await load();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  async function loadExtractions(doc: DocSummary) {
    try {
      const response = await fetch(`/api/v1/documents/${doc.id}/extractions`, {
        credentials: "include",
      });
      if (!response.ok) throw new Error("load failed");
      const rows = (await response.json()) as Extraction[];
      setExtractions((current) => ({ ...current, [doc.id]: rows }));
    } catch {
      setNotice("Extraction details could not be loaded.");
    }
  }

  async function analyze(doc: DocSummary, extraction: Extraction) {
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch(
        `/api/v1/documents/${doc.id}/extractions/${extraction.id}/extract`,
        {
          method: "POST",
          credentials: "include",
          headers: { "X-CSRF-Token": csrf },
        },
      );
      if (!response.ok) {
        const detail = (await response.json().catch(() => null)) as {
          detail?: string;
        } | null;
        throw new Error(
          detail?.detail ??
            "Analysis failed. A consented provider route is required.",
        );
      }
      setNotice("Analysis complete. Review each candidate below.");
      await loadExtractions(doc);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Analysis failed");
    } finally {
      setBusy(false);
    }
  }

  async function decide(
    doc: DocSummary,
    extraction: Extraction,
    index: number,
    action: "CONFIRM" | "REJECT",
  ) {
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch(
        `/api/v1/extractions/${extraction.id}/candidates/${index}/decision`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          body: JSON.stringify({ action }),
        },
      );
      if (!response.ok) throw new Error("Decision could not be saved.");
      setNotice(
        action === "CONFIRM"
          ? "Fact confirmed into your profile."
          : "Candidate rejected.",
      );
      await loadExtractions(doc);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Decision failed");
    } finally {
      setBusy(false);
    }
  }

  if (!signedIn) {
    return (
      <section className="placeholder" aria-labelledby="docs-signed-out">
        <p className="eyebrow">DOCUMENTS</p>
        <h1 id="docs-signed-out">Sign in to manage documents</h1>
      </section>
    );
  }

  return (
    <div className="providers" aria-labelledby="documents-title">
      <p className="eyebrow">DOCUMENTS</p>
      <h1 id="documents-title">Resumes and source documents</h1>
      <p className="intro">
        Originals stay private to your workspace. Parsed facts only join your
        profile after you confirm each one.
      </p>

      <p className="form-status" role="status" aria-live="polite">
        {loadState === "loading" ? "Loading documents…" : notice}
      </p>
      {loadState === "error" && (
        <p className="form-status is-error" role="alert">
          Documents could not be loaded. Check your connection and try again.
        </p>
      )}

      <section aria-labelledby="upload-title">
        <h2 id="upload-title">Upload</h2>
        <p className="data-notice">
          PDF or DOCX, up to 5 MiB each — at most ten documents and 50 MiB per
          account.
        </p>
        <div className="upload-row">
          <div className="field">
            <label htmlFor="doc-type">Document type</label>
            <select
              id="doc-type"
              className="control"
              value={docType}
              onChange={(event) => setDocType(event.target.value)}
            >
              {DOC_TYPES.map((entry) => (
                <option value={entry.value} key={entry.value}>
                  {entry.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="doc-file">File</label>
            <input
              id="doc-file"
              className="control"
              type="file"
              accept=".pdf,.docx"
              ref={fileInput}
            />
          </div>
          <button
            className="primary-action"
            type="button"
            disabled={busy}
            onClick={() => void upload()}
          >
            Upload document
          </button>
        </div>
      </section>

      <section aria-labelledby="doc-list-title">
        <h2 id="doc-list-title">Your documents</h2>
        {documents.length === 0 && loadState === "ready" && (
          <p className="data-notice">No documents yet.</p>
        )}
        {documents.map((doc) => (
          <div className="doc-card" key={doc.id}>
            <div className="doc-head">
              <strong>{doc.file_name}</strong>
              <span className="status-badge">{doc.parse_state}</span>
              {doc.is_default && <span className="status-badge">Default</span>}
            </div>
            <p className="key-purposes">
              {doc.document_type.toLowerCase().replace("_", " ")} ·{" "}
              {formatSize(doc.size_bytes)}
            </p>
            <div className="button-row">
              <a
                className="text-link"
                href={`/api/v1/documents/${doc.id}/download`}
              >
                Download
              </a>
              {!doc.is_default && doc.parse_state !== "NOT_STARTED" && (
                <button
                  className="text-link"
                  type="button"
                  disabled={busy}
                  onClick={() => void setDefault(doc)}
                >
                  Make default
                </button>
              )}
              <button
                className="text-link"
                type="button"
                disabled={busy}
                onClick={() => void loadExtractions(doc)}
              >
                Review facts
              </button>
              <button
                className="text-link danger-action"
                type="button"
                disabled={busy}
                onClick={() => void removeDocument(doc)}
              >
                Delete
              </button>
            </div>
            {(extractions[doc.id] ?? []).map((extraction) => (
              <div className="extraction-panel" key={extraction.id}>
                <p className="key-purposes">
                  Extraction · {extraction.review_state}
                  {extraction.redacted_error
                    ? ` · ${extraction.redacted_error}`
                    : ""}
                </p>
                {extraction.candidates.length === 0 &&
                  extraction.review_state === "REVIEW_REQUIRED" && (
                    <>
                      <p className="data-notice">
                        Text was parsed locally. Run analysis with a consented
                        provider to suggest profile facts — nothing is confirmed
                        automatically.
                      </p>
                      <button
                        className="text-link"
                        type="button"
                        disabled={busy}
                        onClick={() => void analyze(doc, extraction)}
                      >
                        Analyze with provider
                      </button>
                    </>
                  )}
                {extraction.candidates.map((candidate) => (
                  <div className="fact-row" key={candidate.index}>
                    <div className="fact-main">
                      <strong>{candidate.fact_key}</strong>
                      <span className="fact-value">
                        {typeof candidate.value === "string"
                          ? candidate.value
                          : JSON.stringify(candidate.value)}
                      </span>
                      <span className="key-purposes">
                        {candidate.anchor.page
                          ? `page ${candidate.anchor.page} · `
                          : ""}
                        {candidate.decision ?? "awaiting review"}
                      </span>
                    </div>
                    {!candidate.decision && (
                      <div className="fact-actions">
                        <button
                          className="text-link"
                          type="button"
                          disabled={busy}
                          onClick={() =>
                            void decide(
                              doc,
                              extraction,
                              candidate.index,
                              "CONFIRM",
                            )
                          }
                        >
                          Confirm
                        </button>
                        <button
                          className="text-link danger-action"
                          type="button"
                          disabled={busy}
                          onClick={() =>
                            void decide(
                              doc,
                              extraction,
                              candidate.index,
                              "REJECT",
                            )
                          }
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </div>
        ))}
      </section>
    </div>
  );
}
