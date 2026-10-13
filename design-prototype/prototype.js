(function () {
  "use strict";

  const routeGroups = {
    home: [
      ["home/empty", "Empty home"], ["home/returning", "Returning home"]
    ],
    profile: [
      ["profile/summary", "Profile summary"], ["profile/documents", "Documents · parse & confirm"], ["profile/providers", "AI providers"]
    ],
    applications: [
      ["applications/list", "Application list"], ["applications/detail", "Application detail"], ["applications/evidence", "Evidence timeline"]
    ],
    email: [
      ["email/draft", "Draft"], ["email/review", "Review message"], ["email/handoff", "Gmail handoff"], ["email/confirm", "Send confirmation"], ["email/sent", "Confirmed by user"]
    ],
    alerts: [
      ["alerts/setup", "Add a public source"], ["alerts/digest", "Morning digest"], ["alerts/partial", "Partial scan"], ["alerts/failure", "Source failed"], ["alerts/paused", "Monitoring paused"]
    ],
    notifications: [
      ["notifications/inbox", "Notification inbox"], ["notifications/empty", "Empty inbox"], ["notifications/error", "Inbox unavailable"], ["notifications/revoked", "Permission revoked"]
    ],
    settings: [["settings/privacy", "Privacy & settings"], ["settings/export", "Review data export"], ["settings/deletion", "Review account deletion"]],
    extension: [
      ["extension/detected", "1 · Detected"], ["extension/analyzing", "2 · Analyzing"], ["extension/suggestions", "3 · Suggestions"], ["extension/manual", "4 · Needs your answer"], ["extension/filled", "5 · Fill results"], ["extension/review", "6 · Review on site"], ["extension/tracking", "7 · Submission evidence"]
    ],
    onboarding: [
      ["onboarding/basics", "1 · Basics"], ["onboarding/experience", "2 · Experience"], ["onboarding/documents", "3 · Documents"], ["onboarding/ai", "4 · Optional AI setup"]
    ]
  };

  const routeMeta = {
    signin: ["Sign in", "A calm sign-in starting point."],
    "signin/forgot": ["Reset password", "Request an account reset through managed sign-in."],
    "onboarding/basics": ["Basics", "Start with the information needed to personalize your workspace."],
    "onboarding/experience": ["Experience", "Add the work and projects you want applications to draw from."],
    "onboarding/documents": ["Documents", "Upload only the documents you choose to use."],
    "onboarding/ai": ["Optional AI setup", "Choose a provider when you are ready. Manual tools remain available."],
    "home/empty": ["Home", "A quiet place to see what needs your attention."],
    "home/returning": ["Home", "A short view of what changed and what you can do next."],
    "profile/summary": ["Profile", "Your confirmed facts, documents, and preferences in one place."],
    "profile/documents": ["Documents", "Review extracted details before they become profile facts."],
    "profile/providers": ["AI providers", "Manage optional providers and fallback choices."],
    "applications/list": ["Applications", "Keep real applications separate from drafts and discovered jobs."],
    "applications/detail": ["Application detail", "See the latest status and the context behind this record."],
    "applications/evidence": ["Evidence timeline", "Each status change should show the evidence that supports it."],
    "email/draft": ["Email applications", "Prepare a message grounded in facts you have confirmed."],
    "email/review": ["Review your email", "Check the exact message and recipient before opening Gmail."],
    "email/handoff": ["Gmail handoff", "Gmail opens only when you choose it. Attachments and Send stay with you."],
    "email/confirm": ["Did you send it?", "Opening a compose window does not confirm that an email was sent."],
    "email/sent": ["Email confirmation", "An application can be recorded by email only after you confirm sending."],
    "alerts/setup": ["Job alerts", "Follow selected public career pages on your schedule."],
    "alerts/digest": ["Morning digest", "New openings are separate from your application history."],
    "alerts/partial": ["Some results may be missing", "The latest scan did not cover every saved source."],
    "alerts/failure": ["Source check failed", "A failed check is visible and never looks like an empty search."],
    "alerts/paused": ["Monitoring paused", "Paused sources are not being checked."],
    "notifications/inbox": ["Notifications", "One place for new matches and actions that need your attention."],
    "notifications/empty": ["Notifications", "You are up to date. New items will appear here."],
    "notifications/error": ["Notifications unavailable", "We could not load this inbox right now."],
    "notifications/revoked": ["Permission needed", "Notification permission is unavailable or was revoked."],
    "settings/privacy": ["Privacy & settings", "Choose what is saved, what is shared, and when work happens."],
    "settings/export": ["Review data export", "See what an export contains before requesting it."],
    "settings/deletion": ["Review account deletion", "Understand the cleanup and retention boundaries before continuing."],
    "extension/detected": ["Job detected", "Confirm the role before sending selected details for analysis."],
    "extension/analyzing": ["Analyzing this job", "A short progress view; no answers are applied in this step."],
    "extension/suggestions": ["Review suggestions", "Every suggested answer includes a source or asks you to provide one."],
    "extension/manual": ["Needs your answer", "Unknown facts, attestations, and declarations stay manual."],
    "extension/filled": ["Fill results", "Only supported answers are applied. An unfilled field remains untouched."],
    "extension/review": ["Review on the job site", "Rolevo never presses Submit or Next for you."],
    "extension/tracking": ["Submission evidence", "A click is an attempt, not proof that the site accepted an application."]
  };

  const sectionFor = (route) => route.split("/")[0];
  let lastRenderedRoute = null;
  const routeUrl = (route) => `#${route}`;
  const icon = (name, cls = "icon") => {
    const paths = {
      home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
      apps: '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 5V3h8v2M4 10h16M9 14h2m2 0h2"/>',
      mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/>',
      radar: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="m12 12 5-5"/>',
      user: '<circle cx="12" cy="8" r="3.5"/><path d="M4 21c.7-4.1 3.4-6.2 8-6.2s7.3 2.1 8 6.2"/>',
      bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9m-8 12a2 2 0 0 0 4 0"/>',
      settings: '<path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z"/><path d="m19.4 15 .1.1 1.1.9-1 1.8-1.4-.5a7.5 7.5 0 0 1-1.4.8l-.3 1.5h-2l-.4-1.5a8 8 0 0 1-1.6 0l-.7 1.3-1.8-1 .4-1.3a7 7 0 0 1-1.1-1.4L5.8 16l-.7-1.9 1.3-.8a8 8 0 0 1-.1-1.7l-1.4-.7.7-1.9 1.5.2a7 7 0 0 1 1.1-1.3L7.7 6.4l1.8-1 .9 1.2a8 8 0 0 1 1.7-.1l.7-1.4 1.9.7-.2 1.5a7 7 0 0 1 1.3 1.1l1.5-.5 1 1.8-1.2.9a8 8 0 0 1 .1 1.7l1.4.7-.7 1.9-1.5-.2Z"/>',
      file: '<path d="M6 3h8l5 5v13H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z"/><path d="M14 3v5h5M8 13h8m-8 4h8"/>',
      check: '<path d="m5 12 4 4L19 6"/>',
      alert: '<path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v5m0 3h.01"/>',
      arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
      lock: '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 1 1 8 0v3"/>',
      spark: '<path d="m12 2 2.2 6.2L20 10l-5.8 1.8L12 18l-2.2-6.2L4 10l5.8-1.8L12 2Zm7 13 .9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15Z"/>',
      clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
      link: '<path d="M10 13a5 5 0 0 0 7 .1l2-2a5 5 0 0 0-7-7l-1.2 1.2"/><path d="M14 11a5 5 0 0 0-7-.1l-2 2a5 5 0 0 0 7 7l1.2-1.2"/>',
      shield: '<path d="M12 3 20 6v5c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6l8-3Z"/><path d="m9 12 2 2 4-4"/>',
      close: '<path d="m6 6 12 12M18 6 6 18"/>',
      pin: '<path d="M12 21s7-6.1 7-12a7 7 0 1 0-14 0c0 5.9 7 12 7 12Z"/><circle cx="12" cy="9" r="2"/>',
      more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
      plus: '<path d="M12 5v14M5 12h14"/>',
      chevron: '<path d="m7 10 5 5 5-5"/>'
    };
    return `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.spark}</svg>`;
  };

  const brand = (caption = true) => `<a class="brand" href="#home/empty" aria-label="Rolevo prototype home"><img src="../design-system/logos/rolevo-symbol.svg" alt=""><span><span class="brand-name">Rolevo</span>${caption ? '<span class="brand-caption">Career workspace</span>' : ''}</span></a>`;
  const sampleBanner = `<div class="prototype-banner"><strong>Design prototype</strong><span>Sample states only · no data is saved or sent</span></div>`;
  const navItems = [
    ["home", "Home", "home", "home/empty"],
    ["applications", "Applications", "apps", "applications/list"],
    ["email", "Email", "mail", "email/draft"],
    ["alerts", "Job alerts", "radar", "alerts/setup"],
    ["profile", "Profile", "user", "profile/summary"]
  ];
  const navLink = ([key,label,iconName,path], current, mobile = false) => `<a class="${mobile ? "" : "nav-link"}" href="${routeUrl(path)}"${current === path ? ' aria-current="page"' : ""}>${icon(iconName)}<span>${label}</span>${key === "notifications" && !mobile ? '<span class="nav-count">2</span>' : ""}</a>`;

  function parseRoute() {
    const raw = location.hash.replace(/^#\/?/, "");
    if (!raw) return "home/empty";
    return routeMeta[raw] ? raw : "home/empty";
  }
  function routeTabs() { return ""; }
  function stateSelect(route) {
    const group = sectionFor(route);
    const entries = routeGroups[group] || [];
    if (entries.length < 2 || group === "onboarding" || group === "extension") return "";
    return `<label class="state-select-wrap"><span>Explore view</span><select aria-label="Explore ${group} screen" data-route-select>${entries.map(([to,label]) => `<option value="${to}"${route === to ? " selected" : ""}>${label}</option>`).join("")}</select></label>`;
  }
  function pageHeading(route) {
    const [title, desc] = routeMeta[route] || routeMeta["home/empty"];
    return `<header class="page-heading"><div><p class="eyebrow">${sectionFor(route) === "home" ? "Your workspace" : sectionFor(route).replace(/^[a-z]/, x => x.toUpperCase())}</p><h1>${title}</h1><p>${desc}</p></div>${stateSelect(route)}</header>${routeTabs(route)}`;
  }
  const button = (label, to, kind = "primary", iconName = "") => `<a class="button ${kind}" href="${routeUrl(to)}">${iconName ? icon(iconName) : ""}${label}</a>`;
  const status = (label, kind = "neutral") => `<span class="status ${kind}">${label}</span>`;
  const chip = (text) => `<span class="source-chip">${icon("file")}${text}</span>`;
  const card = (title, body, extra = "") => `<section class="card"><div class="card-head"><div><h2>${title}</h2>${body ? `<p>${body}</p>` : ""}</div>${extra}</div>`;
  const cardEnd = "</section>";
  const callout = (title, text, type = "info", iconName = "shield") => `<aside class="callout ${type}" role="note">${icon(iconName)}<div><strong>${title}</strong><p>${text}</p></div></aside>`;
  const sampleNote = `<p class="notice-line">Example content for reviewing layout and language. No account or external service is connected.</p>`;

  function renderHome(route) {
    const returning = route.endsWith("returning");
    if (!returning) return `${pageHeading(route)}
      <section class="card empty-state" aria-labelledby="empty-heading">
        <div class="empty-illustration" aria-hidden="true"><span class="orbit"></span><span class="orbit two"></span><span class="center"></span><span class="star"></span></div>
        <p class="eyebrow">A clear place to begin</p><h2 id="empty-heading">No applications yet</h2>
        <p>Your first application will appear here after a real submission attempt. Job openings and drafts stay in their own sections.</p>
        <div class="button-row">${button("Complete your profile", "profile/summary")}${button("Preview the extension", "extension/detected", "secondary")}</div>
      </section>
      <div class="grid two" style="margin-top:18px">
        ${card("A short setup checklist", "Only the next useful steps.")}
          <div class="list"><div class="list-item"><span class="leading-icon">${icon("user")}</span><div class="list-main"><strong>Profile details</strong><small>Add confirmed facts and the résumé you want to use.</small></div>${status("Optional next step","info")}</div><div class="list-item"><span class="leading-icon">${icon("apps")}</span><div class="list-main"><strong>First application</strong><small>Use the extension on a job form you choose.</small></div></div><div class="list-item"><span class="leading-icon">${icon("radar")}</span><div class="list-main"><strong>Job alerts</strong><small>Optional: follow public career pages.</small></div></div></div>
        ${cardEnd}
        ${card("Your work stays yours", "Review every answer and submit from the employer’s site.")}${callout("No activity has been created", "This is the genuine empty-state design. Examples shown elsewhere are labeled as samples.", "success", "shield")}${cardEnd}
      </div>`;
    return `${pageHeading(route)}${callout("One update needs your attention", "A site accepted a submission attempt but did not return confirmation. Check the employer site before marking it Applied.", "warning", "alert")}
      <div class="grid two" style="margin-top:18px">
        ${card("Next up", "A single recommended action.")}
          <div class="list-item"><span class="leading-icon">${icon("apps")}</span><div class="list-main"><strong>Confirm your application status</strong><small>Product designer · Northstar Studio · attempted Oct 9</small></div>${button("Review evidence", "applications/evidence", "secondary small")}</div>${cardEnd}
        ${card("Recent activity", "Application events, not discovered openings.")}
          <div class="list"><div class="list-item"><span class="leading-icon">${icon("check")}</span><div class="list-main"><strong>Applied · Meridian Labs</strong><small>Email · user confirmed · Oct 10</small></div>${status("Confirmed","success")}</div><div class="list-item"><span class="leading-icon">${icon("clock")}</span><div class="list-main"><strong>Submission attempted · Northstar Studio</strong><small>Web form · awaiting confirmation · Oct 9</small></div>${status("Needs follow-up","warning")}</div></div>${cardEnd}
        ${card("New job matches", "Two new matches from sources checked in the latest partial scan.")}
          <div class="list-item"><span class="leading-icon">${icon("radar")}</span><div class="list-main"><strong>Product designer · Fieldwork</strong><small>New · public careers page · found 9:02 a.m.</small></div>${button("View digest", "alerts/digest", "secondary small")}</div>${cardEnd}
        ${card("Source health", "Two of three saved pages checked successfully.")}
          <div class="list-item"><span class="leading-icon">${icon("alert")}</span><div class="list-main"><strong>One source needs attention</strong><small>Last check didn’t finish. Some results may be missing.</small></div>${button("Review sources", "alerts/partial", "secondary small")}</div>${cardEnd}
      </div>${sampleNote}`;
  }

  function renderProfile(route) {
    const key = route.split("/")[1];
    if (key === "documents") return `${pageHeading(route)}${sampleNote}<div class="grid two">
      ${card("Your documents", "Originals stay private; extracted facts need your confirmation.")}
        <div class="doc-tile"><span class="doc-mark">PDF</span><div class="list-main"><strong>Resume.pdf · example only</strong><small>Added Oct 8 · 1.4 MB · private storage not connected</small></div>${status("Review needed","warning")}</div><div class="doc-tile"><span class="doc-mark">PDF</span><div class="list-main"><strong>LinkedIn export · not uploaded</strong><small>Optional · PDF profile export</small></div>${status("Not added","neutral")}</div><div class="doc-tile"><span class="doc-mark">DOC</span><div class="list-main"><strong>Cover letter · not uploaded</strong><small>Optional writing-style context</small></div>${status("Not added","neutral")}</div>${cardEnd}
      ${card("Parse preview · example", "Each extracted fact stays a candidate until you review its source.")}
        <div class="fact"><span class="fact-label">Product role</span><span class="fact-value">Product Designer at Cedar Studio</span>${chip("Resume · page 1")}</div><div class="fact-actions"><span>${status("Needs confirmation","warning")}</span><button class="button secondary small" type="button" disabled>Confirm fact · demo</button></div><div class="fact"><span class="fact-label">Experience dates</span><span class="fact-value">2023–2025 · check before use</span>${chip("Resume · page 1")}</div><div class="fact-actions"><span>${status("Needs confirmation","warning")}</span><button class="button secondary small" type="button" disabled>Confirm fact · demo</button></div><div class="fact"><span class="fact-label">Project outcome</span><span class="fact-value">No quantified result found</span>${chip("Needs your input")}</div>${callout("Nothing is confirmed by this preview", "Review the source and confirm each candidate individually; missing achievements stay blank.", "warning", "alert")}${cardEnd}</div>
      <div class="button-row">${button("View confirmed profile", "profile/summary", "secondary")}</div>`;
    if (key === "providers") return `${pageHeading(route)}${callout("Keys are optional", "You can continue manually. A saved key is used only after you choose a provider and approve the data routing.", "info", "lock")}
      <div class="grid two" style="margin-top:16px">${card("Provider choices", "Credentials are masked and never shown in full again.")}
        <div class="list"><div class="list-item"><span class="leading-icon">1</span><div class="list-main"><strong>OpenRouter · DeepSeek V4 Flash</strong><small>First choice · no key configured</small></div>${status("Not configured","neutral")}</div><div class="list-item"><span class="leading-icon">2</span><div class="list-main"><strong>xAI · Grok</strong><small>Fallback option · no key configured</small></div>${status("Not configured","neutral")}</div><div class="list-item"><span class="leading-icon">3</span><div class="list-main"><strong>Google · Gemini</strong><small>Fallback option · no key configured</small></div>${status("Not configured","neutral")}</div></div>${cardEnd}
        ${card("Routing & consent", "Background monitoring requires separate saved-key consent.")}
          <div class="field"><label for="provider-order">Interactive order</label><select id="provider-order" class="control"><option>Choose when you add a provider</option></select></div><div class="field"><label for="fallback">Fallback behavior</label><select id="fallback" class="control"><option>Only continue after a provider is exhausted or unavailable</option></select></div><div class="data-notice">Before each analysis, show what job text and selected profile facts go to the selected provider. Never include unrelated personal details.</div>${cardEnd}
      </div>${sampleNote}`;
    return `${pageHeading(route)}${sampleNote}<div class="grid two">
      ${card("Contact", "Facts you entered or confirmed; unknown remains unknown.")}
        <div class="fact"><span class="fact-label">Name</span><span class="fact-value">Jordan Morgan</span>${chip("Manual · confirmed")}</div><div class="fact"><span class="fact-label">Email</span><span class="fact-value">jordan@example.test</span>${chip("Manual · confirmed")}</div><div class="fact"><span class="fact-label">Phone</span><span class="fact-value">Not added</span>${status("Optional","neutral")}</div><div class="fact"><span class="fact-label">LinkedIn</span><span class="fact-value">Profile link not added</span>${status("Optional","neutral")}</div>${cardEnd}
      ${card("Experience", "Summary of reviewed experience and projects.")}
        <div class="list-item"><span class="leading-icon">01</span><div class="list-main"><strong>Product Designer · Cedar Studio</strong><small>2023–2025 · source fact awaiting confirmation</small></div>${status("Review","warning")}</div><div class="list-item"><span class="leading-icon">02</span><div class="list-main"><strong>Portfolio project</strong><small>Project detail not confirmed</small></div>${status("Needs your input","warning")}</div>${cardEnd}
      ${card("Preferences", "Useful defaults for relevant applications.")}
        <div class="fact"><span class="fact-label">Roles</span><span class="fact-value">Product design, UX research</span></div><div class="fact"><span class="fact-label">Location</span><span class="fact-value">Remote · Karachi</span></div><div class="fact"><span class="fact-label">Writing notes</span><span class="fact-value">Concise, direct, warm</span></div>${cardEnd}
      ${card("Documents & providers", "Manage sources and model choices separately.")}
        <div class="button-row">${button("Review documents", "profile/documents", "secondary small")}${button("Provider settings", "profile/providers", "secondary small")}${button("Privacy & settings", "settings/privacy", "secondary small")}</div>${cardEnd}
    </div>`;
  }

  function renderApplications(route) {
    const key = route.split("/")[1];
    if (key === "detail") return `${pageHeading(route)}${callout("Submission attempted · awaiting confirmation", "The employer page recorded an attempt, but there is no reliable success signal yet. Confirm on the site before changing this to Applied.", "warning", "clock")}
      <div class="grid two" style="margin-top:17px">${card("Product Designer", "Northstar Studio · Web form · Oct 9 · example record")}
        <div class="fact"><span class="fact-label">Application status</span><span class="fact-value">Submission attempted</span>${status("Awaiting confirmation","warning")}</div><div class="fact"><span class="fact-label">Job URL</span><span class="fact-value">jobs.example.test/design</span>${chip("Source captured")}</div><div class="fact"><span class="fact-label">Last event</span><span class="fact-value">Submit click observed · validation unknown</span>${chip("Extension observer")}</div><div class="button-row">${button("View evidence timeline", "applications/evidence")}${button("Correct status", "applications/evidence", "secondary")}</div>${cardEnd}
        ${card("Prepared context", "Snapshot of what was reviewed; no inferred success.")}
        <div class="fact"><span class="fact-label">Answers</span><span class="fact-value">6 suggested · 5 filled · 1 needs review</span></div><div class="fact"><span class="fact-label">Resume</span><span class="fact-value">Manual attachment reminder shown</span></div><div class="fact"><span class="fact-label">Site confirmation</span><span class="fact-value">Not detected</span>${status("Unknown","neutral")}</div>${cardEnd}</div>${sampleNote}`;
    if (key === "evidence") return `${pageHeading(route)}${callout("Evidence determines the status", "A button click alone is not proof that a form was accepted. Corrections add history instead of erasing earlier evidence.", "info", "shield")}
      <div class="grid two" style="margin-top:17px">${card("Northstar Studio · Product Designer", "Example evidence timeline")}
        <div class="timeline"><div class="timeline-item"><span class="timeline-dot"></span><div class="timeline-copy"><strong>Session prepared</strong><small>Oct 9 · job context reviewed · no application created yet</small></div></div><div class="timeline-item"><span class="timeline-dot"></span><div class="timeline-copy"><strong>Submission attempted</strong><small>Oct 9 · user clicked the employer’s Submit button</small></div></div><div class="timeline-item pending"><span class="timeline-dot"></span><div class="timeline-copy"><strong>Awaiting confirmation</strong><small>No success signal has been verified; state remains attempted.</small></div></div></div>${cardEnd}
        ${card("Evidence available", "What supports this record and what is still unknown.")}
          <div class="list-item"><span class="leading-icon">${icon("file")}</span><div class="list-main"><strong>URL and timestamp</strong><small>Observed form URL · local time shown in the user's zone</small></div>${status("Captured","success")}</div><div class="list-item"><span class="leading-icon">${icon("alert")}</span><div class="list-main"><strong>Site response</strong><small>Success text not recognized or independently checked</small></div>${status("Unknown","neutral")}</div>${cardEnd}</div>
      <div class="button-row">${button("Back to applications", "applications/list", "secondary")}</div>`;
    return `${pageHeading(route)}${sampleNote}${card("Recent applications", "Filters are secondary; actionable records stay near the top.")}
      <div class="table-wrap"><table><thead><tr><th>Company & role</th><th>Date</th><th>Channel</th><th>Status</th><th></th></tr></thead><tbody>
      <tr><td><strong>Northstar Studio</strong><small>Product Designer</small></td><td>Oct 9</td><td>Web form</td><td>${status("Submission attempted","warning")}</td><td><a href="#applications/detail">View</a></td></tr>
      <tr><td><strong>Meridian Labs</strong><small>UX Researcher</small></td><td>Oct 10</td><td>Email</td><td>${status("Applied · confirmed","success")}</td><td><a href="#applications/evidence">Evidence</a></td></tr>
      <tr><td><strong>Fieldwork</strong><small>Product Designer</small><small>Prepared email · not an application</small></td><td>Oct 11</td><td>Email draft</td><td>${status("Draft","neutral")}</td><td><a href="#email/draft">Open draft</a></td></tr>
      </tbody></table></div>${cardEnd}
      <div class="grid two" style="margin-top:16px">${card("Kept out of this list", "Openings found by alerts are not applications.")}
        <div class="list-item"><span class="leading-icon">${icon("radar")}</span><div class="list-main"><strong>2 new roles in Job alerts</strong><small>Discovered vacancies have their own saved list.</small></div>${button("View matches", "alerts/digest", "secondary small")}</div>${cardEnd}
        ${card("A draft stays a draft", "Prepared answers do not create an application record.")}
        <div class="list-item"><span class="leading-icon">${icon("mail")}</span><div class="list-main"><strong>Email · Fieldwork</strong><small>Ready to review · no email sent</small></div>${button("Review email", "email/review", "secondary small")}</div>${cardEnd}</div>`;
  }

  function renderEmail(route) {
    const key = route.split("/")[1];
    if (key === "review") return `${pageHeading(route)}${callout("Review the exact recipient and message", "Attach the selected résumé manually in Gmail. Rolevo does not have access to your Gmail account.", "warning", "alert")}
      <div class="card" style="margin-top:16px"><div class="field"><label for="review-to">To</label><input class="control" id="review-to" value="hiring@example.test" readonly></div><div class="field"><label for="review-subject">Subject</label><input class="control" id="review-subject" value="Product Designer application · Jordan Morgan"></div><div class="field"><label for="review-body">Message</label><textarea class="control" id="review-body">Hello Hiring Team,\n\nI’m writing to apply for the Product Designer role. My recent work has focused on clear, accessible product experiences. I’d be glad to share how my confirmed design experience could support your team.\n\nBest,\nJordan</textarea><span class="helper">Example draft · edit before handoff. One claim is grounded in the confirmed profile summary.</span></div><div class="data-notice">Attachment reminder: add your résumé in Gmail. No file will be attached automatically.</div><div class="button-row">${button("Preview Gmail handoff", "email/handoff")}${button("Back to draft", "email/draft", "secondary")}</div></div>${sampleNote}`;
    if (key === "handoff") return `${pageHeading(route)}<div class="grid two">
      ${card("Compose preview", "This shows what the handoff would contain.")}
        <div class="fact"><span class="fact-label">To</span><span class="fact-value">hiring@example.test</span></div><div class="fact"><span class="fact-label">Subject</span><span class="fact-value">Product Designer application · Jordan Morgan</span></div><div class="fact"><span class="fact-label">Attachment</span><span class="fact-value">Add résumé manually</span></div>${cardEnd}
      ${card("Compose opened", "The user must review, attach, and send from Gmail.")}
        ${status("Not sent","warning")}<p>Opening compose is not an application and does not prove delivery.</p>${callout("This is a prototype only", "No Gmail tab will open and nothing is copied, attached, or sent.", "info", "shield")}<p class="helper">Copy fallback in the product</p><div class="button-row"><button class="button secondary small" type="button" disabled>Copy recipient · demo</button><button class="button secondary small" type="button" disabled>Copy subject · demo</button><button class="button secondary small" type="button" disabled>Copy message · demo</button></div><div class="button-row">${button("Continue as if compose opened", "email/confirm")}${button("Return to review", "email/review", "secondary")}</div>${cardEnd}</div>`;
    if (key === "confirm") return `${pageHeading(route)}${card("Did you send this email?", "Confirm only after you press Send in Gmail.")}
      <div class="callout warning">${icon("alert")}<div><strong>Compose opened does not mean sent</strong><p>This step creates an application record only after the user explicitly confirms sending.</p></div></div>
      <label class="checkline"><input type="checkbox"><span>I confirm that I sent this email. <strong>Example only</strong></span></label>
      <div class="button-row"><button class="button" type="button" data-email-confirm disabled>Preview user-confirmed state</button>${button("Not sent / leave as draft", "email/draft", "secondary")}</div>${cardEnd}${sampleNote}`;
    if (key === "sent") return `${pageHeading(route)}${card("Email confirmation", "This screen illustrates the state after an explicit user confirmation.")}
      ${callout("Applied by email · user confirmed", "Recorded only because the applicant confirmed sending · Oct 12, 9:14 a.m. (example)", "success", "check")}
      <div class="data-notice">Example state only: this prototype did not send an email or save an application. In the product, the event source is USER_CONFIRMED_EMAIL.</div>
      <div class="button-row">${button("View application evidence", "applications/evidence")}${button("Return to email", "email/draft", "secondary")}</div>${cardEnd}`;
    return `${pageHeading(route)}${callout("A grounded draft starts with job context", "The subject and body remain editable. Missing facts stay visible instead of being invented.", "info", "spark")}
      <div class="grid two" style="margin-top:16px">
        ${card("Job and recipient", "Enter only the details needed for this message.")}
          <div class="field"><label for="email-to">Recipient email</label><input id="email-to" class="control" value="hiring@example.test"><span class="helper">Example domain; no email address will be contacted.</span></div><div class="grid two"><div class="field"><label for="company">Company</label><input id="company" class="control" value="Fieldwork"></div><div class="field"><label for="role">Role</label><input id="role" class="control" value="Product Designer"></div></div><div class="field"><label for="job-desc">Job description</label><textarea id="job-desc" class="control">Help shape an accessible product experience across discovery, design, and delivery.</textarea></div><div class="field"><label for="start-note">Starting note (optional)</label><textarea id="start-note" class="control" placeholder="Add a point you want the draft to include."></textarea></div>${cardEnd}
        ${card("Context to use", "Choose reviewed sources; cover letters inform style, not accomplishments.")}
          <div class="list-item"><span class="leading-icon">${icon("file")}</span><div class="list-main"><strong>Resume · selected</strong><small>Available to refer to; attach it yourself in Gmail.</small></div><span class="option-pill selected">Selected</span></div><div class="list-item"><span class="leading-icon">${icon("apps")}</span><div class="list-main"><strong>Portfolio project · example</strong><small>Source fact needs confirmation before use.</small></div><span class="option-pill">Review</span></div>${callout("One relevant detail needs confirmation", "The prototype keeps uncertain project outcomes out of the draft.", "warning", "alert")}<div class="button-row">${button("Review example draft", "email/review")}</div>${cardEnd}
      </div>`;
  }

  function renderAlerts(route) {
    const key = route.split("/")[1];
    if (key === "digest") return `${pageHeading(route)}${callout("Latest scan was partial · example · Asia/Karachi", "Two of three sources completed. Some results may be missing. The next scheduled run is Oct 13 at 9:00 a.m. local time.", "warning", "clock")}
      <div class="grid two" style="margin-top:17px">${card("New matches", "Open roles found on selected public pages. Not applications.")}
        <div class="list-item"><span class="leading-icon">01</span><div class="list-main"><strong>Product Designer · Fieldwork</strong><small>Remote · discovered today, 9:01 a.m. · public career page</small></div>${status("New","info")}</div><p><strong>Why it matched:</strong> role preference and remote-work preference.</p><span class="source-chip">Public source · example URL</span><div class="divider-label">Next match</div><div class="list-item"><span class="leading-icon">02</span><div class="list-main"><strong>UX Researcher · Meridian Labs</strong><small>Karachi · discovered today, 9:03 a.m.</small></div>${status("New","info")}</div>${cardEnd}
        ${card("Followed career pages", "2 of 3 public sources checked successfully.")}
        <div class="list-item"><span class="leading-icon">${icon("check")}</span><div class="list-main"><strong>Fieldwork · checked</strong><small>Last success today · next check 9:00 a.m.</small></div>${status("Healthy","success")}</div><div class="list-item"><span class="leading-icon">${icon("alert")}</span><div class="list-main"><strong>Northstar Studio · partial</strong><small>Some results may be missing.</small></div>${status("Partial","warning")}</div><div class="button-row">${button("Review partial scan", "alerts/partial", "secondary small")}${button("Manage sources", "alerts/setup", "quiet small")}</div>${cardEnd}</div>${sampleNote}`;
    if (key === "partial") return `${pageHeading(route)}${callout("Some results may be missing", "Two of three supported public sources were checked. One source timed out; we cannot say there were no new jobs there.", "warning", "alert")}
      <div class="card" style="margin-top:16px"><div class="card-head"><div><h2>Run details</h2><p>Example scan · Oct 12 · started at 9:00 a.m. local time.</p></div>${status("Partial","warning")}</div><div class="list-item"><span class="leading-icon">${icon("check")}</span><div class="list-main"><strong>Fieldwork</strong><small>Page checked · 2 matching roles</small></div>${status("Complete","success")}</div><div class="list-item"><span class="leading-icon">${icon("check")}</span><div class="list-main"><strong>Meridian Labs</strong><small>Page checked · no new matches in this completed source</small></div>${status("Complete","success")}</div><div class="list-item"><span class="leading-icon">${icon("clock")}</span><div class="list-main"><strong>Northstar Studio</strong><small>Timed out · result unknown</small></div>${status("Incomplete","warning")}</div><div class="button-row">${button("Edit this source", "alerts/failure", "secondary")}${button("View completed matches", "alerts/digest", "quiet")}</div></div>`;
    if (key === "failure") return `${pageHeading(route)}${callout("Last check didn’t finish", "This public page returned an access error. We did not retry around a sign-in, CAPTCHA, or site restriction.", "danger", "alert")}
      <div class="grid two" style="margin-top:16px">${card("Northstar Studio careers", "https://careers.example.test/northstar · example address")}
        <div class="fact"><span class="fact-label">Source support</span><span class="fact-value">Access denied by source</span>${status("Unsupported now","danger")}</div><div class="fact"><span class="fact-label">Last attempt</span><span class="fact-value">Oct 12 · 9:02 a.m. Asia/Karachi</span></div><div class="fact"><span class="fact-label">Next run</span><span class="fact-value">Not scheduled until source is fixed</span></div><div class="data-notice">No CAPTCHA or login bypass is available. Other sources can continue independently.</div><div class="button-row">${button("Edit source URL", "alerts/setup")}${button("Pause this source", "alerts/paused", "secondary")}</div>${cardEnd}
        ${card("What we know", "The source request failed; its job results are unknown.")}
        <p>Do not interpret this failure as “no jobs found.” The failure remains visible until the address or source changes.</p>${cardEnd}</div>`;
    if (key === "paused") return `${pageHeading(route)}${callout("Monitoring is paused", "This source will not be checked. Rolevo has no current coverage for this page.", "warning", "clock")}
      <div class="card" style="margin-top:16px"><div class="list-item"><span class="leading-icon">${icon("radar")}</span><div class="list-main"><strong>Fieldwork public careers</strong><small>Paused Oct 12 · example source</small></div>${status("Paused","warning")}</div><p>Last successful check: Oct 11 at 9:01 a.m. · no upcoming run.</p><div class="button-row">${button("Preview resume confirmation", "alerts/setup")}${button("View last digest", "alerts/digest", "secondary")}</div></div>`;
    return `${pageHeading(route)}${callout("Rolevo checks selected public career pages", "Choose a page, review its support status, and consent to the 9:00 a.m. local check before saving.", "info", "radar")}
      <div class="grid two" style="margin-top:16px">
        ${card("Add a source", "One URL at a time · up to five public sources.")}
          <div class="field"><label for="source-url">Public careers page URL</label><input id="source-url" class="control" value="https://careers.example.test/fieldwork"><span class="helper">Use a public listing page. Login, CAPTCHA, and JavaScript-only sites are unsupported.</span></div><div class="field"><label for="roles">Roles to look for</label><input id="roles" class="control" value="Product Designer, UX Researcher"></div><div class="field"><label for="locations">Location and work style</label><input id="locations" class="control" value="Remote, Karachi"></div><div class="field"><label for="timezone">Daily check time</label><select id="timezone" class="control"><option>9:00 a.m. · Asia/Karachi (example)</option></select></div>${status("Sample preview · not checked","neutral")}<div class="button-row">${button("Preview example matches", "alerts/digest")}</div>${cardEnd}
        ${card("Before a daily check", "The choices that enable background work.")}
          <div class="list-item"><span class="leading-icon">${icon("shield")}</span><div class="list-main"><strong>Public page only</strong><small>No login, CAPTCHA, or access-control bypass.</small></div></div><div class="list-item"><span class="leading-icon">${icon("user")}</span><div class="list-main"><strong>Minimum matching details</strong><small>Role and location preferences plus job text.</small></div></div><label class="checkline"><input type="checkbox"><span>I agree to daily checks of this selected public page.</span></label><label class="checkline"><input type="checkbox"><span>I allow a saved provider key to be used for background matching.</span></label><div class="onboarding-note">Contact details, date of birth, and private documents are not sent to background matching.</div>${cardEnd}
      </div>${sampleNote}`;
  }

  function renderNotifications(route) {
    const key = route.split("/")[1];
    if (key === "empty") return `${pageHeading(route)}${card("You're all caught up", "New matching jobs and actions needing you will appear here.")}
      <div class="empty-state"><div class="empty-illustration" aria-hidden="true"><span class="orbit"></span><span class="orbit two"></span><span class="center"></span><span class="star"></span></div><h2>No new notifications</h2><p>Completed checks with no new matches are quiet. Paused and failed sources remain visible on Job alerts.</p>${button("View job-alert status", "alerts/setup", "secondary")}</div>${cardEnd}`;
    if (key === "error") return `${pageHeading(route)}${callout("Notifications unavailable", "Your inbox did not load. No notification state has been changed.", "danger", "alert")}${card("Try again later", "Your saved sources and application records are not affected.")}${button("Review alert health", "alerts/partial", "secondary")}${cardEnd}`;
    if (key === "revoked") return `${pageHeading(route)}${callout("Browser notifications are turned off", "You can still see updates in this inbox. Change browser permission in site settings if you want desktop alerts.", "warning", "shield")}${card("Updates remain available in Rolevo", "Turning off browser permission does not erase your inbox.")}
      <div class="list-item"><span class="leading-icon">${icon("bell")}</span><div class="list-main"><strong>In-app inbox</strong><small>Available when you open Rolevo.</small></div>${status("Available","success")}</div><div class="list-item"><span class="leading-icon">${icon("close")}</span><div class="list-main"><strong>Browser permission</strong><small>Revoked · no push notification will be delivered.</small></div>${status("Off","warning")}</div>${cardEnd}`;
    return `${pageHeading(route)}${sampleNote}${card("Recent", "Grouped by source and date so unchanged results do not repeat.")}
      <div class="list-item"><span class="leading-icon">${icon("radar")}</span><div class="list-main"><strong>2 new roles match your preferences</strong><small>Fieldwork · today, 9:03 a.m. · open morning digest</small></div>${status("New","info")}${button("Open","alerts/digest","secondary small")}</div>
      <div class="list-item"><span class="leading-icon">${icon("alert")}</span><div class="list-main"><strong>A source check was partial</strong><small>Northstar Studio · some results may be missing</small></div>${status("Action needed","warning")}${button("Review","alerts/partial","secondary small")}</div>
      <div class="list-item"><span class="leading-icon">${icon("apps")}</span><div class="list-main"><strong>Submission awaits confirmation</strong><small>Northstar Studio · Oct 9</small></div>${status("Follow up","warning")}${button("View","applications/evidence","secondary small")}</div>${cardEnd}`;
  }

  function renderSettings(route) {
    if (route === "settings/export") return `${pageHeading(route)}${callout("Example export contents", "A real export is versioned, includes original documents, and never includes provider key plaintext.", "info", "file")}${card("Included in the export", "Review the scope before you request a copy.")}
      <div class="list-item"><span class="leading-icon">${icon("user")}</span><div class="list-main"><strong>Profile facts and preferences</strong><small>Confirmed values, source, and revision history.</small></div>${status("Included","success")}</div><div class="list-item"><span class="leading-icon">${icon("file")}</span><div class="list-main"><strong>Original documents</strong><small>Private files you uploaded.</small></div>${status("Included","success")}</div><div class="list-item"><span class="leading-icon">${icon("apps")}</span><div class="list-main"><strong>Applications and evidence</strong><small>Status timeline, answer snapshot, and supporting events.</small></div>${status("Included","success")}</div><div class="list-item"><span class="leading-icon">${icon("lock")}</span><div class="list-main"><strong>Provider key plaintext</strong><small>Never present in the export.</small></div>${status("Excluded","neutral")}</div><div class="button-row"><button class="button" type="button" disabled>Export unavailable in prototype</button>${button("Back to privacy", "settings/privacy", "secondary")}</div>${cardEnd}`;
    if (route === "settings/deletion") return `${pageHeading(route)}${callout("This cannot be undone", "This prototype will not delete an account. A real flow must explain consequences and ask for a fresh confirmation.", "danger", "alert")}${card("What account deletion does", "Review this before a future confirmation step.")}
      <div class="list-item"><span class="leading-icon">${icon("clock")}</span><div class="list-main"><strong>Stop scheduled work</strong><small>Cancel pending scans and prevent new work.</small></div></div><div class="list-item"><span class="leading-icon">${icon("lock")}</span><div class="list-main"><strong>Revoke sessions and keys</strong><small>Stop future provider calls and client access.</small></div></div><div class="list-item"><span class="leading-icon">${icon("file")}</span><div class="list-main"><strong>Remove private documents and profile data</strong><small>Explain any legally required retention before final confirmation.</small></div></div><div class="button-row"><button class="button" type="button" disabled>Deletion unavailable in prototype</button>${button("Back to privacy", "settings/privacy", "secondary")}</div>${cardEnd}`;
    return `${pageHeading(route)}${callout("Privacy at the moment of action", "Before analysis or background checks, show what selected profile facts and job text leave Rolevo.", "info", "lock")}
      <div class="grid two" style="margin-top:16px">${card("Your data controls", "Choose what is retained and how it is used.")}
        <div class="list-item"><span class="leading-icon">${icon("file")}</span><div class="list-main"><strong>Profile and documents</strong><small>Documents are private; facts stay unconfirmed until you review them.</small></div>${status("User controlled","success")}</div><div class="list-item"><span class="leading-icon">${icon("spark")}</span><div class="list-main"><strong>Provider data routing</strong><small>Ask before sending selected job text and profile facts.</small></div>${status("Per action","info")}</div><div class="list-item"><span class="leading-icon">${icon("radar")}</span><div class="list-main"><strong>Background monitoring</strong><small>Requires selected source, 9 a.m. timezone, and saved-key consent.</small></div>${status("Optional","neutral")}</div><div class="list-item"><span class="leading-icon">${icon("shield")}</span><div class="list-main"><strong>Form fill exposure</strong><small>Hiring-page scripts can see values before you press Submit.</small></div>${status("Explain first","warning")}</div>${cardEnd}
        ${card("Privacy actions", "Visible controls with a confirmation step for irreversible work.")}
          <div class="field"><label>Account export</label><p class="helper">Download a versioned copy, including original documents; provider key plaintext is excluded.</p>${button("Review export contents", "settings/export", "secondary small")}</div><div class="field"><label>Account deletion</label><p class="helper">Stops scheduled work, removes keys and sessions, and explains retention boundaries.</p>${button("Review deletion details", "settings/deletion", "secondary small")}</div><div class="field"><label for="privacy-appearance">Appearance</label><select id="privacy-appearance" class="control"><option>Light · selected preview</option></select></div>${cardEnd}</div>${sampleNote}`;
  }

  function renderOnboarding(route) {
    const step = route.split("/")[1];
    const steps = routeGroups.onboarding.map(([to,label]) => {
      const [num,...rest] = label.split(" · ");
      const index = Number(num);
      const current = to === route;
      const completed = index <= ["basics","experience","documents","ai"].indexOf(step);
      return `<a class="progress-step ${current ? "active" : completed ? "done" : ""}" href="${routeUrl(to)}"${current ? ' aria-current="step"' : ""}><span class="step-num">${completed ? "✓" : num}</span><span>${rest.join(" ")}</span></a>`;
    }).join("");
    let fields = "";
    if (step === "basics") fields = `<div class="grid two"><div class="field"><label for="name">Name</label><input class="control" id="name" placeholder="Your name"></div><div class="field"><label for="email">Email</label><input class="control" id="email" type="email" placeholder="you@example.com"></div><div class="field"><label for="phone">Phone <span class="helper">optional</span></label><input class="control" id="phone" placeholder="Add only if useful"></div><div class="field"><label for="linkedin">Profile link <span class="helper">optional</span></label><input class="control" id="linkedin" placeholder="https://…"></div></div><div class="onboarding-note">Age and date of birth are not requested by default. Optional sensitive details need a specific supported purpose and separate controls.</div>`;
    if (step === "experience") fields = `<div class="field"><label for="roles">Preferred roles</label><input class="control" id="roles" placeholder="e.g. Product designer, UX researcher"></div><div class="grid two"><div class="field"><label for="location">Location</label><input class="control" id="location" placeholder="City or remote"></div><div class="field"><label for="workstyle">Work style</label><select class="control" id="workstyle"><option>Choose if you want</option><option>Remote</option><option>Hybrid</option><option>On-site</option></select></div></div><div class="field"><label for="experience">Experience, projects, education</label><textarea class="control" id="experience" placeholder="Add details at your pace. Unknowns remain blank."></textarea></div><div class="field"><label for="notes">Application notes <span class="helper">optional</span></label><textarea class="control" id="notes" placeholder="Tone, useful context, or reminders"></textarea></div>`;
    if (step === "documents") fields = `<div class="onboarding-note">Your originals stay private. Extracted facts appear as candidates for your review; nothing is treated as confirmed automatically.</div><div class="doc-tile"><span class="doc-mark">PDF</span><div class="list-main"><strong>Resume</strong><small>Recommended · uploaded only after you choose a file</small></div><button class="button secondary small" type="button" disabled>Choose file · demo</button></div><div class="doc-tile"><span class="doc-mark">PDF</span><div class="list-main"><strong>LinkedIn profile export</strong><small>Optional · you can add it later</small></div><button class="button secondary small" type="button" disabled>Optional</button></div><div class="doc-tile"><span class="doc-mark">DOC</span><div class="list-main"><strong>Existing cover letter</strong><small>Optional style context; not proof of achievements</small></div><button class="button secondary small" type="button" disabled>Optional</button></div>`;
    if (step === "ai") fields = `<div class="grid two"><div class="field"><label for="first-provider">Provider choice</label><select id="first-provider" class="control"><option>Choose later</option><option>OpenRouter · DeepSeek V4 Flash</option><option>xAI · Grok</option><option>Google · Gemini</option></select></div><div class="field"><label for="fallback-choice">Fallback order</label><select id="fallback-choice" class="control"><option>Set after adding keys</option><option>Use one provider only</option></select></div></div><div class="data-notice">Keys are encrypted if saved; usage may cost money under the provider's terms. Only consented fallback choices are tried. Background checks need separate saved-key consent.</div><div class="field"><label for="key-example">API key</label><input id="key-example" class="control" type="password" placeholder="Optional · not connected in this prototype" disabled></div>${callout("You can skip this step", "Profile setup and manual application preparation remain available without an API key.", "info", "shield")}`;
    const prev = {experience:"onboarding/basics",documents:"onboarding/experience",ai:"onboarding/documents"}[step];
    const next = {basics:"onboarding/experience",experience:"onboarding/documents",documents:"onboarding/ai",ai:"home/empty"}[step];
    const label = step === "ai" ? "Finish setup preview" : "Continue";
    return `${sampleBanner}<main class="onboarding-main"><header class="onboarding-header">${brand(false)}<a href="#signin">Exit setup</a></header><div class="progress-steps" aria-label="Onboarding progress">${steps}</div><p class="eyebrow">Step ${["basics","experience","documents","ai"].indexOf(step)+1} of 4 · ${step === "ai" ? "optional" : "save as you go"}</p><h1>${routeMeta[route][0]}</h1><p class="lead">${routeMeta[route][1]}</p><section class="onboarding-card">${fields}<div class="onboarding-foot">${prev ? button("Back", prev, "secondary") : '<span></span>'}<div style="display:flex;align-items:center;gap:12px">${step === "ai" ? '<a href="#home/empty">Skip for now</a>' : ""}${button(label, next)}</div></div></section><p class="prototype-footer">Example flow · progress is not stored · managed sign-in is not connected</p></main>`;
  }

  function renderSignin(route = "signin") {
    if (route === "signin/forgot") return `${sampleBanner}<main class="auth-layout"><section class="auth-art">${brand()}<div><p class="eyebrow">A secure account flow</p><h1>Get back to your workspace.</h1><p>Reset access using the managed identity flow configured for the product.</p></div><p class="notice-line">Identity provider selection and tenant setup remain pending owner confirmation.</p></section><section class="auth-panel"><div class="auth-card"><p class="eyebrow">Account recovery</p><h2>Reset your password</h2><p>Enter your account email. The connected identity service would send the reset link.</p><div class="field"><label for="reset-email">Email</label><input id="reset-email" type="email" class="control" placeholder="you@example.com"></div><button class="button" type="button" disabled>Send reset link · not connected</button><div class="button-row">${button("Return to sign in", "signin", "secondary")}</div><p class="prototype-footer">No email is sent by this prototype.</p></div></section></main>`;
    return `${sampleBanner}<main class="auth-layout"><section class="auth-art">${brand()}<div><p class="eyebrow">Your next step, made clearer</p><h1>Make your job search feel more manageable.</h1><p>Prepare grounded applications, write thoughtful emails, and keep track of new roles—one clear step at a time.</p></div><p class="notice-line">Rolevo is the owner-selected product identity. This prototype does not authenticate.</p><img class="auth-mark" src="../design-system/logos/rolevo-symbol.svg" alt=""></section><section class="auth-panel"><div class="auth-card"><p class="eyebrow">Welcome</p><h2>Sign in to Rolevo</h2><p>Use your managed account to continue. This prototype does not authenticate.</p><div class="field"><label for="signin-email">Email</label><input id="signin-email" type="email" class="control" placeholder="you@example.com"></div><div class="field"><label for="signin-password">Password</label><input id="signin-password" type="password" class="control" placeholder="Your password"></div><button class="button" type="button" disabled>Continue · identity not connected</button><div class="button-row" style="justify-content:space-between"><a href="#onboarding/basics">Create an account</a><a href="#signin/forgot">Reset password</a></div><div class="divider-label">Preview the first-run flow</div><p>Sign-in, email verification, and account recovery are plan designs only.</p><div class="button-row">${button("Explore onboarding", "onboarding/basics", "secondary")}</div><p class="prototype-footer">Read the <a href="#settings/privacy">privacy overview</a></p></div></section></main>`;
  }

  function renderExtension(route) {
    const key = route.split("/")[1];
    const stepIndex = routeGroups.extension.findIndex(([to]) => to === route);
    const stepNames = ["Detected", "Analyzing", "Suggestions", "Manual"];
    const stepLinks = routeGroups.extension.slice(0,4).map(([to], i) => `<a href="${routeUrl(to)}"${to === route ? ' aria-current="page"' : ""}>${stepNames[i]}</a>`).join("");
    let content = "";
    if (key === "detected") content = `<div class="card"><div class="card-head"><div><p class="eyebrow">Current tab · example</p><h2>Product Designer</h2><p>Fieldwork · jobs.example.test</p></div>${status("Form detected","success")}</div><div class="fact"><span class="fact-label">Role</span><span class="fact-value">Product Designer</span><a href="#extension/detected">Edit</a></div><div class="fact"><span class="fact-label">Description</span><span class="fact-value">Visible · 420 words</span>${status("Ready","success")}</div><div class="fact"><span class="fact-label">Selected form</span><span class="fact-value">Application · 8 fields</span><a href="#extension/detected">Change</a></div><div class="data-notice">Before analysis, review the selected job text and the profile facts that may be sent to your chosen provider.</div><div class="button-row">${button("Analyze this job", "extension/analyzing")}</div></div><p class="notice-line">Only the selected visible form is inspected. This panel does not read other pages or submit for you.</p>`;
    if (key === "analyzing") content = `${callout("Analysis is in progress · example state", "Three steps are shown so you can see what is happening. This prototype does not contact an AI provider.", "info", "spark")}<div class="card" style="margin-top:13px"><div class="timeline"><div class="timeline-item"><span class="timeline-dot"></span><div class="timeline-copy"><strong>Job context reviewed</strong><small>Employer and role selected by the user.</small></div></div><div class="timeline-item"><span class="timeline-dot"></span><div class="timeline-copy"><strong>Selected profile facts mapped</strong><small>Only relevant, confirmed facts are eligible.</small></div></div><div class="timeline-item pending"><span class="timeline-dot"></span><div class="timeline-copy"><strong>Draft suggestions</strong><small>Results will remain drafts until you review them.</small></div></div></div><div class="button-row">${button("Preview suggestions", "extension/suggestions")}</div></div>`;
    if (key === "suggestions") content = `<div class="card"><div class="card-head"><div><p class="eyebrow">Field group · contact</p><h2>Review suggested answers</h2><p>Example suggestions with visible sources.</p></div>${status("3 ready · 2 need you","info")}</div><div class="fact"><span class="fact-label">Email</span><span class="fact-value">jordan@example.test</span>${chip("Profile · confirmed")}</div><div class="fact"><span class="fact-label">Portfolio</span><span class="fact-value">No confirmed link</span>${status("Needs your answer","warning")}</div><div class="fact"><span class="fact-label">Work authorization</span><span class="fact-value">Not known · not inferred</span>${status("Manual","warning")}</div><div class="fact"><span class="fact-label">Short introduction</span><span class="fact-value">Draft based on confirmed role summary</span>${chip("Profile · review")}</div><div class="fact"><span class="fact-label">Work style</span><span class="fact-value">Remote</span>${chip("Preference · confirmed")}</div>${callout("Before applying answers", "The hiring page and its scripts can see filled values before you press Submit. Only supported answers will be written; unknown fields stay untouched.", "warning", "shield")}<div class="button-row">${button("Review manual questions", "extension/manual", "secondary")}${button("Apply supported answers", "extension/filled")}</div></div>`;
    if (key === "manual") content = `${callout("Needs your answer", "We did not find a confirmed answer for this question. Leave it unanswered or enter your own answer on the employer's form.", "warning", "alert")}<div class="card" style="margin-top:13px"><p class="eyebrow">Employer question</p><h2>Are you legally authorized to work in the location of this role?</h2><p>Legal/work-authorization attestations are never guessed from profile details.</p><div class="field" style="margin-top:16px"><label for="authorization-answer">Your answer · optional</label><select id="authorization-answer" class="control"><option>Leave blank for now</option><option>Yes</option><option>No</option></select><span class="helper">The prototype does not write this answer to any page.</span></div><div class="button-row">${button("Leave unanswered and review", "extension/filled")}</div></div>`;
    if (key === "filled") content = `${callout("Fill completed · example result", "Three supported values were written. Unknown or unsupported fields stayed untouched. Review on the employer page.", "success", "check")}<div class="card" style="margin-top:13px"><div class="list-item"><span class="leading-icon">${icon("check")}</span><div class="list-main"><strong>Email</strong><small>Filled · confirmed profile fact</small></div>${status("Filled","success")}</div><div class="list-item"><span class="leading-icon">${icon("check")}</span><div class="list-main"><strong>Preferred title</strong><small>Filled · profile preference</small></div>${status("Filled","success")}</div><div class="list-item"><span class="leading-icon">${icon("check")}</span><div class="list-main"><strong>Work style</strong><small>Remote selected · confirmed preference matched</small></div>${status("Selected","success")}</div><div class="list-item"><span class="leading-icon">${icon("alert")}</span><div class="list-main"><strong>Work authorization</strong><small>Not filled · you need to answer on the site</small></div>${status("Untouched","warning")}</div><div class="list-item"><span class="leading-icon">${icon("close")}</span><div class="list-main"><strong>Portfolio URL</strong><small>Unsupported field · kept unchanged</small></div>${status("Not filled","neutral")}</div><div class="button-row">${button("Review on the job site", "extension/review")}</div></div>`;
    if (key === "review") content = `${callout("Rolevo did not submit", "Review each answer, finish manual questions, attach your résumé yourself, and use the site's own Submit button.", "warning", "alert")}<div class="card" style="margin-top:13px"><h2>Before you submit</h2><div class="checkline"><span>${icon("check")}</span><span>Check every answer against your real experience.</span></div><div class="checkline"><span>${icon("check")}</span><span>Complete attestations and sensitive declarations yourself.</span></div><div class="checkline"><span>${icon("check")}</span><span>Attach the résumé on the employer site if needed.</span></div><div class="checkline"><span>${icon("check")}</span><span>Use the employer's Submit button; Rolevo never presses it.</span></div><div class="data-notice">Form values are visible to the hiring page and its scripts now—not only after Submit. This is explained before the first fill.</div>${button("Preview post-submit evidence", "extension/tracking", "secondary")}</div>`;
    if (key === "tracking") content = `${callout("Submission attempted · awaiting confirmation", "An attempt is not proof that the employer accepted your application.", "warning", "clock")}<div class="card" style="margin-top:13px"><div class="timeline"><div class="timeline-item"><span class="timeline-dot"></span><div class="timeline-copy"><strong>Review completed</strong><small>Example UI state · before site submission</small></div></div><div class="timeline-item"><span class="timeline-dot"></span><div class="timeline-copy"><strong>Submit click observed</strong><small>Example event · Oct 12, 9:20 a.m.</small></div></div><div class="timeline-item pending"><span class="timeline-dot"></span><div class="timeline-copy"><strong>Awaiting confirmation</strong><small>No verified success signal; user can confirm or correct later.</small></div></div></div><div class="data-notice">This illustration is not connected to an application record. A real status change requires site evidence or explicit user confirmation.</div>${button("Open example application detail", "applications/detail", "secondary")}</div>`;
    return `${sampleBanner}<main class="extension-page"><section class="extension-shell"><header class="extension-header">${brand(false)}<a class="open-app" href="#home/empty">Open Rolevo ↗</a></header><div class="extension-content"><p class="eyebrow">Extension · example panel</p><div class="page-heading"><h1>${routeMeta[route][0]}</h1><p>${routeMeta[route][1]}</p></div><div class="extension-step-marker" aria-hidden="true">${routeGroups.extension.map((_, i) => `<span class="${i <= stepIndex ? "active" : ""}"></span>`).join("")}</div><nav class="segmented" aria-label="Extension states">${stepLinks}<a href="#extension/filled"${key === "filled" ? ' aria-current="page"' : ""}>5 Fill</a><a href="#extension/review"${key === "review" ? ' aria-current="page"' : ""}>6 Review</a><a href="#extension/tracking"${key === "tracking" ? ' aria-current="page"' : ""}>7 Track</a></nav><div style="margin-top:14px">${content}</div></div><footer class="extension-footer"><span>Example state · no page writes</span><span>Shortcuts <a href="#profile/summary">profile</a></span></footer></section></main>`;
  }

  function renderMain(route) {
    let content = "";
    if (route.startsWith("home/")) content = renderHome(route);
    else if (route.startsWith("profile/")) content = renderProfile(route);
    else if (route.startsWith("applications/")) content = renderApplications(route);
    else if (route.startsWith("email/")) content = renderEmail(route);
    else if (route.startsWith("alerts/")) content = renderAlerts(route);
    else if (route.startsWith("notifications/")) content = renderNotifications(route);
    else if (route.startsWith("settings/")) content = renderSettings(route);
    return `${sampleBanner}<div class="shell"><aside class="sidebar">${brand()}<div class="profile-switch"><span class="avatar">JM</span><span class="profile-meta"><strong>Jordan Morgan</strong><small>Personal · example</small></span>${icon("chevron")}</div><p class="nav-group-label">Workspace</p><nav class="primary-nav" aria-label="Main navigation">${navItems.map((item) => navLink(item,route)).join("")}</nav><div class="sidebar-spacer"></div><a class="nav-link utility" href="#extension/detected">${icon("spark")}<span>Extension preview</span></a><a class="nav-link utility" href="#signin">${icon("user")}<span>Sign-in & setup preview</span></a><a class="nav-link utility" href="#notifications/inbox">${icon("bell")}<span>Notifications</span><span class="nav-count">2</span></a><a class="nav-link utility" href="#settings/privacy">${icon("settings")}<span>Privacy & settings</span></a><div class="sidebar-divider"></div><p class="sidebar-note">Rolevo is the owner-selected name. Sample content is not user data.</p></aside><div class="main-column"><header class="topbar"><div class="breadcrumb"><span>Workspace</span><span aria-hidden="true">/</span><strong>${(routeMeta[route]||[])[0]}</strong></div><div class="top-actions"><a class="icon-button" href="#notifications/inbox" aria-label="Notifications, 2 unread">${icon("bell")}<span class="unread-dot"></span></a><div class="top-user"><span class="avatar">JM</span><span>Example workspace</span></div></div></header><main class="content">${content}<footer class="prototype-footer">Static design proposal · No saved data · No provider, Gmail, employer, or browser service is connected</footer></main></div></div><nav class="mobile-nav" aria-label="Compact navigation">${navItems.map((item) => navLink(item,route,true)).join("")}</nav>`;
  }

  function render() {
    const route = parseRoute();
    const routeChanged = lastRenderedRoute !== null && lastRenderedRoute !== route;
    lastRenderedRoute = route;
    document.title = `${routeMeta[route]?.[0] || "Rolevo"} · Design prototype`;
    const app = document.getElementById("app");
    if (route === "signin") app.innerHTML = renderSignin();
    else if (route === "signin/forgot") app.innerHTML = renderSignin(route);
    else if (route.startsWith("onboarding/")) app.innerHTML = renderOnboarding(route);
    else if (route.startsWith("extension/")) app.innerHTML = renderExtension(route);
    else app.innerHTML = renderMain(route);
    app.insertAdjacentHTML("afterbegin", '<a class="skip-link" href="#main-content">Skip to main content</a>');
    app.querySelector(".skip-link")?.addEventListener("click", (event) => {
      event.preventDefault();
      app.querySelector("main")?.focus();
    });
    const main = app.querySelector("main");
    if (main) {
      main.id = "main-content";
      main.tabIndex = -1;
    }
    app.querySelectorAll("[data-route-select]").forEach((select) => select.addEventListener("change", (event) => { location.hash = event.currentTarget.value; }));
    app.querySelectorAll("form").forEach((form) => form.addEventListener("submit", (event) => event.preventDefault()));
    const emailConfirmation = app.querySelector('input[type="checkbox"]');
    const previewConfirmation = app.querySelector("[data-email-confirm]");
    if (emailConfirmation && previewConfirmation) {
      emailConfirmation.addEventListener("change", () => { previewConfirmation.disabled = !emailConfirmation.checked; });
      previewConfirmation.addEventListener("click", () => { if (emailConfirmation.checked) location.hash = "email/sent"; });
    }
    window.scrollTo(0, 0);
    if (routeChanged) {
      const heading = app.querySelector("main h1");
      if (heading) {
        heading.tabIndex = -1;
        heading.focus({ preventScroll: true });
      }
    }
  }
  window.addEventListener("hashchange", render);
  window.addEventListener("DOMContentLoaded", render);
  render();
})();
