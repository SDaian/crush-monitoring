# 004 — Delight pair: success-state entrance + underline stamp-in

- **Status**: TODO
- **Commit**: 9217479
- **Severity**: LOW (missed opportunities A + B)
- **Category**: Missed opportunities
- **Estimated scope**: 2 files (`landing/src/styles/global.css`,
  `landing/src/pages/index.astro`), ~30 lines

## Problem

Two one-time, high-leverage moments render with no motion:

1. **Form status** (`index.astro`, `#form-status`): "You're on the list." —
   the page's conversion moment — teleports in when JS sets `textContent`.
2. **Hero underline** (`global.css:60–66`, `.underline-stamp`): the brand's
   signature red underline is painted statically on load.

## Target

```css
/* status message rises in — completion feedback at the causal moment */
#form-status.is-in { animation: rise-in 200ms var(--ease-out) both; }
@keyframes rise-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: none; }
}

/* underline is stamped on after the page settles: scaleX draw from the
   left (reading direction), transform-only, one-time */
.headline .underline-stamp {
  position: relative;
  background: none;             /* replace the background-image underline */
}
.headline .underline-stamp::after {
  content: "";
  position: absolute;
  left: 0; right: 0; bottom: 0.02em;
  height: 4px;
  background: var(--color-stamp);
  transform-origin: left;
  animation: stamp-in 400ms var(--ease-out) 300ms both;
}
@keyframes stamp-in { from { transform: scaleX(0); } to { transform: scaleX(1); } }
```

```js
// index.astro `say()` — retrigger the entrance per message
status.classList.remove("is-in");
void status.offsetWidth;         // restart the animation
status.classList.add("is-in");
```

## Repo conventions to follow

- `--ease-out` token from plan 001; keyframes live beside the others in
  `@layer components`.
- The underline's visual end state must match the prototype exactly
  (4px stamp red, sitting at the text's baseline area).

## Steps

1. In `global.css`, replace `.underline-stamp`'s background-image approach
   with the `::after` element + `stamp-in` keyframes above.
2. Add the `rise-in` keyframes + `#form-status.is-in` rule.
3. In `index.astro`'s `say()` helper, add the class-retrigger lines before
   setting `textContent` styles.
4. Add the reduced-motion lines from plan 003's target for both.

## Boundaries

- Do NOT animate the headline text itself — only the underline draws.
- The underline animation runs once on load; never on scroll or hover.
- Do NOT delay interactivity: the form must be usable during the stamp-in.

## Verification

- **Mechanical**: `npm run build` succeeds.
- **Feel check**: reload — underline draws left→right in ~0.4s after a
  0.3s beat, landing exactly where the static one sat (compare against
  `landing/prototype/capitol-trades-landing.html` side by side). Submit an
  invalid then valid email — each status message rises in; repeated
  submissions retrigger the rise. Emulate reduced motion: underline is
  fully drawn statically; status appears without translate.
- **Done when**: both animations fire once per trigger, visual end states
  identical to the previous static rendering.
