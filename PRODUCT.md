# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary reader is a **retail investor who watches capital flows**. They
trade or invest their own money. They read the disclosures for signal about
what well-placed people buy and sell, and they open the email beside a
brokerage account, early, before the session starts.

Two audiences follow the same record without being the target: journalists and
researchers who need every filing linked to its source document, and
accountability readers who care that officials trade while they legislate.
Both are served by the same pages. Neither steers the design.

## Product Purpose

Capitol Ledger publishes every stock trade a US politician discloses, from
Congress and the executive branch, in one readable place. The disclosures are
already public. They sit scattered across three government portals, locked in
PDFs, and they arrive weeks or months after the trade. The product reads all
of them every morning and sends back what changed.

Success is **subscribers to the daily email, with organic search as the funnel
that feeds it**. Search brings a reader in on a ticker or a member. The email
keeps them.

## Positioning

Three claims a neighbouring product could not truthfully copy today.

- **Executive-branch coverage.** The President's OGE Form 278-T filings sit in
  the same record as the House and Senate PTRs. Most trackers stop at Congress.
- **Sourced only from official filings.** House Clerk, Senate eFD, OGE. No
  rumours, no scraped social posts. Every row links to the document it came
  from.
- **Honest labelling as a discipline, not a disclaimer.** Amounts are the
  brackets as filed. Estimates say they are estimates. The 30-to-45-day legal
  lag stays visible on every surface. The product never presents itself as
  real-time or as advice.

## Operating Context

- The reader receives one email each morning, targeted at ~9am Madrid time.
  It leads with new disclosures, then the featured-stock readings.
- Quiet days do not send. When the market printed no new close and no filing
  arrived, the run skips every delivery.
- Search traffic lands on `/tickers/<symbol>` and `/members/<slug>`, not the
  home page. Those pages carry their own signup form for that reason.
- The whole record stays searchable at `/tracker`, and each morning report
  keeps a dated permalink at `/report/<date>`.
- A daily GitHub Action refreshes everything: fetch, holdings, landing data,
  social drafts, indicators, the report, then prices.

## Capabilities and Constraints

**Confirmed capabilities.** 13,016 disclosed trades from 161 filers across the
House, the Senate and the executive branch. 98 ticker pages, 11 featured
member pages, per-member estimated holdings, return-since-buy estimates
against the S&P 500, daily technical readings for every ticker page, and a
market volatility reading.

**Legal and source constraints.**

- Filings arrive 30 to 45 days after the trade. The median lag is 27 days.
  The product is a public record, never real-time.
- Filings disclose **amount brackets**, never exact sums. Every total is a
  bracket midpoint or a range, and says so.
- Paper filings have no text layer. The pipeline skips them and says so.
- Some annual reports arrive as scans. Those members show an inferred estimate
  rather than a parsed portfolio.

**Product constraints.**

- **Not investment advice, ever.** No signals, no tips, no predictions. The
  mechanical buy/hold/sell tally is a transparent tally of displayed
  indicators, published with its full breakdown.
- **Per-ticker and per-member follows do not exist yet.** No surface may
  promise them. The promise is the daily email.
- **Free today, and a paid tier stays possible.** Future work must not block
  one, and must not assume one either.

**Terminology.** A **Filing** is one submitted document. It contains many
**Disclosures**, each one reported trade. **Late** means past the STOCK Act's
45-day statutory maximum. `landing/CONTEXT.md` holds the full glossary, and
its terms are binding.

## Brand Commitments

- The name is **Capitol Ledger**. The wordmark is text, never a hosted image.
- `landing/DESIGN.md` is the identity and design system. When a design and
  that manual disagree, the manual wins.
- `landing/prototype/capitol-trades-landing.html` is the visual source of
  truth. Four agreed deviations are listed in `landing/README.md`.
- The voice is plain, declarative and unhyped. It names things directly.
- The product discloses that AI builds and maintains its pipeline, on
  `/how-it-works`. That disclosure stays.

## Evidence on Hand

**Real, and usable.**

- 13,016 disclosures, each linked to its official filing document.
- Live figures on the home page: 2,905 trades this year, ~$142M estimated
  disclosed volume, a 27-day median filing lag.
- Named records with real depth: Pelosi, Trump, Tuberville, Greene and six
  other featured members.
- A working daily email, archived at dated permalinks.

**Absent, and future work must not fabricate it.**

- **The three testimonials on the home page are invented.** Fictional people,
  fictional quotes, star ratings nobody gave. The owner knows and has chosen
  to keep them for now. No future work may add more, and none may cite them as
  evidence of real reception.
- There are no subscriber counts, no press mentions, no case studies, and no
  customer logos. Do not invent any.
- Committee assignments are real and now visible: each featured member
  page lists their seats and subcommittees from the official rosters.
  The page states the seat and the trade, and draws no line between
  them.

## Product Principles

1. **Every number traces to an official filing.** Nothing is modelled,
   guessed, or invented. An estimate carries the word "estimate".
2. **Publish the record, never the recommendation.** The reader decides. The
   product's job is to make the disclosure impossible to miss.
3. **State the limit beside the number.** The legal lag, the bracket, the
   skipped paper filing. A caveat that only appears in the small print is a
   caveat the reader will not have.
4. **The email is the product; the pages are the door.** Search brings a
   reader in on a ticker or a member. Every content page ends in a real signup
   form because of that.
5. **An empty result is not one thing.** No holdings, no committee, no
   reading — each has a cause, and the causes need different answers. Record
   the reason rather than the blank.
