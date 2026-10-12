# Proposed component-state library

Design review artifact for DGN-002; the HTML/CSS specimen is not imported into `apps/web`.

| Component | Required states | Behavior and accessibility |
| --- | --- | --- |
| Primary/secondary/quiet button | default, hover, focus-visible, active, disabled, loading | 44px minimum height; native button; loading keeps a readable label and exposes `aria-busy`; destructive actions require a separate semantic style and confirmation where contractually required. |
| Text input/select/textarea | empty, populated, hover, focus-visible, invalid, disabled, read-only | Persistent visible label; helper/error referenced with `aria-describedby`; `aria-invalid` on invalid; never rely on placeholder as label. |
| Status badge | success, warning, error, informational, neutral | Icon/wording accompanies color; map only to observed application/source/operation states; include accessible text. |
| Notice/callout | information, decision required, error, success | Text describes what happened and what the user can do; do not imply submit/send, job coverage, or provider success without evidence. |
| Evidence/source row | confirmed source, generated draft, missing fact, unsupported | Source and revision are visible; unknown is not a negative answer; field is left untouched when unsupported. |
| Card/section | default, selected, loading, empty, partial, unavailable | Neutral surface and border; selection also has non-color cue and programmatic state. |
| Navigation item | default, hover, keyboard focus, current | Text plus icon; `aria-current="page"` on current destination; no color-only active state. |
| Checkbox/radio/select option | unchecked, checked, focused, disabled, unknown/manual | Native semantics; selected option reflects only a fact with matching meaning/scope; attestations/demographics stay manual. |
| Loading/empty/error result | loading, empty, partial, unsupported, failed, permission revoked | Each state says what is known, what is not, and a next step. Partial/failed monitoring never says “no jobs found.” |

Use the proposed semantic token pairs from `../tokens/tokens.css`. Respect `prefers-reduced-motion`; preserve browser focus indication. Core controls target 44px touch height and must remain usable at narrow extension widths. DGN-003 creates responsive screen frames; DGN-005 performs the complete accessibility and production handoff gate.
