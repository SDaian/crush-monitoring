# 006 — Hamburger icon: the middle bar fades with the morph, on the house curve

- **Status**: TODO
- **Commit**: c0a93bc
- **Severity**: MEDIUM
- **Category**: Interruptibility & cohesion; Easing & duration
- **Estimated scope**: 1 file (`landing/src/components/Header.astro`), ~5 lines of CSS

## Problem

The three-bar icon turns into an ✕ when the phone menu opens. The outer bars
rotate over 200ms, but the middle bar vanishes on the first frame: it hides
by `background: transparent`, and `background` is not in the transition
list. The listed `opacity` transition is dead, because nothing changes
opacity. The curve is the weak built-in `ease`, while every other control on
the site uses `--ease-out`.

```css
/* landing/src/components/Header.astro:141-152 — current */
.menu-ico,
.menu-ico::before,
.menu-ico::after {
  content: "";
  display: block;
  width: 1.25rem;
  height: 2px;
  background: currentColor;
  transition:
    transform 0.2s ease,
    opacity 0.2s ease;
}
```

```css
/* landing/src/components/Header.astro:166-168 — current */
.menu-btn[aria-expanded="true"] .menu-ico {
  background: transparent;
}
```

## Target

The middle bar fades out over the same 200ms as the outer bars rotate, so
the ✕ forms as one motion. `opacity` cannot be used on `.menu-ico`: it would
also hide its `::before` and `::after` (the outer bars). Its own
`background-color` fades instead, and the children keep their own
backgrounds.

```css
/* target */
.menu-ico,
.menu-ico::before,
.menu-ico::after {
  content: "";
  display: block;
  width: 1.25rem;
  height: 2px;
  background-color: currentColor;
  transition:
    transform 200ms var(--ease-out),
    background-color 200ms var(--ease-out);
}
.menu-btn[aria-expanded="true"] .menu-ico {
  background-color: transparent;
}
```

`--ease-out` is `cubic-bezier(0.23, 1, 0.32, 1)` (`global.css:45`).

## Repo conventions to follow

- Use the `--ease-out` token; do not add a curve.
- Exemplar transition list with named properties and the token:
  `landing/src/styles/global.css:229-230` (`.btn`).

## Steps

1. In `Header.astro`, in the `.menu-ico, .menu-ico::before, .menu-ico::after`
   rule, change `background: currentColor;` to
   `background-color: currentColor;` and replace the `transition` value with
   `transform 200ms var(--ease-out), background-color 200ms var(--ease-out)`.
2. In `.menu-btn[aria-expanded="true"] .menu-ico`, change
   `background: transparent;` to `background-color: transparent;`.

## Boundaries

- Do NOT touch the `::before`/`::after` transforms, positions or sizes.
- Do NOT touch the `.mobile-menu` rules (plan 005) or the
  `prefers-reduced-motion` block (plan 007). Under reduced motion the icon
  keeps snapping: it is a small state glyph, not movement through space.
- If the code does not match the excerpts, STOP and report.

## Verification

- **Mechanical**: `cd landing && npm run build` succeeds.
- **Feel check** at 375px:
  - Tap the hamburger and step through at 10% playback: the middle bar fades
    while the outer bars rotate; there is no frame where the middle bar is
    gone and the outer bars are still parallel.
  - Close it: the reverse, in the same 200ms.
  - Tap twice quickly: the morph reverses from where it is, never restarting
    from zero (transitions retarget).
- **Done when**: no `ease` keyword and no `opacity` remain in the icon's
  transition list, and the middle bar's computed `background-color` passes
  through intermediate alpha values during the morph.
