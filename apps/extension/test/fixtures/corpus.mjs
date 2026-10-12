const scenarios = [
  ["contact", ["Name", "Email address", "Telephone", "Portfolio URL", "Location", "Summary", "Headline", "LinkedIn URL", "Website"]],
  ["preferences", ["Preferred role", "Location", "Remote or hybrid", "Minimum salary", "Travel preference", "Start date", "Work type", "Team size", "Role level"]],
  ["experience", ["Employer", "Job title", "Start month", "End month", "Current role", "Responsibilities", "Project name", "Project link", "Impact summary"]],
  ["education", ["Institution", "Degree", "Field of study", "Start year", "End year", "Currently enrolled", "Coursework", "Credential", "Education summary"]],
  ["profile", ["Professional summary", "Key skill", "Experience years", "Preferred industry", "Work authorization note", "Public profile", "Career interest", "Availability", "Preferred schedule"]],
  ["sensitive", ["Social Security number", "Date of birth", "Gender identity", "Race and ethnicity", "Disability status", "Veteran status", "Citizenship status", "Religion", "Credit card number"]],
  ["controlled", ["Controlled text", "Controlled email", "Controlled select", "Dynamic field", "Replaced field", "Manual edit", "Required answer", "Option group", "Review answer"]],
  ["options", ["Work location", "Employment type", "Role category", "Seniority", "Relocation", "Travel", "Availability", "Work preference", "Office frequency"]],
  ["manual-edit-race", ["Name edited after inspection", "Email edited after inspection", "Role changed after inspection", "New field", "Removed field", "Disabled field", "Read-only field", "Changed option", "Replacement control"]],
  ["validation", ["Required name", "Required email", "Numeric value", "Date value", "Maximum length", "Pattern input", "Invalid select", "Terms question", "Consent question"]],
  ["unrelated-forms", ["Search query", "Login email", "Account password", "Newsletter email", "Application name", "Search button", "Hidden token", "File upload", "Feedback text"]],
  ["unsupported-regions", ["Iframe field", "Shadow widget", "Rich text editor", "CAPTCHA answer", "Offscreen control", "Hidden control", "Disabled control", "Multi-step next", "Custom dropdown"]],
];

export function fixtureCorpus() {
  return scenarios.map(([name, labels], scenarioIndex) => ({
    name,
    visibleTopLevel: !["unsupported-regions"].includes(name),
    controls: labels.map((label, index) => ({
      id: `f${scenarioIndex + 1}-${index + 1}`,
      type: /email/i.test(label) ? "email" : /select|option|location|type|level/i.test(label) ? "select" : /password|hidden|token|upload|button/i.test(label) ? "hidden" : "text",
      label,
      visible: !/offscreen|hidden/i.test(label),
      enabled: !/disabled|read.only/i.test(label),
      options: /select|option|location|type|level/i.test(label)
        ? [{ id: "one", label: "Synthetic option", value: "synthetic" }]
        : [],
      currentValue: "synthetic current value is never exposed",
    })),
  }));
}
