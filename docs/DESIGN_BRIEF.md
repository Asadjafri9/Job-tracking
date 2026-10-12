# Aster — product design brief

**Status:** Proposed product and visual direction
**Scope:** Dashboard, Chrome extension, onboarding, application/email flows, and job alerts
**Product stack:** React + FastAPI + PostgreSQL; deployment planning targets Azure. No Azure service or account is needed to make or review these design decisions.

## 1. Design intent

Aster should make a complicated job search feel like a short, understandable sequence of decisions. The product prepares useful work, explains what it did, and leaves consequential actions with the applicant. The user should always be able to answer three questions: **Where am I? What needs my attention? What happens if I continue?**

The product has three pillars, but they should not compete for attention on every screen:

1. **Prepare applications:** profile, job-form autofill, review, and honest application tracking.
2. **Write email applications:** make a grounded draft, review it, then hand off to Gmail or copy it.
3. **Find relevant openings:** monitor selected public career pages and summarize new matches.

The main experience is a calm work surface, not an AI chat. AI is a quiet assistant embedded at the moment it is useful. Show sources and uncertainty beside suggestions; never make a fluent answer look more certain than its supporting profile facts.

## 2. Users and experience principles

Design for a first-time applicant who may be short on time, unfamiliar with AI settings, and nervous about making a mistake on a real application. Also support repeat users who need to move quickly through a weekly routine.

- **Progressive disclosure:** ask for the minimum useful information first. Put provider keys, background checks, optional personal details, and advanced preferences behind a clearly named next step.
- **One main action per view:** make the likely next step visually clear. Use secondary links for less common actions; do not turn every feature into a dashboard card.
- **Calm confidence:** use plain status language and restrained visual emphasis. Use a small brand illustration for empty states and orientation, never as decoration competing with tasks.
- **Evidence before assertion:** distinguish saved facts, generated suggestions, user edits, submission attempts, confirmed applications, drafts, compose openings, and user-confirmed email sending.
- **User stays in control:** autofill never submits. Email is never sent by opening Gmail. The user can edit, undo, skip, or leave unknown answers unanswered.
- **Privacy at the decision point:** explain what profile or job information is sent immediately before the action that sends it; do not rely on a one-time blanket disclosure.
- **Consistent mental model:** the dashboard and extension share terminology, field provenance, status meaning, and visual tokens.

## 3. Brand and logo direction

### Name and promise

Keep **Aster** as the working product name. Brand idea: **a steady guide through a moving career path**. Suggested concise promise: **“Your next step, made clearer.”** The name and phrase need a separate trademark/domain check before public launch.

### Logo concept: “Guiding A”

Create a compact, original symbol from a single continuous path that forms a lowercase **a** and ends in a small four-point north star. It should suggest direction and forward motion without using a briefcase, robot, sparkle cloud, or generic checkmark. At small sizes, the letter and star endpoint must remain visually distinct. Use a simple geometric wordmark reading **aster** in lowercase beside the symbol. The current DGN-002 SVGs are proposals, not a final mark. A small supporting descriptor, if used in marketing, is “career workspace”; do not lock it into the small product logo.

Logo rules:

- Provide horizontal, symbol-only, monochrome, and reversed versions; the symbol must work at 16–24 px in the browser toolbar and extension header.
- Keep the path and star legible at small sizes; avoid tiny cutouts and fine strokes.
- Use the logo's green only as an identity accent; the entire interface should not be green.
- Validate distinctiveness, contrast, and trademark availability before treating this direction as final.

## 4. Visual system

### Recommended default: “Sage & ink”

Use a warm-white canvas, near-black ink, soft neutral dividers, and one muted botanical green for primary actions and active navigation. Add a small, warm amber only for attention states; reserve red for errors. Most surfaces remain neutral. The visual hierarchy comes from typography, spacing, and alignment rather than gradients, large shadows, or colorful cards.

Starting color tokens (refine and verify in contrast tests):

| Token | Starting value | Use |
| --- | --- | --- |
| `canvas` | `#F7F8F6` | App background |
| `surface` | `#FFFFFF` | Main content and cards |
| `ink` | `#202824` | Primary text |
| `muted` | `#66736C` | Supporting text |
| `line` | `#E3E8E4` | Dividers, input borders |
| `brand` | `#356D50` | Main action, active state, logo |
| `brand-soft` | `#EAF2ED` | Quiet selected/positive surface |
| `attention` | `#8A5A16` | Warning requiring a decision |
| `danger` | `#A33D36` | Error or destructive action |

Treat values as candidates, not a claim that every pairing already passes WCAG. Define semantic foreground/background pairings and test actual rendered states. Keep text contrast accessible in light and dark themes; never communicate success or failure through color alone.

### Type, shape, and graphic style

- Use a legible system sans-serif stack initially, with an optional licensed brand typeface only after localization and performance review. Use a restrained 1.2–1.3 heading scale; body text starts at 14–16 px, dense table labels never become tiny.
- Use a consistent 4/8 px spacing rhythm, 8–12 px control radii, one-pixel borders, and very light elevation only where it clarifies layering.
- Use simple, consistent outline icons with text labels for navigation. Do not use emoji as interface icons.
- Reserve larger graphic moments for onboarding, no-results states, and a daily job digest. Build these from a small set of quiet line shapes or “path / orbit / star” motifs. Keep data screens predominantly typographic.
- Avoid decorative gradients, oversized empty-state blobs, dense all-caps tracking, and multiple competing accent colors.

### Theme policy

Ship one default light theme first. Add a dark theme only when all core screens, extension states, charts, contrast, and operating-system preference behavior are specified and tested. Do not present three equally weighted themes during onboarding or split the product into different visual systems. If a theme control ships, place it in Settings and remember it per user.

## 5. Information architecture

Use a stable desktop sidebar with a small brand header and these five user-facing destinations:

1. **Home** — next action, recent application activity, a concise alert summary.
2. **Applications** — submitted/attempted application history and drafts with clearly separated status groups.
3. **Email** — prepared messages and explicit sent-confirmation follow-up.
4. **Job alerts** — saved public sources, next/last checks, matches and source health.
5. **Profile** — experience, documents, confirmed facts, and AI provider settings as a secondary section.

Place account, help/privacy, and appearance in a lower utility area or profile menu. Notifications use a bell/badge in the top bar and a dedicated inbox view, not another permanent top-level feature unless usability testing demonstrates a need.

The extension is contextual, not a miniature dashboard. It is centered on the current job form and presents only: detected job, readiness/unsupported state, **Analyze and autofill**, answers and evidence, unresolved items, **Apply answers**, and a reminder that the user must review and submit on the hiring site.

## 6. Main screens and behavior

### 6.1 Sign in

Keep sign-in focused: proposed brand, one-sentence product purpose, the hosted email/password/reset flow specified by the current Microsoft Entra External ID contract, and account-creation/reset actions. Avoid product metrics, AI promises, and dashboard preview clutter. On small viewports, use a single column. Explain account/data privacy on a short linked page. Entra External ID is a plan default pending owner confirmation; production identity configuration and UI must not imply that a tenant is provisioned.

### 6.2 First-run onboarding

Use a short, skippable, resumable sequence with a clear progress indicator. Save each step and show what is optional.

1. **Basics:** name and contact details; optional phone and profile links. Age/DOB are optional, purpose-scoped facts under the onboarding contract. Do not request them by default or infer them. Do not expose a collection/use flow until a specific supported purpose and disclosure are approved; otherwise omit the fields.
2. **Experience:** roles, skills, projects, education, preferred roles/locations, and concise application notes.
3. **Documents:** résumé first; LinkedIn-export PDF and existing cover letter optional. Show private-storage explanation, parse preview, source, and explicit confirmation for extracted facts. Never turn cover-letter style into proof of an accomplishment.
4. **AI setup (optional):** introduce provider choices in plain language. Let a user skip and continue with manual tools. Explain per-provider data routing, key storage, cost responsibility, fallback behavior, and that background monitoring needs saved-key consent. Ask for a key only when the user chooses to configure one.

After setup, land on a real empty Home screen. Never show seeded or fabricated activity as if it belonged to the user.

### 6.3 Home — useful first, quiet by default

First use contains a single welcome sentence and one primary next action: **Add your résumé** or **Complete your profile**, based on what is missing. A compact checklist can show profile, first application, and optional job alerts; collapse or remove completed steps. Below it show “No applications yet” with a short explanation and direct link to the extension setup. Job matches and application history are separate entities and sections.

For returning users, promote only actionable items: latest new matches, applications needing follow-up, a recent submission attempt needing confirmation, or a failed source check. Keep counts and a short activity list. Do not fill the screen with equal-sized pillar cards, fabricated charts, or a large time widget.

### 6.4 Profile and documents

Use a readable summary first, then grouped editable sections: Contact, Experience, Projects, Skills, Preferences, Notes, Documents, and AI providers. Show document status and extracted facts separately. Each fact displays its source (manual, résumé, LinkedIn PDF, etc.), last-confirmed date, and edit/confirm/remove actions. Optional sensitive facts are hidden by default and have specific purpose controls. Provider credentials show provider, masked suffix, status, last used, and remove/replace action—never the full key again.

### 6.5 Browser extension: analyze, fill, review

The side panel should use a concise vertical flow:

1. **Detected:** employer, role, and source URL with an Edit option; clearly say if the form or job description is incomplete.
2. **Analyze this job:** one explicit action and just-in-time notice describing which visible job text and selected profile facts will be sent to the chosen provider(s).
3. **Suggestions:** group answers by form section. Each suggestion shows a short source label and confidence/explanation when useful. Highlight missing evidence as **Needs your answer**; keep attestations, demographic and legal declarations manual. Never show opaque AI confidence percentages without calibration.
4. **Apply answers:** fill only supported fields/options and show per-field outcome. Keep a failed/unsupported field visibly untouched. Preserve user edits and current values.
5. **Review on the site:** durable reminder that Aster did not submit and the applicant should verify each answer, attach the résumé manually, and use the site's own submit button.

Do not add settings, key management, application history, or job-alert setup to the extension's primary flow. Offer a single “Open Aster” link for those tasks. On a recognized user submit, record **Submission attempted**; only a tested positive site signal or user confirmation changes it to **Applied**. Clearly expose uncertainty and validation failure.

Form writes expose values to the hiring page and its scripts before final submission. Explain this before the first fill and require the initiating user action; never imply values remain private until Submit. If a site auto-submits on input, classify it unsupported. The extension never triggers or prevents Submit/Next.

### 6.6 Application history

Provide a simple list/table with employer, role, date, channel, and plain-language status. Default view prioritizes actionable recent records; filters and search are secondary. Drafts and prepared form sessions remain separate from application records. The UI may summarize canonical application states with **Submission attempted**, **Applied**, and **Needs follow-up**; **Draft** and **Ready to review** describe drafts/sessions, not application statuses, while **Closed** is available only where supported by canonical state/history. A detail view shows a dated evidence timeline and the context/answer snapshot. A click on Submit is not a success claim. Discovered vacancies never appear as applications. The backend statuses and evidence rules in the PRD/API remain authoritative.

### 6.7 Email studio

Use a compact form with recipient, employer/role, job description, optional starting note, and selected résumé/project context. Generated subject/body remain an editable draft with evidence/source hints and missing-fact warnings. A review step displays the exact recipient and message plus an attachment reminder. Primary action: **Open in Gmail**; secondary actions: copy recipient/subject/body, open Gmail without prefill, or use mailto fallback. Do not request Gmail access. Opening the compose screen is **Compose opened**, not **Applied**; after return, ask “Did you send it?” and record only an explicit confirmation. Keep file attachment and Send with the user in Gmail.

### 6.8 Job alerts

Explain the feature in one sentence: Aster checks selected public career pages at the user's chosen local time. Setup adds one source at a time, up to the contract maximum of five, with a URL, parsing/support preview, role/location preferences, timezone, and explicit scheduled-check and saved-key/background-use consent. Only bounded public sources are supported; login, CAPTCHA, access denial, and JavaScript-only pages remain unsupported, with no bypass. Background matching receives job text and role/location preferences, not contact details, DOB, or private documents. Show source health, last success, next check, pause/remove, and a restrained **Check now** action. Separate **New matches** from **Applications**. A daily digest shows role, company, location if known, source link, discovery time, and one short reason it matched. If a scan is partial, unsupported, paused, or failed, say so; do not display “no jobs found” as if coverage were complete.

### 6.9 Notifications

Use a bell with a small unread count, plus a list with source, date, and direct action. Group related results into a digest rather than one alert per unchanged result. Offer readable empty, error, and permission-revoked states. The design plan targets daily checks at 9 a.m. local time, as specified in the implementation plan; users must see timezone and next-run time.

## 7. Content and state language

Use short verbs and describe what the system actually observed.

| Internal condition | User-facing wording |
| --- | --- |
| Form context incomplete | “We couldn’t confirm the role. Edit the job details before continuing.” |
| Generated answer grounded in fact | “Draft answer” + “Based on: [profile fact/project]” |
| Insufficient evidence | “Needs your answer” |
| Field could not be filled | “Not filled — this field needs a review on the job site.” |
| Submit click observed, no success proof | “Submission attempted — awaiting confirmation” |
| Site success evidence is verified | “Applied” + evidence and time |
| Gmail compose opened | “Email draft opened in Gmail” |
| User confirms sending | “Applied by email” + user confirmation/time |
| Monitoring failed or incomplete | “Last check didn’t finish” / “Some results may be missing” |

Avoid “AI completed your application,” “sent,” “success” without evidence, vague “smart” claims, and provider acronyms as default user copy.

## 8. Accessibility and responsive behavior

- Target WCAG 2.2 AA for all essential flows; validate text, control, status, focus, and selected-state contrast rather than relying on palette intuition.
- Full keyboard use, visible focus, semantic landmarks/headings, labels and errors announced by screen readers, reduced-motion support, zoom to 200%, and touch targets at least 24×24 CSS px (prefer 40–44 px for primary controls).
- Pair status colors with an icon and clear text. Do not encode selected answers or source health by color alone.
- At narrow widths, move navigation to a labeled compact menu, stack content in task order, keep the primary action reachable, and avoid horizontal scrolling for core forms. The Chrome panel must remain usable at narrow side-panel widths and with browser zoom.
- Do not use placeholder-only form labels. Announce autofill completion and per-field failures without stealing focus.

## 9. Motion, feedback, and empty/loading/error states

Keep motion under 200 ms for small transitions and honor reduced-motion settings. Use a simple progress indicator for analysis with status text; no animated robot or indefinite spinner. Preserve typed input on provider failure or navigation error. Every major view defines loading, empty, populated, partial, unsupported, offline, and permission-revoked states. Empty states give one explanatory sentence plus one useful action. Use meaningful illustrations sparingly; no large black circles or placeholder geometry.

## 10. Design validation and handoff

Before implementation, create low-to-high fidelity frames for desktop (1440 px), laptop (1280 px), narrow dashboard (390 px), and extension widths (360–420 px) for:

- Sign-in and four onboarding steps;
- empty and returning Home;
- profile, document parse/confirm, and provider settings;
- detected form, analyzing, suggestions, manual/unknown answer, fill result, and submission tracking;
- application list/detail/evidence;
- email draft/review/Gmail handoff/explicit sent confirmation;
- job-source setup, match digest, partial scan, failure and paused state;
- notification inbox and settings/privacy states.

Review prototypes with at least five representative job seekers before locking. Ask them to complete: set up a usable profile, prepare and review a job form without submitting, find out whether an application was confirmed, draft an email and open Gmail, and add a job-alert source. Observe hesitation and errors rather than asking only whether they like the colors. Refine the language and information hierarchy before component implementation.

Create design tokens and a small component library for navigation, buttons, inputs, status badges, empty states, notices, source chips, answer/evidence cards, tables, dialogs, and extension panel. Include all state variants, keyboard/focus behavior, content lengths, and React implementation notes. Run contrast checks and keyboard/screen-reader review; document unresolved issues. The design brief guides product design and does not claim these frames or tests exist yet.

## 11. Inspiration and applicable lessons

This direction takes structural inspiration rather than copying a brand:

- [Linear’s interface refresh](https://linear.app/changelog/2026-03-12-ui-refresh): consistent headers/navigation across workflows, calmer side navigation, clearer scanning.
- [Figma’s design-system foundations guide](https://www.figma.com/blog/design-systems-102-how-to-build-your-design-system/): treat color, type, iconography, dimensions, component reuse, and accessibility as one system.
- [Figma’s accessibility guide for design systems](https://www.figma.com/blog/the-future-of-design-systems-is-accessible/): bake keyboard, focus, contrast, target size, and responsive behavior into reusable patterns from the outset.

The product should feel as orderly as a well-designed productivity tool while making application evidence and AI boundaries more visible than a conventional task tracker. The result is an Aster-specific system, not a replica of these products.

## 12. Relationship to the implementation plan

This brief is the proposed design source of truth for visual language, information hierarchy, and screen behavior. `plan.md` and its active product/security contracts remain the implementation and engineering authority. Existing requirements for fact provenance, purpose-specific consent, manual attestations, user-controlled submission/sending, local-time job scans, safe public-source limits, and truthful tracking remain binding. The reconciliation and open owner decisions are recorded in `docs/DECISIONS.md` ADR-011 and [DGN-001 evidence](evidence/DGN-001.md). If later design changes conflict with `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/ONBOARDING.md`, `docs/AUTOFILL_TRACKING.md`, `docs/PROVIDERS.md`, `docs/EMAIL_APPLICATIONS.md`, `docs/JOB_MONITORING.md`, `docs/API.md`, or `docs/SECURITY_PRIVACY.md`, update both documents through a recorded product decision before code is implemented.

**Prototype status:** this direction is represented in `design-exploration/dist/` as a browser-only visual prototype, including an initial Guiding A logo mark and core screen flows. It has no product backend or persistence and does not represent a final approved brand. Validate the design with users and accessibility checks before adopting it in the React application.
