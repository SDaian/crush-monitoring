"""Market validation: de-vig bookmaker odds and compare to the model.

The methodology requires validating the model's 1X2 against the de-vigorized
market (and any public 'supercomputer' consensus), and flagging when the model
diverges by more than ~5-7 points so calibration can be revisited.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


def devig(odds_home: float, odds_draw: float, odds_away: float) -> Dict[str, float]:
    """Convert decimal odds to fair probabilities (proportional de-vig).

    Returns fair probabilities plus the bookmaker overround (margin).
    """
    imp_h = 1.0 / odds_home
    imp_d = 1.0 / odds_draw
    imp_a = 1.0 / odds_away
    overround = imp_h + imp_d + imp_a
    return {
        "home": imp_h / overround,
        "draw": imp_d / overround,
        "away": imp_a / overround,
        "overround": overround - 1.0,
    }


@dataclass
class ValidationRow:
    label: str
    home: float
    draw: float
    away: float


def max_divergence(
    model: Tuple[float, float, float], market: Tuple[float, float, float]
) -> float:
    """Largest absolute 1X2 difference between two sources (in probability)."""
    return max(abs(m - k) for m, k in zip(model, market))


def validation_table(
    model: Tuple[float, float, float],
    market_odds: Optional[Tuple[float, float, float]] = None,
    supercomputer: Optional[Tuple[float, float, float]] = None,
) -> Tuple[str, Optional[float]]:
    """Build a comparison table string and return (table, max_divergence_vs_market)."""
    rows = [ValidationRow("Own model", *model)]
    div = None
    if market_odds is not None:
        fair = devig(*market_odds)
        rows.append(ValidationRow("Market (de-vig)", fair["home"], fair["draw"], fair["away"]))
        div = max_divergence(model, (fair["home"], fair["draw"], fair["away"]))
    if supercomputer is not None:
        rows.append(ValidationRow("Supercomputer", *supercomputer))

    width = max(len(r.label) for r in rows)
    lines = [f"{'Source'.ljust(width)} |  Home |  Draw | Away"]
    lines.append("-" * (width + 32))
    for r in rows:
        lines.append(
            f"{r.label.ljust(width)} | {r.home:6.1%} | {r.draw:6.1%} | {r.away:6.1%}"
        )
    if div is not None:
        flag = "OK (aligned)" if div <= 0.07 else "REVIEW calibration (>7 pts)"
        lines.append("")
        lines.append(f"Max model vs market divergence: {div*100:.1f} pts -> {flag}")
    return "\n".join(lines), div
