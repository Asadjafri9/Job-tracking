const sample = [
  ["demo-name", "Alex Morgan"],
  ["demo-email", "alex@example.test"],
  ["demo-role", "designer"],
  ["demo-terms", "remote"],
];

document.getElementById("apply-sample").addEventListener("click", () => {
  const outcomes = sample.map(([id, value]) => {
    const element = document.getElementById(id);
    const result = globalThis.ExtensionFilling.setNativeValue(element, value);
    return result.applied && globalThis.ExtensionFilling.validateWithoutSubmitting(element).valid !== false;
  });
  const invalid = sample.map(([id]) => globalThis.ExtensionFilling.validateWithoutSubmitting(document.getElementById(id)).valid === false).filter(Boolean).length;
  document.getElementById("demo-result").textContent = `${outcomes.filter(Boolean).length} sample values applied. ${invalid} fields need correction. No submission was made.`;
});
