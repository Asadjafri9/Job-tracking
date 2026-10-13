import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createManifest, exactApiOrigin, extensionId, parseArgs } from "../scripts/build.mjs";
import { fixtureCorpus } from "./fixtures/corpus.mjs";

await import("../src/extraction.js");
await import("../src/filling.js");
await import("../src/observation.js");
await import("../src/api-origin.js");
const Extraction = globalThis.ExtensionExtraction;
const Filling = globalThis.ExtensionFilling;
const Observation = globalThis.ExtensionObservation;
const ApiOrigin = globalThis.ExtensionApiOrigin;

test("API origin is extracted from development and production host permissions", () => {
  assert.equal(ApiOrigin.fromHostPermissions(["http://127.0.0.1:18000/*"]), "http://127.0.0.1:18000");
  assert.equal(ApiOrigin.fromHostPermissions(["https://api.example.test/*"]), "https://api.example.test");
  assert.throws(() => ApiOrigin.fromHostPermissions([]), /no API host permission/);
  assert.throws(() => ApiOrigin.fromHostPermissions(["https://api.example.test/v1/*"]), /origin wildcard/);
});

class FakeControl {
  constructor({ type = "text", value = "", checked = false, maxLength = -1, valid = true } = {}) {
    this.type = type;
    this.tagName = type === "select" ? "SELECT" : "INPUT";
    this._value = value;
    this.checked = checked;
    this.maxLength = maxLength;
    this.valid = valid;
    this.isConnected = true;
    this.disabled = false;
    this.readOnly = false;
    this.events = [];
    this.options = [];
    this.listeners = new Map();
  }
  get value() { return this._value; }
  set value(value) { this._value = String(value); }
  addEventListener(name, listener) { this.listeners.set(name, listener); }
  dispatchEvent(event) { this.events.push(event.type); this.listeners.get(event.type)?.(event); return true; }
  checkValidity() { return this.valid; }
  get validationMessage() { return this.valid ? "" : "This field is required."; }
}

test("development manifest uses a stable ID and only exact required permissions/origin", () => {
  const manifest = createManifest({ apiOrigin: "http://127.0.0.1:18000" });
  assert.deepEqual(manifest.permissions, ["activeTab", "scripting", "storage", "identity", "sidePanel"]);
  assert.deepEqual(manifest.host_permissions, ["http://127.0.0.1:18000/*"]);
  assert.equal(manifest.side_panel.default_path, "panel.html");
  assert.equal(extensionId(manifest.key), "digpnmcecpkodggeieillcjpfgpokgnk");
  assert.equal("content_scripts" in manifest, false);
  assert.equal("tabs" in manifest.permissions, false);
  assert.equal(manifest.permissions.includes("debugger"), false);
  assert.equal(manifest.host_permissions.some((origin) => origin.includes("*://")), false);
});

test("build argument and API origin validation reject broad or insecure targets", () => {
  assert.equal(parseArgs(["--dev"]).has("dev"), true);
  assert.throws(() => parseArgs(["--dev", "--production"]));
  assert.throws(() => exactApiOrigin("http://example.com", { development: true }));
  assert.throws(() => exactApiOrigin("https://api.example.test/v1"));
  assert.equal(exactApiOrigin("https://api.example.test"), "https://api.example.test");
});

test("extraction excludes sensitive and unsupported questions without reading their values", () => {
  for (const label of ["Social Security number", "Citizenship status", "I agree to terms", "Credit card number"])
    assert.equal(Extraction.normalizeField({ id: "field-1", type: "text", label, visible: true }), null);
  for (const type of ["password", "hidden", "file", "submit"])
    assert.equal(Extraction.normalizeField({ id: "field-2", type, label: "Contact", visible: true }), null);
  assert.equal(Extraction.normalizeField({ id: "field-3", type: "text", label: "Name", visible: false }), null);
  const field = Extraction.normalizeField({
    id: "field-4", type: "email", label: "Email address", visible: true, enabled: true,
    currentValuePresent: true, maxLength: 320,
  });
  assert.equal(field.current_value_present, true);
  assert.equal("current_value" in field, false);
});

test("immigration and attestation questions are manual-only without flagging ordinary job questions", () => {
  const manualOnly = [
    "Will you now or in the future require visa sponsorship?",
    "Will you require employer sponsorship now or in the future?",
    "Will you need immigration sponsorship?",
    "Will you require work sponsorship?",
    "Are you legally authorized to work in this country?",
    "Do you have a work permit or immigration status for this role?",
    "I certify that all information in this application is true and complete.",
    "I acknowledge that my answers are accurate.",
    "Please confirm the accuracy of the information supplied.",
    "Do you agree to comply with company policies?",
  ];
  for (const label of manualOnly) assert.equal(Extraction.isSensitive(label), true, label);

  const ordinary = [
    "Describe your sponsorship experience with customer events.",
    "How do you improve accuracy in machine-learning models?",
    "Would you agree to work hybrid hours?",
    "Describe your experience with visa processing software.",
  ];
  for (const label of ordinary) assert.equal(Extraction.isSensitive(label), false, label);
});

test("sensitive snapshots return before value/options getters, including grouped questions", () => {
  let sensitiveValueReads = 0;
  let sensitiveOptionReads = 0;
  const sensitiveSelect = {};
  Object.defineProperty(sensitiveSelect, "value", { get() { sensitiveValueReads += 1; throw new Error("sensitive value read"); } });
  Object.defineProperty(sensitiveSelect, "options", { get() { sensitiveOptionReads += 1; throw new Error("sensitive options read"); } });
  assert.equal(Extraction.snapshotControl({ label: "Date of birth", type: "select", element: sensitiveSelect }), null);

  const sensitiveChoice = {};
  for (const property of ["value", "checked"]) {
    Object.defineProperty(sensitiveChoice, property, { get() { sensitiveValueReads += 1; throw new Error(`sensitive ${property} read`); } });
  }
  assert.equal(Extraction.snapshotControl({
    label: "Choose an option",
    type: "radio",
    element: {},
    choiceControls: [sensitiveChoice],
    relatedQuestions: [{ label: "Citizenship status", autocomplete: "" }],
    optionLabel: () => "Yes",
  }), null);
  assert.equal(sensitiveValueReads, 0);
  assert.equal(sensitiveOptionReads, 0);

  const attestationChoice = {};
  for (const property of ["value", "checked"]) {
    Object.defineProperty(attestationChoice, property, { get() { sensitiveValueReads += 1; throw new Error(`attestation ${property} read`); } });
  }
  assert.equal(Extraction.snapshotControl({
    label: "Confirm",
    type: "checkbox",
    element: {},
    choiceControls: [attestationChoice],
    relatedQuestions: [{ label: "I certify that the information above is accurate" }],
    optionLabel: () => "Yes",
  }), null);
  assert.equal(sensitiveValueReads, 0, "group-level attestation is rejected before choice values are read");
});

test("select inspection and filling cap DOM option reads at thirty", () => {
  let reads = 0;
  const collection = {
    length: 100000,
    item(index) {
      reads += 1;
      return { label: `Option ${index}`, value: `v${index}`, disabled: false, selected: false };
    },
  };
  const select = {
    tagName: "SELECT", get options() { return collection; }, value: "v0", isConnected: true,
    disabled: false, readOnly: false,
    dispatchEvent() { return true; },
  };
  const snapshot = Extraction.snapshotControl({ label: "Role", type: "select", element: select });
  assert.equal(reads, 30);
  assert.equal(snapshot.options.length, 30);
  assert.equal(snapshot.optionsTruncated, true);
  reads = 0;
  assert.deepEqual(Filling.setNativeValue(select, "v0"), { applied: false, reason: "unknown_option" });
  assert.equal(reads, 0, "oversize controls are declined before enumerating options");
});

test("multi-select snapshots use the same array shape as observed fill state", () => {
  const select = {
    tagName: "SELECT",
    multiple: true,
    options: [],
    selectedOptions: [{ value: "remote" }, { value: "hybrid" }],
    value: "remote",
    disabled: false,
    readOnly: false,
  };

  const snapshot = Extraction.snapshotControl({ label: "Work style", type: "select", element: select });

  assert.deepEqual(snapshot.initialState, ["remote", "hybrid"]);
});

test("context envelope validates opaque tab, document, and optional form handles", () => {
  const handles = {
    schema_version: 1,
    tab_handle: "123e4567-e89b-42d3-a456-426614174000",
    document_handle: "223e4567-e89b-42d3-a456-426614174000",
    form_handle: "323e4567-e89b-42d3-a456-426614174000",
  };
  assert.deepEqual(Extraction.normalizeContextHandles(handles, { requireForm: true }), handles);
  assert.equal(Extraction.normalizeContextHandles({ ...handles, document_handle: "../../resume.pdf" }), null);
  assert.equal(Extraction.normalizeContextHandles({ ...handles, form_handle: "selector:input[name=email]" }, { requireForm: true }), null);
  assert.equal(Extraction.normalizeContextHandles({ schema_version: 1, tab_handle: handles.tab_handle, document_handle: handles.document_handle }, { requireForm: true }), null,
    "form-scoped operations require an opaque form handle");
});

test("selected form schema is bounded by field, label, option, and serialized byte caps", () => {
  const form = Extraction.normalizeSelectedForm({
    formId: "123e4567-e89b-42d3-a456-426614174000",
    fields: Array.from({ length: 150 }, (_, index) => ({
      id: `field-${index}`, type: "select", label: `Role ${index}`.repeat(40), visible: true,
      options: Array.from({ length: 50 }, (_, option) => ({ id: `o${option}`, label: `Choice ${option}`, value: `v${option}` })),
    })),
  });
  assert.equal(form.schema_version, 1);
  assert.ok(form.fields.length <= 100);
  assert.ok(form.fields.every((field) => field.label.length <= 240 && field.options.length <= 30));
  assert.ok(new TextEncoder().encode(JSON.stringify(form)).length <= 32768);
  assert.equal(form.fields_truncated, true);
});

test("synthetic compatibility corpus covers twelve form scenarios and at least one hundred controls", () => {
  const corpus = fixtureCorpus();
  assert.equal(corpus.length, 12);
  assert.equal(corpus.reduce((count, fixture) => count + fixture.controls.length, 0), 108);
  const normalized = corpus.map((fixture) => Extraction.normalizeSelectedForm({
    formId: "123e4567-e89b-42d3-a456-426614174000",
    fields: fixture.controls.map((control) => ({ ...control, autocomplete: "" })),
  }));
  assert.ok(normalized.flatMap((form) => form.fields).every((field) => !Extraction.isSensitive(field.label)));
  assert.ok(normalized.flatMap((form) => form.fields).every((field) => !["password", "hidden", "file"].includes(field.type)));
});

test("job context requires explicit selection, bounds text, and strips URL query/fragment", () => {
  const context = Extraction.normalizeJobContext({
    selectedText: "x".repeat(8500),
    pageTitle: " Senior designer ",
    pageUrl: "https://jobs.example.test/role?id=secret#apply",
  });
  assert.equal(context.selected_text.length, 8000);
  assert.equal(context.selected_text_truncated, true);
  assert.equal(context.page_url, "https://jobs.example.test/role");
  assert.equal(context.page_title, "Senior designer");
});

test("fill proposals require opaque UUID field handles and bounded reviewed values", () => {
  const valid = "123e4567-e89b-42d3-a456-426614174000";
  const accepted = Filling.normalizeProposalEntries([
    { field_id: valid, value: "Alex" },
    { field_id: "selector:input[name=email]", value: "bad" },
    { field_id: valid, value: "x".repeat(10001) },
    { field_id: valid, value: ["ok", 3] },
  ]);
  assert.deepEqual(accepted, [{ field_id: valid, value: "Alex" }]);
});

test("manual edits are preserved, native setters emit input/change, and validation failure is reported", () => {
  assert.equal(Filling.unchangedSinceSnapshot("edited", "original", true), false);
  assert.equal(Filling.unchangedSinceSnapshot("original", "original", false), true);
  const input = new FakeControl({ maxLength: 10, valid: false });
  assert.deepEqual(Filling.setNativeValue(input, "Alex"), { applied: true });
  assert.equal(input.value, "Alex");
  assert.deepEqual(input.events, ["input", "change"]);
  assert.deepEqual(Filling.validateWithoutSubmitting(input), { valid: false, message: "This field is required." });
  assert.deepEqual(Filling.setNativeValue(input, "value is too long"), { applied: false, reason: "value_too_long" });
});

test("a second reviewed fill may replace extension-owned state, but trusted manual edits win", () => {
  let lastExtensionState = "initial";
  let manuallyEdited = false;
  assert.equal(Filling.canApplyReviewedValue("initial", lastExtensionState, manuallyEdited), true);
  assert.deepEqual(Filling.setNativeValue(new FakeControl({ value: "initial" }), "first reviewed value"), { applied: true });
  lastExtensionState = "first reviewed value";
  assert.equal(Filling.canApplyReviewedValue(lastExtensionState, lastExtensionState, manuallyEdited), true);
  assert.equal(Filling.isTrustedManualEvent({ isTrusted: false }), false);
  assert.equal(Filling.isTrustedManualEvent({ isTrusted: true }), true);
  manuallyEdited = Filling.isTrustedManualEvent({ isTrusted: true });
  assert.equal(Filling.canApplyReviewedValue("user's correction", lastExtensionState, manuallyEdited), false);
});

test("select/radio options are exact; unknown option IDs/values remain unchanged", () => {
  const select = new FakeControl({ type: "select" });
  select.options = [{ value: "remote", selected: false, disabled: false }, { value: "hybrid", selected: false, disabled: false }];
  assert.deepEqual(Filling.setNativeValue(select, "remote"), { applied: true });
  assert.equal(select.options[0].selected, true);
  assert.equal(Filling.setNativeValue(select, "onsite").reason, "unknown_option");
  const radioA = new FakeControl({ type: "radio", value: "yes" });
  const radioB = new FakeControl({ type: "radio", value: "no" });
  assert.deepEqual(Filling.setChoiceGroup([radioA, radioB], "yes"), { applied: true });
  assert.equal(radioA.checked, true);
  assert.equal(radioB.checked, false);
  assert.equal(Filling.valueMatches("yes", ["yes"], "radio"), true);
  assert.equal(Filling.setChoiceGroup([radioA, radioB], "unknown").reason, "unknown_option");
  assert.deepEqual(Filling.setChoiceGroup([radioA, radioB], ["yes", "no"]), { applied: false, reason: "invalid_selection" });
  assert.deepEqual([radioA.checked, radioB.checked], [true, false], "invalid radio multi-selection leaves state untouched");
  assert.deepEqual(Filling.setNativeValue(select, ["remote", "hybrid"]), { applied: false, reason: "invalid_selection" });
  assert.deepEqual(select.options.map((option) => option.selected), [true, false], "invalid single-select multi-selection leaves state untouched");
});

test("checkbox groups and React-style controlled values classify acceptance versus revert", () => {
  const a = new FakeControl({ type: "checkbox", value: "remote" });
  const b = new FakeControl({ type: "checkbox", value: "hybrid" });
  assert.deepEqual(Filling.setChoiceGroup([a, b], ["remote"]), { applied: true });
  assert.deepEqual([a.checked, b.checked], [true, false]);
  assert.equal(Filling.valueMatches(["remote"], ["remote"], "checkbox"), true);
  assert.equal(Filling.valueMatches(["remote"], ["hybrid"], "checkbox"), false);
  class ReactLikeControl extends FakeControl {
    dispatchEvent(event) {
      super.dispatchEvent(event);
      if (event.type === "input" && this.rejectInput) this._value = "";
      return true;
    }
  }
  const controlled = new ReactLikeControl({});
  controlled.rejectInput = true;
  Filling.setNativeValue(controlled, "draft");
  assert.equal(controlled.value, "");
  assert.equal(Filling.valueMatches("draft", controlled.value, "text"), false);
});

test("passive observer reports unknown/validation states without preventing or submitting", () => {
  const listeners = new Map();
  const form = {
    addEventListener: (name, listener) => listeners.set(name, listener),
    removeEventListener: (name) => listeners.delete(name),
    contains: () => true,
  };
  const reports = [];
  const dispose = Observation.observeForm(form, (event) => reports.push(event));
  let preventDefaultCalled = false;
  let nativeSubmitCalls = 0;
  listeners.get("submit")({ isTrusted: true, preventDefault: () => { preventDefaultCalled = true; } });
  listeners.get("invalid")({ isTrusted: true, target: {} });
  assert.deepEqual(reports.map((event) => event.outcome), ["unknown", "not_submitted"]);
  assert.equal(preventDefaultCalled, false);
  assert.equal(nativeSubmitCalls, 0);
  dispose();
  assert.equal(listeners.size, 0);
});

test("extension UI includes keyboard/live status and explicit unsupported/manual states", async () => {
  const panel = await readFile(new URL("../src/panel.html", import.meta.url), "utf8");
  const scripts = await readFile(new URL("../src/panel.js", import.meta.url), "utf8");
  assert.match(panel, /aria-live="polite"/);
  assert.match(panel, /role="status"/);
  assert.match(panel, /You submit, always/);
  assert.match(panel, /id="sign-in"/);
  assert.match(scripts, /No submission was made/);
  for (const source of ["content.js", "worker.js", "panel.js", "filling.js"])
    assert.doesNotMatch(await readFile(new URL(`../src/${source}`, import.meta.url), "utf8"), /\.requestSubmit\s*\(|\.submit\s*\(/);
  const content = await readFile(new URL("../src/content.js", import.meta.url), "utf8");
  const worker = await readFile(new URL("../src/worker.js", import.meta.url), "utf8");
  const inspect = content.slice(content.indexOf("function inspectForm"), content.indexOf("async function applyReviewedValues"));
  assert.match(inspect, /snapshotControl\(/);
  assert.doesNotMatch(inspect, /(?:element|candidate|option)\.(?:value|options)\b/);
  assert.match(content, /MAX_FORM_SCAN_NODES\s*=\s*4000/);
  assert.match(content, /sender\.url !== chrome\.runtime\.getURL\("worker\.js"\)/);
  assert.match(worker, /sender\.url === chrome\.runtime\.getURL\("panel\.html"\)/);
  assert.match(worker, /contextHandles\.tab_handle !== tabHandle/);
  assert.match(worker, /chrome\.identity\.launchWebAuthFlow/);
  assert.match(worker, /chrome\.storage\.session\.set\(\{ authSession: session \}\)/);
  assert.match(worker, /if \(!response\.ok && response\.status !== 401\)/);
  assert.match(scripts, /if \(result\.error\) \{[\s\S]*?return;/);
});
