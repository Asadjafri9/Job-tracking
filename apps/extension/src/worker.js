import "./extraction.js";
import "./api-origin.js";
import "./outbox.js";

// Bind the side panel to the tab whose toolbar action the user clicked. Looking
// up the "active" tab later from a side panel can return a different tab (or a
// tab without activeTab access), so keep the user-activated tab explicitly.
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false });

const tabHandles = new Map();
const documentHandles = new Map();
let activatedTabId = null;
let activatedWindowId = null;

chrome.action.onClicked.addListener((tab) => {
  if (!Number.isInteger(tab?.id)) return;
  activatedTabId = tab.id;
  activatedWindowId = Number.isInteger(tab.windowId) ? tab.windowId : null;
  chrome.storage.session.set({ activatedTabId, activatedWindowId }).catch(() => {});
  // Call open directly in the user-gesture handler; Chrome requires this.
  chrome.sidePanel.open({ tabId: tab.id }).catch(() => {});
});

function trustedPanel(sender) {
  return sender.id === chrome.runtime.id && sender.url === chrome.runtime.getURL("panel.html");
}

async function activeTab() {
  if (!Number.isInteger(activatedTabId)) {
    const saved = await chrome.storage.session.get("activatedTabId");
    activatedTabId = saved.activatedTabId ?? null;
    activatedWindowId = saved.activatedWindowId ?? null;
  }
  if (!Number.isInteger(activatedTabId)) {
    return { error: "not_activated", explanation: "Click the Rolevo toolbar icon on the page you want to inspect, then try again." };
  }
  const activeTabs = await chrome.tabs.query({ active: true });
  const currentTab = activeTabs.find((candidate) => candidate.windowId === activatedWindowId);
  if (currentTab?.id !== activatedTabId) {
    return { error: "not_activated", explanation: "The active tab changed. Click the Rolevo toolbar icon on this page, then inspect it." };
  }
  let tab;
  try { tab = await chrome.tabs.get(activatedTabId); }
  catch { return { error: "not_activated", explanation: "That tab is no longer open. Click the Rolevo toolbar icon on the page you want to inspect." }; }
  if (!tab.url || !/^https?:\/\//.test(tab.url)) {
    return { error: "unsupported_page", explanation: "This browser page cannot be inspected. Open a regular web page." };
  }
  return tab;
}

async function sendToActivePage(message, { inject = false, startContext = false, requireForm = false } = {}) {
  const tab = await activeTab();
  if (tab?.error) return tab;
  let tabHandle;
  let contextHandles;
  if (startContext) {
    tabHandle = crypto.randomUUID();
    tabHandles.set(tab.id, tabHandle);
    documentHandles.delete(tab.id);
  } else {
    contextHandles = globalThis.ExtensionExtraction.normalizeContextHandles(message.context_handles, { requireForm });
    tabHandle = tabHandles.get(tab.id);
    if (!contextHandles || !tabHandle || contextHandles.tab_handle !== tabHandle) {
      return { error: "stale_context", explanation: "The active tab changed. Inspect the current page again." };
    }
    if (documentHandles.get(tab.id) && contextHandles.document_handle !== documentHandles.get(tab.id)) {
      return { error: "stale_context", explanation: "This page changed. Inspect the current page again." };
    }
    if (requireForm && message.form_id !== contextHandles.form_handle) {
      return { error: "stale_context", explanation: "The selected form changed. Choose it again." };
    }
  }
  try {
    if (inject) {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ["extraction.js", "filling.js", "observation.js", "content.js"],
      });
    }
    const result = await chrome.tabs.sendMessage(tab.id, startContext
      ? { ...message, tab_handle: tabHandle }
      : { ...message, context_handles: contextHandles });
    const returnedHandles = globalThis.ExtensionExtraction.normalizeContextHandles(result?.context_handles, { requireForm });
    if (!result?.error && (!returnedHandles || returnedHandles.tab_handle !== tabHandle)) {
      return { error: "stale_context", explanation: "The page context could not be verified. Inspect it again." };
    }
    if (returnedHandles) documentHandles.set(tab.id, returnedHandles.document_handle);
    return result;
  } catch {
    return { error: "unsupported_page", explanation: "The page blocks inspection or has navigated. Reopen the panel and try a visible top-level form." };
  }
}

function apiOrigin() {
  return globalThis.ExtensionApiOrigin.fromHostPermissions(
    chrome.runtime.getManifest().host_permissions,
  );
}

async function sha256Hex(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function extensionSession() {
  const { authSession } = await chrome.storage.session.get("authSession");
  if (!authSession?.access_token || Date.parse(authSession.expires_at) <= Date.now()) {
    return null;
  }
  return authSession;
}

async function accountKey() {
  const session = await extensionSession();
  return session ? sha256Hex(session.access_token) : null;
}

const outbox = globalThis.ExtensionOutbox.createOutbox({
  storage: chrome.storage.local,
  send: async (event) => {
    const session = await extensionSession();
    if (!session) throw Object.assign(new Error("signed_out"), { terminal: true });
    const response = await fetch(`${apiOrigin()}/api/v1/submission-events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.access_token}`,
      },
      body: JSON.stringify(event),
    });
    if (!response.ok) {
      // 4xx means the session, window, or shape is wrong; replay cannot fix it.
      const terminal = response.status >= 400 && response.status < 500;
      throw Object.assign(new Error(`api_${response.status}`), { terminal });
    }
  },
});

async function trackingSessionFor(tabId, documentHandle) {
  const { trackingSessions } = await chrome.storage.session.get("trackingSessions");
  const binding = trackingSessions?.[tabId];
  return binding?.document_handle === documentHandle ? binding : null;
}

async function buildSubmissionEvent(observation, contextHandles, sessionId) {
  const kindMap = {
    user_submit_intent: ["SUBMIT_CLICK", "USER_GESTURE"],
    validation_blocked: ["VALIDATION_BLOCKED", "CONTENT_OBSERVER"],
    native_submit_observed: ["SITE_SIGNAL", "CONTENT_OBSERVER"],
  };
  const mapped = kindMap[observation?.kind];
  if (!mapped || typeof observation.observed_at !== "string") return null;
  const keySource = `${observation.kind}:${contextHandles.form_handle}:${observation.observed_at}`;
  const keyDigest = await sha256Hex(keySource);
  return {
    event_idempotency_key: [
      keyDigest.slice(0, 8), keyDigest.slice(8, 12), keyDigest.slice(12, 16),
      keyDigest.slice(16, 20), keyDigest.slice(20, 32),
    ].join("-"),
    application_session_id: sessionId,
    evidence_type: mapped[0],
    evidence_source: mapped[1],
    observed_at: observation.observed_at,
    gesture_ref_hash: await sha256Hex(
      `${observation.kind}:${contextHandles.tab_handle}:${contextHandles.document_handle}:${contextHandles.form_handle}`,
    ),
    ...(observation.kind === "validation_blocked" ? { signal_code: "VALIDATION_BLOCKED" } : {}),
    evidence: { outcome_code: observation.outcome ?? "unknown" },
  };
}

function randomToken(bytes = 32) {
  const value = new Uint8Array(bytes);
  crypto.getRandomValues(value);
  return btoa(String.fromCharCode(...value)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

async function signInExtension() {
  const extensionId = chrome.runtime.id;
  const state = randomToken(32);
  const verifier = randomToken(48);
  const challengeBytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  const challenge = btoa(String.fromCharCode(...new Uint8Array(challengeBytes)))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  await chrome.storage.session.set({ authPending: { state, verifier } });
  const login = new URL(`${apiOrigin()}/auth/login`);
  login.searchParams.set("extension_id", extensionId);
  login.searchParams.set("extension_state", state);
  login.searchParams.set("extension_challenge", challenge);
  const callback = await chrome.identity.launchWebAuthFlow({ url: login.href, interactive: true });
  if (!callback) throw new Error("Sign-in was canceled.");
  const result = new URL(callback);
  const pending = (await chrome.storage.session.get("authPending")).authPending;
  await chrome.storage.session.remove("authPending");
  if (!pending || result.searchParams.get("state") !== pending.state) {
    throw new Error("Sign-in response could not be verified.");
  }
  const grant = result.searchParams.get("grant");
  if (!grant) throw new Error("Sign-in did not return an extension grant.");
  const response = await fetch(`${apiOrigin()}/auth/extension/exchange`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ grant, state: pending.state, code_verifier: pending.verifier }),
  });
  if (!response.ok) throw new Error("Sign-in could not be completed.");
  const session = await response.json();
  await chrome.storage.session.set({ authSession: session });
  const key = await accountKey();
  if (key) await outbox.flush(key);
  return { ok: true, expires_at: session.expires_at };
}

// Service-worker restarts must not lose queued events: flush whatever the
// current account still owns on every cold start.
void accountKey().then((key) => (key ? outbox.flush(key) : null)).catch(() => {});

async function recordObservation(tabId, contextHandles, observation) {
  const binding = await trackingSessionFor(tabId, contextHandles.document_handle);
  if (!binding) return; // passive tracking only exists inside a prepared session
  const event = await buildSubmissionEvent(observation, contextHandles, binding.session_id);
  const key = await accountKey();
  if (!event || !key) return;
  await outbox.enqueue(event, key);
  await outbox.flush(key);
}

async function prepareTracking(message) {
  const session = await extensionSession();
  if (!session) return { error: "signed_out", explanation: "Sign in before tracking this page." };
  const tab = await activeTab();
  if (tab?.error) return tab;
  const tabHandle = tabHandles.get(tab.id);
  const documentHandle = documentHandles.get(tab.id);
  if (!tabHandle || !documentHandle) {
    return { error: "stale_context", explanation: "Inspect the page before tracking it." };
  }
  // Snapshot every currently confirmed AUTOFILL-permitted fact at its exact
  // revision; the server revalidates each ref before binding it.
  const profileResponse = await fetch(`${apiOrigin()}/api/v1/profile`, {
    headers: { Authorization: `Bearer ${session.access_token}` },
  });
  let selectedFactVersions = [];
  if (profileResponse.ok) {
    const profile = await profileResponse.json();
    selectedFactVersions = (profile.facts ?? [])
      .filter(
        (fact) =>
          fact.confirmation_state === "CONFIRMED" &&
          (fact.allowed_purposes ?? []).includes("AUTOFILL"),
      )
      .slice(0, 100)
      .map((fact) => ({ fact_id: fact.id, revision: fact.current_revision }));
  }
  const response = await fetch(`${apiOrigin()}/api/v1/application-sessions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
    },
    body: JSON.stringify({
      employer: String(message.employer ?? "").slice(0, 255),
      role: String(message.role ?? "").slice(0, 255),
      raw_job_url: tab.url,
      job_context: { excerpt: String(message.excerpt ?? "").slice(0, 4000) },
      form_reference: message.form_handle ?? null,
      selected_fact_versions: selectedFactVersions,
    }),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    return { error: "api_error", explanation: detail?.detail ?? "The session could not be prepared." };
  }
  const created = await response.json();
  const { trackingSessions } = await chrome.storage.session.get("trackingSessions");
  await chrome.storage.session.set({
    trackingSessions: {
      ...(trackingSessions ?? {}),
      [tab.id]: {
        session_id: created.id,
        document_handle: documentHandle,
        context_revision: created.context_revision,
        profile_revision: created.profile_revision,
      },
    },
  });
  return { ok: true, session: created };
}

const FIELD_TYPE_MAP = {
  text: "TEXT", url: "TEXT", number: "TEXT", textarea: "TEXTAREA",
  select: "SELECT", radio: "RADIO", checkbox: "CHECKBOX",
  date: "DATE", email: "EMAIL", tel: "TEL",
};
const MAX_DRAFT_QUESTIONS = 10;

async function draftAnswers(message) {
  const session = await extensionSession();
  if (!session) return { error: "signed_out", explanation: "Sign in before drafting answers." };
  const tab = await activeTab();
  if (tab?.error) return tab;
  const binding = await trackingSessionFor(tab.id, documentHandles.get(tab.id));
  if (!binding) {
    return { error: "no_session", explanation: "Prepare a tracked session before drafting answers." };
  }
  const fields = Array.isArray(message.fields) ? message.fields : [];
  const questions = fields
    .filter((field) => FIELD_TYPE_MAP[field.type] && !field.sensitive)
    .slice(0, MAX_DRAFT_QUESTIONS)
    .map((field) => ({
      field_id: String(field.id).slice(0, 128),
      label: String(field.label).slice(0, 512),
      field_type: FIELD_TYPE_MAP[field.type],
      options: (field.options ?? []).slice(0, 100).map((option) => String(option.label)),
      required: field.required === true,
      sensitive: false,
    }));
  if (!questions.length) {
    return { error: "no_questions", explanation: "No ordinary open questions were found to draft." };
  }
  const response = await fetch(
    `${apiOrigin()}/api/v1/application-sessions/${binding.session_id}/draft-answers`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.access_token}`,
      },
      body: JSON.stringify({
        questions,
        expected_profile_revision: binding.profile_revision,
        context_excerpt: String(message.context_excerpt ?? "").slice(0, 10000),
      }),
    },
  );
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    const status = response.status === 409 ? "stale_context" : "api_error";
    return { error: status, explanation: detail?.detail ?? "Answers could not be drafted." };
  }
  const drafted = await response.json();
  if (Number.isInteger(drafted.revision)) {
    const { trackingSessions } = await chrome.storage.session.get("trackingSessions");
    await chrome.storage.session.set({
      trackingSessions: {
        ...(trackingSessions ?? {}),
        [tab.id]: { ...binding, context_revision: drafted.revision },
      },
    });
  }
  return { ok: true, ...drafted };
}

async function reportAppliedAnswers(tabId, entries) {
  const session = await extensionSession();
  const documentHandle = documentHandles.get(tabId);
  const binding = documentHandle ? await trackingSessionFor(tabId, documentHandle) : null;
  if (!session || !binding) return;
  const response = await fetch(
    `${apiOrigin()}/api/v1/application-sessions/${binding.session_id}/applied-answers`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.access_token}`,
      },
      body: JSON.stringify({
        entries: entries.slice(0, 50).map((entry) => ({
          field_id: String(entry.field_id ?? entry.fieldId ?? "").slice(0, 128),
          value: entry.value ?? null,
          status: entry.status ?? "unknown",
          expected_option_ids: Array.isArray(entry.expected_option_ids)
            ? entry.expected_option_ids.slice(0, 100)
            : [],
        })),
        expected_context_revision: binding.context_revision,
      }),
    },
  );
  // A stale revision means the page/context changed; reporting is best-effort
  // and never blocks the user's own fill.
  return response.ok;
}

async function signOutExtension() {
  const { authSession } = await chrome.storage.session.get("authSession");
  if (authSession?.access_token) {
    const response = await fetch(`${apiOrigin()}/auth/extension/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${authSession.access_token}` },
    });
    if (!response.ok && response.status !== 401) {
      throw new Error("Sign-out could not reach the account service. Try again.");
    }
  }
  await chrome.storage.session.remove(["authSession", "authPending"]);
  return { ok: true };
}

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (message?.type === "submit-observation") {
    const contextHandles = globalThis.ExtensionExtraction.normalizeContextHandles(message.context_handles, { requireForm: true });
    if (sender.id === chrome.runtime.id && Number.isInteger(sender.tab?.id)
      && sender.documentId && contextHandles
      && contextHandles.tab_handle === tabHandles.get(sender.tab.id)
      && contextHandles.document_handle === documentHandles.get(sender.tab.id)) {
      chrome.runtime.sendMessage({ type: "panel-submit-observation", observation: message.observation }).catch(() => {});
      void recordObservation(sender.tab.id, contextHandles, message.observation);
    }
    return false;
  }
  if (!trustedPanel(sender)) return false;

  if (message?.type === "panel-auth-sign-in") {
    signInExtension().then(respond).catch((error) => respond({ error: error.message }));
    return true;
  }
  if (message?.type === "panel-auth-sign-out") {
    signOutExtension()
      .then(async (result) => {
        await Promise.all([
          outbox.purge(),
          chrome.storage.session.remove("trackingSessions"),
        ]);
        return result;
      })
      .then(respond)
      .catch(() => respond({ error: "Sign-out failed." }));
    return true;
  }
  if (message?.type === "panel-auth-status") {
    chrome.storage.session.get("authSession").then(({ authSession }) => {
      const valid = authSession?.access_token && Date.parse(authSession.expires_at) > Date.now();
      respond({ signed_in: Boolean(valid), expires_at: valid ? authSession.expires_at : null });
    }).catch(() => respond({ signed_in: false }));
    return true;
  }

  let operation;
  switch (message?.type) {
    case "panel-list-forms":
      operation = sendToActivePage({ type: "rolevo-list-forms" }, { inject: true, startContext: true });
      break;
    case "panel-inspect-form":
      operation = sendToActivePage({ type: "rolevo-inspect-form", form_id: message.form_id, context_handles: message.context_handles }, { requireForm: true });
      break;
    case "panel-get-selected-job-text":
      operation = sendToActivePage({ type: "rolevo-get-selected-job-text", context_handles: message.context_handles });
      break;
    case "panel-prepare-tracking":
      operation = prepareTracking(message);
      break;
    case "panel-draft-answers":
      operation = draftAnswers(message);
      break;
    case "panel-apply-reviewed-values":
      operation = sendToActivePage({
        type: "rolevo-apply-reviewed-values",
        form_id: message.context_handles?.form_handle,
        context_handles: message.context_handles,
        entries: message.entries,
      }, { requireForm: true }).then(async (result) => {
        if (!result?.error && Number.isInteger(activatedTabId)) {
          const statusMap = { unchanged: "skipped", unsupported: "skipped" };
          const reported = (result.results ?? []).map((item) => ({
            field_id: item.field_id,
            value: item.status === "filled" || item.status === "filled_invalid"
              ? (message.entries ?? []).find((entry) => entry.field_id === item.field_id)?.value ?? null
              : null,
            status: statusMap[item.status] ?? item.status,
          }));
          await reportAppliedAnswers(activatedTabId, reported).catch(() => {});
        }
        return result;
      });
      break;
    default:
      return false;
  }
  operation.then(respond).catch(() => respond({ error: "unsupported_page", explanation: "The page could not be reached." }));
  return true;
});
