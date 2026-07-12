# 001 — Strong ease-out for the feed entrance + motion tokens

- **Status**: TODO
- **Commit**: 9217479
- **Severity**: MEDIUM
- **Category**: Easing & duration + Cohesion & tokens
- **Estimated scope**: 1 file (`landing/src/styles/global.css`), ~10 lines

## Problem

The feed rows — the page's signature moment — enter with the weak built-in
`ease`, and easings/durations are hand-typed with no tokens. Nav link hover
colors snap (no transition) while the button transitions, so the chrome is
inconsistent.

```css
/* landing/src/styles/global.css:121 — current */
.feed-row { … animation: drop 0.5s ease both; }
```

## Target

```css
/* in @theme */
--ease-out: cubic-bezier(0.23, 1, 0.32, 1); /* strong ease-out for UI */

/* feed entrance */
.feed-row { … animation: drop 0.5s var(--ease-out) both; }

/* nav links (in the markup's Tailwind classes or a component rule) */
transition: color 150ms ease;
```

## Repo conventions to follow

- Tokens live in the `@theme` block of `landing/src/styles/global.css`
  (Tailwind v4); component motion lives in `@layer components`.

## Steps

1. Add `--ease-out: cubic-bezier(0.23, 1, 0.32, 1);` to `@theme`.
2. Change `.feed-row`'s `animation` to `drop 0.5s var(--ease-out) both`.
3. Add a `nav a { transition: color 150ms ease; }` rule in `@layer components`.

## Boundaries

- Do NOT change durations, delays, or the keyframes themselves.
- Do NOT touch markup.

## Verification

- **Mechanical**: `cd landing && npm run build` succeeds.
- **Feel check**: reload; rows should land decisively (fast start, soft
  settle) — in DevTools Animations panel at 10% speed, the row's motion
  front-loads. Nav hover eases instead of snapping.
- **Done when**: computed style of `.feed-row` shows the cubic-bezier.
