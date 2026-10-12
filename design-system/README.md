# Proposed Aster design system

Design exploration artifact for DGN-002; not wired into `apps/web` or `apps/extension`. The existing [browser preview](../design-exploration/README.md) informed the starting Sage & ink palette. These tokens refine it with explicit semantic color pairs and stronger control/focus boundaries.

## Artifacts

- [`tokens/tokens.css`](tokens/tokens.css): semantic light-theme pairs, type scale, spacing, shape, focus, and reduced-motion tokens.
- [`logos/`](logos/): proposed horizontal, symbol-only, monochrome horizontal-lockup, and reversed horizontal-lockup Guiding A SVGs; [`logos/preview.html`](logos/preview.html) shows toolbar-size variants.
- [`components/COMPONENTS.md`](components/COMPONENTS.md): reusable component/state and accessibility contract.
- [`rendered/contrast-specimen.png`](rendered/contrast-specimen.png): raster-rendered semantic text, status, control-border, and focus-ring contrast specimen.
- [`rendered/guiding-a-16.png`](rendered/guiding-a-16.png), [`guiding-a-24.png`](rendered/guiding-a-24.png), and [`guiding-a-32.png`](rendered/guiding-a-32.png): raster-rendered mark-size review assets. [`rendered/guiding-a-monochrome.png`](rendered/guiding-a-monochrome.png) is the full monochrome lockup. The mark geometry is one continuous SVG path ending at the star; name and identity remain unapproved.
- [`components/components.css`](components/components.css) and [`components/index.html`](components/index.html): static specimen for review; no application behavior or product integration.

Brand, name, palette, typeface, and logo remain proposed pending owner acceptance and the separate DGN-006 public-use review. Contrast calculations and rendered specimens are recorded in [`docs/evidence/DGN-002.md`](../docs/evidence/DGN-002.md).
