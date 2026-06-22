"""Unit tests for the predictor core. Pure stdlib + unittest, no pytest needed.

Run with:  python -m unittest discover -s tests/predictor -p 'test_*.py'
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from predictor.model import (  # noqa: E402
    build_score_matrix,
    derive_markets,
    poisson_pmf,
    dc_tau,
)
from predictor.calibrate import MatchCalibration, TeamInputs, suggest_rho  # noqa: E402
from predictor.confidence import confidence_index  # noqa: E402
from predictor.validate import devig, max_divergence  # noqa: E402
from predictor.match import run_match  # noqa: E402
from predictor.simulate import simulate  # noqa: E402


class TestPoisson(unittest.TestCase):
    def test_pmf_sums_to_one(self):
        total = sum(poisson_pmf(k, 1.4) for k in range(40))
        self.assertAlmostEqual(total, 1.0, places=9)

    def test_pmf_known_value(self):
        # P(X=0) = e^-lambda
        self.assertAlmostEqual(poisson_pmf(0, 2.0), 0.1353352832, places=8)

    def test_zero_lambda(self):
        self.assertEqual(poisson_pmf(0, 0.0), 1.0)
        self.assertEqual(poisson_pmf(3, 0.0), 0.0)


class TestDixonColes(unittest.TestCase):
    def test_tau_unaffected_above_one(self):
        self.assertEqual(dc_tau(2, 3, 1.4, 1.1, -0.06), 1.0)

    def test_tau_directions(self):
        # negative rho should inflate 0-0 and 1-1, deflate 1-0 and 0-1
        self.assertGreater(dc_tau(0, 0, 1.4, 1.1, -0.06), 1.0)
        self.assertGreater(dc_tau(1, 1, 1.4, 1.1, -0.06), 1.0)
        self.assertLess(dc_tau(1, 0, 1.4, 1.1, -0.06), 1.0)
        self.assertLess(dc_tau(0, 1, 1.4, 1.1, -0.06), 1.0)


class TestScoreMatrix(unittest.TestCase):
    def test_normalized(self):
        sm = build_score_matrix(1.45, 1.0, rho=-0.06)
        total = sum(sm.matrix[i][j] for i in range(sm.max_goals + 1) for j in range(sm.max_goals + 1))
        self.assertAlmostEqual(total, 1.0, places=9)

    def test_all_nonnegative(self):
        sm = build_score_matrix(0.3, 0.3, rho=-0.08)
        for row in sm.matrix:
            for p in row:
                self.assertGreaterEqual(p, 0.0)

    def test_dc_raises_low_score_density(self):
        # DC with negative rho should put more mass on 0-0 than plain Poisson
        sm_dc = build_score_matrix(1.3, 1.1, rho=-0.07)
        sm_plain = build_score_matrix(1.3, 1.1, rho=0.0)
        self.assertGreater(sm_dc.matrix[0][0], sm_plain.matrix[0][0])


class TestMarkets(unittest.TestCase):
    def setUp(self):
        self.sm = build_score_matrix(1.6, 1.0, rho=-0.06)
        self.m = derive_markets(self.sm)

    def test_1x2_sums_to_one(self):
        self.assertAlmostEqual(self.m.p_home + self.m.p_draw + self.m.p_away, 1.0, places=9)

    def test_home_favored_with_higher_lambda(self):
        self.assertGreater(self.m.p_home, self.m.p_away)

    def test_xg_recovers_lambda_approximately(self):
        # Exact xG from the matrix should be close to the input lambdas
        # (DC perturbs it slightly; large max_goals keeps truncation tiny).
        self.assertAlmostEqual(self.m.xg_home, 1.6, delta=0.05)
        self.assertAlmostEqual(self.m.xg_away, 1.0, delta=0.05)

    def test_over_under_complementary(self):
        for ln in self.m.over:
            self.assertAlmostEqual(self.m.over[ln] + self.m.under[ln], 1.0, places=9)

    def test_btts_complementary(self):
        self.assertAlmostEqual(self.m.btts_yes + self.m.btts_no, 1.0, places=9)

    def test_top_scorelines_sorted(self):
        probs = [p for _, p in self.m.top_scorelines]
        self.assertEqual(probs, sorted(probs, reverse=True))


class TestCalibration(unittest.TestCase):
    def test_lambda_multiplicative(self):
        cal = MatchCalibration(
            home=TeamInputs("A", attack=1.2, defense=0.9),
            away=TeamInputs("B", attack=0.8, defense=1.1),
            base_home=1.35,
            base_away=1.15,
        )
        lam = cal.lambdas()
        self.assertAlmostEqual(lam["home"], 1.35 * 1.2 * 1.1 * 1.0, places=3)
        self.assertAlmostEqual(lam["away"], 1.15 * 0.8 * 0.9 * 1.0, places=3)

    def test_suggest_rho(self):
        self.assertEqual(suggest_rho("low_block"), -0.08)
        self.assertEqual(suggest_rho("open"), -0.04)
        self.assertEqual(suggest_rho("unknown_style"), -0.06)


class TestValidate(unittest.TestCase):
    def test_devig_sums_to_one(self):
        fair = devig(2.10, 3.30, 3.60)
        self.assertAlmostEqual(fair["home"] + fair["draw"] + fair["away"], 1.0, places=9)

    def test_devig_overround_positive(self):
        fair = devig(2.10, 3.30, 3.60)
        self.assertGreater(fair["overround"], 0.0)

    def test_max_divergence(self):
        self.assertAlmostEqual(max_divergence((0.5, 0.3, 0.2), (0.45, 0.30, 0.25)), 0.05, places=9)


class TestConfidence(unittest.TestCase):
    def test_clear_favorite_is_high(self):
        level, _ = confidence_index((0.80, 0.13, 0.07))
        self.assertEqual(level, "HIGH")

    def test_even_match_is_low(self):
        level, _ = confidence_index((0.40, 0.32, 0.28))
        self.assertEqual(level, "LOW")

    def test_divergence_downgrades(self):
        high, _ = confidence_index((0.62, 0.22, 0.16))
        self.assertEqual(high, "HIGH")
        downgraded, _ = confidence_index((0.62, 0.22, 0.16), market_divergence=0.10)
        self.assertEqual(downgraded, "MEDIUM")


class TestIntegration(unittest.TestCase):
    def test_run_match_end_to_end(self):
        cfg = {
            "meta": {"home": "Arg", "away": "Mex", "stage": "test"},
            "calibration": {
                "rho": -0.06,
                "base_home": 1.35,
                "base_away": 1.15,
                "home": {"name": "Arg", "attack": 1.25, "defense": 0.85},
                "away": {"name": "Mex", "attack": 0.95, "defense": 1.05},
            },
            "market": {"odds": [1.80, 3.50, 4.50]},
            "cards": {"referee_yellow_avg": 4.0},
        }
        res = run_match(cfg)
        self.assertAlmostEqual(
            res.markets.p_home + res.markets.p_draw + res.markets.p_away, 1.0, places=9
        )
        self.assertIn(res.confidence_level, {"HIGH", "MEDIUM", "LOW"})
        self.assertIsNotNone(res.market_divergence)
        self.assertIsNotNone(res.cards)
        self.assertGreater(res.markets.p_home, res.markets.p_away)

    def test_simulation_converges_to_exact(self):
        sm = build_score_matrix(1.5, 1.1, rho=-0.06)
        m = derive_markets(sm)
        sim = simulate(sm, n=120_000, seed=7)
        # Monte Carlo should land within ~1 point of the exact 1X2.
        self.assertAlmostEqual(sim["home"], m.p_home, delta=0.012)
        self.assertAlmostEqual(sim["draw"], m.p_draw, delta=0.012)
        self.assertAlmostEqual(sim["away"], m.p_away, delta=0.012)


if __name__ == "__main__":
    unittest.main()
