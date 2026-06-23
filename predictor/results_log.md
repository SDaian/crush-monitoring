# Results log — Prediction vs Reality (World Cup 2026)

A logbook to measure the model's **calibration** over the course of the tournament.
The idea is not to count "hits" (the favorite often wins and there's little merit in
that), but to see whether the **xG and probabilities** were well placed, and to
separate what was right for good reasons from what was variance.

Legend: ✅ right for the right reason · 🟡 right but by luck/margin ·
❌ wrong · ⏳ result pending.

---

## 1X2 Summary

| Date | Match | Model (H/D/A) | Confidence | Actual result | 1X2 |
|---|---|---|---|---|---|
| 2026-06-20 | Ecuador vs Curaçao | 79.0 / 15.8 / 5.1 | HIGH | 0-0 (draw) | 🟡 |
| 2026-06-21 | Tunisia vs Japan | 14.7 / 21.7 / 63.6 | HIGH | 0-4 (Japan win) | ✅ |
| 2026-06-21 | Spain vs Saudi Arabia | 82.0 / 13.4 / 4.7 | HIGH | 4-0 (Spain win) | ✅ |
| 2026-06-21 | Egypt vs N. Zealand | 58.2 / 24.4 / 17.4 | MEDIUM | 3-1 (Egypt win) | ✅ |
| 2026-06-21 | Belgium vs Iran | 67.9 / 21.9 / 10.2 | HIGH | 0-0 (draw) | 🟡 |
| 2026-06-21 | Uruguay vs Cape Verde | 63.4 / 24.6 / 12.0 | HIGH | 2-2 (draw) | 🟡 |
| 2026-06-22 | Argentina vs Austria | 61.4 / 22.4 / 16.2 | HIGH | 2-0 (Argentina win) | ✅ |
| 2026-06-22 | Norway vs Senegal | 42.8 / 25.5 / 31.7 | LOW | 3-1 (Norway win) | ✅ |
| 2026-06-22 | Jordan vs Algeria | 15.6 / 23.2 / 61.2 | HIGH | ⏳ pending | ⏳ |

### Emerging pattern: favorites vs low block (key)

On these matchdays there were THREE 0-0 draws of favorites frustrated by low blocks:
Ecuador-Curaçao (MD1), Cape Verde-Spain (MD1) and Belgium-Iran (MD2). But also
two routs (Spain 4-0, Japan 4-0). **Honest conclusion:** "favorite breaks down the
block" has enormous variance and NEITHER my bottom-up NOR following the market hits
consistently. My bottom-up underestimates the favorite by ~8-9pts (I correct it to
the market), but the draw (~22-25%) materializes often. The correct reading is not
"does the favorite win?" but "the draw/Under is worth more than it seems when
the opponent is a PROVEN low block". Don't over-update with small n.

**Belgium-Iran 0-0 note:** the 1X2 missed (the 68% favorite didn't win; the 21.9%
draw came in), BUT the value reads DID land: with Iran in a 5-4-1 I flagged BTTS No
(61%), Under 3.5 (76%) and "few goals" — all won. A process hit in the goals markets
even though the favorite didn't break the deadlock.

**Uruguay-Cape Verde 2-2 note (KEY refinement of the pattern):** Cape Verde
frustrated ANOTHER favorite (the debutant's 3rd point), confirming the pattern. BUT
it was 2-2, not 0-0 — and that forces two refinements:
1. "Low block" ≠ "harmless": I underestimated Cape Verde's attack (λ 0.60; they
   scored 2, including a screamer). When the match opens up and the favorite
   stretches, the block DOES create and convert. Its xG-for is not fixed at ~0.
2. The correct vehicle for the "frustrated favorite" thesis is the DRAW / double
   chance, NOT the Under/BTTS-No. Here I recommended Under 2.5 (60%) and BTTS No
   (62%) and BOTH lost (2-2 = Over + BTTS Yes); the draw, on the other hand, came in.
   Lesson: express "favorite doesn't break down the block" via RESULT, not via goals.

## xG calibration (what really matters)

| Match | Team | λ model | actual xG | Verdict |
|---|---|---|---|---|
| Tunisia vs Japan | Japan | 2.00 | 2.07 | ✅ almost exact |
| Tunisia vs Japan | Tunisia | 0.855 | 0.05 | ❌ overestimated (Tunisia was null) |
| Spain vs Saudi Arabia | Spain | 2.60 | 4 goals, 21 shots | ❌ underestimated (my anti-market lean failed) |

---

## 2026-06-21 · Spain 4-0 Saudi Arabia (Group H, Matchday 2)

**Model prediction:** Spain 82.0% / Draw 13.4% / Saudi Arabia 4.7%. I set myself
DELIBERATELY ~4-7 pts BELOW the market (86.4%), with the thesis of "Spain blunt
without a striker, coming off a 0-0 with Cape Verde, value in the draw".

**Actual result:** Spain 4-0, with 21 shots. Spain came out to overwhelm (3-0 by
the 27'). **My contrarian lean FAILED outright: the market was right and I wasn't.**

**Honest reading:**
- ✅ 1X2: the favorite won (little merit, it was the easy scenario).
- ❌ My bias "Spain doesn't rout / value in the draw" got swallowed by a rout. The
  0-0 with Cape Verde wasn't the norm, it was the outlier; I over-corrected for it.
- 📌 Lesson symmetric to Tunisia-Japan: there the market and I agreed and it turned
  out well; here I broke from consensus and consensus won. Breaking from the market
  is where the value is BUT also where being wrong costs the most.
- 💸 User's bet (6-leg combo, odds 10.0, €30): closed (cash out) at
  **€214.29** (profit +€184). Held beyond the EV-optimal halftime cash out
  (~€80) and variance rewarded it; de-risked well by closing at 85' with
  4-0 (a fair-to-generous close). Good RESULT; the process was +variance, not
  +EV — a good ending doesn't retroactively validate the riskier path.

---

## 2026-06-21 · Tunisia 0-4 Japan (Group F, match No. 1000)

**Model prediction:** Japan 63.6% / Draw 21.7% / Tunisia 14.7% (aligned with the
market, divergence ~2 pts). Confidence HIGH. Suggested: Japan win, scoreline 0-2.
xG: Japan 2.00, Tunisia 0.855.

**Actual result:** Tunisia 0-4 Japan. Goals: Kamada 4', Ueda 31' and 83', Ito 69'.
**Actual stats:** possession 36-55; shots 2 (0 on target) vs 10 (4 on target);
**xG 0.05 vs 2.07**; Japan >5 corners; Tunisia eliminated.

**Honest reading:**
- ✅ **Japan wins / clean sheet / corner dominance:** structurally correct
  reading. My Japan λ (2.00) nailed the actual xG (2.07): the chances created
  were exactly as modeled.
- ✅ **Tunisia doesn't score:** correct, and in fact **safer** than the model
  said. Tunisia generated 0.05 of xG (2 shots, 0 on target): it was even more
  harmless than what I (and the market) assumed.
- ❌ **I overestimated Tunisia:** I gave it λ 0.855 expecting some "Renard bounce"
  and for it to open up; it generated nothing. Lesson: for a battered team without
  a striker, "must attack" doesn't translate into xG.
- 🟡 **The 0-4 was finishing variance, not model variance:** Japan converted 4 with
  2.07 of xG (≈2× its expected output). My suggested scoreline (0-2) reflected
  the correct central scenario; the rout was in the tail (Japan by 4+ = 8.3%).
- 📌 **Betting note:** the final combo (BTTS No + Japan win + Japan +4
  corners + Japan more corners) won all 4 legs. But it was still **−EV** by
  the model (~−17% at odds 3.60): winning doesn't make it good retroactively.
  Process hit: **not** having added "Under 3.5", which would have lost
  (total = 4 goals).

**Process note:** a very clear favorite that won as expected (little merit in
the result); the value was in calibrating Japan well and in trimming the
combo. The model was transparent about what it doesn't control (the magnitude).

---

## 2026-06-20 · Ecuador vs Curaçao (Group E)

**Model prediction:** Ecuador 79.0% / Draw 15.8% / Curaçao 5.1%. Confidence
HIGH (aligned with market, Opta 86.1). Suggested: Ecuador win, scoreline 2-0.
xG: Ecuador 2.30, Curaçao 0.44.

**Actual result:** Ecuador 0-0 Curaçao. Eloy Room (Curaçao's goalkeeper) made
~15 saves, one of the best individual performances in World Cup history. Ecuador
75% possession, 642 passes, and couldn't break the deadlock.

**Honest reading:**
- 🟡 1X2: the favorite did NOT win. The draw (which the model gave 26% — more than
  the market) happened. My skepticism about "blunt favorite vs low block" was
  VALIDATED here (unlike Spain, where the same skepticism failed).
- The suggested scoreline (2-0) missed, but the model was already flagging high
  draw risk and I was below the market on the rout.
- 📌 Betting note (passes prop): Piero Hincapié finished with 72 passes
  (62/72, 86%) per Opta — the "142" going around was Hincapié+Pacho COMBINED.

*(Correction logged: the referee of this match was NOT István Kovács; that
data came from a single source and turned out to be wrong — Kovács officiated Tunisia-Japan.)*

---

## 2026-06-21 · Egypt 3-1 New Zealand (Group G, MD2)

**Model:** Egypt 58.2 / Draw 24.4 / NZ 17.4 (MEDIUM, aligned with market).
Lambdas Egypt 1.75 / NZ 0.85, rho -0.05 (open game).

**Actual result:** Egypt 3-1 (Egypt came from behind). Both teams scored; 4 goals
total; 3 yellow cards. Referee Omar Al Ali.

**Honest read — a POSITIVE counterpoint to the low-block 0-0s:**
- ✅ 1X2: favorite won.
- ✅ The key call was reading this as the OPEN game of the group: New Zealand is
  NOT a low block (4-2-3-1, scored twice vs Iran), so I explicitly said the
  "favorite frustrated by a low block" pattern did NOT apply and flagged
  BTTS/Over as the value angle. Result: BTTS Yes, Over 3.5, favorite wins.
  Correctly distinguished an open underdog (NZ) from a parked-bus one
  (Cape Verde / Iran / Saudi).
- Refinement confirmed: classify the underdog's setup first. Low block ->
  draw/Under value; open/attacking underdog -> back the favorite + goals.
- 📌 User's combo (Egypt win + BTTS Yes + Under 5 cards) hit all three legs;
  cashed out at $106.

---

## 2026-06-22 · Argentina 2-0 Austria (Group J, MD2)

**Model:** Argentina 61.4 / Draw 22.4 / Austria 16.2 (HIGH, aligned with market).
Lambdas Argentina 1.95 / Austria 0.90, rho -0.05. Expected total goals 2.85.

**Actual result:** Argentina 2-0. Won comfortably but controlled, not a goal-fest;
Argentina dominated possession yet did NOT generate many corners (<5).

**Honest read:**
- ✅ 1X2: favorite won.
- ❌ Over 2.5 missed (2-0 = 2 goals). Over was 54% (so ~46% to be Under) — within
  range, mostly variance: Austria competed defensively enough and Argentina
  converted efficiently rather than piling on.
- ❌ **Corners calibration error (a real lesson, not just variance):** I set
  Argentina corners λ 6.0; they finished under 5. **Dominance/possession does NOT
  reliably translate into corners** — a side that attacks through the middle, or
  whose opponent clears without conceding corners, can dominate with few corners.
  Lower the corner-lambda assumption for possession-dominant favorites.
- 💸 User's 4-leg Bet Builder (Over 2.5 + Messi G/A + Argentina win + Argentina
  +4 corners) lost on the volume legs (corners, and Over 2.5). It was +EV by the
  model (~+30%) but only ~26% to hit; losing was the expected outcome. The
  failure mode is the recurring one: the RESULT (favorite wins) is robust, the
  VOLUME props (corners/Over) carry the variance — and here the corner leg was
  also over-modeled.

**Takeaway:** trust the result/Messi-involvement reads more than goal/corner
VOLUME reads; specifically recalibrate corners downward for favorites that
dominate without a wing-heavy, corner-generating style.

---

## 2026-06-22 · Norway 3-1 Senegal (Group I, MD2)

**Model:** Norway 42.8 / Draw 25.5 / Senegal 31.7 (LOW confidence — flagged as
the most even match, no strong read). Lambdas 1.60 / 1.35, total xG 2.95.

**Actual result:** Norway 3-1 (Haaland brace). Both scored, 4 goals, **0 cards**.

**Honest read:**
- ✅ Open-game read VALIDATED: I called this the open match of the group (both
  full-strength, attacking) and flagged BTTS + several goals as the picture.
  Result: BTTS Yes, Over 3.5, 4 goals. The LOW-confidence slight favorite won.
- ✅ Haaland delivered (brace), consistent with his red-hot form.
- ❌ **Cards model: big miss (the noisiest market, as warned).** Expected ~4.28
  yellows on the Sampaio (card-happy) signal; actual was 0. That is a ~1.4% tail
  event (e^-4.28). Not a calibration error on the mean — it's extreme variance in
  a market the model itself labels "near random". Reinforces the rule: do NOT
  lean on cards as a value read even with a strong referee signal; the referee
  inclines the distribution, it does not determine a single game.

---

## 2026-06-22 · Jordan vs Algeria (Group J, MD2) — ⏳ PENDING

**Pre-match forecast (not yet played).** Both lost MD1 (Jordan 1-3 Austria;
Algeria 0-3 Argentina) and sit on 0 points: a must-win for both.

**Model:** Jordan 15.6 / Draw 23.2 / Algeria 61.2 (HIGH). Lambdas Jordan 0.82 /
Algeria 1.85, total xG 2.67, rho -0.05. Monte Carlo (N=200k) converges:
Home 15.5 / Draw 23.1 / Away 61.4 (max diff 0.14 pts vs closed form).

**Calibration vs market:** de-vig market 15.8 / 22.6 / 61.6 (book margin 5.4%);
max divergence 0.6 pts → aligned. No anti-market lean; Algeria is the quality
side (Mahrez, Gouiri, Aouar, Amoura), Jordan a competitive but limited underdog.

**Most probable scorelines:** 0-1 (12.3%), 0-2 (11.9%), 1-1 (11.0%), 1-2 (9.7%),
0-0 (7.5%). Goals: Over 2.5 49.9% (a coin-flip total), BTTS 47.7%, Algeria clean
sheet 44%.

**Pre-match read:** Algeria should win but the margin is the uncertain part — a
clean-sheet 0-1/0-2 is the central scenario, not a rout. The two open low-block
risks logged this tournament (favourite frustrated 0-0) are a tail here too:
Jordan will go for it (must-win), so the game is more likely to open up than to
be parked. Recalibrate with the confirmed XIs ~60 min before kickoff.

*To be graded after the match (xG vs actual, 1X2, lesson).*
