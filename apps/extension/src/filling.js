(() => {
  const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

  function normalizeProposalEntries(entries) {
    if (!Array.isArray(entries)) return [];
    let totalBytes = 0;
    const normalized = [];
    for (const entry of entries.slice(0, 100)) {
      if (!entry || typeof entry.field_id !== "string" || !UUID_PATTERN.test(entry.field_id)) continue;
      const value = entry.value;
      if (typeof value !== "string" && typeof value !== "boolean" && !Array.isArray(value)) continue;
      if (Array.isArray(value) && (value.length > 30 || value.some((item) => typeof item !== "string" || item.length > 256))) continue;
      if (typeof value === "string" && value.length > 10000) continue;
      totalBytes += new TextEncoder().encode(JSON.stringify({ field_id: entry.field_id, value })).length;
      if (totalBytes > 32768) break;
      normalized.push({ field_id: entry.field_id, value });
    }
    return normalized;
  }

  function nativeValueSetter(element, value) {
    let prototype = Object.getPrototypeOf(element);
    while (prototype) {
      const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
      if (descriptor?.set) {
        descriptor.set.call(element, value);
        return;
      }
      prototype = Object.getPrototypeOf(prototype);
    }
    element.value = value;
  }

  function selectedOptionValues(element, requested) {
    if (!element.multiple && Array.isArray(requested) && requested.length > 1) return null;
    const requestedValues = new Set(Array.isArray(requested) ? requested.map(String) : [String(requested)]);
    const collection = element.options;
    if (collection.length > 30) return null;
    const options = [];
    for (let index = 0; index < collection.length; index += 1) {
      options.push(collection.item ? collection.item(index) : collection[index]);
    }
    if ([...requestedValues].some((value) => !options.some((option) => option.value === value && !option.disabled))) {
      return null;
    }
    return { options, states: options.map((option) => requestedValues.has(option.value)) };
  }

  function setChoiceGroup(elements, requested) {
    const controls = Array.isArray(elements) ? elements : [];
    if (!controls.length || controls.some((element) => !element.isConnected || element.disabled)) {
      return { applied: false, reason: "unavailable" };
    }
    const type = controls[0].type;
    if (controls.some((element) => element.type !== type) || !["radio", "checkbox"].includes(type)) {
      return { applied: false, reason: "unsupported_choice" };
    }
    if (type === "radio" && Array.isArray(requested) && requested.length > 1) {
      return { applied: false, reason: "invalid_selection" };
    }
    const requestedValues = type === "checkbox" && typeof requested === "boolean"
      ? new Set(requested ? controls.map((element) => element.value) : [])
      : new Set(Array.isArray(requested) ? requested.map(String) : [String(requested)]);
    if ([...requestedValues].some((value) => !controls.some((element) => element.value === value))) {
      return { applied: false, reason: "unknown_option" };
    }
    controls.forEach((element) => {
      const next = requestedValues.has(element.value);
      if (element.checked !== next) {
        element.checked = next;
        element.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
        element.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
    return { applied: true };
  }

  function unchangedSinceSnapshot(current, initial, manuallyEdited) {
    return !manuallyEdited && JSON.stringify(current) === JSON.stringify(initial);
  }

  function canApplyReviewedValue(current, expectedExtensionState, manuallyEdited) {
    return !manuallyEdited && JSON.stringify(current) === JSON.stringify(expectedExtensionState);
  }

  function isTrustedManualEvent(event) {
    return event?.isTrusted === true;
  }

  function valueMatches(requested, actual, type) {
    if (type === "radio") {
      const expected = Array.isArray(requested) ? requested.map(String) : requested === "" ? [] : [String(requested)];
      return JSON.stringify(expected.sort()) === JSON.stringify([...actual].map(String).sort());
    }
    if (type === "checkbox" && typeof requested === "boolean") return (actual.length > 0) === requested;
    if (type === "checkbox") {
      const expected = Array.isArray(requested) ? requested.map(String) : [String(requested)];
      return JSON.stringify(expected.sort()) === JSON.stringify([...actual].map(String).sort());
    }
    if (Array.isArray(requested)) return JSON.stringify([...requested].sort()) === JSON.stringify([...actual].sort());
    return String(requested) === String(actual);
  }

  function setNativeValue(element, value) {
    if (!element || !element.isConnected || element.disabled || element.readOnly) {
      return { applied: false, reason: "unavailable" };
    }
    if (element.type === "checkbox" || element.type === "radio") {
      const checked = Boolean(value);
      if (element.type === "radio" && !checked) return { applied: true, value: false };
      element.checked = checked;
    } else if (element.tagName === "SELECT") {
      if (!element.multiple && Array.isArray(value) && value.length > 1) {
        return { applied: false, reason: "invalid_selection" };
      }
      const selection = selectedOptionValues(element, value);
      if (!selection) return { applied: false, reason: "unknown_option" };
      selection.options.forEach((option, index) => { option.selected = selection.states[index]; });
    } else {
      const stringValue = String(value);
      const maxLength = Number(element.maxLength);
      if (Number.isFinite(maxLength) && maxLength >= 0 && stringValue.length > maxLength) {
        return { applied: false, reason: "value_too_long" };
      }
      nativeValueSetter(element, stringValue);
    }
    element.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    return { applied: true };
  }

  function validateWithoutSubmitting(element) {
    if (typeof element.checkValidity !== "function") return { valid: null, message: null };
    const valid = element.checkValidity();
    return { valid, message: valid ? null : String(element.validationMessage || "Check this field.").slice(0, 200) };
  }

  globalThis.ExtensionFilling = Object.freeze({
    normalizeProposalEntries,
    setNativeValue,
    setChoiceGroup,
    validateWithoutSubmitting,
    unchangedSinceSnapshot,
    canApplyReviewedValue,
    isTrustedManualEvent,
    valueMatches,
  });
})();
