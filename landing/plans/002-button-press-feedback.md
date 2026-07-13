# 002 — Press feedback on the CTA buttons

- **Status**: TODO
- **Commit**: 9217479
- **Severity**: MEDIUM
- **Category**: Physicality & origin
- **Estimated scope**: 1 file (`landing/src/styles/global.css`), ~5 lines

## Problem

`.btn` — the conversion CTA, appearing twice — has hover color transitions
but zero press feedback (`landing/src/styles/global.css:67–86`). Feedback
must arrive on pointer-down (Apple: response is the foundation); currently
pressing feels like painted paper.

```css
/* current */
.btn { … transition: background 0.15s, color 0.15s, border-color 0.15s; }
```

## Target

```css
.btn {
  … transition: background 0.15s, color 0.15s, border-color 0.15s,
    transform 160ms var(--ease-out);
}
.btn:active { transform: scale(0.97); }
```

## Repo conventions to follow

- `--ease-out` token from plan 001 (`@theme` in the same file).

## Steps

1. Append `transform 160ms var(--ease-out)` to `.btn`'s transition list.
2. Add `.btn:active { transform: scale(0.97); }` after the hover rule.

## Boundaries

- Do NOT add hover transforms or shadows — press feedback only.
- Depends on plan 001 (the token).

## Verification

- **Mechanical**: `npm run build` succeeds.
- **Feel check**: press-and-hold the CTA — it compresses instantly on
  pointer-down (not on release), subtle (0.97), and returns smoothly. Works
  on touch (tap shows the compress).
- **Done when**: `:active` computed transform is `matrix(0.97,…)`.
