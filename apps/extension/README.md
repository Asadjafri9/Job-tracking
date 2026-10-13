# Browser extension prototype

This Manifest V3 Chrome extension is a user-invoked form helper. It injects its reader only after the user opens the side panel and chooses **Inspect this page**. It inspects one selected visible top-level form, omits sensitive controls, reads only job text explicitly selected by the user, and does not access other tabs or persist page content. Login, profile retrieval, document upload, and provider connectivity are intentionally not implemented here.

## Build and test

Use Node.js 22 for the dependency-free scripts (the repository pins `>=22 <23`):

```sh
node --test apps/extension/test/*.test.mjs
node apps/extension/scripts/build.mjs --dev
```

The development build is written to the ignored `apps/extension/dist/development` directory. Its exact API permission is `http://127.0.0.1:18000/*`. A public development manifest key fixes the local unpacked ID at `digpnmcecpkodggeieillcjpfgpokgnk`; no private signing key is kept in the repository.

For a release build, supply an approved HTTPS API origin and release public manifest key:

```sh
node apps/extension/scripts/build.mjs --production --api-origin https://api.example.org --manifest-key BASE64_DER_PUBLIC_KEY
```

The output grants host access only to that one origin. Do not put a private signing key in the repository or command history.

## Load unpacked in Chrome

1. Build the development package.
2. Open `chrome://extensions`, enable Developer mode, and choose **Load unpacked**.
3. Select `apps/extension/dist/development` and check that the displayed ID is `digpnmcecpkodggeieillcjpfgpokgnk`.
4. Pin/open the extension side panel. Tab through its controls and confirm headings, field names, button labels, status announcements, and unsupported-page messages are available to assistive technology.
5. Open the extension's **Safe demo form**. Choose **Fill sample values**; confirm values appear and the page says no submission was made. There is no Submit control in the fixture.
6. Serve `apps/extension/test/fixtures` locally with `python3 -m http.server 4174 --bind 127.0.0.1 --directory apps/extension/test/fixtures`, then open `http://127.0.0.1:4174/manual-form.html`. This page has fictional fields, makes no network calls, and has no Submit control. **On this page, click the Rolevo toolbar button to activate and open the extension for that exact tab, then choose Inspect this page.** If you switch tabs, click Rolevo on the new tab before inspecting it. Chrome's `activeTab` access is temporary and is revoked when you navigate to a different origin. Confirm the name/email/select/radio fields are listed, values stay local, and a manual edit made after inspection remains unchanged. Stop the local server when finished. Do not test on a real application form until the project has a permitted controlled environment.

## Prototype limits

This build covers form inventory, bounded metadata, exact option matching, prototype native setters, explicit value review, post-render reversion checks, and passive trusted-event observation. A bare action is reported as an attempt with an unknown outcome; the extension does not infer success. Validation failures remain visible. It never calls a form submission API. Iframes, shadow-root widgets, hidden/offscreen controls, file uploads, CAPTCHA, custom rich controls, multi-step navigation, and unsupported page schemes remain manual.

The automated suite tests pure schemas/setters/observer behavior and static manifest constraints. It does not replace the browser install checklist, a11y review, vendor compatibility corpus, or extension behavior on a live site. A separate read-only public-form structure inspection is recorded in `docs/evidence/EXT-003.md`; it did not load this extension or interact with any form.
