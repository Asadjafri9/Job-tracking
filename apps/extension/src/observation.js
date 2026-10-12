(() => {
  function observeForm(form, report) {
    let disposed = false;
    let lastTrustedIntentAt = 0;
    const submitSelector = 'button[type="submit"], input[type="submit"], button:not([type])';

    const onClick = (event) => {
      if (!event.isTrusted || !form.contains(event.target)) return;
      if (!(event.target instanceof Element) || !event.target.closest(submitSelector)) return;
      lastTrustedIntentAt = Date.now();
      report({ kind: "user_submit_intent", outcome: "unknown", observed_at: new Date().toISOString() });
    };
    const onKeydown = (event) => {
      if (!event.isTrusted || event.key !== "Enter" || !form.contains(event.target)) return;
      if (event.target instanceof Element && event.target.matches("textarea")) return;
      lastTrustedIntentAt = Date.now();
      report({ kind: "user_submit_intent", outcome: "unknown", observed_at: new Date().toISOString() });
    };
    const onInvalid = (event) => {
      if (!event.isTrusted && event.isTrusted !== undefined) return;
      if (!form.contains(event.target)) return;
      report({ kind: "validation_blocked", outcome: "not_submitted", observed_at: new Date().toISOString() });
    };
    const onSubmit = (event) => {
      if (!event.isTrusted) return;
      lastTrustedIntentAt = Date.now();
      report({ kind: "native_submit_observed", outcome: "unknown", observed_at: new Date().toISOString() });
    };
    form.addEventListener("click", onClick, true);
    form.addEventListener("keydown", onKeydown, true);
    form.addEventListener("invalid", onInvalid, true);
    form.addEventListener("submit", onSubmit, true);
    return () => {
      disposed = true;
      form.removeEventListener("click", onClick, true);
      form.removeEventListener("keydown", onKeydown, true);
      form.removeEventListener("invalid", onInvalid, true);
      form.removeEventListener("submit", onSubmit, true);
      return disposed && lastTrustedIntentAt >= 0;
    };
  }

  globalThis.ExtensionObservation = Object.freeze({ observeForm });
})();
