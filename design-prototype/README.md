# Rolevo browser-only design prototype

This static Rolevo prototype makes the user journeys and key states in `docs/DESIGN_BRIEF.md` section 10 explorable without a backend. Rolevo is the owner-selected product name and the R mark is used across the prototype. Controls that would save, upload, authenticate, contact a provider, send an email, check a public source, write to an employer form, or delete data are disabled or only navigate to a clearly labeled example state.

## Open it

Open `index.html` in a modern browser. Choose screens from the `Explore view` menu, the four onboarding progress links, or the extension-state selector. Hash routes can also be opened directly; the route inventory is listed below.

## View coverage

| Journey | Selectable routes |
| --- | --- |
| Sign-in and setup | `#signin`, `#signin/forgot`, `#onboarding/basics`, `#onboarding/experience`, `#onboarding/documents`, `#onboarding/ai` |
| Home | `#home/empty`, `#home/returning` |
| Profile and providers | `#profile/summary`, `#profile/documents`, `#profile/providers` |
| Autofill extension | `#extension/detected`, `#extension/analyzing`, `#extension/suggestions`, `#extension/manual`, `#extension/filled`, `#extension/review`, `#extension/tracking` |
| Applications | `#applications/list`, `#applications/detail`, `#applications/evidence` |
| Email | `#email/draft`, `#email/review`, `#email/handoff`, `#email/confirm`, `#email/sent` |
| Job alerts | `#alerts/setup`, `#alerts/digest`, `#alerts/partial`, `#alerts/failure`, `#alerts/paused` |
| Notifications | `#notifications/inbox`, `#notifications/empty`, `#notifications/error`, `#notifications/revoked` |
| Privacy and settings | `#settings/privacy`, `#settings/export`, `#settings/deletion` |

All pages carry a sample-state banner. The email send confirmation, filled form and submission-attempt screens illustrate product behavior only; they do not perform those actions. No user data is stored or sent.

## Rendered review evidence

`rendered/screens/` contains 46 Chromium screenshots for the journeys and viewport checks, three earlier review contact sheets, and a `render-results.json` manifest. The manifest records route, viewport, page heading, body-content length, overflow result, and browser errors. Targets include 1440px and 1280px desktop screens, 390px/320px dashboards, and 360px/420px/320px extension panels. Regenerate the individual screenshots with:

```sh
node design-prototype/scripts/render_prototype.mjs
```

The renderer uses local Chrome and a temporary profile; it does not contact external services. Run `node scripts/audit_accessibility.mjs` for the 38-route keyboard, semantic, reduced-motion, control-name/target, and 320px reflow audit. See `docs/evidence/DGN-003.md` for the original capture and `docs/evidence/DGN-005.md` for updated accessibility evidence and limits. The owner waived the five-person DGN-004 study for M0; no research findings are claimed.
