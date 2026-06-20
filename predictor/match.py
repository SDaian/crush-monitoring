"""Match configuration: load a match from JSON, run the full pipeline.

A match is fully described by a JSON file so every prediction is reproducible
and auditable -- you can read exactly which lambdas were used and why.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional, Tuple

from .calibrate import MatchCalibration, TeamInputs
from .confidence import confidence_index
from .extras import CardsModel, CornersModel
from .model import ScoreMatrix, build_score_matrix, derive_markets, Markets
from .validate import devig, max_divergence


@dataclass
class MatchMeta:
    home: str
    away: str
    venue: str = ""
    date: str = ""
    stage: str = ""
    stakes: str = ""


@dataclass
class MatchResult:
    meta: MatchMeta
    calibration: MatchCalibration
    score_matrix: ScoreMatrix
    markets: Markets
    market_fair: Optional[dict]
    supercomputer: Optional[Tuple[float, float, float]]
    market_divergence: Optional[float]
    confidence_level: str
    confidence_reason: str
    corners: Optional[dict]
    cards: Optional[dict]
    recommendation: dict


def _team(d: dict) -> TeamInputs:
    return TeamInputs(
        name=d.get("name", "?"),
        attack=d.get("attack", 1.0),
        defense=d.get("defense", 1.0),
        context=d.get("context", 1.0),
        notes=d.get("notes", []),
    )


def run_match(cfg: dict) -> MatchResult:
    meta_d = cfg.get("meta", {})
    meta = MatchMeta(
        home=meta_d.get("home", cfg.get("calibration", {}).get("home", {}).get("name", "Local")),
        away=meta_d.get("away", cfg.get("calibration", {}).get("away", {}).get("name", "Visitante")),
        venue=meta_d.get("venue", ""),
        date=meta_d.get("date", ""),
        stage=meta_d.get("stage", ""),
        stakes=meta_d.get("stakes", ""),
    )

    cal_d = cfg["calibration"]
    cal = MatchCalibration(
        home=_team(cal_d["home"]),
        away=_team(cal_d["away"]),
        base_home=cal_d.get("base_home", 1.35),
        base_away=cal_d.get("base_away", 1.15),
        rho=cal_d.get("rho", -0.06),
    )

    override = cfg.get("lambdas_override")
    if override:
        lam_home, lam_away = override["home"], override["away"]
    else:
        lam = cal.lambdas()
        lam_home, lam_away = lam["home"], lam["away"]

    sm = build_score_matrix(lam_home, lam_away, rho=cal.rho)
    markets = derive_markets(sm)

    one_x_two = (markets.p_home, markets.p_draw, markets.p_away)

    market_fair = None
    market_div = None
    market_cfg = cfg.get("market", {})
    if market_cfg.get("odds"):
        market_fair = devig(*market_cfg["odds"])
        market_div = max_divergence(
            one_x_two, (market_fair["home"], market_fair["draw"], market_fair["away"])
        )
    supercomputer = tuple(market_cfg["supercomputer"]) if market_cfg.get("supercomputer") else None

    level, reason = confidence_index(
        one_x_two,
        market_divergence=market_div,
        data_unstable=cfg.get("data_unstable", False),
    )

    corners = None
    if cfg.get("corners"):
        corners = CornersModel(**cfg["corners"]).markets()
    cards = None
    if cfg.get("cards"):
        cards = CardsModel(**cfg["cards"]).markets()

    # Recommendation: pick the modal 1X2 outcome and the modal scoreline.
    outcome = max(
        [("Local", markets.p_home), ("Empate", markets.p_draw), ("Visitante", markets.p_away)],
        key=lambda kv: kv[1],
    )
    top_score = markets.top_scorelines[0]
    recommendation = {
        "result": outcome[0],
        "result_prob": outcome[1],
        "scoreline": f"{top_score[0][0]}-{top_score[0][1]}",
        "scoreline_prob": top_score[1],
    }

    return MatchResult(
        meta=meta,
        calibration=cal,
        score_matrix=sm,
        markets=markets,
        market_fair=market_fair,
        supercomputer=supercomputer,
        market_divergence=market_div,
        confidence_level=level,
        confidence_reason=reason,
        corners=corners,
        cards=cards,
        recommendation=recommendation,
    )


def load_match_file(path: str) -> MatchResult:
    with open(path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    return run_match(cfg)
