const icons = {
  home: '<path d="m3 10 9-7 9 7"/><path d="M5 9v11h14V9M9 20v-6h6v6"/>',
  briefcase: '<rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18M10 12v2h4v-2"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
  radar: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="m12 12 6-6M15 6h3v3"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  spark: '<path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3Z"/><path d="m19 15 .9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15Z"/>',
  settings: '<path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"/><path d="m19.4 15 .1.1 1.3 1-1.4 2.4-1.6-.6a8 8 0 0 1-1.5.9l-.3 1.7h-2.8l-.3-1.7a8 8 0 0 1-1.5-.9l-1.6.6-1.4-2.4 1.3-1a7 7 0 0 1 0-1.8l-1.3-1 1.4-2.4 1.6.6a8 8 0 0 1 1.5-.9l.3-1.7h2.8l.3 1.7a8 8 0 0 1 1.5.9l1.6-.6 1.4 2.4-1.3 1a7 7 0 0 1-.1 1.8Z" transform="translate(-2 -2)"/>',
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  chevron: '<path d="m9 18 6-6-6-6"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  document: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8M8 17h8"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  upload: '<path d="M12 16V4m0 0L7 9m5-5 5 5"/><path d="M4 16v4h16v-4"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.1 0l2-2A5 5 0 0 0 12 3.9l-1.1 1.1"/><path d="M14 11a5 5 0 0 0-7.1 0l-2 2A5 5 0 0 0 12 20.1l1.1-1.1"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  shield: '<path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  star: '<path d="m12 2 2.7 7.3L22 12l-7.3 2.7L12 22l-2.7-7.3L2 12l7.3-2.7L12 2Z"/><path d="M12 7v10M7 12h10"/>',
  location: '<path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
};
const icon = (name, cls = '') => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.info}</svg>`;
const mark = `<span class="brand-mark" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none"><path d="M8 24.5 15.7 7l7.8 17.5M10.7 18.4h10.6" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round"/><path d="m24.5 5 .9 2.6L28 8.5l-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9.9-2.6Z" fill="currentColor"/></svg></span>`;

const state = {
  page: 'home',
  menuOpen: false,
  profileStep: 1,
  emailGenerated: false,
  emailSent: false,
  extensionAnalyzed: false,
  extensionFilled: false,
  sourceFormOpen: false,
  sources: [],
  alertFilter: 'New matches',
  profileTab: 'Overview',
};

const navItems = [
  ['home', 'Home', 'home'],
  ['applications', 'Applications', 'briefcase'],
  ['email', 'Email', 'mail'],
  ['alerts', 'Job alerts', 'radar'],
  ['profile', 'Profile', 'user'],
];

function navButton(page, label, iconName, active = false) {
  return `<button class="nav-item ${active ? 'active' : ''}" data-go="${page}" ${active ? 'aria-current="page"' : ''}>${icon(iconName)}<span>${label}</span></button>`;
}

function sidebar() {
  return `<aside class="sidebar ${state.menuOpen ? 'open' : ''}" id="sidebar" aria-label="Main navigation">
    <a class="brand" href="#home" data-go="home">${mark}<span><span class="brand-name">aster</span><span class="brand-tagline">Career workspace</span></span></a>
    <p class="nav-label">Workspace</p>
    <nav class="nav-group">${navItems.map(([page, label, glyph]) => navButton(page, label, glyph, state.page === page)).join('')}</nav>
    <div class="nav-divider"></div>
    <p class="nav-label">Tools</p>
    <div class="nav-group">${navButton('extension', 'Browser extension', 'spark', state.page === 'extension')}</div>
    <div class="nav-spacer"></div>
    <div class="sidebar-tip"><div class="sidebar-tip-title">${icon('shield')} Your decisions stay yours</div><p>Aster prepares a draft. You review it and take every final action.</p></div>
    <div class="nav-group">${navButton('settings', 'Settings', 'settings', state.page === 'settings')}</div>
    <div class="account"><span class="avatar" aria-hidden="true">JM</span><span><span class="account-name">Jordan Morgan</span><span class="account-caption">Design preview</span></span><button class="account-menu" aria-label="View sign-in screen preview" data-go="signin">${icon('more')}</button></div>
  </aside>`;
}

function topbar() {
  const names = {home:'Home', applications:'Applications', email:'Email studio', alerts:'Job alerts', profile:'Profile', extension:'Browser extension', settings:'Settings', notifications:'Notifications', onboarding:'Set up your profile'};
  return `<header class="topbar">
    <div style="display:flex;align-items:center;gap:10px;min-width:0">
      <button class="icon-button mobile-menu" aria-label="Open navigation" aria-expanded="${state.menuOpen}" data-action="menu">${icon('menu')}</button>
      <div class="crumb"><span>Workspace</span><span class="crumb-sep">/</span><strong>${names[state.page] || 'Home'}</strong></div>
    </div>
    <div class="top-actions"><button class="icon-button" aria-label="Notifications" data-go="notifications">${icon('bell')}<span class="unread-dot" aria-hidden="true"></span></button><span class="avatar" aria-hidden="true">JM</span></div>
  </header>`;
}

function pageHead(eyebrow, title, copy, action = '') {
  return `<div class="page-head"><div class="page-head-copy"><p class="eyebrow">${eyebrow}</p><h1>${title}</h1>${copy ? `<p class="subhead">${copy}</p>` : ''}</div>${action}</div>`;
}

function homePage() {
  return `${pageHead('Your career workspace', 'Good morning, Jordan.', 'A clear place to prepare applications, keep track, and find your next opportunity.')}
    <section class="panel home-intro" aria-labelledby="welcome-title">
      <div class="home-intro-copy"><p class="eyebrow">A good place to begin</p><h2 id="welcome-title" style="font-size:21px">Build your profile once.<br>Use it when you’re ready.</h2><p class="subhead">Add your experience and résumé so Aster can prepare more relevant drafts. You can skip anything and come back later.</p><div class="home-intro-actions"><button class="button" data-go="onboarding">Complete your profile ${icon('arrow')}</button><button class="button secondary" data-go="extension">See how autofill works</button></div></div>
      <div class="guide-graphic" aria-hidden="true"><span class="orbit-dot one"></span><span class="orbit-dot two"></span><span class="guide-star">${icon('star')}</span></div>
    </section>
    <div class="home-columns">
      <section class="panel getting-started" aria-labelledby="steps-heading"><div class="panel-head"><div><p class="eyebrow">Start at your pace</p><h2 id="steps-heading">Your next steps</h2></div><span class="badge neutral">0 of 3 complete</span></div><div class="step-list">
        <button class="step-row" data-go="onboarding"><span class="step-number">1</span><span><span class="step-name">Add your profile and résumé</span><span class="step-description">Share experience you want to reuse.</span></span><span class="step-arrow">›</span></button>
        <button class="step-row" data-go="extension"><span class="step-number">2</span><span><span class="step-name">Prepare your first application</span><span class="step-description">Review drafts before they go anywhere.</span></span><span class="step-arrow">›</span></button>
        <button class="step-row" data-go="alerts"><span class="step-number">3</span><span><span class="step-name">Follow a few career pages</span><span class="step-description">Optional daily checks for new roles.</span></span><span class="step-arrow">›</span></button>
      </div></section>
      <section class="panel application-empty" aria-labelledby="applications-empty-title"><span class="feature-icon">${icon('briefcase')}</span><p class="eyebrow">Applications</p><h2 id="applications-empty-title">Nothing here yet</h2><p>Applications appear after you prepare a form or confirm that you sent an email.</p><a href="#applications" class="inline-link" data-go="applications">View applications ${icon('arrow')}</a></section>
    </div>
    <section class="panel note-row"><span class="note-icon">${icon('clock')}</span><div><strong>Job alerts are optional</strong><p>Add a public careers page whenever you’re ready. You choose the daily check time and timezone.</p></div><button class="button secondary small" data-go="alerts">Set up alerts</button></section>`;
}

function emptyCard(iconName, title, copy, buttonLabel, target) {
  return `<section class="panel empty-card"><div class="empty-card-inner"><div class="job-empty-graphic" aria-hidden="true"><svg viewBox="0 0 90 80" fill="none"><path d="M12 61c16-32 47-48 67-37M16 67c18-20 39-27 60-24" stroke="#d9e6dc" stroke-width="1.4" stroke-linecap="round"/><circle cx="24" cy="48" r="4" fill="#88ad91"/><circle cx="68" cy="30" r="3.5" fill="#c6a575"/><rect x="32" y="31" width="27" height="27" rx="9" fill="white" stroke="#c9dbce"/><path d="m45.5 36 2.3 6.2L54 44.5l-6.2 2.3-2.3 6.2-2.3-6.2-6.2-2.3 6.2-2.3 2.3-6.2Z" stroke="#4e805e" stroke-width="1.4" stroke-linejoin="round"/></svg></div><h2>${title}</h2><p>${copy}</p><button class="button secondary small" data-go="${target}">${buttonLabel} ${icon('arrow')}</button></div></section>`;
}

function applicationsPage() {
  return `${pageHead('Your history', 'Applications', 'See what you prepared, what you submitted, and what still needs your attention.', `<button class="button" data-go="extension">Prepare an application ${icon('arrow')}</button>`)}
    <div class="segmented" role="group" aria-label="Application filters" style="margin-bottom:14px"><button aria-pressed="true">All</button><button aria-pressed="false">In progress</button><button aria-pressed="false">Applied</button><button aria-pressed="false">Follow-up</button></div>
    ${emptyCard('briefcase','Your application list is ready when you are','A job you discover or a draft you prepare will not appear as an application until you take the next step.','Learn about autofill','extension')}
    <p class="fine-print">A submission attempt and a confirmed application are shown as different statuses.</p>`;
}

function profilePage() {
  const tabs = ['Overview', 'Experience', 'Documents', 'AI providers'];
  const tabMarkup = tabs.map((tab) => `<button data-profile-tab="${tab}" aria-current="${state.profileTab === tab ? 'page' : 'false'}">${tab}</button>`).join('');
  const content = state.profileTab === 'Documents' ? `<div class="panel panel-pad"><div class="section-title"><h2>Your documents</h2><p>Documents stay private. Extracted details remain suggestions until you confirm them.</p></div><div class="file-drop"><span class="feature-icon">${icon('upload')}</span><div class="file-drop-copy"><div class="file-drop-title">Add a résumé or CV</div><div class="file-drop-help">PDF or DOCX · private to your account</div></div><button class="button secondary small" data-action="preview">Choose file</button></div><div class="list-row section-gap"><span class="doc-mark">PDF</span><span class="list-row-main"><span class="list-row-title">LinkedIn profile PDF</span><span class="list-row-copy">Optional · Add when useful</span></span><button class="button quiet small" data-action="preview">Add</button></div><div class="list-row"><span class="doc-mark">DOC</span><span class="list-row-main"><span class="list-row-title">Current cover letter</span><span class="list-row-copy">Optional · Helps match your writing style</span></span><button class="button quiet small" data-action="preview">Add</button></div></div>` : state.profileTab === 'AI providers' ? `<div class="panel panel-pad"><div class="section-title"><h2>AI provider keys</h2><p>Connect a provider only if you want AI-assisted drafts. Your key stays masked after saving.</p></div><div class="callout">${icon('info')}<span>Provider use may send selected job text and relevant confirmed profile facts. Review each provider’s processing terms and your key settings.</span></div><div class="list-row section-gap"><span class="provider-icon">O</span><span class="list-row-main"><span class="list-row-title">OpenRouter · DeepSeek V4 Flash</span><span class="list-row-copy">Not connected</span></span><button class="button secondary small" data-action="preview">Add key</button></div><div class="list-row"><span class="provider-icon">X</span><span class="list-row-main"><span class="list-row-title">Grok by xAI</span><span class="list-row-copy">Optional provider</span></span><button class="button secondary small" data-action="preview">Add key</button></div><div class="list-row"><span class="provider-icon">G</span><span class="list-row-main"><span class="list-row-title">Gemini</span><span class="list-row-copy">Optional provider</span></span><button class="button secondary small" data-action="preview">Add key</button></div><p class="fine-print">Saved keys are required only for unattended daily job checks. Fallback requires your explicit consent.</p></div>` : state.profileTab === 'Experience' ? `<div class="panel panel-pad"><div class="section-title"><h2>Experience and preferences</h2><p>Add information you want to reuse. You can leave any field blank.</p></div><div class="form-grid"><div class="field"><label for="role-title">Preferred role</label><input class="input" id="role-title" placeholder="e.g. Product designer"></div><div class="field"><label for="location">Preferred location</label><input class="input" id="location" placeholder="e.g. Remote or Karachi"></div><div class="field full"><label for="experience-text">Experience, projects, or skills</label><textarea class="textarea" id="experience-text" placeholder="Add a role, project, skill, or result in your own words…"></textarea></div><div class="field full"><label for="writing-notes">Writing notes <span class="field-help">Optional</span></label><textarea class="textarea" id="writing-notes" placeholder="How you like applications to sound…"></textarea></div></div><button class="button" data-action="preview">Save changes</button><p class="fine-print">Changes are not saved in this design preview.</p></div>` : `<div class="two-col"><section class="panel panel-pad"><div class="panel-head"><div><p class="eyebrow">Contact</p><h2>Personal details</h2></div><button class="button quiet small" data-action="preview">Edit</button></div><p class="panel-copy" style="margin:13px 0 0">Add the details you want available for applications. Sensitive details are optional and only used when you choose.</p><div class="list-row section-gap"><span class="list-row-main"><span class="list-row-title">Name and contact</span><span class="list-row-copy">Not added yet</span></span><span class="badge neutral">Optional</span></div><div class="list-row"><span class="list-row-main"><span class="list-row-title">Profile links</span><span class="list-row-copy">LinkedIn, portfolio, or personal site</span></span><span class="badge neutral">Optional</span></div></section><section class="panel panel-pad"><div class="panel-head"><div><p class="eyebrow">Documents</p><h2>Keep your context together</h2></div><span class="feature-icon" style="margin:0">${icon('document')}</span></div><p class="panel-copy" style="margin:13px 0 16px">Résumé first; a LinkedIn PDF and cover letter can be added later.</p><button class="button secondary small" data-profile-tab="Documents">View documents ${icon('arrow')}</button></section></div><section class="panel panel-pad section-gap"><div class="panel-head"><div><p class="eyebrow">Your facts</p><h2>Only confirmed details are used</h2></div><span class="badge neutral">No facts yet</span></div><p class="panel-copy" style="margin:9px 0 0">When Aster reads a document, you review each suggested fact and confirm what is correct before it can support an answer.</p><button class="button quiet small" style="margin-top:7px" data-profile-tab="Experience">Add experience ${icon('arrow')}</button></section>`;
  return `${pageHead('Your context', 'Profile', 'Give Aster the background you want to reuse. Nothing is required to get started.')}
    <div class="subnav" aria-label="Profile sections">${tabMarkup}</div>${content}`;
}

function emailPage() {
  const primary = state.emailGenerated ? `<button class="button" data-action="open-gmail">Open in Gmail ${icon('arrow')}</button>` : `<button class="button" data-action="generate-email">Prepare a draft ${icon('arrow')}</button>`;
  const preview = state.emailGenerated ? `<section class="panel panel-pad section-gap"><div class="panel-head"><div><p class="eyebrow">Draft for your review</p><h2>Check every detail before opening Gmail</h2></div><span class="badge neutral">Not sent</span></div><div class="field"><label>To</label><input class="input" value="recruiting@example.com"></div><div class="field"><label>Subject</label><input class="input" value="Application — Product Designer"></div><div class="field"><label>Message</label><textarea class="textarea">Hello hiring team,\n\nI’m interested in the Product Designer role. My experience with product design and simplifying onboarding flows is relevant to the work described. I’d be glad to share more about my projects and approach.\n\nThank you for your time,\nJordan</textarea></div><div class="callout">${icon('info')}<span>This example is illustrative, not generated from your profile. Review claims and add your résumé in Gmail before sending.</span></div><div class="onboard-footer"><button class="button secondary small" data-action="copy-draft">Copy message</button><button class="button small" data-action="open-gmail">Open in Gmail ${icon('arrow')}</button></div><p class="fine-print">Opening Gmail does not send the message. After sending, return and confirm it here.</p></section>` : '';
  return `${pageHead('Email applications', 'Write a thoughtful first draft.', 'Add the role details and choose what context to include. You stay in charge of the final message.')}
    <section class="panel panel-pad"><div class="panel-head"><div><p class="eyebrow">New email</p><h2>Tell us about the opportunity</h2><p class="panel-copy" style="margin:5px 0 0">A few details help shape a useful, specific draft.</p></div><span class="stepper-num">1</span></div><div class="form-grid section-gap"><div class="field"><label for="email-recipient">Recipient email</label><input class="input" id="email-recipient" type="email" placeholder="recruiter@company.com"></div><div class="field"><label for="email-company">Company</label><input class="input" id="email-company" placeholder="Company name"></div><div class="field"><label for="email-role">Role</label><input class="input" id="email-role" placeholder="Job title"></div><div class="field"><label for="email-context">Resume or project context</label><select class="select" id="email-context"><option>Choose later</option><option>Résumé</option><option>Product design project</option></select></div><div class="field full"><label for="email-description">Job description or key points</label><textarea class="textarea" id="email-description" placeholder="Paste the most relevant parts of the job opening…"></textarea></div><div class="field full"><label for="email-note">Starting message <span class="field-help">Optional</span></label><textarea class="textarea" id="email-note" style="min-height:82px" placeholder="Add anything you want the draft to include…"></textarea></div></div><div class="callout">${icon('shield')}<span>Your message is an editable draft. Aster will not open Gmail, attach files, or send until you choose the next action.</span></div><div class="onboard-footer"><span class="fine-print" style="margin:0">No Gmail connection needed.</span>${primary}</div></section>${preview}`;
}

function alertsPage() {
  const sourceForm = state.sourceFormOpen ? `<div class="source-form section-gap"><div class="form-grid"><div class="field full"><label for="source-url">Public careers page URL</label><input class="input" id="source-url" type="url" placeholder="https://company.com/careers"></div><div class="field"><label for="source-role">Role keywords</label><input class="input" id="source-role" placeholder="Product designer"></div><div class="field"><label for="source-timezone">Time zone</label><select class="select" id="source-timezone"><option>Asia/Karachi</option><option>Europe/London</option><option>America/New_York</option></select></div></div><div class="onboard-footer"><span class="fine-print" style="margin:0">Preview only · no site will be checked.</span><div style="display:flex;gap:8px"><button class="button secondary small" data-action="cancel-source">Cancel</button><button class="button small" data-action="save-source">Add source</button></div></div></div>` : '';
  const sourceRows = state.sources.map((source) => `<div class="list-row"><span class="feature-icon" style="margin:0">${icon('link')}</span><span class="list-row-main"><span class="list-row-title">${escapeHtml(source.host)}</span><span class="list-row-copy">${escapeHtml(source.url)} · Preview only</span></span><span class="badge neutral">Not checked</span></div>`).join('');
  return `${pageHead('A quieter way to keep looking', 'Job alerts', 'Follow a few public career pages. Aster checks them at a time you choose and brings back relevant new roles.', `<button class="button" data-action="add-source">${icon('plus')} Add a source</button>`)}
    <section class="panel digest"><div><p class="eyebrow">Your daily check</p><h2 class="digest-title">A small update, when there’s something new.</h2><p class="digest-copy">Choose your time zone. Results appear here; they never count as applications.</p></div><div class="time-display"><strong>9:00 AM</strong><span>Asia / Karachi</span></div></section>
    <div class="home-columns" style="margin-top:17px"><section class="panel panel-pad"><div class="panel-head"><div><p class="eyebrow">Sources you follow</p><h2>Career pages</h2></div><span class="badge neutral">${state.sources.length} of 5</span></div>${state.sources.length ? sourceRows : `<div class="list-row section-gap"><span class="feature-icon" style="margin:0">${icon('radar')}</span><span class="list-row-main"><span class="list-row-title">Not following a source yet</span><span class="list-row-copy">Add a company’s public jobs page to get started.</span></span><button class="button secondary small" data-action="add-source">Add URL</button></div>`}${sourceForm}<div class="field section-gap"><label for="alert-roles">Roles you’re looking for</label><input class="input" id="alert-roles" placeholder="Product designer, UX researcher…"></div><div class="field"><label for="alert-location">Locations or work style</label><input class="input" id="alert-location" placeholder="Remote, Karachi…"></div><div class="callout warning">${icon('info')}<span>Background checks need an enabled provider key and your explicit consent. Sources that need sign-in or a CAPTCHA aren’t supported.</span></div></section>
      <section><div class="section-title"><p class="eyebrow">New matches</p><h2>Nothing to review yet</h2><p>Matches show here after a source check. Each role includes its source and why it matched.</p></div>${emptyCard('radar','Your next opportunity will show up here','Add a public career page to start a daily check. You can pause or remove any source later.','Add a source','alerts')}</section></div>
    <p class="fine-print">Checks run while you’re away only after you enable scheduled checks and saved-key processing. Last check and next check will be shown here.</p>`;
}

function extensionPage() {
  return `${pageHead('On the job form', 'Review first. Submit yourself.', 'Aster reads the current form, prepares answers from confirmed facts, and waits for your review.')}
    <div class="callout section-gap" style="margin-bottom:15px">${icon('info')}<span>This is a sample job form. Names, projects, and answer text below are illustrative examples, not user data.</span></div>
    <div class="browser-demo"><section class="mock-browser" aria-label="Sample job application"><div class="browser-chrome"><i></i><i></i><i></i><span class="browser-address">northwind.example/jobs/product-designer</span></div><div class="mock-job"><span class="mock-company">NORTHWIND STUDIO</span><h2>Product designer</h2><p class="mock-job-summary">Work with a small product team to make clear, useful tools. Help improve onboarding and collaborate with engineering and research.</p><label class="mock-question">Your name</label><div class="mock-input ${state.extensionFilled ? 'filled' : ''}" id="mock-name">${state.extensionFilled ? 'Jordan Morgan' : 'Type your answer'}</div><label class="mock-question">Why are you interested in this role?</label><div class="mock-input ${state.extensionFilled ? 'filled' : ''}" id="mock-answer" style="min-height:58px">${state.extensionFilled ? 'I’m interested in the role’s focus on thoughtful product work and improving onboarding.' : 'Write a response'}</div><label class="mock-question">Work authorization</label><div class="mock-input">Choose an option — answer yourself</div></div></section>
      <section class="extension-panel" aria-label="Aster browser extension preview"><div class="extension-header">${mark}<strong>Aster for Chrome</strong><span class="extension-demo-label">PREVIEW</span></div><div class="extension-body"><div class="extension-job"><div><strong>Product designer</strong><span>Northwind Studio · Sample profile</span></div><span class="badge ${state.extensionAnalyzed ? 'attention' : 'neutral'}"><span class="badge-dot"></span>${state.extensionAnalyzed ? '2 suggestions' : 'Form found'}</span></div><div class="extension-notice">${icon('info')}<span>${state.extensionAnalyzed ? 'Two example drafts are ready. Work authorization stays for you to answer.' : 'Review the job and selected profile context before analysis.'}</span></div>${state.extensionAnalyzed ? `<div class="answer"><div class="answer-head"><strong>Your name</strong><span class="answer-source">Profile example</span></div><textarea aria-label="Draft answer for name">Jordan Morgan</textarea></div><div class="answer"><div class="answer-head"><strong>Why this role?</strong><span class="answer-source">Project example</span></div><textarea aria-label="Draft answer for interest">I’m interested in the role’s focus on thoughtful product work and improving onboarding.</textarea></div>` : ''}<div class="extension-actions">${state.extensionAnalyzed ? `<button class="button secondary" data-action="reset-extension">Edit context</button><button class="button" data-action="apply-answers">Apply 2 answers</button>` : `<button class="button" data-action="analyze">Analyze this job</button>`}</div><p class="extension-foot">Aster never clicks Submit or accepts legal declarations for you. Check every answer and attach your résumé yourself.</p></div></section></div>
    ${state.extensionFilled ? `<section class="panel note-row section-gap"><span class="note-icon">${icon('check')}</span><div><strong>Example answers placed in the sample form</strong><p>This preview does not submit the form or create an application record.</p></div></section>` : ''}`;
}

function notificationsPage() {
  return `${pageHead('Stay in the loop', 'Notifications', 'Useful updates in one place. You control background checks and their schedule.')}${emptyCard('bell','You’re all caught up','New role matches, source issues, and account updates will appear here when there is something to review.','Set up job alerts','alerts')}`;
}

function settingsPage() {
  return `${pageHead('Preferences and privacy', 'Settings', 'A few clear controls for how Aster looks and works.')}
    <div class="two-col"><section class="panel panel-pad"><p class="eyebrow">Appearance</p><h2>Simple by default</h2><p class="panel-copy">Aster uses a quiet light palette with readable contrast. A dark theme can be added after the whole experience is validated.</p><div class="list-row section-gap"><span class="list-row-main"><span class="list-row-title">Color theme</span><span class="list-row-copy">Sage & ink · Light</span></span><span class="badge">Default</span></div></section><section class="panel panel-pad"><p class="eyebrow">Daily checks</p><h2>Your local time</h2><p class="panel-copy">Choose when enabled public job sources should be checked.</p><div class="field"><label for="timezone">Time zone</label><select class="select" id="timezone"><option>Asia/Karachi</option><option>Europe/London</option><option>America/New_York</option></select></div><div class="field"><label for="check-time">Check time</label><input class="input" id="check-time" type="time" value="09:00"></div><p class="fine-print">Changing schedule is a preview only. No checks run from this page.</p></section></div>
    <section class="panel panel-pad section-gap"><p class="eyebrow">Your information</p><h2>You can review and remove what you add</h2><p class="panel-copy">The full product will show what profile facts, documents, AI keys, applications, and alerts are stored, along with export and deletion controls.</p><button class="button secondary small" data-action="preview">Review privacy controls</button></section>`;
}

function signInPage() {
  return `<main class="auth-shell"><section class="auth-aside"><a class="brand" href="#home" data-go="home">${mark}<span><span class="brand-name">aster</span><span class="brand-tagline">Career workspace</span></span></a><p class="eyebrow">Your career, in motion</p><h1>Your next step,<br>made clearer.</h1><p>Keep your experience close. Prepare applications with care. Know what happens next.</p><div class="auth-art" aria-hidden="true"><span class="guide-star">${icon('star')}</span><span class="orbit-dot one"></span><span class="orbit-dot two"></span></div></section><section class="auth-main"><div class="auth-card"><p class="eyebrow">Welcome back</p><h2>Sign in to Aster</h2><p class="panel-copy">Pick up where you left off.</p><div class="field section-gap"><label for="signin-email">Email address</label><input class="input" id="signin-email" type="email" placeholder="you@example.com"></div><div class="field"><label for="signin-password">Password</label><input class="input" id="signin-password" type="password" placeholder="Your password"></div><button class="inline-link auth-forgot" data-action="preview">Forgot password?</button><button class="button auth-submit" data-action="preview">Sign in</button><p class="auth-switch">New to Aster? <button class="inline-link" data-go="onboarding">Create an account</button></p><p class="fine-print">Sign-in is not connected in this design preview.</p><button class="button quiet small" data-go="home">Back to preview</button></div></section></main>`;
}

function onboardingPage() {
  const steps = ['Basics', 'Experience', 'Documents', 'AI setup'];
  const i = state.profileStep - 1;
  const body = i === 0 ? `<h2>Start with the basics</h2><p class="panel-copy">Use only details you want available when preparing an application.</p><div class="form-grid section-gap"><div class="field"><label for="on-name">Your name</label><input class="input" id="on-name" placeholder="Full name"></div><div class="field"><label for="on-email">Email address</label><input class="input" id="on-email" type="email" placeholder="you@example.com"></div><div class="field"><label for="on-phone">Phone <span class="field-help">Optional</span></label><input class="input" id="on-phone" placeholder="Phone number"></div><div class="field"><label for="on-linkedin">LinkedIn or portfolio <span class="field-help">Optional</span></label><input class="input" id="on-linkedin" placeholder="Profile link"></div></div><div class="callout section-gap">${icon('shield')}<span>Optional personal details stay optional. You can skip them and still use Aster.</span></div>` : i === 1 ? `<h2>What have you worked on?</h2><p class="panel-copy">Add experience, education, projects, skills, or preferences in your own words.</p><div class="form-grid section-gap"><div class="field"><label for="on-role">Preferred role</label><input class="input" id="on-role" placeholder="Product designer"></div><div class="field"><label for="on-location">Location or work style</label><input class="input" id="on-location" placeholder="Remote, Karachi…"></div><div class="field full"><label for="on-exp">Experience and projects</label><textarea class="textarea" id="on-exp" placeholder="A role, project, skill, or result you want to remember…"></textarea></div><div class="field full"><label for="on-notes">Application notes <span class="field-help">Optional</span></label><textarea class="textarea" id="on-notes" style="min-height:82px" placeholder="How you like applications to sound…"></textarea></div></div>` : i === 2 ? `<h2>Add the documents you choose</h2><p class="panel-copy">A résumé is a useful place to start. Documents are private, and extracted details need your review.</p><div class="file-drop section-gap"><span class="feature-icon">${icon('upload')}</span><div class="file-drop-copy"><div class="file-drop-title">Résumé or CV</div><div class="file-drop-help">PDF or DOCX · You can skip this step</div></div><button class="button secondary small" data-action="preview">Choose file</button></div><div class="list-row section-gap"><span class="doc-mark">PDF</span><span class="list-row-main"><span class="list-row-title">LinkedIn profile PDF</span><span class="list-row-copy">Optional supporting context</span></span><button class="button quiet small" data-action="preview">Add</button></div><div class="list-row"><span class="doc-mark">DOC</span><span class="list-row-main"><span class="list-row-title">Current cover letter</span><span class="list-row-copy">Optional writing-style context, not proof of facts</span></span><button class="button quiet small" data-action="preview">Add</button></div>` : `<h2>AI help is optional</h2><p class="panel-copy">Connect a provider key if you want help drafting answers. You can skip this and come back later.</p><div class="callout section-gap">${icon('info')}<span>When you ask for a draft, selected job text and relevant confirmed facts may be sent to the provider you choose. Daily checks also need a saved-key choice and separate consent.</span></div><div class="provider-card section-gap"><span class="provider-icon">O</span><span><span class="provider-title">OpenRouter · DeepSeek V4 Flash</span><span class="provider-copy">Add a key in Profile when ready</span></span><span class="badge neutral">Optional</span></div><div class="provider-card section-gap"><span class="provider-icon">X</span><span><span class="provider-title">Grok by xAI</span><span class="provider-copy">Another provider option</span></span><span class="badge neutral">Optional</span></div><div class="provider-card section-gap"><span class="provider-icon">G</span><span><span class="provider-title">Gemini</span><span class="provider-copy">Another provider option</span></span><span class="badge neutral">Optional</span></div>`;
  return `${pageHead('A few quick steps', 'Set up your profile', 'Skip any step. You can review or change these details later.')}
    <div class="stepper" aria-label="Profile setup progress">${steps.map((name, idx) => `<div class="stepper-step ${idx === i ? 'active' : ''} ${idx < i ? 'done' : ''}"><span class="stepper-num">${idx < i ? '✓' : idx + 1}</span><span>${name}</span></div>${idx < steps.length - 1 ? '<span class="stepper-line"></span>' : ''}`).join('')}</div>
    <section class="panel panel-pad"><div>${body}</div><div class="onboard-footer"><button class="button quiet small" data-action="skip-onboarding">Skip setup</button><div style="display:flex;gap:8px">${i > 0 ? '<button class="button secondary small" data-action="prev-step">Back</button>' : ''}<button class="button small" data-action="next-step">${i === 3 ? 'Finish setup' : 'Continue'} ${icon('arrow')}</button></div></div></section>`;
}

function render() {
  const pages = { home: homePage, applications: applicationsPage, email: emailPage, alerts: alertsPage, profile: profilePage, extension: extensionPage, notifications: notificationsPage, settings: settingsPage, onboarding: onboardingPage };
  const body = (pages[state.page] || homePage)();
  if (state.page === 'signin') {
    document.getElementById('app').innerHTML = signInPage();
    bindControls();
    return;
  }
  document.getElementById('app').innerHTML = `<div class="app-shell">${sidebar()}<div class="drawer-backdrop ${state.menuOpen ? 'open' : ''}" data-action="close-menu"></div><main class="workspace">${topbar()}<div class="content">${body}</div></main></div>`;
  bindControls();
}

let toastTimer;
function showToast(message) {
  const el = document.getElementById('toast');
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}

function go(page) {
  state.page = page;
  state.menuOpen = false;
  window.location.hash = page === 'home' ? '' : page;
  render();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function bindControls() {
  document.querySelectorAll('[data-go]').forEach((el) => el.addEventListener('click', (event) => {
    event.preventDefault();
    go(el.dataset.go);
  }));
  document.querySelectorAll('[data-profile-tab]').forEach((el) => el.addEventListener('click', () => {
    if (el.dataset.profileTab) state.profileTab = el.dataset.profileTab;
    render();
  }));
  document.querySelectorAll('[data-action]').forEach((el) => el.addEventListener('click', (event) => {
    event.preventDefault();
    const action = el.dataset.action;
    if (action === 'menu') { state.menuOpen = !state.menuOpen; render(); }
    else if (action === 'close-menu') { state.menuOpen = false; render(); }
    else if (action === 'preview') showToast('This control is illustrative. Data is not saved in the design preview.');
    else if (action === 'account') showToast('Account controls will be connected with sign-in in the application.');
    else if (action === 'add-source') {
      if (state.sources.length >= 5) showToast('This preview shows the five-source limit.');
      else { state.sourceFormOpen = true; render(); document.getElementById('source-url')?.focus(); }
    }
    else if (action === 'cancel-source') { state.sourceFormOpen = false; render(); }
    else if (action === 'save-source') {
      const field = document.getElementById('source-url');
      try {
        const parsed = new URL(field.value);
        if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('Only public web URLs can be shown here.');
        if (state.sources.some((source) => source.url === parsed.href)) throw new Error('This URL is already shown in the preview.');
        state.sources.push({ url: parsed.href, host: parsed.hostname });
        state.sourceFormOpen = false;
        render();
        showToast('Source added in this preview only. It was not checked or saved.');
      } catch (error) {
        showToast(error.message === 'This URL is already shown in the preview.' ? error.message : 'Enter a valid public careers page URL.');
      }
    }
    else if (action === 'analyze') { state.extensionAnalyzed = true; render(); }
    else if (action === 'reset-extension') { state.extensionAnalyzed = false; state.extensionFilled = false; render(); }
    else if (action === 'apply-answers') { state.extensionFilled = true; render(); }
    else if (action === 'generate-email') { state.emailGenerated = true; render(); }
    else if (action === 'open-gmail') showToast('Gmail handoff is not connected in this design preview. The draft has not been sent.');
    else if (action === 'copy-draft') showToast('Copy is illustrative in this preview.');
    else if (action === 'skip-onboarding') go('home');
    else if (action === 'prev-step') { state.profileStep = Math.max(1, state.profileStep - 1); render(); }
    else if (action === 'next-step') {
      if (state.profileStep < 4) { state.profileStep += 1; render(); }
      else { go('home'); showToast('Setup preview complete. Nothing was saved.'); }
    }
  }));
}

function initFromHash() {
  const page = window.location.hash.replace('#', '');
  const valid = ['home','applications','email','alerts','profile','extension','notifications','settings','onboarding','signin'];
  if (valid.includes(page)) state.page = page;
  render();
}

window.addEventListener('hashchange', initFromHash);
initFromHash();
