"""Monte Carlo simulation over the Dixon-Coles score matrix.

The exact markets in ``model.derive_markets`` are the source of truth. This
module draws N samples from the same normalized matrix so we can *show* that a
large simulation converges to the exact numbers (the methodology asked for
100k-300k sims). It uses numpy if present for speed, and falls back to the
standard library otherwise.
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Dict, Tuple

from .model import ScoreMatrix

try:  # optional acceleration
    import numpy as _np
except Exception:  # pragma: no cover - numpy is optional
    _np = None


def simulate(sm: ScoreMatrix, n: int = 200_000, seed: int | None = 42) -> Dict[str, float]:
    """Return 1X2 probabilities estimated by sampling the matrix.

    Used purely as a convergence check against the exact values.
    """
    size = sm.max_goals + 1
    flat = [sm.matrix[i][j] for i in range(size) for j in range(size)]

    if _np is not None:
        rng = _np.random.default_rng(seed)
        probs = _np.asarray(flat, dtype=float)
        probs = probs / probs.sum()
        idx = rng.choice(len(flat), size=n, p=probs)
        hg = idx // size
        ag = idx % size
        home = int((hg > ag).sum())
        draw = int((hg == ag).sum())
        away = n - home - draw
    else:
        cum = []
        run = 0.0
        for p in flat:
            run += p
            cum.append(run)
        rng = random.Random(seed)
        counts = Counter()
        import bisect

        for _ in range(n):
            r = rng.random() * run
            k = bisect.bisect_left(cum, r)
            i, j = divmod(k, size)
            if i > j:
                counts["home"] += 1
            elif i == j:
                counts["draw"] += 1
            else:
                counts["away"] += 1
        home, draw, away = counts["home"], counts["draw"], counts["away"]

    return {
        "home": home / n,
        "draw": draw / n,
        "away": away / n,
        "n": n,
    }


def convergence_report(sm: ScoreMatrix, exact: Tuple[float, float, float], n: int = 200_000) -> str:
    sim = simulate(sm, n=n)
    eh, ed, ea = exact
    lines = [
        f"Monte Carlo convergence check (N={n:,}):",
        f"  Home  exact {eh:6.2%} | sim {sim['home']:6.2%} | diff {abs(eh-sim['home'])*100:4.2f} pts",
        f"  Draw  exact {ed:6.2%} | sim {sim['draw']:6.2%} | diff {abs(ed-sim['draw'])*100:4.2f} pts",
        f"  Away  exact {ea:6.2%} | sim {sim['away']:6.2%} | diff {abs(ea-sim['away'])*100:4.2f} pts",
    ]
    return "\n".join(lines)
