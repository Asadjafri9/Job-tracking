# Form/source compatibility contract

Desktop Chrome MV3, declared minimum 120; release evidence tests current and previous stable Chrome on macOS/Windows and records exact versions. English labels/questions initially. A user invokes one visible top-level form at a time; whole-site/ATS compatibility is never inferred from one field test.

| Pattern | Inspect/fill behavior |
| --- | --- |
| Native text/email/tel/URL/textarea | inspect and fill exact confirmed/drafted value with constraints |
| Native select/radio/checkbox/multi-select | inspect options; fill only exact known factual/preference option IDs |
| Native number/date | fill when format/meaning has tested mapping; otherwise manual |
| Tested React-controlled native inputs | use tested setters/events and verify post-render persistence |
| Repeated native education/experience groups | fill only unambiguous selected source/group ordering; no automatic row creation |
| Legal attestations/terms/consent/demographics | classify and highlight; never automatically accept/infer |
| Explicit employer/site policy says not to use AI in the application | leave the application manual; do not claim generic extraction/fill detects or honors this policy |
| Missing/ambiguous scoped facts | report needs_information; leave unchanged |
| Password/hidden/offscreen/disabled controls | exclude from extraction/fill |
| File upload | detect/remind selected document; manual attachment |
| Iframe/shadow root/rich custom widgets | report unsupported region; no guessing |
| Dynamic or replaced controls | invalidate/reinspect; bind fresh field/revision |
| Multi-step page | inspect current step; user clicks Next/Back |
| CAPTCHA/site auto-submit on input | unsupported/manual handoff |

Manifest: activeTab/scripting/storage/identity/sidePanel, exact API origin only; development localhost permission only in dev. No all_urls/debugger/Gmail host permissions/persistent career host access. Stable public manifest key per environment is not a secret; no private signing key in repo.

Form corpus ≥12 fixtures/100 controls: contact, labels/negation, select/radio/multi choices, sensitive declarations, known/missing factual answers, controlled accept/revert, dynamic/replaced fields, manual edit race, repeated groups, multiple login/search forms, iframe/shadow widgets, submit keyboard/pointer/invalid/native/SPA outcome, worker/navigation/offline replay. Include candidate Greenhouse/Lever native patterns but don't claim full vendor support. M0 reads ≥four permitted public forms/two hosts; actual fill tests use local/explicitly permitted controlled application environments. Beta requires two controlled environments completing the form journey.

Monitor sources: public rendered HTML/listing regions, JobPosting JSON-LD, RSS/Atom and evaluated public ATS endpoints. Start with permitted Greenhouse/Lever public feeds/API adapters plus generic structured HTML. JavaScript-only/authenticated/CAPTCHA sources are unsupported; arbitrary website guarantee is absent. Every adapter has empty/new/duplicate/changed/closed/partial/denied/error fixtures and safe-fetch tests. A generic page can require user-selected listing region; no unbounded crawl.

Gmail compose prefill is best-effort external UI, with copy/mailto fallback. App has no Gmail send/delivery observer. Browser popup/login/multiple-account/long-message paths are tested without sending email.

Coverage evidence lists exact host/pattern/date/browser and observed limits. Unsupported cases reduce coverage; they are never counted as successful fill/extraction. Adding a site/widget/source needs permitted fixture capture and regression evidence.
