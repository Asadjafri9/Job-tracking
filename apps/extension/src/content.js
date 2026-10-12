(() => {
  if (globalThis.__rolevoContentInstalled) return;
  globalThis.__rolevoContentInstalled = true;
  const { normalizeSelectedForm, snapshotControl } = globalThis.ExtensionExtraction;
  const { normalizeContextHandles, isOpaqueHandle } = globalThis.ExtensionExtraction;
  const forms = new Map();
  const MAX_FORM_SCAN_NODES = 4000;
  const documentHandle = crypto.randomUUID();
  let fieldHandles = new Map();
  let selectedFormId = null;
  let tabHandle = null;
  let stopObserving = null;

  function isVisible(element) {
    if (!(element instanceof Element) || element.closest('[aria-hidden="true"]')) return false;
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity) !== 0 && rect.width > 0 && rect.height > 0;
  }

  function labelFor(element) {
    const labels = [...(element.labels ?? [])].map((label) => label.innerText || label.textContent || "");
    const aria = element.getAttribute("aria-label") || "";
    const labelledBy = (element.getAttribute("aria-labelledby") || "")
      .split(/\s+/).map((id) => document.getElementById(id)?.innerText || "").join(" ");
    const parentLabel = element.closest("label")?.innerText || "";
    const placeholder = element.getAttribute("placeholder") || "";
    const legend = element.closest("fieldset")?.querySelector("legend")?.innerText || "";
    return [...labels, aria, labelledBy, parentLabel, legend, placeholder]
      .map((part) => String(part).replace(/\s+/g, " ").trim()).filter(Boolean).join(" ").slice(0, 240);
  }

  function normalizedType(element) {
    if (element.tagName === "TEXTAREA") return "textarea";
    if (element.tagName === "SELECT") return "select";
    return String(element.type || "text").toLowerCase();
  }

  function formName(form, index) {
    const legend = form.querySelector("legend")?.innerText || "";
    const aria = form.getAttribute("aria-label") || "";
    const heading = form.querySelector("h1,h2,h3")?.innerText || "";
    return (aria || legend || heading || `Form ${index + 1}`).replace(/\s+/g, " ").trim().slice(0, 120);
  }

  function visibleForms(limit) {
    const found = [];
    const collection = document.forms;
    const scanLimit = Math.min(collection.length, 100);
    for (let index = 0; index < scanLimit && found.length < limit; index += 1) {
      if (isVisible(collection[index])) found.push(collection[index]);
    }
    return found;
  }

  function visibleControls(form, limit) {
    const walker = document.createTreeWalker(form, NodeFilter.SHOW_ELEMENT);
    const controls = [];
    let visited = 0;
    let truncated = false;
    while (walker.nextNode()) {
      visited += 1;
      if (visited > MAX_FORM_SCAN_NODES) { truncated = true; break; }
      const element = walker.currentNode;
      if (!element.matches("input,textarea,select") || !isVisible(element)) continue;
      controls.push(element);
      if (controls.length >= limit) { truncated = true; break; }
    }
    return { controls, truncated };
  }

  function listForms(requestedTabHandle) {
    if (!isOpaqueHandle(requestedTabHandle)) return { error: "stale_context", explanation: "Reopen the extension panel and inspect this page again." };
    forms.clear();
    selectedFormId = null;
    fieldHandles = new Map();
    if (stopObserving) stopObserving();
    tabHandle = requestedTabHandle;
    const formsOnPage = visibleForms(10);
    const items = formsOnPage.map((form, index) => {
      const id = crypto.randomUUID();
      forms.set(id, form);
      const { controls, truncated } = visibleControls(form, 100);
      return { id, label: formName(form, index), field_count: controls.length, fields_truncated: truncated };
    });
    return {
      kind: "form_inventory",
      context_handles: { schema_version: 1, tab_handle: tabHandle, document_handle: documentHandle },
      forms: items,
      unsupported: { iframes: Math.min(document.getElementsByTagName("iframe").length, 50), shadow_roots: "not inspected" },
      explanation: items.length ? "Choose one visible form to inspect." : "No visible top-level form was found.",
    };
  }

  function inspectForm(formId, suppliedHandles) {
    const context = normalizeContextHandles(suppliedHandles, { requireForm: true });
    if (!context || context.document_handle !== documentHandle || context.tab_handle !== tabHandle || context.form_handle !== formId) {
      return { error: "stale_context", explanation: "This tab or form changed. Choose the form again." };
    }
    const form = forms.get(formId);
    if (!isOpaqueHandle(formId) || !form || !isVisible(form)) return { error: "form_changed", explanation: "The selected form changed. Inspect it again." };
    selectedFormId = formId;
    fieldHandles = new Map();
    if (stopObserving) stopObserving();
    const raw = [];
    const { controls, truncated: controlsTruncated } = visibleControls(form, 100);
    const grouped = new Set();
    for (const element of controls) {
      if (grouped.has(element)) continue;
      const label = labelFor(element);
      const type = normalizedType(element);
      const allChoiceControls = ["radio", "checkbox"].includes(type) && element.name
        ? controls.filter((candidate) => candidate.type === type && candidate.name === element.name)
        : [element];
      allChoiceControls.forEach((candidate) => grouped.add(candidate));
      const id = crypto.randomUUID();
      const displayLabel = type === "radio" || (type === "checkbox" && allChoiceControls.length > 1)
        ? (element.closest("fieldset")?.querySelector("legend")?.innerText || label || "Choose an option")
        : label;
      const relatedQuestions = allChoiceControls.map((candidate) => ({
        label: labelFor(candidate),
        autocomplete: candidate.getAttribute("autocomplete") || "",
      }));
      const snapshot = snapshotControl({
        label: displayLabel,
        autocomplete: element.getAttribute("autocomplete") || "",
        relatedQuestions,
        type,
        element,
        choiceControls: allChoiceControls,
        optionLabel: labelFor,
      });
      if (!snapshot) continue;
      const field = {
        id,
        type,
        label: displayLabel,
        autocomplete: element.getAttribute("autocomplete") || "",
        required: snapshot.choiceElements.length
          ? snapshot.choiceElements.some((candidate) => candidate.required)
          : element.required === true,
        multiple: type === "checkbox" && snapshot.choiceElements.length > 1,
        maxLength: element.maxLength >= 0 ? element.maxLength : null,
        currentValuePresent: snapshot.currentValuePresent,
        visible: isVisible(element),
        enabled: true,
        optionsTruncated: snapshot.optionsTruncated,
        options: snapshot.options,
      };
      raw.push(field);
      const initialState = snapshot.initialState;
      const fieldElements = type === "checkbox" || type === "radio" ? snapshot.choiceElements : [element];
      fieldHandles.set(id, { elements: fieldElements, initialState, lastExtensionState: null, manuallyEdited: false, type });
      for (const candidate of fieldElements) {
        const markTrustedEdit = (event) => {
          const entry = fieldHandles.get(id);
          if (entry && globalThis.ExtensionFilling.isTrustedManualEvent(event)) entry.manuallyEdited = true;
        };
        candidate.addEventListener("input", markTrustedEdit, { capture: true });
        candidate.addEventListener("change", markTrustedEdit, { capture: true });
      }
    }
    const selected = normalizeSelectedForm({ formId, fields: raw, fieldsTruncated: controlsTruncated, unsupportedFrames: document.getElementsByTagName("iframe").length });
    const contextHandles = { schema_version: 1, tab_handle: tabHandle, document_handle: documentHandle, form_handle: formId };
    stopObserving = globalThis.ExtensionObservation.observeForm(form, (observation) => {
      chrome.runtime.sendMessage({ type: "submit-observation", context_handles: contextHandles, observation }).catch(() => {});
    });
    return { kind: "selected_form", context_handles: contextHandles, form: selected, warnings: selected.fields_truncated ? ["Some fields were omitted to keep inspection bounded."] : [] };
  }

  async function applyReviewedValues(entries, suppliedHandles) {
    const context = normalizeContextHandles(suppliedHandles, { requireForm: true });
    if (!context || context.document_handle !== documentHandle || context.tab_handle !== tabHandle || context.form_handle !== selectedFormId) {
      return { error: "stale_context", results: [] };
    }
    const form = forms.get(selectedFormId);
    if (!form || !isVisible(form)) return { error: "form_changed", results: [] };
    const results = [];
    for (const entry of globalThis.ExtensionFilling.normalizeProposalEntries(entries)) {
      const saved = fieldHandles.get(entry.field_id);
      if (!saved || saved.elements.some((element) => !form.contains(element) || !isVisible(element))) {
        results.push({ field_id: entry.field_id, status: "unsupported", reason: "field_changed" });
        continue;
      }
      const current = ["checkbox", "radio"].includes(saved.type)
        ? saved.elements.filter((element) => element.checked).map((element) => element.value)
        : saved.elements[0].value;
      const expectedState = saved.lastExtensionState ?? saved.initialState;
      if (!globalThis.ExtensionFilling.canApplyReviewedValue(current, expectedState, saved.manuallyEdited)) {
        results.push({ field_id: entry.field_id, status: "unchanged", reason: "manual_edit_preserved" });
        continue;
      }
      const result = ["checkbox", "radio"].includes(saved.type)
        ? globalThis.ExtensionFilling.setChoiceGroup(saved.elements, entry.value)
        : globalThis.ExtensionFilling.setNativeValue(saved.elements[0], entry.value);
      if (!result.applied) {
        results.push({ field_id: entry.field_id, status: "unchanged", reason: result.reason });
        continue;
      }
      await new Promise((resolve) => setTimeout(resolve, 40));
      const after = ["checkbox", "radio"].includes(saved.type)
        ? saved.elements.filter((element) => element.checked).map((element) => element.value)
        : saved.elements[0].tagName === "SELECT" && saved.elements[0].multiple
          ? [...saved.elements[0].selectedOptions].map((option) => option.value)
          : saved.elements[0].value;
      if (!globalThis.ExtensionFilling.valueMatches(entry.value, after, saved.type)) {
        results.push({ field_id: entry.field_id, status: "unknown", reason: "framework_reverted" });
        continue;
      }
      saved.lastExtensionState = after;
      const validity = globalThis.ExtensionFilling.validateWithoutSubmitting(saved.elements[0]);
      results.push({ field_id: entry.field_id, status: validity.valid === false ? "filled_invalid" : "filled", validation: validity });
    }
    return { kind: "fill_results", results, submission_was_attempted: false };
  }

  function selectedJobText(suppliedHandles) {
    const context = normalizeContextHandles(suppliedHandles);
    if (!context || context.document_handle !== documentHandle || context.tab_handle !== tabHandle) {
      return { error: "stale_context", explanation: "This tab changed. Inspect the current page again." };
    }
    const selection = String(globalThis.getSelection?.()?.toString() || "");
    if (!selection.trim()) return { error: "select_text_first", explanation: "Select job text on the page, then try again." };
    return {
      kind: "job_context",
      context_handles: context,
      context: globalThis.ExtensionExtraction.normalizeJobContext({
        selectedText: selection,
        pageUrl: location.href,
        pageTitle: document.title,
      }),
      local_only: true,
    };
  }

  chrome.runtime.onMessage.addListener((message, sender, respond) => {
    if (sender.id !== chrome.runtime.id || sender.url !== chrome.runtime.getURL("worker.js")) return false;
    if (message?.type === "rolevo-list-forms") { respond(listForms(message.tab_handle)); return false; }
    if (message?.type === "rolevo-inspect-form") { respond(inspectForm(message.form_id, message.context_handles)); return false; }
    if (message?.type === "rolevo-get-selected-job-text") { respond(selectedJobText(message.context_handles)); return false; }
    if (message?.type === "rolevo-apply-reviewed-values") {
      applyReviewedValues(message.entries, message.context_handles).then(respond).catch(() => respond({ error: "fill_failed" }));
      return true;
    }
    return false;
  });
})();
