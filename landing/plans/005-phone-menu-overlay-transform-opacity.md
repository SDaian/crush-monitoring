# 005 — Phone menu: an overlay that animates transform and opacity only

- **Status**: TODO
- **Commit**: c0a93bc
- **Severity**: HIGH
- **Category**: Performance (also covers a keyboard-initiated close and a snapping border)
- **Estimated scope**: 1 file (`landing/src/components/Header.astro`), ~40 lines of CSS and ~10 of script

## Problem

The phone menu (below 768px) opens by animating a layout property. Every
frame recomputes layout and pushes the whole page down about 260px, with the
weak built-in `ease`:

```css
/* landing/src/components/Header.astro:177-190 — current */
.mobile-menu {
  display: grid;
  grid-template-rows: 0fr;
  overflow: hidden;
  transition: grid-template-rows 0.28s ease;
}
.mm-inner {
  display: grid;
  min-height: 0; /* let the row collapse; a grid item floors at auto */
}
.mobile-menu.open {
  grid-template-rows: 1fr;
  border-bottom: 1px solid var(--color-rule);
}
```

Three related defects, all fixed here:

1. **Layout animation.** `grid-template-rows` is not `transform`/`opacity`;
   `landing/DESIGN.md` §6 allows only those two.
2. **The bottom border snaps.** It belongs to `.open`, so on close it
   disappears on the first frame while the panel is still ~260px tall.
3. **Esc animates.** The Esc handler (`Header.astro:252-256`) runs the full
   280ms collapse. Keyboard-initiated actions must land instantly.

```ts
// landing/src/components/Header.astro:252-257 — current
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && btn.getAttribute("aria-expanded") === "true") {
    setOpen(false);
    btn.focus();
  }
});
```

## Target

The panel lies over the page, directly under the header's double rule, and
the page below never moves. It opens in 200ms and closes faster, in 150ms,
moving only `opacity` and `transform`. Esc closes with no animation. A tap
outside the open panel closes it (an overlay must be dismissable by tapping
away).

```css
/* target */
.site-head {
  position: relative;
}
.mobile-menu {
  position: absolute;
  inset-inline: 0;
  top: 100%;
  z-index: 50;
  background: var(--color-paper);
  border-bottom: 1px solid var(--color-rule);
  opacity: 0;
  transform: translateY(-0.5rem);
  visibility: hidden;
  transition:
    opacity 150ms var(--ease-out),
    transform 150ms var(--ease-out),
    visibility 0s linear 150ms;
}
.mobile-menu.open {
  opacity: 1;
  transform: none;
  visibility: visible;
  transition-duration: 200ms, 200ms, 0s;
  transition-delay: 0s;
}
/* Esc closes with no animation: a keyboard action lands at once. */
.mobile-menu.instant {
  transition: none;
}
```

`--ease-out` is `cubic-bezier(0.23, 1, 0.32, 1)`, defined in
`landing/src/styles/global.css:45`.

## Repo conventions to follow

- The only easing token is `--ease-out` (`global.css:45`); use it, do not add
  another curve.
- Exemplar of an exit faster than its entrance, with discrete visibility:
  `landing/src/components/SignupModal.astro` (`.cl-modal` transitions: 200ms
  in, 150ms out).
- Comments in `.astro` markup use `{/* … */}`, never `<!-- … -->` (a test
  fails on HTML comments). CSS comments `/* … */` inside `<style>` are fine.
- `inert` already removes the closed panel from focus and the accessibility
  tree (`Header.astro:241-242`); keep it.

## Steps

1. In `Header.astro`'s `<style>`, add `.site-head { position: relative; }`
   above the `.mobile-menu` rule.
2. Replace the `.mobile-menu`, `.mm-inner` and `.mobile-menu.open` rules
   (lines 176-190) with the target CSS above. Delete the `.mm-inner` rule
   entirely: the `min-height: 0` existed only for the grid-row collapse.
   Keep the comment above `.mobile-menu`, reworded to: "The panel lies over
   the page under the header rule; only opacity and transform move."
3. In the `<script>`, replace the Esc handler with:

   ```ts
   // Esc closes with no animation (a keyboard action lands at once) and
   // returns focus to the trigger. Reading offsetHeight commits the closed
   // style while transitions are off, so removing the class starts nothing.
   document.addEventListener("keydown", (e) => {
     if (e.key === "Escape" && btn.getAttribute("aria-expanded") === "true") {
       menu.classList.add("instant");
       setOpen(false);
       void menu.offsetHeight;
       menu.classList.remove("instant");
       btn.focus();
     }
   });
   ```

4. In the same `<script>`, after the Esc handler, add the tap-away close:

   ```ts
   // An overlay is dismissed by tapping away from it.
   document.addEventListener("pointerdown", (e) => {
     if (btn.getAttribute("aria-expanded") !== "true") return;
     const t = e.target as Node;
     if (!menu.contains(t) && !btn.contains(t)) setOpen(false);
   });
   ```

5. Leave the `@media (min-width: 48rem)` rule (`.menu-btn, .mobile-menu {
   display: none; }`) as it is.

## Boundaries

- Do NOT touch the hamburger icon rules (`.menu-ico*`); plan 006 owns them.
- Do NOT touch the `prefers-reduced-motion` block; plan 007 owns it.
- Do NOT change the markup, the link list, `NAV`, or the desktop nav.
- Do NOT add dependencies.
- If the code at the cited lines does not match the excerpts (drift since
  commit c0a93bc), STOP and report instead of improvising.

## Verification

- **Mechanical**: `cd landing && npm run build` succeeds; then
  `python3 -m unittest discover -s tests/congress -p 'test_*.py'` from the
  repo root passes (it fails on HTML comments in `.astro` files).
- **Feel check** at 375px wide (serve `landing/dist` with
  `python3 -m http.server`):
  - Tap the hamburger: the panel fades in and settles down 8px over 200ms;
    the page content below does not move at all (`main`'s top stays fixed).
  - Close it with the button: it fades out faster (150ms); the bottom rule
    leaves with the panel, never before it.
  - Open, then press Esc: the panel is gone on the next frame, and focus is
    on the hamburger.
  - Open, then tap the page below the panel: it closes.
  - Tap a menu link: it navigates (the menu closes).
  - At 10% playback (DevTools Animations panel), only `opacity` and
    `transform` animate; no layout property appears.
- **Done when**: no `grid-template-rows` transition remains in
  `Header.astro`; `main`'s top coordinate is identical with the menu open and
  closed; Esc closes on the next frame; no sideways scroll at 320/375/414px.
