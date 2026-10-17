# Landing motion plans

From the `improve-animations` audit (commit 9217479), refined against the
`apple-design` principles before implementation.

| # | Title | Severity | Status |
|---|---|---|---|
| 001 | Strong ease-out for the feed entrance + motion tokens | MEDIUM | DONE |
| 002 | Press feedback on the CTA buttons | MEDIUM | DONE |
| 003 | Reduced motion: remove movement, keep comprehension | MEDIUM | DONE |
| 004 | Delight pair: success entrance + underline stamp-in | LOW | DONE |
| 005 | Phone menu: an overlay that animates transform and opacity only | HIGH | DONE |
| 006 | Hamburger icon: the middle bar fades with the morph | MEDIUM | TODO |
| 007 | Phone menu under reduced motion: a short fade, not a snap | LOW | TODO |

**Execution order**: 001 → 002 → 003 → 004 (001 defines the `--ease-out`
token the others use; 003's reduced-motion rules reference 004's elements).

Audit notes: entrances already animate only transform/opacity; no
`scale(0)`, no `transition: all`, no animation on high-frequency actions —
those were verified clean. Considered and initially rejected: stats count-up — later added at the
owner's request (scroll-triggered, once, reduced-motion-safe). Rejected
and still out: hero entrance stagger (the static hero against the
animated feed is a deliberate contrast).

## Phone menu audit (commit c0a93bc)

**Execution order**: 005 → 006 → 007. 007 depends on 005 (it targets the
overlay panel 005 creates); 006 is independent but shares the file, so run
it after 005 to avoid conflicts.

005 changes behaviour, by the owner's choice: the panel lies over the page
instead of pushing it down. It is the only way to keep the menu to
transform and opacity. Not reported: the ungated hover colour on the menu
links (every tap navigates and closes the menu, so the sticky state is never
seen). No missed opportunities: a link stagger would decorate navigation
used repeatedly.
