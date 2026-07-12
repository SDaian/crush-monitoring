# 003 — Reduced motion: remove movement, keep comprehension

- **Status**: TODO
- **Commit**: 9217479
- **Severity**: MEDIUM
- **Category**: Accessibility
- **Estimated scope**: 1 file (`landing/src/styles/global.css`), ~15 lines

## Problem

The reduced-motion block nukes everything
(`landing/src/styles/global.css:169–175`):

```css
/* current */
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  * { animation: none !important; transition: none !important; }
}
```

Reduced motion means fewer/gentler animations, **not zero** (Apple:
"cross-fades, keep opacity/color changes that aid comprehension"). The
blanket rule makes feed rows pop with no fade and button colors snap.

## Target

```css
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  .feed-row {
    animation: fade-in 0.2s ease both;
    animation-delay: 0s !important; /* no stagger under reduce */
  }
  .live-dot { animation: none; }           /* static, still visible */
  .btn { transition: background 0.15s, color 0.15s, border-color 0.15s; }
  .btn:active { transform: none; }          /* scale is movement */
  .headline .underline-stamp::after { animation: none; transform: scaleX(1); }
  #form-status { animation: none; }          /* fades handled by opacity only */
}
@keyframes fade-in { from { opacity: 0; } to { opacity: 1; } }
```

(The `underline-stamp::after` and `#form-status` rules land with plan 004;
include them only if 004 is applied — otherwise omit those two lines.)

## Repo conventions to follow

- Media query lives at the end of `@layer components` in the same file.

## Steps

1. Add a `fade-in` opacity-only keyframes definition.
2. Replace the `* { … }` blanket rule with the targeted rules above.

## Boundaries

- Do NOT remove the `scroll-behavior: auto` override.
- Every element that moved must still *appear* (visible end state).

## Verification

- **Mechanical**: `npm run build` succeeds.
- **Feel check**: DevTools → Rendering → emulate `prefers-reduced-motion:
  reduce`; reload. Rows fade in (no downward drop, no stagger), dot is
  static but visible, button hover still eases colors, pressing does not
  scale.
- **Done when**: with reduce emulated, no computed animation contains a
  transform; all content visible.
