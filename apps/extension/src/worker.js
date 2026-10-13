import "./extraction.js";
import "./api-origin.js";

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
  return { ok: true, expires_at: session.expires_at };
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
    }
    return false;
  }
  if (!trustedPanel(sender)) return false;

  if (message?.type === "panel-auth-sign-in") {
    signInExtension().then(respond).catch((error) => respond({ error: error.message }));
    return true;
  }
  if (message?.type === "panel-auth-sign-out") {
    signOutExtension().then(respond).catch(() => respond({ error: "Sign-out failed." }));
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
    case "panel-apply-reviewed-values":
      operation = sendToActivePage({
        type: "rolevo-apply-reviewed-values",
        form_id: message.context_handles?.form_handle,
        context_handles: message.context_handles,
        entries: message.entries,
      }, { requireForm: true });
      break;
    default:
      return false;
  }
  operation.then(respond).catch(() => respond({ error: "unsupported_page", explanation: "The page could not be reached." }));
  return true;
});
