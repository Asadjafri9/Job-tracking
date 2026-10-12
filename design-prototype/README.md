# Aster browser-only design prototype

This static prototype makes the user journeys and key states in `docs/DESIGN_BRIEF.md` section 10 explorable without a backend. It is a design proposal; the name, logo, and identity experience remain provisional. Controls that would save, upload, authenticate, contact a provider, send an email, check a public source, write to an employer form, or delete data are disabled or only navigate to a clearly labeled example state.

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

`rendered/screens/` contains 42 Chromium screenshots for the journeys, three review contact sheets, and a `render-results.json` manifest. The manifest records route, viewport, page heading, body-content length, overflow result, and browser errors. Targets include 1440px and 1280px desktop screens, a 390px dashboard, and 360px/420px extension panels. Regenerate the individual screenshots with:

```sh
node design-prototype/scripts/render_prototype.mjs
```

The renderer uses local Chrome and a temporary profile; it does not contact external services. See `docs/evidence/DGN-003.md` for the captured results and review limitations. DGN-004 user validation and DGN-005 accessibility/handoff review are still separate tasks.
