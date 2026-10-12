import "./extraction.js";

chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

const tabHandles = new Map();
const documentHandles = new Map();

function trustedPanel(sender) {
  return sender.id === chrome.runtime.id && sender.url === chrome.runtime.getURL("panel.html");
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (!tab?.id || !tab.url || !/^https?:\/\//.test(tab.url)) return null;
  return tab;
}

async function sendToActivePage(message, { inject = false, startContext = false, requireForm = false } = {}) {
  const tab = await activeTab();
  if (!tab) return { error: "unsupported_page", explanation: "This browser page cannot be inspected. Open a regular web page." };
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

  let operation;
  switch (message?.type) {
    case "panel-list-forms":
      operation = sendToActivePage({ type: "aster-list-forms" }, { inject: true, startContext: true });
      break;
    case "panel-inspect-form":
      operation = sendToActivePage({ type: "aster-inspect-form", form_id: message.form_id, context_handles: message.context_handles }, { requireForm: true });
      break;
    case "panel-get-selected-job-text":
      operation = sendToActivePage({ type: "aster-get-selected-job-text", context_handles: message.context_handles });
      break;
    case "panel-apply-reviewed-values":
      operation = sendToActivePage({
        type: "aster-apply-reviewed-values",
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
