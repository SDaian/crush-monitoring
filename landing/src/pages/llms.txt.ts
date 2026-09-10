// "/llms.txt" — the llmstxt.org convention: a short, plain-text brief that an
// LLM can read instead of scraping 152 HTML pages.
//
// Built as an endpoint rather than dropped in public/ so the numbers come from
// the same generated stats every other surface reads. A hand-written file
// would state a trade count that goes stale the next morning, and this repo's
// rule is that every number is a true statement about real disclosures.
//
// Static output prerenders this to /llms.txt at build time — no server runtime.
import type { APIRoute } from "astro";
import stats from "../data/stats.json";
import tickerIndex from "../data/tickers/_index.json";
import memberIndex from "../data/members/_index.json";

const SITE = "https://capitolledger.io";

export const GET: APIRoute = () => {
  const tickers = (tickerIndex.tickers ?? []).length;
  const members = (memberIndex.members ?? []).length;
  const trades = stats.tradesThisYear.toLocaleString("en-US");

  const body = `# Capitol Ledger

> Every stock trade a US politician discloses under the STOCK Act — who, what,
> how much, and how late — read from official filings and published daily.

Capitol Ledger reads three government sources every morning, normalizes what
they publish, and puts it on one site: the House Clerk's Periodic Transaction
Reports, the Senate's Electronic Financial Disclosure system, and the Office of
Government Ethics Form 278-T filings for executive-branch officials.

## What the data is, and is not

- Amounts are the **legal disclosure brackets** ("$1,001 - $15,000"), never
  exact figures. Filers are not required to state a real number.
- Filings lag the trade by **30 to 45 days by law**. Nothing here is
  real-time, and ${stats.pctFiledLate}% of ${stats.year} filings arrived past
  the 45-day statutory maximum.
- Holdings shown on member pages are an **estimate**: the member's latest
  annual report rolled forward with every trade filed since, using bracket
  midpoints rather than share counts.
- Return figures are the stock's move since the disclosed trade date. They are
  **not** a member's realized profit — holding period, position size, sells and
  dividends are all unknown.
- Technical readings are a mechanical tally of published indicators.
  **Nothing on this site is investment advice.**

## Current coverage

- ${trades} trades disclosed in ${stats.year}
- ${tickers} stock pages, one per symbol with enough disclosed trades
- ${members} featured member pages
- Median filing lag: ${stats.medianLagDays} days

## Pages

- [Live feed](${SITE}/tracker): every disclosed trade, filterable by member,
  ticker, chamber, party and date.
- [Members](${SITE}/members): per-politician pages — their trades, most-traded
  tickers, filing timeliness and estimated holdings.
- [Stocks](${SITE}/tickers): per-symbol pages — who in Congress traded it, the
  buy/sell split, and a link to every official filing.
- [Late filers](${SITE}/late): filings that arrived past the statutory maximum.
- [Morning report](${SITE}/report): the daily digest, with a dated archive.
- [How it works](${SITE}/how-it-works): the pipeline, the sources, and the
  limits of the data.
- [Roadmap](${SITE}/roadmap): what is shipped and what is planned.
- [Privacy](${SITE}/privacy): what the site collects, which is very little.

## Raw data

- [congress-trades.json](${SITE}/data/congress-trades.json): the full
  normalized trade record.
- [ai-indicators.json](${SITE}/data/ai-indicators.json): daily mechanical
  technical readings per symbol.
- [returns.json](${SITE}/data/returns.json): per-buy return since the trade
  date.

## Sources

- House Clerk financial disclosures: https://disclosures-clerk.house.gov
- Senate Electronic Financial Disclosure: https://efdsearch.senate.gov
- Office of Government Ethics: https://extapps2.oge.gov

Public-domain government works. Attribution appreciated: ${SITE}
`;

  return new Response(body, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
};
