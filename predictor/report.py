"""Render a MatchResult as the full English report, in the required order:

  1. Match context
  2. How it was calibrated (hard data + xG reasoning)
  3. 1X2 table
  4. Validation vs market and supercomputers
  5. Goals markets
  6. Most probable scorelines
  7. Confidence index
  8. Pool (prode) recommendation
  9. Uncertainty warnings
"""

from __future__ import annotations

from .match import MatchResult
from .model import KnockoutOdds
from .simulate import convergence_report


def _pct(x: float) -> str:
    return f"{x:6.1%}"


def render_knockout(result: MatchResult, ko: KnockoutOdds) -> str:
    """Render the single-elimination advancement block (appended to the report).

    A knockout has no draw: the 90' draw probability is resolved through extra
    time and then penalties, so the deliverable is who ADVANCES.
    """
    meta = result.meta
    out = []
    out.append("")
    out.append("[K] KNOCKOUT — WHO ADVANCES (90' + extra time + penalties)")
    out.append(f"  {meta.home:<24} {ko.adv_home:6.1%}")
    out.append(f"  {meta.away:<24} {ko.adv_away:6.1%}")
    out.append("  ----------------------------------------------")
    out.append(f"  Settled in 90'        : {1 - ko.p_draw_reg:6.1%}")
    out.append(f"  Goes to extra time    : {ko.p_draw_reg:6.1%}")
    out.append(f"  Goes to penalties     : {ko.p_pens:6.1%}")
    out.append(
        f"  How {meta.home} advances: "
        f"reg {ko.win_reg:.1%} · ET {ko.win_et:.1%} · pens {ko.win_pens:.1%}"
    )
    out.append(
        "  (Extra time = a 30' mini-match at 1/3 of the goal rate; penalties "
        "modelled as a coin-flip — shootouts are near-random.)"
    )
    return "\n".join(out)


def render(result: MatchResult, include_convergence: bool = True) -> str:
    m = result.markets
    meta = result.meta
    out = []

    out.append("=" * 64)
    out.append(f"  {meta.home}  vs  {meta.away}".upper())
    out.append("=" * 64)

    # 1. Context
    out.append("\n[1] MATCH CONTEXT")
    out.append(f"  Venue: {meta.venue or 'n/a'}")
    out.append(f"  Date:  {meta.date or 'n/a'}")
    out.append(f"  Stage: {meta.stage or 'n/a'}")
    if meta.stakes:
        out.append(f"  Stakes: {meta.stakes}")

    # 2. Calibration
    out.append("\n[2] HOW IT WAS CALIBRATED (xG reasoning)")
    out.append("  " + result.calibration.reasoning().replace("\n", "\n  "))
    out.append(
        f"\n  => final lambda: {meta.home} {m.xg_home:.2f} | "
        f"{meta.away} {m.xg_away:.2f}  (model xG)"
    )

    # 3. 1X2
    out.append("\n[3] 1X2 (probabilities)")
    out.append(f"  {meta.home} win{'':<13} {_pct(m.p_home)}")
    out.append(f"  Draw{'':<19} {_pct(m.p_draw)}")
    out.append(f"  {meta.away} win{'':<13} {_pct(m.p_away)}")

    # 4. Validation
    out.append("\n[4] VALIDATION vs MARKET / SUPERCOMPUTER")
    if result.market_fair or result.supercomputer:
        out.append(f"  {'Source':<18} |  Home |  Draw |  Away")
        out.append("  " + "-" * 46)
        out.append(
            f"  {'Own model':<18} | {_pct(m.p_home)} | {_pct(m.p_draw)} | {_pct(m.p_away)}"
        )
        if result.market_fair:
            f = result.market_fair
            out.append(
                f"  {'Market (de-vig)':<18} | {_pct(f['home'])} | {_pct(f['draw'])} | "
                f"{_pct(f['away'])}   (book margin {f['overround']*100:.1f}%)"
            )
        if result.supercomputer:
            s = result.supercomputer
            out.append(
                f"  {'Supercomputer':<18} | {_pct(s[0])} | {_pct(s[1])} | {_pct(s[2])}"
            )
        if result.market_divergence is not None:
            flag = "OK (aligned)" if result.market_divergence <= 0.07 else "REVIEW calibration (>7 pts)"
            out.append(
                f"  Max model vs market divergence: "
                f"{result.market_divergence*100:.1f} pts -> {flag}"
            )
    else:
        out.append("  (no market odds or supercomputer loaded)")

    # 5. Goals markets
    out.append("\n[5] GOALS MARKETS")
    out.append(f"  Total expected goals: {m.exp_total_goals:.2f}")
    for ln in sorted(m.over):
        out.append(
            f"  Over {ln}: {_pct(m.over[ln])}   |  Under {ln}: {_pct(m.under[ln])}"
        )
    out.append(f"  Both teams to score (BTTS): Yes {_pct(m.btts_yes)} | No {_pct(m.btts_no)}")
    out.append(
        f"  Clean sheet: {meta.home} {_pct(m.clean_sheet_home)} | "
        f"{meta.away} {_pct(m.clean_sheet_away)}"
    )

    # 6. Scorelines
    out.append("\n[6] MOST PROBABLE SCORELINES")
    for (h, a), p in m.top_scorelines:
        out.append(f"  {h}-{a}: {_pct(p)}")

    # Extra markets
    if result.corners:
        c = result.corners
        out.append("\n[5b] CORNERS (noisy market, indicative)")
        out.append(f"  Total expected: {c['expected_total']}")
        for ln in sorted(c["over"]):
            out.append(f"  Over {ln}: {_pct(c['over'][ln])} | Under {ln}: {_pct(c['under'][ln])}")
        out.append(f"  Note: {c['_caveat']}")
    if result.cards:
        cd = result.cards
        out.append("\n[5c] CARDS (the most unpredictable market)")
        out.append(
            f"  Expected yellows: {cd['expected_yellows']} "
            f"(referee base {cd['referee_base']})"
        )
        for ln in sorted(cd["over"]):
            out.append(f"  Over {ln}: {_pct(cd['over'][ln])} | Under {ln}: {_pct(cd['under'][ln])}")
        out.append(f"  Note: {cd['_caveat']}")

    # 7. Confidence
    out.append("\n[7] CONFIDENCE INDEX")
    out.append(f"  Level: {result.confidence_level}")
    out.append(f"  Reason: {result.confidence_reason}")
    out.append(
        "  (Confidence is about the expected RESULT, not about whether it lands. "
        "An upset does not lower the grade: it was the improbable scenario already accounted for.)"
    )

    # 8. Pool recommendation
    out.append("\n[8] POOL (PRODE) RECOMMENDATION")
    r = result.recommendation
    out.append(f"  Suggested result:    {r['result']} ({r['result_prob']:.0%})")
    out.append(f"  Suggested scoreline: {r['scoreline']} ({r['scoreline_prob']:.0%})")

    # 9. Warnings
    out.append("\n[9] UNCERTAINTY WARNINGS")
    out.append("  - Football has enormous irreducible variance: these are distributions,")
    out.append("    not closed predictions. 'Most probable' is never 'certain'.")
    if result.confidence_level == "LOW":
        out.append("  - EVEN match: the model has no strong read. Be careful in the pool.")
    out.append("  - Accumulators multiply the risk; cards/corners are almost pure chance.")
    out.append("  - The bookmaker has the long-term edge. Only bet what you are willing to lose.")
    out.append("  - Recalibrate with the confirmed XIs (~60 min before): they can move the lambdas.")

    if include_convergence:
        out.append("\n[+] " + convergence_report(
            result.score_matrix, (m.p_home, m.p_draw, m.p_away)
        ).replace("\n", "\n  "))

    return "\n".join(out)
