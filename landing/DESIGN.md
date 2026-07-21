# Capitol Ledger — Visual Identity & Design Manual

This is the **visual identity of the product**, written to be **agnostic of any
particular design**. It is the manual every page, component, and future redesign
must follow — not a description of one layout. When a design decision and this
manual disagree, this manual wins (or the manual is changed, deliberately, in the
same PR — see [Governance](#12-governance)).

It governs the **Capitol Ledger landing site** (`landing/`). The tracker
(`docs/trades.html`) and the World Cup predictor are separate visual contexts and
are **out of scope** here. This file is the visual/UI layer; it complements — and
does not duplicate — `CONTEXT.md` (domain glossary), `docs/adr/` (decisions), and
the repo-root `ROADMAP.md` (staging).

---

## 1. Brand essence

**Capitol Ledger is a public ledger of the trades power makes.** It takes records
that are technically public but practically buried, and makes them plain,
comparable, and impossible to miss.

**The feeling to project — always:**

- **Editorial** — a publication, not an app. It reads like a serious newspaper's
  data desk.
- **Forensic** — precise, sourced, unembellished. Every claim is checkable.
- **Plain-spoken** — plain language, short sentences, no jargon.
- **Credible** — restraint reads as trust. It never oversells.

**The anti-brand — never become this:**

- A hype fintech (gradients, emojis-as-personality, "🚀 to the moon").
- A trading-signals / stock-tips product (we publish records; we give no advice).
- Anything playful, cute, or ironic about the subject matter.

**Governing metaphor: the broadsheet / the public record.** Ink on paper, hairline
rules, datelines, monospace for data. Every visual choice should be defensible as
"a serious paper would do this."

---

## 2. Logo & wordmark

- **Wordmark:** `Capitol Ledger`, set in the display sans at heavy weight (900),
  **uppercase**, tight negative tracking. **"Ledger" is stamp red; "Capitol" is
  ink.** This is the primary identity mark; there is no separate logotype.
- **Favicon / monogram:** `CL` in paper on a stamp-red field.
- **Clear space:** keep at least the cap-height of the mark clear on all sides.
- **Don'ts:** don't recolor "Capitol" red or "Ledger" ink; don't set it in the
  mono face; don't add a tagline lockup; don't apply effects (shadow, gradient,
  outline); don't lowercase it.

---

## 3. Color identity

The palette is small on purpose. **Paper and ink carry the page; stamp red is the
only accent and is spent sparingly** — it must always mean something (the brand,
the CTA, the accusation of lateness). Two data colors exist solely to tell the
truth of a trade. Values are canonical in `src/styles/global.css` `@theme`; this
table is the meaning behind them.

| Token | OKLCH | Hex | Role / meaning |
|---|---|---|---|
| `--color-paper` | `oklch(0.988 0.003 106.448)` | `#FBFBF9` | Newsprint background. The default surface. |
| `--color-ink` | `oklch(0.2 0.009 264.36)` | `#14161A` | Text, headlines, structural rules — authority. |
| `--color-ink-soft` | `oklch(0.481 0.014 264.438)` | `#5A5E66` | Secondary text, labels, captions. |
| `--color-rule` | `oklch(0.912 0.008 98.888)` | `#E3E2DC` | Hairline dividers, borders, structure. |
| `--color-stamp` | `oklch(0.53 0.207 22.317)` | `#C8102E` | **The single accent.** Brand, primary CTA, "late", live dot. Never decorative. |
| `--color-buy` | `oklch(0.517 0.121 156.294)` | `#0E7C4A` | Data truth: a BUY. |
| `--color-sell` | `oklch(0.501 0.178 28.705)` | `#B3261E` | Data truth: a SELL. |

**Laws.**

- **No hex outside the token set.** New surfaces derive from these tokens (a
  faint "wash" tint for insets is acceptable if added as a token, not a one-off).
- **Stamp red is rationed.** If everything is red, nothing is. One dominant red
  moment per viewport (usually the CTA or the brand), plus functional reds
  (late / sell) that are data, not decoration.
- **Buy-green / sell-red are for data only** — never for UI chrome or emphasis.
- **Contrast is non-negotiable:** every text/background pair meets **WCAG AA
  (≥4.5:1)** on paper; large display text meets ≥3:1. Verify when adding any pair.
- **Dark surfaces** (if ever introduced) are a deliberate, documented exception,
  not a default — the identity is light/paper.

---

## 4. Typographic identity

Two families, two jobs. Both are self-hosted.

- **Libre Franklin (sans)** — the **editorial voice**. Headlines (900), section
  and card titles (800), body (400). Big, confident, tightly tracked display.
- **IBM Plex Mono (mono)** — the **"official record" voice**. Data, tickers,
  amounts, dates, labels, eyebrows, nav, form fields, fine print. Mono signals
  "this is a record," which is the whole point.

**Rules.**

- **Tracking is size-specific.** Display/headline: tight, negative
  (≈ `-0.03` to `-0.04em`). Mono labels/eyebrows: **positive, uppercase**
  (`0.06`–`0.16em`). Body: near zero.
- **Leading tracks size inversely** — tight on large headings (~0.95–1.0),
  comfortable on body (~1.6).
- **Hierarchy comes from weight + size + case together**, not size alone. Mono +
  uppercase + tracking is the label system; heavy sans is the headline system.
- **The signature:** a headline phrase underscored by a **stamp-red bar**
  (the "stamp underline"). This is the one ownable typographic flourish — use it
  once per page at most, on the line that matters.
- Scale everything in `rem`/`em` and `clamp()` so it adapts to width and to the
  user's text-size setting; never fixed px that breaks on zoom.
- `font-synthesis: none` — a missing weight must fail visibly, never be
  browser-faked. Punctuation is real (curly quotes, en/em dashes) — but see the
  voice rule on em dashes in testimonials (§7).

---

## 5. Layout & structure

The structure *is* part of the identity — it's what makes the page read as a
publication.

- **Rule system (borrowed from print):** hairline `--color-rule` (1px) separates
  peers; a **2px ink** rule sits under a section header; a **3px double ink** rule
  marks a major structural break (masthead, band edges). Use them consistently —
  the weight communicates the size of the division.
- **Zero border-radius everywhere.** Sharp corners are the identity
  (`--radius-*: initial`). **The only exception is the live-dot, which is a
  circle because it is literally a dot.** No rounded cards, buttons, or inputs.
- **Grid:** centered, `max-width` ~1200px, `5vw` side gutters. Generous vertical
  rhythm between sections (~`10vh`). Whitespace is a feature — the page breathes
  like newsprint, it is not dense.
- **Editorial motifs** (datelines, mastheads, "Vol." lines, section eyebrows)
  are on-identity and encouraged where they add credibility, not clutter.
- **Mobile-first.** Most visitors arrive on phones. Every layout must hold at
  ≥320px with **zero horizontal overflow** — verify by measuring, never mask with
  `overflow: hidden`. Multi-column structures collapse to one column; data tables
  drop their least-important columns rather than shrink to illegibility.

---

## 6. Motion identity

Restraint. Motion is meaningful or absent — never decorative.

- One easing token: `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)` — entrances
  start fast and settle. Reach for it for entrances and chrome.
- **Motion carries meaning:** a **pulsing dot means "live / real-time."** A
  **static** table means "settled evidence" (e.g. a leaderboard deliberately does
  **not** animate in — it is a record, not a feed). Don't animate something that
  isn't alive.
- Animate only `transform`/`opacity`. Feedback is immediate on press, not on
  release. No looping ambient motion, no parallax, no attention-grabbing loops.
- **Reduced motion is a first-class path**, not an afterthought: honor
  `prefers-reduced-motion` — replace movement with a short opacity fade, drop the
  pulse to static, keep every element's visible end state. Comprehension never
  depends on motion.

---

## 7. Verbal identity (voice & tone)

The words are part of the visual identity — they sit inside the type system and
must match it.

- **Plain, declarative, unhyped.** Short sentences. Active voice. Name things
  directly ("Late filers", not "Compliance insights").
- **The honesty laws (inviolable):**
  - **Every number on a public page traces to an official filing.** Nothing is
    modelled, guessed, or invented.
  - **Estimates are labelled** as estimates (bracket midpoints, "est.").
  - **Not investment advice, ever** — no signals, tips, predictions, or
    "buy/sell" recommendations. We publish records; the reader decides.
  - **Placeholders are flagged** in-source and replaced before launch; fabricated
    content (fake reviews, fake records) never ships as if real.
- **Tone conventions already set:**
  - Testimonials read like real people, not marketing copy — and contain **no em
    dashes** (they read as AI-written). The site's own editorial copy may use
    them; quotes may not.
  - "Late" always means past the STOCK Act's 45-day statutory maximum — use the
    word precisely.
- **Do / don't:**
  - ✅ "Filed 502 days late." ❌ "🚨 INSANE 502-day delay!!"
  - ✅ "One email per day — always. No spam, ever." ❌ "Join 10,000+ smart investors."
  - ✅ "We publish public records in readable form." ❌ "Get the trading edge."

---

## 8. Component library (the applied vocabulary)

These are the reusable primitives any page composes from. They are **design-
agnostic building blocks** — the manual defines the primitive; a page's layout
decides where they go. Canonical CSS lives in `src/styles/global.css` and the
shared Astro components in `src/components/`.

- **Header** — shared, single row: wordmark left; mono nav + one filled CTA
  right; editorial rule beneath. Current page marked (stamp underline / active).
- **Footer** — shared: wordmark + identity blurb, a sitemap, the legal line.
- **Section header** — a title (heavy sans, uppercase, tracked) + optional mono
  tag on the right, over a 2px ink rule. The canonical way to open a section.
- **Eyebrow / kicker** — mono, uppercase, tracked, `ink-soft` with a stamp-red
  emphasis span. Sits above a headline.
- **Headline + stamp underline** — the signature (see §4).
- **Button (`.btn`)** — ink or stamp fill, mono uppercase label, sharp corners,
  press feedback. Primary action is stamp red and rationed to one per view.
- **Form field + contract** — mono, bordered, sharp. Forms POST form-encoded to a
  `PUBLIC_*_ENDPOINT` env var (provider-agnostic); unset → an honest "opens soon"
  state; inline `role="status"` feedback with a rise-in. 16px font on touch
  (iOS-zoom guard).
- **Data primitives** — feed / disclosure row, the "today's email" preview card,
  the stat strip, definition card, review card, FAQ clause, leaderboard row. All
  share: mono for data, `buy`/`sell`/`late` semantic colors, `min-width:0` cells
  that wrap rather than overflow, and real data behind every value.
- **Live dot** — the one circle; pulses only to mean "live."

Adding a component: express it in the tokens and these patterns; if it needs a new
token or breaks a rule here, update this manual in the same PR.

---

## 9. Imagery & iconography

- **Data is the imagery.** The hero "product shot" is a rendering of the actual
  product — the daily email / the feed — not stock photography. There are **no
  photos** and no illustration in the identity.
- **Iconography is minimal and functional:** the live dot, the stamp underline,
  rules. Emoji are used only where they carry real information — country **flags**
  on testimonials, **★ rating stars** — never as decoration or tone.
- Any product screenshot is styled as a broadsheet clipping (sharp border, ink
  rules, a stamp tab), consistent with §5 — not a glossy app frame.

---

## 10. Composing a page (agnostic)

The manual does **not** prescribe one page layout. It prescribes how any page is
assembled:

- Open with the **header**; close with the **footer** (both shared).
- Lead with **one clear promise** and **one primary action** (the stamp CTA);
  don't compete two primary actions in a view.
- Prefer **showing the product** (real data) over describing it.
- Put **trust near the action** (sources, "no spam", privacy, real proof).
- Separate sections with the **rule system** (§5); label them with the **section
  header** (§8).
- Every value on the page obeys the **honesty laws** (§7).

Whether a given page is single-column or split, feed-first or email-first, is a
design choice — as long as it obeys the above, it is on-identity.

---

## 11. Accessibility & performance (identity-level requirements)

Not optional polish — part of "credible."

- **Contrast** AA (§3). **Visible focus** on every interactive element
  (`focus-visible`, stamp outline). **Reduced motion** honored (§6).
- **Semantics:** data tables expose `role="table"`/row/columnheader; status
  messages use `aria-live`; the nav marks the current page. Touch targets ≥ ~44px.
- **Type respects zoom / Dynamic Type** — `rem`/`clamp`, never layout-breaking px.
- **No layout jump on font load:** critical fonts are **preloaded** and paired
  with **metric-matched fallbacks** (fontaine) so the swap never reflows. Self-
  hosted fonts only — no third-party font requests.
- **Static output, minimal JS** — the page works without JavaScript; the only
  client scripts are the forms and the stats count-up, and both degrade cleanly.

---

## 12. Governance

- **This manual is the source of truth for the look.** Changing the system —
  a token value, a type rule, a new primitive, a motion principle — means editing
  this file **in the same PR** as the code change. The code and the manual never
  drift.
- The **prototype** (`landing/prototype/`) remains the historical visual source
  of truth for the original build; documented deviations live in
  `landing/README.md`. Where this manual and the prototype differ, this manual is
  the living authority.
- Relationship to neighbours: **`CONTEXT.md`** = what words mean (domain);
  **`docs/adr/`** = why a decision was made; **`ROADMAP.md`** = what ships when;
  **`DESIGN.md`** (this) = how it must look and feel. Keep them non-overlapping.
- A redesign is not a licence to abandon the identity. New layouts are welcome;
  the essence (§1), the palette discipline (§3), the type roles (§4), the
  structure language (§5), and the honesty laws (§7) carry across all of them.
