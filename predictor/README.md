# World Cup 2026 Match Predictor

A quantitative, decision-support tool for simulating football matches. It
produces **probability distributions**, not certainties — football has huge
irreducible variance, and the goal is to be *correctly uncertain*, not to sound
confident.

> Educational / prode (pool) use. Not betting advice. The house has a long-run
> edge; parlays multiply risk; cards/corners are close to noise. Only stake what
> you can afford to lose.

## Model

- **Bivariate Poisson + Dixon-Coles** low-score correction (parameter `rho`,
  negative, typically -0.03 to -0.08).
- The Dixon-Coles adjusted **score matrix is evaluated exactly** (closed form),
  so 1X2 / over-under / BTTS / clean sheet / scorelines are exact, not sampled.
- A **Monte Carlo** path (`simulate.py`) draws 100k-300k samples purely to *show*
  convergence to the exact numbers (uses numpy if installed, pure-Python
  fallback otherwise).
- **Pure standard library** for the core — runs anywhere, no scientific deps
  required.

## Calibrating xG (the important part)

Do **not** feed raw historical xG. Build each team's expected goals *for this
specific match*, bottom-up and opponent-adjusted, via `calibrate.py`:

```
lambda_home = base_home * attack_home * defense_away * context_home
lambda_away = base_away * attack_away * defense_home * context_away
```

- `base_*`: tournament goal environment + home edge.
- `attack` / `defense`: ratios around 1.0 (1.0 = tournament average).
- `context`: motivation, must-win, fatigue, going for a draw, etc.
- `notes`: write down the reasoning so every lambda is auditable.

`suggest_rho(style)` picks `rho` by match style (low_block → -0.08, open → -0.04).

## Usage

Run a match from a JSON config (see `matches/example.json`):

```bash
python -m predictor predict predictor/matches/example.json
python -m predictor predict predictor/matches/example.json --json
```

Quick one-off from raw lambdas:

```bash
python -m predictor quick --home "Arg" --away "Bra" \
    --lam-home 1.4 --lam-away 1.1 --rho -0.06 --odds 2.4 3.2 3.0
```

## What it outputs (delivery order)

1. Match context (venue, stakes, date)
2. How xG was calibrated (hard data + reasoning)
3. 1X2 table
4. Validation vs de-vigged market + supercomputer consensus (flags >7pt drift)
5. Goals markets (O/U 1.5/2.5/3.5, BTTS, clean sheet) + optional corners/cards
6. Most likely scorelines
7. Confidence index (ALTA / MEDIA / BAJA)
8. Prode recommendation (result + scoreline)
9. Uncertainty warnings
10. Monte Carlo convergence check

## Confidence index

Confidence is about how **clear the expected result** is, not about whether the
prediction "hits". A low-confidence match that lands on the favorite does not
become high confidence retroactively; an upset in a high-confidence match does
not lower the grade (the upset was the improbable branch already priced in).
Drivers: clarity of the 1X2 favorite, agreement across sources, data stability.

## Lineups

XIs are confirmed ~60 min before kickoff and can move the lambdas materially.
Re-run with updated `attack`/`defense`/`context` (or a `lambdas_override`) and
show the before/after.

## Tests

```bash
python -m unittest discover -s tests/predictor -p 'test_*.py'
```
