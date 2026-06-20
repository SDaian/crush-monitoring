"""World Cup 2026 match predictor.

Bivariate Poisson + Dixon-Coles low-score correction, exact score-matrix
evaluation (with optional Monte Carlo convergence check), bottom-up xG
calibration, market de-vig validation, confidence index, and optional
corners/cards markets.

This is a decision-support / prode (pool) tool for educational use, not betting
advice. Football has irreducible variance: the output is a distribution, never a
certainty.
"""

from .model import build_score_matrix, derive_markets, poisson_pmf, dc_tau
from .calibrate import MatchCalibration, TeamInputs, suggest_rho
from .confidence import confidence_index
from .validate import devig, max_divergence
from .match import run_match, load_match_file, MatchResult
from .report import render

__all__ = [
    "build_score_matrix",
    "derive_markets",
    "poisson_pmf",
    "dc_tau",
    "MatchCalibration",
    "TeamInputs",
    "suggest_rho",
    "confidence_index",
    "devig",
    "max_divergence",
    "run_match",
    "load_match_file",
    "MatchResult",
    "render",
]

__version__ = "0.1.0"
