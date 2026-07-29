/**
 * Holdings-composition arithmetic, kept pure and out of the template.
 *
 * Two facts about this data shape everything here, and both will silently
 * produce a lying chart if ignored:
 *
 * 1. **The list is truncated.** `landing_data.MEMBER_HOLDINGS_CAP` caps the
 *    payload at 16 stocks, but members hold far more (Tuberville: 135). The 16
 *    listed cover 99.5% of Pelosi's estimated portfolio and 40.1% of Greene's.
 *    `pctPortfolio` is a share of the FULL estimated total, so the remainder is
 *    recoverable — and it has to be drawn, or the ring reads as the whole
 *    portfolio when it is a minority of it.
 *
 * 2. **Bracket midpoints tie.** Disclosures give ranges, not amounts, so every
 *    position in the same bracket collapses to the same midpoint: Pelosi's top
 *    eight are all exactly $15.0M / 10.9% because all eight are $5M–$25M. Equal
 *    slices mean equal BRACKETS, not equal value, and the caller must say so —
 *    `hasTies` exists to trigger that caption.
 */

export interface Holding {
  ticker: string;
  asset: string;
  estLabel: string;
  pctPortfolio: number | null;
  isNew?: boolean;
}

export interface Segment {
  label: string;
  /** Percent of the estimated portfolio. */
  pct: number;
  /** Ring fill. Ranked slices use the sequential ramp; "Other" is neutral. */
  fill: string;
  /** True for the folded remainder, which is styled and read differently. */
  isOther?: boolean;
}

/**
 * Sequential ramp on the stamp hue: darker = larger share.
 *
 * Mixed in **oklab, not oklch** — oklch interpolates the hue arc, and paper's
 * hue is 106°, so an oklch mix drifts the ramp red → orange → tan. oklab
 * interpolates rectangular a/b and holds the hue while chroma falls off.
 *
 * These are steps of a SEQUENTIAL scale, not categorical hues: their job is
 * magnitude (and they are monotonic in lightness, L 0.530 → 0.841, which is the
 * check that applies). Identity is carried by the labels on the ring and in the
 * legend — never by colour alone, which a single-hue ramp could not do anyway.
 */
export const RAMP = [100, 80, 62, 46, 32].map(
  (p) => `color-mix(in oklab, var(--color-stamp) ${p}%, var(--color-paper))`,
);

/** Neutral for the folded tail — deliberately outside the ramp. */
export const OTHER_FILL =
  "color-mix(in oklab, var(--color-ink-soft) 55%, var(--color-paper))";

/** Ring slices: the top `n`, then everything else folded into one. */
export function segments(holdings: Holding[], positions: number, n = RAMP.length): Segment[] {
  const ranked = holdings
    .filter((h) => (h.pctPortfolio ?? 0) > 0)
    .sort((a, b) => (b.pctPortfolio ?? 0) - (a.pctPortfolio ?? 0));

  const top = ranked.slice(0, n).map((h, i) => ({
    label: h.ticker,
    pct: h.pctPortfolio as number,
    fill: RAMP[i],
  }));

  // Everything not drawn above: the unlisted positions AND the listed ones
  // that didn't make the ring. Rounding can push the sum a hair over 100.
  const rest = Math.max(0, 100 - top.reduce((s, t) => s + t.pct, 0));
  const restCount = Math.max(0, positions - top.length);
  if (rest < 0.05 || restCount === 0) return top;

  return [
    ...top,
    {
      // Deliberately worded to distinguish it from the "N smaller positions
      // not listed" row further down the page: that row is the tail below the
      // 16 listed, this slice is everything outside the top few.
      label: `Everything else · ${restCount} positions`,
      pct: rest,
      fill: OTHER_FILL,
      isOther: true,
    },
  ];
}

/** Share held by the largest `n` positions — the concentration read. */
export function concentration(holdings: Holding[], n = 5): number {
  return holdings
    .map((h) => h.pctPortfolio ?? 0)
    .sort((a, b) => b - a)
    .slice(0, n)
    .reduce((s, p) => s + p, 0);
}

/** Do the leading slices share a value? Then the tie caption is required. */
export function hasTies(segs: Segment[]): boolean {
  const ranked = segs.filter((s) => !s.isOther).map((s) => s.pct);
  return new Set(ranked).size < ranked.length;
}

/** Rounded to one decimal, without a trailing ".0". */
export const pctLabel = (n: number): string =>
  `${Number(n.toFixed(1))}%`;
