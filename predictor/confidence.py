"""Confidence index (ALTA / MEDIA / BAJA).

Confidence describes how strong/clear the *expected* result is, NOT the chance
of "getting it right". A low-confidence match that lands on the favorite does
not retroactively become high confidence, and an upset in a high-confidence
match does not lower the grade -- the upset was the improbable branch that the
distribution already priced in.

Drivers:
  1. How clear the favorite is in the 1X2 (the dominant signal).
  2. How well the sources agree (model vs market vs supercomputer).
  3. Implicitly, data stability -- passed in as an optional penalty.
"""

from __future__ import annotations

from typing import Optional, Tuple

LEVELS = ["BAJA", "MEDIA", "ALTA"]


def confidence_index(
    one_x_two: Tuple[float, float, float],
    market_divergence: Optional[float] = None,
    data_unstable: bool = False,
) -> Tuple[str, str]:
    """Return (level, rationale).

    Thresholds on the top 1X2 probability: ~0.45 -> Baja, ~0.80 -> Alta.
    """
    top = max(one_x_two)

    if top >= 0.60:
        idx = 2  # ALTA
    elif top >= 0.45:
        idx = 1  # MEDIA
    else:
        idx = 0  # BAJA

    reasons = [f"Favorito 1X2 al {top:.0%}"]

    # Downgrade when sources disagree materially.
    if market_divergence is not None and market_divergence > 0.07:
        idx = max(0, idx - 1)
        reasons.append(f"mercado diverge {market_divergence*100:.0f} pts (baja un nivel)")
    elif market_divergence is not None:
        reasons.append("alineado con el mercado")

    if data_unstable:
        idx = max(0, idx - 1)
        reasons.append("datos de base inestables (baja un nivel)")

    if idx == 0:
        reasons.append("partido parejo: el modelo NO tiene lectura fuerte")

    return LEVELS[idx], "; ".join(reasons)
