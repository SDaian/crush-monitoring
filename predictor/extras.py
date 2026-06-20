"""Optional, noisier markets: corners and cards.

Both are modeled with their own independent Poisson, deliberately separate from
the goals model. The honest caveats from the methodology are baked into the
output: corners are noisier than goals, and cards are the single most
unpredictable market -- driven first and foremost by the appointed referee, not
the teams.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from .model import poisson_pmf


def _over_under(mean: float, lines: Tuple[float, ...], max_n: int = 30) -> Dict[float, float]:
    out = {ln: 0.0 for ln in lines}
    for k in range(max_n + 1):
        p = poisson_pmf(k, mean)
        for ln in lines:
            if k > ln:
                out[ln] += p
    return out


@dataclass
class CornersModel:
    """Separate Poisson for total corners. WC average ~9-10 per match."""

    home_corners: float = 5.2
    away_corners: float = 4.3

    @property
    def total(self) -> float:
        return self.home_corners + self.away_corners

    def markets(self, lines: Tuple[float, ...] = (8.5, 9.5, 10.5)) -> dict:
        over = _over_under(self.total, lines)
        return {
            "expected_total": round(self.total, 2),
            "expected_home": self.home_corners,
            "expected_away": self.away_corners,
            "over": {ln: over[ln] for ln in lines},
            "under": {ln: 1 - over[ln] for ln in lines},
            "_caveat": "Corners son mas ruidosos que los goles; tomar como orientativo.",
        }


@dataclass
class CardsModel:
    """Separate Poisson for total yellow cards, anchored on the referee.

    The referee's per-match yellow average is the primary input. World Cup
    matches usually see FEWER cards than league games for the same referee, and
    a lopsided match adds tactical fouls from the weaker side. Those context
    knobs are explicit multipliers.
    """

    referee_yellow_avg: float = 4.0  # referee's league yellows/match
    wc_discount: float = 0.85  # WC tends below league for same ref
    mismatch_bump: float = 1.0  # >1 if lopsided (tactical fouls)

    @property
    def expected_yellows(self) -> float:
        return self.referee_yellow_avg * self.wc_discount * self.mismatch_bump

    def markets(self, lines: Tuple[float, ...] = (3.5, 4.5, 5.5)) -> dict:
        mean = self.expected_yellows
        over = _over_under(mean, lines)
        return {
            "expected_yellows": round(mean, 2),
            "referee_base": self.referee_yellow_avg,
            "over": {ln: over[ln] for ln in lines},
            "under": {ln: 1 - over[ln] for ln in lines},
            "_caveat": (
                "El predictor #1 es el ARBITRO, no los equipos. Es el mercado mas "
                "impredecible: tratar como casi azar."
            ),
        }
