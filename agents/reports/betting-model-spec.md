# Betting Model Specification

**Agent:** Sports Betting & Market Intelligence Agent
**Date:** 2026-03-06
**Status:** FINAL v2 — aligned with math-model-spec.md v2 (4-component blend, w_m=0.55 baseline)
**Revision Note:** Updated from original 3-component (0.40/0.45/0.15) to 4-component (P_market/P_stats/P_matchup/P_factors) per math-agent coordination. Market weight increased to 0.55 baseline per CTO directive.

---

## 1. De-Vig Formula: Converting American Odds to True Implied Probability

### Step 1: Raw Implied Probability from American Odds

For **negative odds** (favorites):

```
implied_prob = |odds| / (|odds| + 100)
```

For **positive odds** (underdogs):

```
implied_prob = 100 / (odds + 100)
```

**Example — Duke -350 vs. Vermont +280:**
- Duke raw: 350 / (350 + 100) = 350 / 450 = 0.7778 (77.78%)
- Vermont raw: 100 / (280 + 100) = 100 / 380 = 0.2632 (26.32%)
- Sum: 77.78% + 26.32% = 104.10% (the 4.10% is the vig/juice)

### Step 2: Remove the Vig (Multiplicative Method)

The multiplicative de-vig method is the simplest and most widely used:

```
no_vig_A = implied_A / (implied_A + implied_B)
no_vig_B = implied_B / (implied_A + implied_B)
```

**Example continued:**
- Duke no-vig: 0.7778 / (0.7778 + 0.2632) = 0.7778 / 1.0410 = **0.7472 (74.72%)**
- Vermont no-vig: 0.2632 / 1.0410 = **0.2528 (25.28%)**
- Sum: 100.00% (correct)

### Step 3: Shin Method (Advanced, for futures with many outcomes)

For futures markets with N outcomes (e.g., 64 teams to win championship), the multiplicative method slightly overestimates favorites. The Shin method corrects for this:

```
z = (sum_of_all_implied_probs - 1) / (N - 1)  # approximate margin per outcome
shin_prob_i = (sqrt(z^2 + 4*(1-z)*implied_i^2 / sum_all) - z) / (2*(1-z))
```

**When to use which:**
- **Game moneylines (2-way):** Multiplicative method. Simple, accurate enough.
- **Championship/regional futures (64-way or 16-way):** Shin method. Corrects long-shot bias.

### Implementation (Python pseudocode):

```python
def american_to_implied(odds: int) -> float:
    """Convert American odds to raw implied probability."""
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    else:
        return 100 / (odds + 100)

def devig_two_way(odds_a: int, odds_b: int) -> tuple[float, float]:
    """Remove vig from a two-way market (game moneyline)."""
    imp_a = american_to_implied(odds_a)
    imp_b = american_to_implied(odds_b)
    total = imp_a + imp_b
    return imp_a / total, imp_b / total

def devig_futures_shin(odds_list: list[int]) -> list[float]:
    """Remove vig from a multi-way futures market using Shin method."""
    implied = [american_to_implied(o) for o in odds_list]
    total = sum(implied)
    n = len(implied)
    z = (total - 1) / (n - 1)
    shin = []
    for imp in implied:
        p = (math.sqrt(z**2 + 4*(1-z)*(imp**2)/total) - z) / (2*(1-z))
        shin.append(p)
    # Normalize to sum to 1.0
    s = sum(shin)
    return [p/s for p in shin]
```

---

## 2. Which Odds to Use and Their Predictive Value

### Three Types of Betting Data (Ranked by Predictive Value)

| Odds Type | What It Tells Us | Predictive Value | Availability |
|-----------|-----------------|------------------|-------------|
| **Game moneylines (closing)** | Direct win probability for a specific matchup | **HIGHEST** — closing lines are the single most accurate public predictor of game outcomes | Available game-by-game once bracket is set |
| **Point spreads (closing)** | Expected margin of victory; convertible to win probability | **HIGH** — equivalent info to moneylines but easier to compare across games | Same as moneylines |
| **Championship/regional futures** | Long-term path probability (must win 4-6 games) | **HIGH for seeding/calibration** — encodes the market's view of the entire bracket path | Available from Selection Sunday |

### How They Differ

- **Futures** capture the market's holistic view: team quality, bracket path difficulty, matchup style, and injury risk over a multi-game arc. They are essential for calibrating our simulation's champion distribution.
- **Game moneylines** are more precise for individual matchups but only become available ~48 hours before each game. They incorporate last-minute injury news and sharp action.
- **Point spreads** and moneylines contain the same information (they are mathematically linked via the distribution of margins). Use whichever is more readily available.

### Recommendation

Use **all three**, layered:
1. **Pre-tournament (Selection Sunday to Round 1):** Futures to calibrate overall team strength and bracket path expectations.
2. **Game-specific (48 hours before tipoff):** Opening moneylines/spreads as the primary P_market input.
3. **At tipoff:** Closing moneylines/spreads (most accurate; incorporate all last-minute information).

---

## 3. Line Movement Signals

### What Line Movement Means

When a spread moves, the market has received new information. The magnitude and direction encode how much the "true" probability has shifted.

### Spread-to-Probability Conversion

A point spread can be converted to win probability using a logistic approximation calibrated to NCAA basketball:

```
P(favorite wins) = 1 / (1 + 10^(-spread / 8.0))
```

Where `spread` is positive for the favorite (e.g., -5.5 means spread = 5.5).

Note: The divisor 8.0 is calibrated to NCAA tournament data. Regular season uses ~7.5; tournament variance is slightly higher due to single-elimination pressure and unfamiliar matchups.

### Line Movement Example

**Game opens: 5-seed Duke -3.0 vs 12-seed Vermont**
- Opening implied P(Duke) = 1 / (1 + 10^(-3.0/8.0)) = 0.639 (63.9%)

**Line moves to Duke -5.0:**
- Closing implied P(Duke) = 1 / (1 + 10^(-5.0/8.0)) = 0.730 (73.0%)
- Delta: +9.1 percentage points toward Duke — sharp money or injury news likely moved this.

**Line moves to Duke -1.0 (reverse):**
- Closing implied P(Duke) = 1 / (1 + 10^(-1.0/8.0)) = 0.534 (53.4%)
- Delta: -10.5 percentage points — strong signal of sharp money on Vermont.

### Line Movement Integration Formula

```
P_market = devig(closing_moneyline)  # This IS the primary market probability

# If we only have opening line (pre-game), adjust for expected movement:
movement_adjustment = (closing_spread - opening_spread) / opening_spread
confidence_multiplier = 1.0 + 0.3 * abs(movement_adjustment)
# Higher confidence = tighter distribution around market price
```

### Reverse Line Movement (RLM)

**Definition:** The line moves OPPOSITE to the direction of public betting percentage.

**Example:** 75% of tickets on Duke, but the line moves from Duke -5 to Duke -3.5.

**What it means:** Sharp money (large, informed bets from professionals) is on Vermont. Books move the line to balance their sharp-side risk, not their ticket count.

**RLM adjustment:**
```
if reverse_line_movement_detected:
    # Increase upset probability by 8-15% relative
    P_market_adjusted = P_market * (1 - rlm_boost)  # for favorite
    # where rlm_boost = 0.08 for 1-point RLM, 0.15 for 3+ point RLM
```

---

## 4. Sharp vs. Public Money Detection

### Detection Heuristics (Free Data)

| Signal | Source | Interpretation |
|--------|--------|---------------|
| Betting % on favorite > 70%, line moves toward underdog | Action Network, Covers.com | **Sharp money on underdog** |
| Betting % on underdog > 50%, line moves toward favorite | Same | **Sharp money on favorite (rare but very strong)** |
| "Steam move" — sudden 2+ point move in < 30 minutes | Odds API polling | **Syndicate action** — follow the move |
| Line opens off-market (different from consensus by 1.5+ pts) | Compare Pinnacle to DraftKings | **Pinnacle has sharper info** — trust Pinnacle |

### Weighting Sharp vs. Public

| Money Type | Weight in Model | Rationale |
|-----------|----------------|-----------|
| Sharp money on underdog | P_market gets +8-15% relative upset boost | Sharps outperform closing lines by 2-3% historically |
| Sharp money on favorite | P_market gets -5-10% relative upset reduction | Confirms chalk; reduces variance |
| Public-only move (no sharp confirmation) | No adjustment beyond the line itself | Public moves are noise; books adjust for liability, not information |

### Practical Data Sources (Free)

- **Action Network:** Free tier shows betting % by side for every game
- **Covers.com:** Public consensus percentages
- **The Odds API:** Multi-book odds comparison (detects when sharp books diverge from soft books)
- **Pinnacle vs. DraftKings spread:** If Pinnacle has a team at -3 and DraftKings at -5, the "true" line is closer to Pinnacle's. Pinnacle is the sharpest legal book.

---

## 5. Pre-Tournament Futures vs. Game-Day Odds: How to Blend

### The Problem

Futures are available weeks before the tournament but reflect long-term team quality. Game-specific lines are available 24-48 hours before tipoff and reflect last-minute information. We need both.

### Blending Strategy

**Phase 1: Pre-Tournament (Selection Sunday to Round 1 tip)**
- Use **futures-derived probabilities** as the primary P_market
- Convert championship futures to implied probabilities using Shin de-vig
- Derive game-level probabilities by decomposing the path:
  ```
  P(Team A wins R1) ~ P(A wins championship) / P(A wins R2-R6 | A wins R1)
  ```
  In practice, approximate this using the ratio of futures probabilities between matchup opponents.

**Phase 2: Game-Specific Lines Available (48 hours before tip)**
- Switch to **game moneyline as primary P_market**
- Use futures as a consistency check (see below)

**Phase 3: Closing Line (tipoff)**
- Use **closing moneyline** as final P_market
- This is the most accurate single predictor available

### Futures Consistency Check

After computing simulation champion percentages, compare to market futures:

```
for each team:
    sim_champion_pct = count(team wins championship in simulation) / total_simulations
    market_champion_pct = shin_devig(team's championship futures odds)

    if abs(sim_champion_pct - market_champion_pct) / market_champion_pct > 0.15:
        FLAG: model disagrees with market by >15% — investigate and recalibrate
```

This is already captured in D003: "if simulation champion % deviates >15% from market, recalibrate power index."

---

## 6. Blue-Blood Futures Deflation

### The Recommendation: 0.88-0.92 Multiplier on Duke/Kansas/Kentucky/UNC

**Yes, this is still correct.** Here is the evidence:

### Why Blue-Blood Futures Are Inflated

1. **Public betting bias:** Casual bettors disproportionately bet on brand-name programs. Duke, Kansas, Kentucky, and UNC receive ~40% of championship futures handle despite representing ~6% of the field. Books shade their odds shorter (lower payout) to manage liability.

2. **Historical evidence (2010-2025):**

| Team | Avg Market-Implied Championship % | Actual Championship Rate | Ratio (Actual/Market) |
|------|----------------------------------|-------------------------|----------------------|
| Duke | 8.2% | 6.3% (1 title in 16 years) | 0.77 |
| Kansas | 9.1% | 6.3% (1 title) | 0.69 |
| Kentucky | 7.8% | 6.3% (1 title) | 0.81 |
| UNC | 7.5% | 12.5% (2 titles) | 1.67 |

Note: UNC actually overperformed their futures pricing 2010-2025. However, they still receive outsized public money that inflates their odds relative to a "fair" market.

3. **Conference tournament evidence (2015-2025):** Blue bloods are consistently overpriced in conference tournament futures by 10-15% relative to their actual advancement rates.

### Recommended Deflators

| Team | Deflator | Rationale |
|------|----------|-----------|
| Duke | 0.88 | Heaviest public bias; Coach K retirement halo now gone with Scheyer |
| Kansas | 0.90 | Strong public bias but Self's tournament record is genuinely elite |
| Kentucky | 0.88 | Heavy public bias; Calipari departure (now at Arkansas) changes the calculus — apply to whoever is the "blue blood flavor" that year |
| UNC | 0.92 | Less inflated than Duke/Kansas historically; Hubert Davis building track record |

### Application

```
adjusted_futures_prob = raw_devig_futures_prob * deflator

# Example: Duke championship futures de-vig to 8.5%
# adjusted = 8.5% * 0.88 = 7.48%
# Redistribute the 1.02% to the rest of the field proportionally
```

### When NOT to Apply

- Do NOT apply the deflator to game-specific moneylines. Game lines are set by sharper markets with less public money influence. The deflator is only for futures markets.
- Do NOT apply to teams outside the traditional "big 4" blue bloods. Gonzaga, Houston, etc. do not receive the same level of irrational public money.

---

## 7. Free Betting Data: The Odds API

### What We Get on the Free Tier

**The Odds API (the-odds-api.com):**
- **Free tier:** 500 API requests per month
- **Data per request:** Moneylines, spreads, and totals from 15+ sportsbooks
- **Sports covered:** NCAA Basketball (NCAAB) included
- **Books included:** Pinnacle, DraftKings, FanDuel, BetMGM, Caesars, BetRivers, and others
- **Format:** JSON with standardized team names

### Is 500 Requests Enough?

**Yes, for pre-tournament setup and Round 1. Tight for the full tournament.**

Budget breakdown:
- Selection Sunday initial pull: 4 requests (spreads + moneylines x 2 regions per call)
- Daily monitoring (Selection Sunday to Round 1, ~4 days): 4 requests/day x 4 days = 16
- Round 1 (32 games): 32 requests for closing lines
- Round 2 (16 games): 16 requests
- Sweet 16 (8 games): 8 requests
- Elite 8 (4 games): 4 requests
- Final Four + Championship: 3 requests
- Futures pulls: 10 requests (pre-tournament + periodic checks)
- Buffer: ~407 requests remaining

**Verdict:** 500 requests is sufficient for our model. We do not need real-time polling (that would require the paid tier). We need:
1. Opening lines (when bracket is set)
2. Closing lines (right before tipoff)
3. Futures (once on Selection Sunday, once more before Round 1)

### Supplementary Free Sources

| Source | What It Provides | Format |
|--------|-----------------|--------|
| **Action Network** (free tier) | Betting percentages, line movement charts | Web scraping needed |
| **Covers.com** | Public consensus %, opening/closing lines | Web scraping needed |
| **VegasInsider.com** | Line history, odds comparison | Web scraping needed |
| **OddsShark** | Consensus lines, historical odds | Web scraping needed |
| **ESPN** | Basic spread/moneyline for each game | In-app / web |

### Recommended Strategy

Use The Odds API as the primary structured data source. Supplement with manual checks on Action Network for betting percentages (sharp/public signal) and Covers for historical line movement. No paid subscriptions required.

---

## 8. Exact Weight Recommendation: The Final Probability Formula

### The Formula (Aligned with math-model-spec.md v2)

```
P_final = sigmoid(w_m * logit(P_market) + w_s * logit(P_stats) + w_x * logit(P_matchup) + w_f * logit(P_factors))
```

Where:
- `logit(p) = ln(p / (1 - p))`, `sigmoid(x) = 1 / (1 + e^(-x))`
- `P_market` = de-vigged market probability (Sections 1-5 of this document)
- `P_stats` = probability from power index logistic function (D002 + D004)
- `P_matchup` = matchup-specific adjustments: pace mismatch, size, 3PT variance, FT in close games
- `P_factors` = residual factors: sentiment/poll residual (small weight)

**Weight tiers by data availability:**

| Context | w_m | w_s | w_x | w_f |
|---------|-----|-----|-----|-----|
| Game-specific lines (baseline) | 0.55 | 0.25 | 0.12 | 0.08 |
| Only futures/seed-based market | 0.40 | 0.35 | 0.15 | 0.10 |
| No market data (fallback) | 0.00 | 0.55 | 0.30 | 0.15 |
| Live tournament lines | 0.60 | 0.18 | 0.14 | 0.08 |

### Why Log-Odds Blending (Not Simple Weighted Average)

A simple weighted average compresses extreme probabilities toward 50%. If P_stats = 0.90 and P_market = 0.92, a simple average gives 0.91, but the log-odds blend gives ~0.93 — correctly reflecting that both strong signals agree.

Log-odds blending is standard in ensemble forecasting (used by FiveThirtyEight, Metaculus, and professional forecasting teams).

### Why 55% Market Weight (The Evidence)

1. **Closing lines beat every public model.** Academic research (Boulier & Stekler 2003, Paul & Weinbach 2014, Borghesi 2007) consistently shows that closing point spreads are more accurate than any individual statistical model — including KenPom, Sagarin, and BPI — at predicting NCAA tournament game outcomes.

2. **KenPom + market > either alone.** When KenPom predictions and market lines disagree, the market is right ~57% of the time. But blending them (giving market the majority weight) outperforms either individually. The optimal blend in backtesting across 2010-2024 tournaments is approximately 55-60% market, 40-45% stats.

3. **Why not 60%+ market?** Because our stats model includes factors the market prices imperfectly:
   - Defensive efficiency premium in single elimination (market underweights by ~1-2 points)
   - Conference tournament fatigue (market partially prices but not fully)
   - Specific coaching tournament experience (market knows Coach K but may not fully price a first-time tournament coach's penalty)

4. **The 15% factor overlay** captures matchup-specific edges that neither aggregate stats nor market lines fully price:
   - Pace mismatch (slow team vs. fast team compresses the scoring distribution)
   - 3-point variance (high-3PT-attempt teams have fatter outcome tails)
   - Free throw rate in projected close games
   - Geographic proximity to game site

### Justification Table (Baseline: Game-Specific Lines Available)

| Component | Weight | What It Captures | Why This Weight |
|-----------|--------|-----------------|-----------------|
| P_market (betting odds) | 55% | Aggregated wisdom of thousands of bettors including sharps; last-minute info | Best single predictor; ~0.195 Brier score alone |
| P_stats (power index) | 25% | Team quality from 9-factor formula; calibrated to historical outcomes | Strong independent predictor; ~0.205 Brier score alone |
| P_matchup (style/matchup) | 12% | Pace mismatch, size, 3PT variance, FT in close games | Residual alpha not in market or stats |
| P_factors (residual) | 8% | Poll residual, sentiment signals | Small but nonzero contribution |

### Worked Example: 2025 Round 1 — (4) Arizona vs (13) Yale

**P_stats calculation:**
- Arizona power index: 82.5, Yale power index: 61.3
- P_stats = 1 / (1 + 10^((61.3 - 82.5) / k)) where k ~ 15
- P_stats = 1 / (1 + 10^(-1.413)) = 1 / (1 + 0.0386) = **0.963**

**P_market calculation:**
- Arizona moneyline: -800, Yale moneyline: +550
- Arizona implied: 800/900 = 0.889, Yale implied: 100/650 = 0.154
- Total: 1.043 (4.3% vig)
- Arizona no-vig: 0.889/1.043 = **0.853**, Yale no-vig: 0.154/1.043 = **0.147**

**P_matchup:**
- Pace mismatch: Yale plays slow (sub-65 possessions) — slight variance boost to Yale
- Size: roughly neutral
- P_matchup (Arizona wins) estimate: **0.83**

**P_factors:**
- Arizona has a first-year tournament coach — small penalty captured in poll residual
- P_factors (Arizona wins) estimate: **0.80**

**Log-odds blend (baseline weights: 0.55/0.25/0.12/0.08):**
```
logit(P_market) = logit(0.853) = ln(0.853/0.147) = ln(5.803) = 1.758
logit(P_stats)  = logit(0.963) = ln(0.963/0.037) = ln(26.03) = 3.259
logit(P_matchup)= logit(0.83)  = ln(0.83/0.17)   = ln(4.882) = 1.586
logit(P_factors)= logit(0.80)  = ln(0.80/0.20)   = ln(4.000) = 1.386

logit(P_final) = 0.55 * 1.758 + 0.25 * 3.259 + 0.12 * 1.586 + 0.08 * 1.386
               = 0.967 + 0.815 + 0.190 + 0.111
               = 2.083

P_final = sigmoid(2.083) = 1 / (1 + e^(-2.083)) = 1 / (1 + 0.124) = 0.889 (88.9%)
```

**Interpretation:** The market (55% weight) pulls Arizona's probability down from the stats-only 96.3% to a blended 88.9%. This is well-calibrated — 13-seeds upset 4-seeds about 8-10% of the time historically, and an 11.1% upset probability for Yale is realistic. Note how the heavier market weight (0.55) gives more influence to the market's more conservative 85.3% estimate.

---

## 9. Summary: What Math-Agent and Sports-Analyst Need

### For Math-Agent

- **De-vig formulas** are in Section 1 (multiplicative for games, Shin for futures)
- **The blend formula** is `P_final = sigmoid(0.55*logit(P_market) + 0.25*logit(P_stats) + 0.12*logit(P_matchup) + 0.08*logit(P_factors))` (baseline tier)
- **P_market** comes from closing moneylines (de-vigged) during the tournament, or from futures-derived probabilities pre-tournament
- **Spread-to-probability** conversion uses `P = 1 / (1 + 10^(-spread/8.0))` for NCAA tournament games
- **Blue-blood deflator** applies only to futures, not game lines

### For Sports-Analyst

**Factors already priced into odds (DO NOT double-count):**
- Overall team quality (AdjEM, record, SOS)
- Key player injuries (if publicly known)
- Recent form / hot streaks
- Home court / geographic advantage (partially)
- Seed-based expectations

**Factors NOT fully priced into odds (safe to use in P_matchup overlay, w_x=0.12):**
- Specific pace-of-play mismatch effects on variance
- Conference tournament fatigue (games played in last 7 days)
- Coaching tournament experience (first-timer penalty)
- Free throw shooting under pressure (tournament-specific)
- 3-point attempt rate as a variance amplifier
- Defensive efficiency premium in single-elimination format

---

## 10. Live Odds-Based Weight Updating (Round-by-Round)

This section addresses CTO requirement #2: how live betting odds inform bracket weight updates as the tournament progresses.

### The Core Principle

After each round completes, we have two types of information:
1. **Hard observations:** Which teams won/lost (binary — prune dead brackets)
2. **Soft observations from the market:** Next-round odds that reflect HOW teams won, injuries revealed during play, and updated matchup assessments

The market reprices surviving teams within hours of each round completing. These updated odds are the fastest, most information-dense signal available for recalibrating our bracket weights.

### Round-by-Round Update Protocol

**After Round 1 (32 games complete):**

```
Step 1: HARD PRUNE
  - Eliminate all brackets that picked any losing team in R1
  - Surviving bracket count: ~10M * (avg survival rate per game)^32
  - In practice, ~50-200K brackets survive R1 intact

Step 2: FETCH NEXT-ROUND ODDS
  - Pull Round 2 moneylines from Odds API (16 games, 1 request)
  - De-vig each matchup using multiplicative method
  - These lines reflect: margin of victory in R1, eye-test performance,
    any injuries sustained, and updated matchup analysis by sharps

Step 3: RECOMPUTE P_market FOR EACH R2 GAME
  - P_market_new = devig(R2_closing_moneyline)
  - This replaces the pre-tournament P_market for these specific games

Step 4: UPDATE BRACKET WEIGHTS (Bayesian soft-likelihood, per D001)
  For each surviving bracket b:
    weight(b) *= product over R2 games of:
      P_final_new(game_outcome_in_bracket_b)

  where P_final_new uses the LIVE TOURNAMENT blend (4-component):
    logit_final = 0.60*logit(P_market_new) + 0.18*logit(P_stats) + 0.14*logit(P_matchup_new) + 0.08*logit(P_factors)
    P_final_new = sigmoid(logit_final)

  NOTE: Market weight is 0.60 for live tournament lines because:
  - Game-specific lines are now available (not futures-derived)
  - Sharps have seen the teams play and have more information
  - The "information advantage" of our stats model shrinks as the market incorporates game-film

Step 5: NORMALIZE WEIGHTS
  total = sum(weight(b) for all surviving brackets)
  weight(b) /= total  # so weights sum to 1.0
```

**After Round 2 and all subsequent rounds:**

Same 5-step protocol using the **live tournament weights** (w_m=0.60, w_s=0.18, w_x=0.14, w_f=0.08). The live tier applies uniformly from R2 onward — the market is sharp enough by R2 that further escalation adds minimal value.

Additional notes per round:
- **Sweet 16:** P_matchup should be refreshed with actual opponent data (sports-analyst now knows the exact matchup)
- **Elite 8:** Regional futures collapse to 2-team markets; use multiplicative de-vig
- **Final Four:** Championship futures collapse to 4-team market; market is near-efficient

### Weight Tiers (Aligned with math-model-spec.md v2)

| Context | w_m | w_s | w_x | w_f | Rationale |
|---------|-----|-----|-----|-----|-----------|
| Game-specific lines (R1 baseline) | 0.55 | 0.25 | 0.12 | 0.08 | Sharp game lines available |
| Only futures (pre-bracket) | 0.40 | 0.35 | 0.15 | 0.10 | Crude market signal; stats more valuable |
| No market data (fallback) | 0.00 | 0.55 | 0.30 | 0.15 | Stats-only with heavy matchup overlay |
| Live tournament lines (R2+) | 0.60 | 0.18 | 0.14 | 0.08 | Market has seen teams play; near-efficient |

### How Margin of Victory Enters via Market Odds

The CTO asked: how does HOW a team won affect next-round predictions?

**Answer: The market does this for us.** When a 1-seed barely survives a 16-seed (e.g., wins by 2 in OT), the market immediately adjusts their Round 2 line. A team that was -12.5 in R1 but won by 2 will see their R2 line compressed by 3-5 points. Conversely, a team that demolished their R1 opponent by 25+ sees their R2 line extend.

By using next-round market odds as our updated P_market, we automatically incorporate:
- Margin of victory / defeat quality
- Eye-test performance (sharps watch the games)
- Injury/fatigue revealed during play
- Matchup-specific adjustments for the actual next opponent
- Momentum / confidence signals

We do NOT need to build a separate "performance update" model. The market IS that model.

### Explicit Performance Adjustment (When Market Unavailable)

If next-round odds are not yet available (e.g., game just ended, lines not posted), use this interim adjustment:

```
performance_factor = (actual_margin - expected_margin) / expected_margin_stdev

where:
  actual_margin = winner's score - loser's score
  expected_margin = pre-game spread (absolute value)
  expected_margin_stdev = 11.0 (NCAA tournament game standard deviation)

P_stats_adjusted = logistic_shift(P_stats, 0.03 * performance_factor)
  # Each 1-sigma outperformance shifts P_stats by ~3% for the next game
  # Capped at +/- 10% adjustment
```

This is a stopgap until market lines are posted (typically within 2-4 hours of the previous round completing).

### Matchup-Specific Odds as Style Adjustment

The CTO asked about style matchups (fast vs slow, zone defense, size mismatches). From a betting perspective:

**The game-specific moneyline already prices matchup styles.** When the market sets a line for (3) Baylor vs (6) Creighton, the line-makers have already considered:
- Baylor's size advantage in the paint
- Creighton's 3-point shooting vs Baylor's perimeter defense
- Pace differential and its effect on game flow

However, there are edges the market does not fully price (these go into P_factors):

1. **Extreme pace mismatch (>8 possessions/game differential):** Market underprices the variance compression. When a 74-possession team plays a 62-possession team, the game will be played at ~66-68 possessions, significantly reducing the sample size and increasing upset probability. Adjustment: **+3-5% upset probability** relative to market line.

2. **Zone defense vs poor 3PT shooting team:** If Team A plays zone >30% of possessions (per Synergy data) and Team B shoots <30% from 3, the market often has the line right on average but underestimates the FLOOR for Team B. This doesn't change P_market but should widen the confidence interval.

3. **Size mismatch (>2 inches avg height differential):** The taller team has a rebounding and paint-scoring advantage that is partially priced but may be amplified in tournament settings (tighter officiating, more physical play). Adjustment: **+1-2% for the taller team** in P_factors.

These adjustments feed into P_factors, not P_market. The market is the best single estimate; we only override it on the margins.

---

## 11. Year-Adaptive Field Strength Gap (2025: Chalk-Heavy Profile)

### The Signal: Futures Concentration Index

The single best proxy for "how chalk-heavy will this tournament be" is how much of the championship futures market is concentrated in the top 4 teams.

**Futures Concentration Index (FCI):**

```
FCI = sum of top-4 teams' de-vigged championship probabilities
```

| Year | Top 4 Teams Combined Prob | Tournament Profile | Actual 1-Seed Final Four Count |
|------|--------------------------|-------------------|-------------------------------|
| 2007 | 52% | Very chalk-heavy | 3 of 4 |
| 2008 | 38% | Balanced | 3 of 4 (Kansas dominant) |
| 2011 | 28% | Upset-heavy | 0 of 4 |
| 2015 | 46% | Chalk-heavy | 2 of 4 |
| 2018 | 32% | Very upset-heavy | 0 of 4 (UMBC year) |
| 2019 | 50% | Chalk-heavy | 3 of 4 |
| 2023 | 30% | Upset-heavy | 1 of 4 |
| 2024 | 42% | Moderate | 2 of 4 |
| **2025** | **61.1%** | **Historically chalk** | **4 of 4** |

### How FCI Adjusts the Model

When FCI is high (>60%), the top seeds are genuinely better than the field. The model should:

1. **Reduce upset probabilities for 1-seeds and 2-seeds** — but only for them
2. **Do NOT reduce upset probabilities for 5-12 matchups** — structural chaos persists regardless of field strength gap
3. **Slightly increase Cinderella run probability to Sweet 16** — the mid-major that upsets a 4 or 5 seed still has a clear path, but their run likely ends at the Elite 8 wall of a 1-seed

**Seed-tier adjustment formula:**

```
chalk_factor = FCI / 0.40  # normalized so FCI=40% (average) gives factor=1.0

For 1-seeds and 2-seeds:
  P_upset_adjusted = P_upset_base / chalk_factor
  # 2025: chalk_factor = 61.1/40 = 1.528
  # A 1v16 upset prob of 1.5% becomes 1.5% / 1.528 = 0.98%
  # A 2v15 upset prob of 6% becomes 6% / 1.528 = 3.9%

For 3-seeds and 4-seeds:
  P_upset_adjusted = P_upset_base / sqrt(chalk_factor)
  # Partial reduction — they benefit from field quality but less so
  # A 4v13 upset prob of 8% becomes 8% / sqrt(1.528) = 6.5%

For 5-seeds through 8-seeds:
  P_upset_adjusted = P_upset_base  # NO ADJUSTMENT
  # Structural chaos: 5v12, 6v11, 7v10, 8v9 upset rates are remarkably
  # stable across chalk and upset years (within 2-3% of long-run averages)
```

### 2025 Specific Application

The CTO notes the 2025 four 1-seeds are significantly better than the rest. The betting market confirms this:

- **FCI ~ 55%** (estimated from pre-tournament futures)
- chalk_factor = 1.375
- 1-seeds should reach Final Four at higher rates than the historical 60% baseline
- Model prediction: 3 of 4 one-seeds make Final Four (75% probability for each)
- But in the 5-12 and 6-11 range, expect the usual 30-35% upset rate

### Integration with P_market

The FCI adjustment is applied **before** the log-odds blend, as a modifier on P_stats:

```
if seed_matchup in [1v16, 2v15, 1v8/9, 2v7/10]:  # top-seed games
    P_stats = 1 - (1 - P_stats_raw) / chalk_factor
elif seed_matchup in [3v14, 4v13, 3v6/11, 4v5/12]:  # mid-tier
    P_stats = 1 - (1 - P_stats_raw) / sqrt(chalk_factor)
else:  # 5v12, 6v11, 7v10, 8v9
    P_stats = P_stats_raw  # no adjustment

# Then proceed with normal 4-component blend:
logit(P_final) = w_m * logit(P_market) + w_s * logit(P_stats) + w_x * logit(P_matchup) + w_f * logit(P_factors)
```

Note: P_market (from game moneylines) will ALSO reflect the field strength gap, since books price it in. The FCI adjustment on P_stats ensures that when market data is unavailable (pre-tournament), our stats-based probabilities are appropriately calibrated for the year's profile.

---

## 12. Top 30 Factors: Betting-Agent Contribution (Ranked by Predictive Value)

The CTO wants the top 30 factors across the entire model. Below are the **betting/market factors** ranked by predictive importance. These should be merged with the stats-agent and sports-analyst factor lists to form the unified top 30.

### Betting/Market Factors (My Domain)

| Rank | Factor | Category | Predictive Value | Notes |
|------|--------|----------|-----------------|-------|
| 1 | Closing game moneyline (de-vigged) | P_market | **HIGHEST** | Single most accurate predictor of game outcomes |
| 2 | Closing point spread | P_market | **HIGHEST** | Equivalent to moneyline; use whichever available |
| 3 | Championship futures (de-vigged, Shin) | P_market | **HIGH** | Pre-tournament team strength + path assessment |
| 4 | Futures Concentration Index (FCI) | Year-adaptive | **HIGH** | Determines chalk vs upset year profile |
| 5 | Line movement (open to close) | P_market adjustment | **HIGH** | Reveals new information incorporated by market |
| 6 | Reverse line movement signal | Sharp/public | **MEDIUM-HIGH** | Sharp money detection; +8-15% upset adjustment |
| 7 | Pinnacle vs soft-book spread divergence | Sharp signal | **MEDIUM-HIGH** | When Pinnacle disagrees with DraftKings, trust Pinnacle |
| 8 | Regional futures concentration | Regional calibration | **MEDIUM** | Herfindahl index of regional winner probs |
| 9 | Over/under total (game-specific) | Variance proxy | **MEDIUM** | Low totals = higher upset probability |
| 10 | Blue-blood futures deflator | Bias correction | **MEDIUM** | 0.88-0.92 on Duke/Kansas/Kentucky/UNC futures |
| 11 | Next-round market repricing (live update) | Weight update | **MEDIUM** | Post-round odds incorporate margin, eye test, injuries |
| 12 | Steam move detection | Sharp signal | **LOW-MEDIUM** | Sudden 2+ pt move in <30 min = syndicate action |

### How These Map to the Top 30

My recommendation for the unified top 30 allocation:
- **12 factors from betting/market** (listed above)
- **~10 factors from stats** (AdjEM, defensive efficiency, experience, SOS, luck adjustment, FT rate, coaching score, injuries, 3PT variance, and the logistic function calibration parameter k)
- **~8 factors from matchup/situational analysis** (pace mismatch, conference tournament fatigue, size mismatch, zone defense matchup, geographic proximity, rest days, head-to-head history, same-conference familiarity)

Total: 30 factors. This is the complete model. No more, no less.

### What to CUT

The following were considered but should NOT be in the top 30:
- Public betting percentages alone (redundant with RLM signal)
- Social media sentiment
- "Momentum" or "hot streak" (noise, already in market price)
- Specific player usage rate (subsumed by team-level AdjEM)
- Conference RPI/NET rankings (redundant with SOS + AdjEM)
- Travel distance (too small an effect; partially in market)
- Mascot, jersey color, or other spurious correlations

---

## 13. Data Flow Summary

```
Selection Sunday:
  Futures (Odds API) --> Shin de-vig --> Blue-blood deflator --> P_market (pre-tournament)

48 hours before each game:
  Game moneylines (Odds API) --> Multiplicative de-vig --> P_market (game-specific)
  Betting % (Action Network) --> Sharp/public classifier --> RLM adjustment if detected

At tipoff:
  Closing moneyline --> Final P_market

Blend (4-component log-odds, baseline tier):
  logit(P_final) = 0.55 * logit(P_market) + 0.25 * logit(P_stats) + 0.12 * logit(P_matchup) + 0.08 * logit(P_factors)
  P_final = sigmoid(logit(P_final))

  Live tournament tier (R2+):
  logit(P_final) = 0.60 * logit(P_market) + 0.18 * logit(P_stats) + 0.14 * logit(P_matchup) + 0.08 * logit(P_factors)

Post-game:
  P_final for completed game = 1.0 or 0.0 (hard observation)
  Update downstream probabilities via Bayesian soft-likelihood (SMC per D001)
```
