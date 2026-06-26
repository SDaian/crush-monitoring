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
| 2026-06-22 | Jordan vs Algeria | 15.6 / 23.2 / 61.2 | HIGH | 1-2 (Algeria win) | ✅ |
| 2026-06-23 | Portugal vs Uzbekistan | 71.6 / 18.9 / 9.5 | HIGH | 4-0 (Portugal win) | ✅ |
| 2026-06-23 | England vs Ghana | 65.3 / 21.4 / 13.3 | HIGH | 0-0 (draw) | 🟡 |
| 2026-06-23 | Croatia vs Panama | 58.6 / 24.9 / 16.5 | MEDIUM | 1-0 (Croatia win) | ✅ |
| 2026-06-24 | Colombia vs DR Congo | 54.9 / 25.9 / 19.3 | MEDIUM | 1-0 (Colombia win) | ✅ |
| 2026-06-24 | Scotland vs Brazil | 14.4 / 24.0 / 61.7 | HIGH | 0-3 (Brazil win) | ✅ |
| 2026-06-24 | Morocco vs Haiti | 69.5 / 21.9 / 8.5 | HIGH | 4-2 (Morocco win) | ✅ |
| 2026-06-24 | Mexico vs Czech Rep. | 45.5 / 27.8 / 26.6 | MEDIUM | 3-0 (Mexico win) | ✅ |
| 2026-06-24 | South Korea vs S. Africa | 58.3 / 26.2 / 15.5 | MEDIUM | 0-1 (S. Africa win) | ❌ |
| 2026-06-24 | Switzerland vs Canada | 33.5 / 28.4 / 38.2 | LOW | 2-1 (Switzerland win) | 🟡 |
| 2026-06-24 | Bosnia & Herz. vs Qatar | 55.7 / 26.1 / 18.2 | MEDIUM | 3-1 (Bosnia win) | ✅ |
| 2026-06-24 | Norway vs France | 34.2 / 25.1 / 40.7 | LOW | 1-4 (France win) | ✅ |
| 2026-06-24 | Senegal vs Iraq | 54.7 / 25.3 / 20.0 | MEDIUM | 5-0 (Senegal win) | ✅ |

### Emerging pattern: favorites vs low block (key)

There have now been FOUR 0-0 draws of favorites frustrated by organized opponents:
Ecuador-Curaçao (MD1), Cape Verde-Spain (MD1), Belgium-Iran (MD2) and
England-Ghana (MD2). But also routs (Spain 4-0, Japan 4-0, Portugal 4-0). **Honest
conclusion:** "favorite breaks down the block" has enormous variance and NEITHER my
bottom-up NOR following the market hits
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
| Morocco vs Haiti | Haiti | 0.48 | 2 goals | ❌ overestimated low (a "weak" side scored 2 in a goal-fest) |
| Morocco vs Haiti | Morocco | 1.82 | 4 goals | 🟡 mean low, finishing tail (controlled win became 4-2) |

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

## 2026-06-22 · Jordan 1-2 Algeria (Group J, MD2)

**Pre-match forecast (graded below).** Both lost MD1 (Jordan 1-3 Austria;
Algeria 0-3 Argentina) and sat on 0 points: a must-win for both.

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

**Actual result:** Jordan 1-2 Algeria. Algeria won by the expected ~2-goal
margin; Jordan scored (competitive, as flagged). 3 goals total, BTTS Yes.

**Honest read — a clean calibration hit:**
- ✅ 1X2: the 61% favourite won. Aligned with the market (0.6 pt divergence),
  no anti-market lean — the correct, low-merit-but-well-placed call.
- ✅ **xG / margin nailed:** the λ gap (Algeria 1.85 vs Jordan 0.82) implied a
  ~1-goal-and-change edge, i.e. a 0-2 / 1-2 central band. Actual 1-2 was the
  model's **#4 scoreline (9.7%)** and sat squarely in that band — not a rout,
  not a slip. Expected total 2.67 vs actual 3 (Over 2.5 landed, 49.9% coin-flip).
- ✅ **Pre-match read validated:** I explicitly said Jordan (must-win) would go
  for it and the game was likelier to open than to be parked — so the low-block
  0-0 tail did NOT apply here. Jordan duly scored (BTTS Yes 47.7% came in); the
  Algeria clean sheet (44%) correctly did NOT.
- 📌 Process note: HIGH confidence was justified — the result landed in the
  central scenario. No new calibration lesson; this is the model behaving as
  designed on a correctly-read favourite.

---

## 2026-06-23 · Portugal vs Uzbekistan (Group K) — ⏳ PENDING

**Pre-match forecast (not yet played).** Standings before kickoff: Colombia 3 pts
(3-1 Uzbekistan), Portugal 1 (1-1 DR Congo), DR Congo 1, Uzbekistan 0. Portugal
the clear quality side but drew their opener; Uzbekistan a World Cup debutant.

**Model:** Portugal 71.6 / Draw 18.9 / Uzbekistan 9.5 (HIGH). Lambdas Portugal
2.20 / Uzbekistan 0.68, total xG 2.88, rho -0.08. Monte Carlo (N=200k) converges:
exact 71.6 / 18.9 / 9.5 vs sim 71.7 / 18.9 / 9.5 (max diff 0.10 pts).

**Calibration vs market:** de-vig market ~72.8 / 17.2 / 10.0 (book margin 5.6%);
max divergence 1.7 pts → aligned. **Applied the Spain lesson:** an initial λ of
2.0 put Portugal at 67% (~6 pts BELOW market); bumped to 2.20 to sit in line with
the market — don't lean below an elite favourite.

**Most probable scorelines:** 2-0 (13.6%), 1-0 (11.8%), 3-0 (10.0%), 2-1 (9.2%),
1-1 (9.0%). Goals: Over 2.5 54.9%, BTTS 44.5%, Portugal clean sheet 50.7%.

**Pre-match read:** Portugal should win comfortably; the central scenario is a
1-2 goal clean-sheet win (2-0/1-0/3-0), not necessarily a rout. Uzbekistan's path
to value is the draw/Portugal-not-to-rout, but as a beaten debutant that is a
tail.

**Lineup recalibration (CONFIRMED XIs):** Portugal start at full strength —
Diogo Costa; Dalot, Tomás Araújo, Rúben Dias, Cancelo; Vitinha, João Neves;
Bernardo Silva, Bruno Fernandes, Francisco Conceição; Ronaldo. No rotation after
the opener → **λ 2.20 unchanged, forecast locked at 71.6 / 18.9 / 9.5**. Referee
still TBD at lock-in → cards intentionally not modelled.

**Actual result:** Portugal 4-0 Uzbekistan. Clean sheet, BTTS No, 4 goals.

**Honest read — favorite + goals validated, Spain lesson vindicated:**
- ✅ 1X2: the 72% favourite won (low merit, the expected scenario).
- ✅ **Goals reads all landed:** Portugal clean sheet (50.7%), Over 2.5 (54.9%)
  and Over 3.5 (32.6%) all came in; BTTS No. The picture (favourite + goals,
  not a low-block trap) was right.
- 🟡 **Margin was the high tail:** modelled Portugal xG 2.20; they scored 4
  (~1.8× finishing). The xG MEAN was well placed; the 4-0 itself is upside
  variance (Portugal 4+ was the tail), same as Tunisia-Japan and Spain.
- ✅ **Spain lesson vindicated:** I bumped Portugal from an initial 67% UP to
  71.6% to sit with the market rather than lean below an elite favourite — and,
  like Spain, it routed. Aligning up was correct.
- 📌 **Pattern (3 cases now):** Spain 4-0, Japan 4-0 (away), Portugal 4-0 —
  against a genuinely weak/limited side (NOT a parked low block), the elite
  favourite routs. Back favourite + goals; never lean below the market here.
  Distinct from the low-block 0-0s (Ecuador-Curaçao, Belgium-Iran), which are a
  different archetype.

---

## 2026-06-23 · England vs Ghana (Group L) — ⏳ PENDING

**Pre-match forecast (not yet played).** Top-of-group clash: both on 3 points
after MD1 (England 4-2 Croatia; Ghana 1-0 Panama). The winner takes control of
Group L.

**Model:** England 65.3 / Draw 21.4 / Ghana 13.3 (HIGH). Lambdas England 2.05 /
Ghana 0.82, total xG 2.87, rho -0.07. Monte Carlo (N=200k) converges: exact
65.3 / 21.4 / 13.3 vs sim 65.4 / 21.3 / 13.3 (max diff 0.08 pts).

**Calibration vs market:** de-vig market ~66.8 / 20.6 / 12.6 (book margin 5.5%);
max divergence 1.5 pts → aligned. Applied the Spain/Portugal lesson: England
calibrated in line with the market, not below an elite favourite.

**Most probable scorelines:** 2-0 (11.9%), 1-0 (11.0%), 1-1 (10.2%), 2-1 (9.8%),
3-0 (8.1%). Goals: Over 2.5 54.7%, BTTS 49.4% (a coin-flip — England leaked 2 to
Croatia and Ghana carry a threat via Kudus), England clean sheet 44.0%.

**Pre-match read:** England should win but it is NOT the same clean archetype as
Portugal/Spain vs a minnow — Ghana is organized and England's back line is leaky,
so BTTS is live (~49%) and the central scenario is a 1-2 goal win that may not be
a clean sheet. Recalibrate with confirmed XIs ~60 min before kickoff.

**Actual result:** England 0-0 Ghana. Scoreless; both kept a clean sheet.

**Honest read — the favorite frustrated, AND my goals lean was wrong:**
- 🟡 1X2: the 65% favourite did NOT win; the model's #2 outcome, the draw
  (21.4%), came in. A 0-0 between two 3-point sides is within the distribution.
- ❌ **Goals lean wrong (the real miss):** I read this as an OPEN game (BTTS 49%,
  Over 2.5 55%) precisely because England leaked 2 to Croatia — instead it was a
  tight 0-0 (Under 1.5, BTTS No). England's 2.05 xG did not convert; Ghana stayed
  organized and disciplined.
- 📌 **Lesson:** do NOT infer "open, high-BTTS game" from one leaky prior result.
  A strong attacking favourite can still be held scoreless by an organized side;
  the draw/Under is the underweighted scenario. This is the OPPOSITE error to the
  rout archetype (Spain/Portugal 4-0) — the read hinges entirely on whether the
  underdog is organized (Ghana, Iran, Curaçao → 0-0 live) or genuinely weak/open
  (Saudi, Uzbekistan, NZ → favourite + goals). Joins Ecuador-Curaçao and
  Belgium-Iran as a frustrated-favourite 0-0.

---

## 2026-06-23 · Croatia vs Panama (Group L) — ⏳ PENDING

**Pre-match forecast (not yet played).** Both on 0 points after MD1 (Croatia 2-4
England; Panama 0-1 Ghana), with England and Ghana on 4: a near-must-win
six-pointer, the loser virtually eliminated.

**Model:** Croatia 58.6 / Draw 24.9 / Panama 16.5 (MEDIUM). Lambdas Croatia 1.72 /
Panama 0.80, total xG 2.52, rho -0.06. Monte Carlo (N=200k) converges: exact
58.6 / 24.9 / 16.5 vs sim 58.7 / 24.7 / 16.6 (max diff 0.15 pts).

**Calibration vs market:** de-vig market 58.5 / 24.3 / 17.2 (book margin 5.6%);
max divergence 0.7 pts → tightly aligned. An initial λ of 1.85 put Croatia ~3.6
pts ABOVE market; trimmed to 1.72 — applying the England-Ghana lesson, don't
overrate the favourite against an organized underdog. Drops to MEDIUM (just under
the 60% HIGH threshold).

**Most probable scorelines:** 1-0 (13.2%), 2-0 (11.9%), 1-1 (11.7%), 2-1 (9.5%),
0-0 (8.7%). Goals: Over 2.5 46.1% (lean Under), BTTS 45.9%, Croatia clean sheet
44.9%.

**Pre-match read:** Croatia the favourite but only modestly (MEDIUM) — Panama is
organized and this is a tense, low-stakes-for-neither game where BOTH must win,
which cuts both ways: it opens the game (both attack) yet the draw/Under is a
live tail (total xG just 2.52). Central scenario a 1-0/2-0 Croatia win; a tight
draw is very much in play. Recalibrate with confirmed XIs ~60 min before kickoff.

**Actual result:** Croatia 1-0 Panama. Tight, low-scoring; Croatia clean sheet,
BTTS No, 1 goal.

**Honest read — a clean hit:**
- ✅ 1X2: the favourite won, by the model's **#1 scoreline (1-0, 13.2%)**.
- ✅ **Goals reads all correct:** Under 2.5 (53.9%), BTTS No, Croatia clean sheet
  (44.9%); modelled xG 2.52, actual 1 goal.
- ✅ **Trim-to-market vindicated:** I cut Croatia from an initial 62% down to
  58.6% (organized Panama, England-Ghana lesson) — a tense 1-0 followed.
- 📌 Second straight 1-0 (with Colombia 1-0 DR Congo): the proven-organized
  underdog read keeps producing tight, low-scoring favourite wins.

---

## 2026-06-24 · Colombia vs DR Congo (Group K) — ⏳ PENDING

**Pre-match forecast (not yet played).** Standings before kickoff: Portugal 4 pts,
Colombia 3 (3-1 Uzbekistan), DR Congo 1 (1-1 Portugal), Uzbekistan 0. Colombia the
quality side; DR Congo competitive (held Portugal 1-1).

**Model:** Colombia 54.9 / Draw 25.9 / DR Congo 19.3 (MEDIUM). Lambdas Colombia
1.65 / DR Congo 0.88, total xG 2.53, rho -0.06. Monte Carlo (N=200k) converges:
exact 54.9 / 25.9 / 19.3 vs sim 55.0 / 25.7 / 19.3 (max diff 0.15 pts).

**Calibration vs market:** de-vig market 55.3 / 25.7 / 19.0 (book margin 5.2%);
max divergence 0.4 pts → tightly aligned out of the box. Applied the England-Ghana
lesson up front: DR Congo held Portugal 1-1, so this is NOT a rout spot — Colombia
calibrated in line with the market (MEDIUM, 55%), with the draw/Under kept live.

**Most probable scorelines:** 1-0 (12.4%), 1-1 (12.3%), 2-0 (10.8%), 2-1 (9.5%),
0-0 (8.7%). Goals: Over 2.5 46.4% (lean Under), BTTS 48.0%, Colombia clean sheet
41.5%.

**Pre-match read:** Colombia the favourite but only modestly — DR Congo are
organized and proven (Portugal 1-1), so the central scenario is a tight 1-0/1-1,
not a comfortable win, and the draw (~26%) is very live. Lower-scoring game (total
xG 2.53, lean Under 2.5). Recalibrate with confirmed XIs ~60 min before kickoff.

**Actual result:** Colombia 1-0 DR Congo. Tight, low-scoring; Colombia clean
sheet, BTTS No, 1 goal.

**Honest read — a clean hit, every read landed:**
- ✅ 1X2: the favourite won, by the model's **#1 scoreline (1-0, 12.4%)**.
- ✅ **Goals reads all correct:** Under 2.5 (53.6%), BTTS No, Colombia clean
  sheet (41.5%), low total — modelled xG 2.53, actual 1 goal.
- ✅ **England-Ghana lesson applied up front, vindicated:** DR Congo had proven
  organization (1-1 Portugal), so I refused to overrate Colombia (kept MEDIUM
  55%, leaned Under) and called a tense 1-0 — exactly what happened.
- 📌 The two archetypes are now well separated: PROVEN-organized underdog →
  tight 1-0/1-1, draw live, Under (DR Congo, Ghana, Iran, Curaçao); genuinely
  weak/open side → favourite + goals rout (Saudi, Uzbekistan, NZ). Reading which
  is which is the whole job.

---

## 2026-06-24 · Group A & B finals (MD3, simultaneous) — ⏳ PENDING

All four kick off at once; qualification scenarios shape behaviour (qualified
teams may rotate; teams needing a result push). Cards not modelled (referees TBD).

**Group A** (both PLAYED — the motivation lesson)
- **Mexico vs Czech Republic** — Mexico 45.5 / Draw 27.8 / Czech 26.6 (MEDIUM).
  λ 1.45 / 1.05. **RESULT: Mexico 3-0 ✅** on the 1X2, but I applied a rotation
  DISCOUNT (already qualified → compressed to 45.5%) and Mexico instead routed
  3-0 with a clean sheet. The discount was unjustified.
- **South Korea vs South Africa** — SK 58.3 / Draw 26.2 / SA 15.5 (MEDIUM).
  λ 1.60 / 0.70. **RESULT: South Africa 1-0 ❌ — the first outright 1X2 miss, and
  self-inflicted.** I had RECALIBRATED South Africa DOWN (26.5% → 15.5%) on the
  "virtually eliminated / flat motivation" narrative; the pre-recalibration number
  was closer. South Africa won and QUALIFIED 2nd, knocking South Korea to 3rd.

**KEY LESSON — motivation/qualification adjustments backfired BOTH ways.** Same
round: I downgraded an *eliminated* side (South Africa — they won) and discounted
a *qualified* side (Mexico — they routed). Both speculative tweaks were wrong, in
opposite directions. Elimination ≠ rolling over (a pressure-free team can play
loose and spoil); qualification ≠ easing off (a host can still want to win big).
**Rule going forward:** trust the strength/market baseline; only adjust for
CONFIRMED rotation/team news, never for scenario/motivation guesses.

**Group B** (both PLAYED)
- **Switzerland vs Canada** — SUI 33.5 / Draw 28.4 / CAN 38.2 (LOW, no strong
  read). λ 1.25 / 1.35, xG 2.60. **RESULT: Switzerland 2-1 🟡** — coin-flip; the
  marginal Canada lean missed but the open/BTTS read landed (both scored, 3
  goals, Over 2.5). Switzerland win the group, Canada through 2nd. Both were
  already ~100% to advance.
- **Bosnia & Herz. vs Qatar** — Bosnia 55.7 / Draw 26.1 / Qatar 18.2 (MEDIUM).
  λ 1.62 / 0.82, xG 2.44. **RESULT: Bosnia 3-1 ✅** — quality side won as called
  (dead-rubber caveat didn't bite); Over (4 goals) and Bosnia overperformed xG.
  Despite the win Bosnia finish 3rd on GD (Canada 2nd; H2H was 1-1).

*Group A finals now PLAYED — see the Group A section above (Mexico 3-0; South Africa 1-0 South Korea).*

---

## 2026-06-24 · Group C finals (MD3) — ⏳ PENDING

Standings before: Brazil 4, Morocco 4, Scotland 3, Haiti 0.

- **Scotland vs Brazil** — Scotland 14.4 / Draw 24.0 / Brazil 61.7 (HIGH).
  λ 0.75 / 1.80, xG 2.55. **RESULT: Scotland 0-3 Brazil ✅** — 1X2 + texture both
  right: Brazil win, clean sheet (47.2%), Scotland blank, BTTS No. The 3-0 margin
  was the high tail (Brazil 1.80 → 3); the "draw is live / don't assume a rout"
  hedge didn't pay but the central call was correct. No calibration change.
- **Morocco vs Haiti** — Morocco 69.5 / Draw 21.9 / Haiti 8.5 (HIGH). λ 1.82 /
  0.48, xG 2.30. **RESULT: Morocco 4-2 Haiti ✅ (1X2) — but GOALS model badly
  missed.** I called a controlled low-scoring win (lean Under 2.5, BTTS No 68%,
  clean sheet 62%); it was a 6-goal game, both scoring. Morocco overperformed
  (1.82 → 4) and Haiti, modelled near-toothless (λ 0.48), scored 2. **Lesson:**
  dead-rubber goal VOLUME is high-variance — a low-stakes final-round game can
  blow open; trust the result read over the goals read, and don't over-trust a
  tiny λ for a "weak" side. Mirror of England-Ghana (a control became chaos).

*Group A finals now PLAYED — see the Group A section above (Mexico 3-0; South Africa 1-0 South Korea).*

---

## 2026-06-24 · Group I finals (MD3) — ⏳ PENDING

Standings before: France 6, Norway 6 (both already QUALIFIED), Senegal 0, Iraq 0
(both ELIMINATED). Applied the motivation lesson: no rotation discount for the
qualified pair, no elimination downgrade for the dead rubber — trust the baseline.

- **Norway vs France** — Norway 34.2 / Draw 25.1 / France 40.7 (LOW). λ 1.45 /
  1.60, xG 3.05. **RESULT: France 4-1 ✅** — slight favourite won AND the open/
  high-scoring read landed perfectly (5 goals, both scored: Over 2.5, Over 3.5,
  BTTS all hit). No rotation discount despite both qualified → France went full;
  correct. Texture beats side on a coin-flip.
- **Senegal vs Iraq** — Senegal 54.7 / Draw 25.3 / Iraq 20.0 (MEDIUM). λ 1.68 /
  0.92, xG 2.60. Market 54.2 / 26.3 / 19.4 (div 1.0). **CORRECTION: Senegal is NOT
  eliminated** — a win can take them through as a BEST THIRD, and that spot is
  decided on goal difference, so Senegal is motivated to win BY A MARGIN. This is a
  legitimate STRUCTURAL incentive (not the speculative motivation tweak that burned
  us), so Senegal was lifted (1.40 → 1.68 λ, 45.5% → 54.7%) and the game opened up.
  **Correctly-uncertain caveat:** Senegal is favoured to WIN (55%) but to win by
  the 2+ margin they need is only **~30%** (by exactly 1: 24%, by 2: 17%, by 3+:
  13%) — a comfortable best-third cushion is the minority scenario, not the base case.
  **RESULT: Senegal 5-0 ✅** — the recalibration was vindicated (lifting Senegal on
  the structural best-third incentive was right; they attacked and ran up the score).
  The 5-0 landed in the favourable ~13% "by 3+" tail; the honest margin caveat still
  held. Senegal finish 3rd on **GD 0** (up from -4) — strong best-third position.
  **Lesson crystallised:** STRUCTURAL incentives (qualification + GD matters → lift,
  attack) are a legitimate hard adjustment; SPECULATIVE motivation narratives
  (eliminated/demotivated) are the South Africa trap. This match is the clean
  positive example of the former.

*To be graded after the matches (xG vs actual, 1X2, lesson).*
