"""Bottom-up xG (lambda) calibration helpers.

The methodology is emphatic: do NOT feed raw historical xG into the model.
Build each team's expected goals *for this specific match*, adjusted to the
opponent and context. These helpers make that reasoning explicit and
reproducible instead of hiding it inside a magic number.

The model is multiplicative around a tournament baseline, in the spirit of the
classic attack/defence strength factorization:

    lambda_home = base_home * att_home * def_away * context_home
    lambda_away = base_away * att_away * def_home * context_away

where ``base`` already folds in the tournament's goal environment and a small
home-edge, and the strength factors are ratios around 1.0 (1.0 = tournament
average, >1 stronger attack / leakier defence).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class TeamInputs:
    """Per-team calibration inputs, all as ratios around 1.0 unless noted."""

    name: str
    attack: float = 1.0  # >1 = generates more than tournament avg
    defense: float = 1.0  # >1 = concedes more than avg (leakier); <1 = elite
    # Free-form context multiplier applied to this team's lambda
    # (motivation, must-win, fatigue, altitude, going for a draw, etc.)
    context: float = 1.0
    notes: List[str] = field(default_factory=list)


@dataclass
class MatchCalibration:
    home: TeamInputs
    away: TeamInputs
    # Tournament goal environment: expected goals for an average team in an
    # average match at this tournament (split per side, includes home edge).
    base_home: float = 1.35
    base_away: float = 1.15
    rho: float = -0.06

    def lambdas(self) -> Dict[str, float]:
        lam_home = self.base_home * self.home.attack * self.away.defense * self.home.context
        lam_away = self.base_away * self.away.attack * self.home.defense * self.away.context
        return {"home": round(lam_home, 3), "away": round(lam_away, 3)}

    def reasoning(self) -> str:
        lam = self.lambdas()
        out = [
            "Bottom-up xG calibration",
            "------------------------",
            f"Tournament base: home {self.base_home} | away {self.base_away} "
            f"(folds in goal environment + home edge)",
            f"rho (Dixon-Coles): {self.rho}",
            "",
            f"{self.home.name} (HOME): attack x{self.home.attack} * "
            f"opp_def x{self.away.defense} * context x{self.home.context} "
            f"=> lambda {lam['home']}",
        ]
        for n in self.home.notes:
            out.append(f"    - {n}")
        out.append(
            f"{self.away.name} (AWAY): attack x{self.away.attack} * "
            f"opp_def x{self.home.defense} * context x{self.away.context} "
            f"=> lambda {lam['away']}"
        )
        for n in self.away.notes:
            out.append(f"    - {n}")
        return "\n".join(out)


def suggest_rho(style: str) -> float:
    """Pick rho by match style, per the methodology's guidance.

    - "low_block" / "cagey": more negative (-0.07/-0.08) -> more 0-0,1-0,1-1
    - "open" / "end_to_end": less negative (-0.03)
    - default balanced: -0.06
    """
    table = {
        "low_block": -0.08,
        "cagey": -0.07,
        "balanced": -0.06,
        "open": -0.04,
        "end_to_end": -0.03,
    }
    return table.get(style, -0.06)
