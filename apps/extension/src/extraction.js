(() => {
  const MAX_FORMS = 10;
  const MAX_FIELDS = 100;
  const MAX_OPTIONS = 30;
  const MAX_LABEL = 240;
  const MAX_OPTION_LABEL = 180;
  const MAX_JOB_TEXT = 8000;
  const MAX_PAYLOAD_BYTES = 32768;
  const SENSITIVE = /\b(password|passcode|one.time.code|verification code|social security|ssn|tax id|date of birth|birth date|gender|race|ethnicity|disability|veteran|citizenship|credit card|card number|security code|cvv|iban|bank account|medical|health condition|sexual orientation|religion|political affiliation|national id|legal name|terms and conditions|terms of service|privacy policy|consent to)\b/i;
  const IMMIGRATION = /\b(right to work|work authorization|authorization to work|authorized to work|eligible to work|legally authorized to work|work permit|(?:visa|immigration)\s+(?:status|type|number|authorization|permit|sponsorship)|(?:need|require|have|hold|possess|obtain).{0,35}(?:visa|immigration|work permit)|(?:visa|immigration).{0,35}(?:status|type|number|sponsorship|required|needed|authorized)|(?:need|require)\s+(?:employment\s+)?sponsorship|(?:need|require).{0,25}(?:employer|employment|visa|immigration|work)\s+sponsorship|sponsorship\s+(?:is\s+)?(?:required|needed)|(?:employment|visa|immigration|work)\s+sponsorship|sponsorship.{0,48}(?:visa|immigration|work permit|employment authorization)|(?:visa|immigration|work permit|employment authorization).{0,48}sponsorship)\b/i;
  const ATTESTATION = /\b(i\s+(?:certify|attest|acknowledge|affirm|authorize)|(?:certify|attest|acknowledge|affirm)\s+that|(?:certify|attest|affirm)\b.{0,48}\b(?:application|information|answer|response|statement|true|accurate|complete|correct)|(?:information|answers|responses|application|statement).{0,48}(?:true|accurate|correct|complete)|(?:truthfulness|accuracy|correctness)\s+of\s+(?:the\s+)?(?:information|answers|responses|application)|(?:agree|accept|acknowledge).{0,48}(?:terms|conditions|policies?|privacy|statement|certification|truth|accuracy)|(?:confirm|certify|attest|acknowledge|affirm).{0,48}(?:truth|accuracy|correctness|complete|accurate|true)|(?:accuracy|correctness|truthfulness)\s+(?:of|and)\s+(?:the\s+)?(?:information|answers|responses|application|statements))\b/i;
  const EXCLUDED_TYPES = new Set(["hidden", "password", "file", "submit", "button", "reset", "image"]);
  const ALLOWED_TYPES = new Set(["text", "email", "tel", "url", "number", "date", "textarea", "select", "radio", "checkbox"]);
  const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

  function bounded(value, max) {
    return String(value ?? "").replace(/\s+/g, " ").trim().slice(0, max);
  }

  function isSensitive(label, autocomplete = "") {
    const question = `${label} ${autocomplete}`;
    return SENSITIVE.test(question) || IMMIGRATION.test(question) || ATTESTATION.test(question);
  }

  function snapshotControl({ label, autocomplete = "", relatedQuestions = [], type, element, choiceControls = [], optionLabel = () => "" }) {
    if (!ALLOWED_TYPES.has(type) || EXCLUDED_TYPES.has(type)
      || isSensitive(label, autocomplete) || relatedQuestions.some((question) => isSensitive(question.label, question.autocomplete))) {
      return null;
    }

    const isChoice = type === "radio" || type === "checkbox";
    const readableChoices = isChoice
      ? choiceControls.filter((control) => control.disabled !== true && control.readOnly !== true)
      : [];
    if ((isChoice && !readableChoices.length) || (!isChoice && (element.disabled === true || element.readOnly === true))) return null;

    let options = [];
    let optionsTruncated = false;
    if (type === "select") {
      const source = element.options;
      const count = Math.min(source.length, MAX_OPTIONS);
      optionsTruncated = source.length > MAX_OPTIONS;
      for (let index = 0; index < count; index += 1) {
        const option = source.item ? source.item(index) : source[index];
        if (!option || option.disabled) continue;
        const optionLabel = bounded(option.label || option.textContent, MAX_OPTION_LABEL);
        const value = String(option.value ?? "").slice(0, 256);
        if (optionLabel && value) options.push({ id: `o${index + 1}`, label: optionLabel, value });
      }
    } else if (type === "radio" || type === "checkbox") {
      const controls = readableChoices.slice(0, MAX_OPTIONS);
      optionsTruncated = readableChoices.length > MAX_OPTIONS;
      options = controls.map((control, index) => ({
        id: `o${index + 1}`,
        label: bounded(optionLabel(control), MAX_OPTION_LABEL),
        value: String(control.value ?? "").slice(0, 256),
        disabled: control.disabled === true,
      })).filter((option) => option.label && option.value && !option.disabled)
        .map(({ disabled, ...option }) => option);
    }

    const controls = isChoice ? readableChoices.slice(0, MAX_OPTIONS) : [];
    const initialState = controls.length
      ? controls.filter((control) => control.checked).map((control) => String(control.value))
      : type === "select" && element.multiple
        ? [...element.selectedOptions].map((option) => String(option.value))
        : String(element.value ?? "");
    return {
      initialState,
      choiceElements: controls,
      currentValuePresent: Array.isArray(initialState) ? initialState.length > 0 : initialState.length > 0,
      options,
      optionsTruncated,
    };
  }

  function isOpaqueHandle(value) {
    return typeof value === "string" && UUID_PATTERN.test(value);
  }

  function normalizeContextHandles(value, { requireForm = false } = {}) {
    if (!value || value.schema_version !== 1 || !isOpaqueHandle(value.tab_handle) || !isOpaqueHandle(value.document_handle)
      || (requireForm && !isOpaqueHandle(value.form_handle))
      || (value.form_handle !== undefined && !isOpaqueHandle(value.form_handle))) return null;
    return {
      schema_version: 1,
      tab_handle: value.tab_handle.toLowerCase(),
      document_handle: value.document_handle.toLowerCase(),
      ...(value.form_handle ? { form_handle: value.form_handle.toLowerCase() } : {}),
    };
  }

  function safePageUrl(value) {
    try {
      const url = new URL(value);
      if (url.protocol !== "http:" && url.protocol !== "https:") return null;
      return `${url.origin}${url.pathname}`.slice(0, 2048);
    } catch {
      return null;
    }
  }

  function normalizeJobContext({ selectedText, pageUrl, pageTitle }) {
    const text = String(selectedText ?? "").slice(0, MAX_JOB_TEXT);
    return {
      schema_version: 1,
      page_url: safePageUrl(pageUrl),
      page_title: bounded(pageTitle, 200),
      selected_text: text,
      selected_text_truncated: String(selectedText ?? "").length > MAX_JOB_TEXT,
    };
  }

  function normalizeField(field) {
    const label = bounded(field.label, MAX_LABEL);
    const type = String(field.type ?? "text").toLowerCase();
    if (!ALLOWED_TYPES.has(type) || EXCLUDED_TYPES.has(type) || !label) return null;
    if (field.visible !== true || field.enabled === false || isSensitive(label, field.autocomplete)) {
      return null;
    }
    const options = Array.isArray(field.options)
      ? field.options
          .slice(0, MAX_OPTIONS)
          .filter((option) => option && option.disabled !== true)
          .map((option, index) => ({
            id: bounded(option.id || `option-${index + 1}`, 64),
            label: bounded(option.label, MAX_OPTION_LABEL),
            value: String(option.value ?? "").slice(0, 256),
          }))
          .filter((option) => option.label && option.value)
      : [];
    return {
      id: bounded(field.id, 64),
      type,
      label,
      required: field.required === true,
      multiple: field.multiple === true,
      max_length: Number.isInteger(field.maxLength) ? Math.min(Math.max(field.maxLength, 0), 10000) : null,
      options,
      options_truncated: field.optionsTruncated === true,
      current_value_present: field.currentValuePresent === true,
    };
  }

  function normalizeSelectedForm({ formId, fields, unsupportedFrames = 0, fieldsTruncated = false }) {
    const accepted = [];
    for (const field of (Array.isArray(fields) ? fields : []).slice(0, MAX_FIELDS * 2)) {
      const normalized = normalizeField(field);
      if (normalized) accepted.push(normalized);
      if (accepted.length >= MAX_FIELDS) break;
    }
    const payload = {
      schema_version: 1,
      form_id: bounded(formId, 64),
      fields: accepted,
      fields_truncated: fieldsTruncated || (Array.isArray(fields) && fields.length > MAX_FIELDS),
      unsupported: { iframes: Math.min(Math.max(Number(unsupportedFrames) || 0, 0), 50), shadow_roots: 0 },
    };
    while (BufferlessSize(payload) > MAX_PAYLOAD_BYTES && payload.fields.length > 0) {
      payload.fields.pop();
      payload.fields_truncated = true;
    }
    return payload;
  }

  function BufferlessSize(value) {
    return new TextEncoder().encode(JSON.stringify(value)).length;
  }

  globalThis.ExtensionExtraction = Object.freeze({
    MAX_FIELDS,
    MAX_OPTIONS,
    MAX_JOB_TEXT,
    MAX_PAYLOAD_BYTES,
    normalizeField,
    normalizeJobContext,
    normalizeContextHandles,
    normalizeSelectedForm,
    snapshotControl,
    safePageUrl,
    isOpaqueHandle,
    isSensitive,
  });
})();
