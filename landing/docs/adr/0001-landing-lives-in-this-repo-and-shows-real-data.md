# Landing page lives in this repo and renders real pipeline data

The "Capitol Gains" landing page (Astro, Vercel) is built in `landing/`
inside this repo instead of the standalone repo its PRD assumed, and its
disclosure feed and stats are generated from the repo's real congressional
trades pipeline (`docs/data/congress-trades.json`, refreshed daily) rather
than the PRD's placeholder JSON. Placement: the working session can only
push to this repo, and colocation puts the page one directory away from the
data it markets; extraction later is a `git subtree split`. Real data: the
page's stated goal is credibility of data sourcing, and the approved
prototype's sample rows attributed invented trades to real, named
politicians — with a live pipeline in the same repo, every rendered number
can simply be true. The daily data commit also triggers Vercel's rebuild,
making the hero's "Updated daily from official filings" literally accurate.

## Considered Options

- Standalone repo + placeholder data (PRD as written) — rejected: not
  executable from this session, and fabricated trades under real names on a
  credibility-branded page.
- Real snapshot, manually refreshed — rejected: "Filed this week" with a
  pulsing live dot over stale rows misleads.

## Consequences

- The prototype's fabricated stats (12,847 trades / $1.2B / 31% late) are
  replaced by real, humbler computed values.
- The landing build depends on this repo's generated data files; if the
  page is ever extracted to its own repo, the data handoff must be redesigned.
