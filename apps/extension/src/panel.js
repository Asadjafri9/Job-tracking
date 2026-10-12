const byId = (id) => document.getElementById(id);
const statusEl = byId("status");
const formPicker = byId("form-picker");
const formWrap = byId("form-picker-wrap");
const inspectButton = byId("inspect");
const inspectFormButton = byId("inspect-form");
const fillButton = byId("fill");
const fieldsRoot = byId("fields");
const unsupportedEl = byId("unsupported");
const suggestions = new Map();
let selectedForm = null;
let pageContextHandles = null;
let selectedFormHandles = null;

function setStatus(message) { statusEl.textContent = message; }
function make(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function request(message) {
  try { return await chrome.runtime.sendMessage(message); }
  catch { return { error: "unsupported_page", explanation: "The extension could not contact the current page." }; }
}

function announceUnsupported(result) {
  if (!result?.error) { unsupportedEl.classList.add("hidden"); unsupportedEl.textContent = ""; return; }
  unsupportedEl.classList.remove("hidden");
  unsupportedEl.textContent = result.explanation || "This page is not supported.";
  setStatus("This page needs a manual step.");
}

inspectButton.addEventListener("click", async () => {
  inspectButton.disabled = true;
  setStatus("Looking for visible forms on this page…");
  const result = await request({ type: "panel-list-forms" });
  inspectButton.disabled = false;
  announceUnsupported(result);
  if (result?.error) return;
  pageContextHandles = result.context_handles;
  selectedFormHandles = null;
  selectedForm = null;
  formPicker.replaceChildren(new Option("Choose a visible form", ""));
  for (const form of result.forms || []) {
    const option = new Option(`${form.label} · ${form.field_count} controls`, form.id);
    formPicker.add(option);
  }
  formWrap.classList.toggle("hidden", !result.forms?.length);
  byId("page-state").textContent = result.forms?.length ? `${result.forms.length} found` : "No form found";
  if (!result.forms?.length) {
    setStatus(result.explanation || "No visible top-level form was found.");
    unsupportedEl.classList.remove("hidden");
    unsupportedEl.textContent = "Try a page with a visible form. Iframes and custom widgets are not inspected.";
  } else {
    unsupportedEl.classList.remove("hidden");
    unsupportedEl.textContent = "Only the form you select will be inspected. Iframes and custom widgets are not inspected.";
    setStatus("Choose the form you want to review.");
  }
});

formPicker.addEventListener("change", () => { inspectFormButton.disabled = !formPicker.value; });

inspectFormButton.addEventListener("click", async () => {
  const result = await request({
    type: "panel-inspect-form",
    form_id: formPicker.value,
    context_handles: { ...pageContextHandles, form_handle: formPicker.value },
  });
  announceUnsupported(result);
  if (result?.error) return;
  selectedForm = result.form;
  selectedFormHandles = result.context_handles;
  suggestions.clear();
  renderFields(result.form);
  fillButton.classList.toggle("hidden", result.form.fields.length === 0);
  fillButton.disabled = result.form.fields.length === 0;
  byId("page-state").textContent = `${result.form.fields.length} safe fields`;
  setStatus(result.form.fields.length ? "Review the fields and enter the values you want filled." : "No supported fields found. Nothing was changed.");
});

function renderFields(form) {
  fieldsRoot.replaceChildren();
  if (!form.fields.length) {
    fieldsRoot.append(make("p", "muted", "No supported fields were found. Sensitive and unsupported questions remain untouched."));
    return;
  }
  for (const field of form.fields) {
    const card = make("div", "field-card");
    const label = make("p", "field-label", `${field.label}${field.required ? " · required" : ""}`);
    const controlId = `value-${field.id}`;
    let control;
    if (["select", "radio"].includes(field.type) && field.options.length) {
      control = document.createElement("select");
      control.add(new Option("Choose a reviewed answer", ""));
      for (const option of field.options) control.add(new Option(option.label, option.value));
    } else if (field.type === "checkbox" && field.multiple && field.options.length) {
      control = document.createElement("select");
      control.multiple = true;
      control.setAttribute("aria-label", `Reviewed choices for ${field.label}`);
      for (const option of field.options) control.add(new Option(option.label, option.value));
    } else if (field.type === "checkbox" && field.options.length === 1) {
      control = document.createElement("input");
      control.type = "checkbox";
    } else if (["text", "email", "tel", "url", "number", "date", "textarea"].includes(field.type)) {
      control = document.createElement(field.type === "textarea" ? "textarea" : "input");
      if (control.tagName === "INPUT") control.type = field.type;
      control.placeholder = "Enter a reviewed value";
      if (field.max_length && control.tagName === "INPUT") control.maxLength = field.max_length;
    } else {
      card.append(label, make("p", "field-meta", "This control needs a manual answer in this prototype."));
      fieldsRoot.append(card);
      return;
    }
    control.id = controlId;
    control.setAttribute("aria-label", `Reviewed value for ${field.label}`);
    const updateSuggestion = () => {
      const value = control.type === "checkbox"
        ? control.checked
        : control.multiple
          ? [...control.selectedOptions].map((option) => option.value)
          : control.value;
      const isEmpty = value === "" || (Array.isArray(value) && value.length === 0);
      if (isEmpty) suggestions.delete(field.id);
      else suggestions.set(field.id, value);
      fillButton.disabled = suggestions.size === 0;
    };
    control.addEventListener("input", updateSuggestion);
    control.addEventListener("change", updateSuggestion);
    card.append(label, control);
    if (field.current_value_present) card.append(make("p", "field-meta", "This field already has a value. It will be preserved if edited."));
    fieldsRoot.append(card);
  }
}

fillButton.addEventListener("click", async () => {
  if (!selectedForm || !suggestions.size) return;
  fillButton.disabled = true;
  setStatus("Applying only the values you entered…");
  const entries = [...suggestions].map(([field_id, value]) => ({ field_id, value }));
  const result = await request({
    type: "panel-apply-reviewed-values",
    form_id: selectedFormHandles?.form_handle,
    entries,
    context_handles: selectedFormHandles,
  });
  if (result?.error) { announceUnsupported(result); return; }
  const counts = { filled: 0, skipped: 0, invalid: 0, unknown: 0 };
  for (const item of result.results || []) {
    if (item.status === "filled") counts.filled += 1;
    else if (item.status === "filled_invalid") counts.invalid += 1;
    else if (item.status === "unknown") counts.unknown += 1;
    else counts.skipped += 1;
  }
  fillButton.disabled = false;
  setStatus(`${counts.filled} filled · ${counts.invalid} need correction · ${counts.skipped} left unchanged · ${counts.unknown} need review. No submission was made.`);
});

byId("capture-job").addEventListener("click", async () => {
  const result = await request({ type: "panel-get-selected-job-text", context_handles: pageContextHandles });
  announceUnsupported(result);
  if (result?.error) return;
  const context = result.context;
  byId("job-summary").textContent = `${context.page_title || "Selected page"}: ${context.selected_text.slice(0, 280)}${context.selected_text.length > 280 ? "…" : ""}`;
  setStatus("Selected job text is held in this page only.");
});

byId("demo").addEventListener("click", () => chrome.tabs.create({ url: chrome.runtime.getURL("demo.html") }));

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type !== "panel-submit-observation") return;
  const observation = message.observation;
  byId("observation").textContent = observation.kind === "validation_blocked"
    ? "The page reported a validation block. No submission was recorded."
    : "A user action was observed. The outcome is unknown until you confirm it.";
});

byId("version").textContent = `v${chrome.runtime.getManifest().version}`;
