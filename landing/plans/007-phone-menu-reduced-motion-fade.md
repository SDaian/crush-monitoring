# 007 — Phone menu under reduced motion: a short fade, not a snap

- **Status**: DONE
- **Commit**: c0a93bc
- **Severity**: LOW
- **Category**: Accessibility
- **Estimated scope**: 1 file (`landing/src/components/Header.astro`), ~10 lines of CSS
- **Depends on**: 005 (this plan targets the overlay panel 005 creates)

## Problem

Under `prefers-reduced-motion: reduce`, the phone menu has every transition
removed, so it snaps open and shut. `landing/DESIGN.md` §6 says reduced
motion replaces movement with a short opacity fade; it does not remove all
feedback.

```css
/* landing/src/components/Header.astro:223-230 — current */
@media (prefers-reduced-motion: reduce) {
  .mobile-menu,
  .menu-ico,
  .menu-ico::before,
  .menu-ico::after {
    transition: none;
  }
}
```

## Target

Under reduced motion the panel keeps its opacity fade (200ms in, 150ms out,
from plan 005) and loses the 8px movement. The icon keeps snapping: it is a
small state glyph, and its morph is rotation, which is movement.

```css
/* target */
@media (prefers-reduced-motion: reduce) {
  .mobile-menu,
  .mobile-menu.open {
    transform: none;
  }
  .menu-ico,
  .menu-ico::before,
  .menu-ico::after {
    transition: none;
  }
}
```

## Repo conventions to follow

- Exemplar of "fade kept, movement dropped":
  `landing/src/components/SignupModal.astro`, its `prefers-reduced-motion`
  block (`@starting-style { .cl-modal[open] { transform: none; } }`).

## Steps

1. Confirm plan 005 is applied (`.mobile-menu` has `opacity`/`transform`
   transitions). If not, STOP.
2. Replace the `@media (prefers-reduced-motion: reduce)` block in
   `Header.astro` with the target block above. Keep a one-line comment:
   "Reduced motion: the panel keeps its fade and drops the movement; the
   icon snaps (DESIGN.md §6)."

## Boundaries

- Do NOT change any rule outside the reduced-motion block.
- If the block does not match the excerpt, STOP and report.

## Verification

- **Mechanical**: `cd landing && npm run build` succeeds.
- **Feel check**: in DevTools Rendering, emulate
  `prefers-reduced-motion: reduce`, then at 375px:
  - Open the menu: it fades in over ~200ms with no vertical movement
    (computed `transform` stays `none` on every frame).
  - Close it: it fades out over ~150ms.
  - The hamburger snaps to ✕ and back with no rotation frames.
- **Done when**: under reduced motion the panel's opacity passes through
  intermediate values while its transform stays `none`.
