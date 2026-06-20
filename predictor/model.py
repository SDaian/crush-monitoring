"""Core probability model: bivariate Poisson with the Dixon-Coles low-score
correction.

Design notes
------------
The reference methodology asks for a Dixon-Coles adjusted Poisson resolved by
Monte Carlo. Monte Carlo only *approximates* the underlying score-probability
matrix, so this module computes that matrix **exactly** (closed form) and
derives every market from it. The Monte Carlo path lives in ``simulate.py`` and
exists to demonstrate convergence, not to be the source of truth.

Everything here is pure standard library so the tool runs anywhere (CI, a bare
container) with no scientific dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


def poisson_pmf(k: int, lam: float) -> float:
    """P(X = k) for X ~ Poisson(lam). Pure-Python, no scipy needed."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * lam ** k / math.factorial(k)


def dc_tau(i: int, j: int, lam_home: float, lam_away: float, rho: float) -> float:
    """Dixon-Coles dependency factor tau(i, j).

    Inflates/deflates the four lowest joint scorelines (0-0, 1-0, 0-1, 1-1) to
    correct the well-known under/over-prediction of low scores by the
    independent Poisson model. ``rho`` is expected to be negative.
    """
    if i == 0 and j == 0:
        return 1.0 - lam_home * lam_away * rho
    if i == 0 and j == 1:
        return 1.0 + lam_home * rho
    if i == 1 and j == 0:
        return 1.0 + lam_away * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


@dataclass
class ScoreMatrix:
    """Normalized joint distribution over (home_goals, away_goals)."""

    lam_home: float
    lam_away: float
    rho: float
    max_goals: int
    matrix: List[List[float]] = field(repr=False)

    def prob(self, i: int, j: int) -> float:
        return self.matrix[i][j]


def build_score_matrix(
    lam_home: float,
    lam_away: float,
    rho: float = -0.06,
    max_goals: int = 10,
) -> ScoreMatrix:
    """Build and normalize the Dixon-Coles adjusted scoreline matrix.

    A negative ``rho`` can in principle push the tau factor for a cell negative
    for extreme lambdas; we clamp each cell at 0 before normalizing so the
    result is always a valid distribution.
    """
    size = max_goals + 1
    matrix = [[0.0] * size for _ in range(size)]
    total = 0.0
    for i in range(size):
        pi = poisson_pmf(i, lam_home)
        for j in range(size):
            p = pi * poisson_pmf(j, lam_away) * dc_tau(i, j, lam_home, lam_away, rho)
            if p < 0:
                p = 0.0
            matrix[i][j] = p
            total += p
    if total <= 0:
        raise ValueError("Degenerate score matrix (total probability is 0).")
    for i in range(size):
        for j in range(size):
            matrix[i][j] /= total
    return ScoreMatrix(lam_home, lam_away, rho, max_goals, matrix)


# --------------------------------------------------------------------------- #
# Market derivation (all exact, from the normalized matrix)
# --------------------------------------------------------------------------- #


@dataclass
class Markets:
    p_home: float
    p_draw: float
    p_away: float
    over: Dict[float, float]
    under: Dict[float, float]
    btts_yes: float
    btts_no: float
    clean_sheet_home: float
    clean_sheet_away: float
    xg_home: float
    xg_away: float
    exp_total_goals: float
    top_scorelines: List[Tuple[Tuple[int, int], float]]

    def as_dict(self) -> dict:
        return {
            "1x2": {"home": self.p_home, "draw": self.p_draw, "away": self.p_away},
            "over": self.over,
            "under": self.under,
            "btts": {"yes": self.btts_yes, "no": self.btts_no},
            "clean_sheet": {
                "home": self.clean_sheet_home,
                "away": self.clean_sheet_away,
            },
            "xg": {"home": self.xg_home, "away": self.xg_away},
            "expected_total_goals": self.exp_total_goals,
            "top_scorelines": [
                {"score": f"{h}-{a}", "prob": p} for (h, a), p in self.top_scorelines
            ],
        }


def derive_markets(
    sm: ScoreMatrix,
    lines: Tuple[float, ...] = (1.5, 2.5, 3.5),
    top_n: int = 7,
) -> Markets:
    size = sm.max_goals + 1
    p_home = p_draw = p_away = 0.0
    btts_yes = 0.0
    cs_home = 0.0  # away fails to score
    cs_away = 0.0  # home fails to score
    over = {ln: 0.0 for ln in lines}
    xg_home = 0.0
    xg_away = 0.0
    scorelines: List[Tuple[Tuple[int, int], float]] = []

    for i in range(size):
        for j in range(size):
            p = sm.matrix[i][j]
            if p == 0.0:
                continue
            scorelines.append(((i, j), p))
            xg_home += i * p
            xg_away += j * p
            if i > j:
                p_home += p
            elif i == j:
                p_draw += p
            else:
                p_away += p
            if i > 0 and j > 0:
                btts_yes += p
            if j == 0:
                cs_home += p
            if i == 0:
                cs_away += p
            tot = i + j
            for ln in lines:
                if tot > ln:
                    over[ln] += p

    under = {ln: 1.0 - over[ln] for ln in lines}
    scorelines.sort(key=lambda kv: kv[1], reverse=True)

    return Markets(
        p_home=p_home,
        p_draw=p_draw,
        p_away=p_away,
        over=over,
        under=under,
        btts_yes=btts_yes,
        btts_no=1.0 - btts_yes,
        clean_sheet_home=cs_home,
        clean_sheet_away=cs_away,
        xg_home=xg_home,
        xg_away=xg_away,
        exp_total_goals=xg_home + xg_away,
        top_scorelines=scorelines[:top_n],
    )
