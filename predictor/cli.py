"""Command-line interface for the predictor.

Examples
--------
Run a match from a JSON config and print the full report:

    python -m predictor predict predictor/matches/example.json

Quick one-off from raw lambdas (skips bottom-up calibration):

    python -m predictor quick --home "Arg" --away "Bra" \
        --lam-home 1.4 --lam-away 1.1 --rho -0.06

Emit machine-readable JSON instead of the text report:

    python -m predictor predict predictor/matches/example.json --json
"""

from __future__ import annotations

import argparse
import json
import sys

from .match import load_match_file, run_match
from .report import render


def _cmd_predict(args: argparse.Namespace) -> int:
    result = load_match_file(args.config)
    if args.json:
        payload = {
            "match": f"{result.meta.home} vs {result.meta.away}",
            "lambdas": {
                "home": result.markets.xg_home,
                "away": result.markets.xg_away,
            },
            "markets": result.markets.as_dict(),
            "confidence": {
                "level": result.confidence_level,
                "reason": result.confidence_reason,
            },
            "recommendation": result.recommendation,
            "market_divergence": result.market_divergence,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(render(result, include_convergence=not args.no_convergence))
    return 0


def _cmd_quick(args: argparse.Namespace) -> int:
    cfg = {
        "meta": {"home": args.home, "away": args.away, "stage": "quick"},
        "calibration": {
            "rho": args.rho,
            "home": {"name": args.home},
            "away": {"name": args.away},
        },
        "lambdas_override": {"home": args.lam_home, "away": args.lam_away},
    }
    if args.odds:
        cfg["market"] = {"odds": args.odds}
    result = run_match(cfg)
    print(render(result, include_convergence=not args.no_convergence))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="predictor",
        description="World Cup 2026 match predictor (Poisson + Dixon-Coles).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    pred = sub.add_parser("predict", help="Run a match from a JSON config file.")
    pred.add_argument("config", help="Path to the match JSON config.")
    pred.add_argument("--json", action="store_true", help="Emit JSON instead of text report.")
    pred.add_argument("--no-convergence", action="store_true", help="Skip Monte Carlo check.")
    pred.set_defaults(func=_cmd_predict)

    quick = sub.add_parser("quick", help="One-off prediction from raw lambdas.")
    quick.add_argument("--home", required=True)
    quick.add_argument("--away", required=True)
    quick.add_argument("--lam-home", type=float, required=True)
    quick.add_argument("--lam-away", type=float, required=True)
    quick.add_argument("--rho", type=float, default=-0.06)
    quick.add_argument(
        "--odds",
        type=float,
        nargs=3,
        metavar=("HOME", "DRAW", "AWAY"),
        help="Decimal market odds for de-vig validation.",
    )
    quick.add_argument("--no-convergence", action="store_true")
    quick.set_defaults(func=_cmd_quick)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
