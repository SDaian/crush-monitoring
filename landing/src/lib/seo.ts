/**
 * Meta-description composition.
 *
 * Google truncates the description it shows at roughly 155-160 characters on
 * desktop and ~120 on mobile. Anything past that is written for nobody. Several
 * of our descriptions interpolate data we do not control the length of (a
 * company name like "Taiwan Semiconductor Manufacturing Company Ltd.", a
 * member's full name), so "count it once and eyeball it" is not a guarantee —
 * a new data value can silently push a page over the line.
 *
 * `seoDescription` makes the limit structural: pass the sentence that must
 * survive first, then optional tail clauses. Each tail clause is appended only
 * if the whole string still fits, so the description degrades by dropping a
 * whole clause instead of being cut mid-word. The final clamp is a backstop for
 * the case where the required part alone is too long.
 *
 * Note this is about *presentation*, not ranking — meta descriptions are not a
 * ranking signal. A description that reads as a complete thought earns the
 * click; a truncated one loses it.
 */

/** Characters we allow. Under Google's desktop cut, comfortably over mobile's. */
export const DESC_MAX = 150;

const squash = (s: string) => s.replace(/\s+/g, " ").trim();

/** Hard cut at the last word boundary that leaves room for the ellipsis. */
function clamp(text: string, max: number): string {
  if (text.length <= max) return text;
  const cut = text.slice(0, max - 1);
  const space = cut.lastIndexOf(" ");
  return `${(space > max * 0.6 ? cut.slice(0, space) : cut).replace(/[\s,;:—-]+$/, "")}…`;
}

/**
 * Compose a description that is guaranteed to fit.
 *
 * @param required The core sentence — front-load the page's own numbers here.
 * @param optional Tail clauses, appended in order while they still fit.
 */
export function seoDescription(required: string, ...optional: string[]): string {
  let out = clamp(squash(required), DESC_MAX);
  for (const raw of optional) {
    const clause = squash(raw);
    if (!clause) continue;
    const next = `${out} ${clause}`;
    if (next.length <= DESC_MAX) out = next;
  }
  return out;
}

/** "1 trade" / "31 trades", with the count thousands-separated. */
export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`;
}
