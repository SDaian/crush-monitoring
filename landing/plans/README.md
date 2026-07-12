# Landing motion plans

From the `improve-animations` audit (commit 9217479), refined against the
`apple-design` principles before implementation.

| # | Title | Severity | Status |
|---|---|---|---|
| 001 | Strong ease-out for the feed entrance + motion tokens | MEDIUM | DONE |
| 002 | Press feedback on the CTA buttons | MEDIUM | DONE |
| 003 | Reduced motion: remove movement, keep comprehension | MEDIUM | DONE |
| 004 | Delight pair: success entrance + underline stamp-in | LOW | DONE |

**Execution order**: 001 → 002 → 003 → 004 (001 defines the `--ease-out`
token the others use; 003's reduced-motion rules reference 004's elements).

Audit notes: entrances already animate only transform/opacity; no
`scale(0)`, no `transition: all`, no animation on high-frequency actions —
those were verified clean. Considered and initially rejected: stats count-up — later added at the
owner's request (scroll-triggered, once, reduced-motion-safe). Rejected
and still out: hero entrance stagger (the static hero against the
animated feed is a deliberate contrast).
