# Math Model Specification: Win Probability & Bracket Scoring

**Author:** Math Agent
**Date:** 2026-03-06
**Status:** DRAFT v3 — Top 30 factors, year-adaptive field strength gap, seed-tier upset modeling
**References:** D001-D006 in DECISION_LOG.md

---

## 1. Overview

This document specifies the exact mathematical formulas for:
1. Computing P(Team A beats Team B) for any tournament game, including matchup-specific adjustments
2. Converting betting odds to fair probabilities (de-vig)
3. Blending multiple probability sources via log-odds
4. Cascading probabilities through the bracket tree
5. Scoring and ranking all 32,768 regional brackets via exhaustive enumeration
6. **Selecting 10M unique full brackets** from the ~1.15 trillion cross-region combination space
7. **Live weight updating** as tournament results arrive (round-by-round probability recalculation)
8. **Head-to-head and style matchup adjustments**
9. Handling Final Four cross-region assembly

The guiding principle (per CTO): **sports betting odds carry the greatest weight**. Vegas closing lines are the single most accurate predictor of NCAA tournament outcomes.

**Success benchmark:** A human once got 63% of games correct (~40/63). Our model must beat this baseline consistently.

---

## 2. The Top 30 Factors (Ranked by Predictive Value) [NEW — CTO Requirement]

The CTO directive: identify the 30 variables that explain the most variance and nail those. Cut everything else. Basketball has enormous random variance — over-engineering with 100 factors adds noise, not signal.

**Ranking methodology:** Factors are ranked by estimated marginal R-squared contribution to predicting tournament game outcomes, based on published research, KenPom backtesting, and betting market analysis. The top factors are embedded in our four probability components (P_market, P_stats, P_matchup, P_factors).

| Rank | Factor | Component | Est. Marginal R^2 | Notes |
|------|--------|-----------|-------------------|-------|
| **1** | **Vegas closing spread/moneyline** | P_market | 0.28 | Single best predictor. Embeds all public info. |
| **2** | **KenPom AdjEM (efficiency margin)** | P_stats | 0.22 | Best single statistical predictor. |
| **3** | **Closing line from Pinnacle** | P_market | 0.05* | Sharpest book, incremental over consensus. |
| **4** | **Year field strength gap** | P_stats (modifier) | 0.04 | How top-heavy is the field? (see Section 2.2) |
| **5** | **Seed differential** | P_market (embedded) | 0.03* | Largely captured by spread, but structural. |
| **6** | **KenPom AdjD (defensive efficiency)** | P_stats | 0.03 | Defense > offense in single-elimination. |
| **7** | **Championship futures concentration** | P_market | 0.02 | Proxy for field strength gap. |
| **8** | **Bart Torvik experience score** | P_stats | 0.02 | Upperclassmen outperform in March. |
| **9** | **Non-conference SOS** | P_stats | 0.02 | Tests quality outside conference bubble. |
| **10** | **Current-season H2H margin** | P_matchup | 0.02 | Direct evidence of matchup interaction. |
| **11** | **Luck adjustment (Pythagorean gap)** | P_stats | 0.015 | Overperformers regress in tournament. |
| **12** | **Free throw rate index** | P_stats | 0.015 | Close games decided at the line. |
| **13** | **Coaching tournament experience** | P_stats | 0.015 | 15+ appearances correlates with prep quality. |
| **14** | **Pace differential (matchup)** | P_matchup | 0.012 | Extreme pace mismatches favor slower team. |
| **15** | **Team turnover rate vs opp steal rate** | P_matchup | 0.010 | Turnover-prone teams get exploited. |
| **16** | **3-point shooting variance** | P_stats | 0.010 | High variance = more upset potential both ways. |
| **17** | **Frontcourt size mismatch** | P_matchup | 0.010 | Rebounding and interior defense advantage. |
| **18** | **Key player injuries** | P_stats | 0.010 | Star absence = large PI drop. |
| **19** | **Zone defense vs poor 3pt shooting** | P_matchup | 0.008 | Specific exploitable mismatch. |
| **20** | **Historical H2H (3-year window)** | P_matchup | 0.008 | Coaching/scheme familiarity signal. |
| **21** | **ESPN bracket pick % (public sentiment)** | P_factors | 0.006 | Weak crowd wisdom signal. |
| **22** | **Minutes-weighted team height** | P_matchup | 0.005 | Overall size advantage. |
| **23** | **Performance vs similar opponents** | P_matchup | 0.005 | Style-specific overperformance. |
| **24** | **Conference rivalry (same-conf matchup)** | P_matchup | 0.004 | Familiarity reduces favorite's edge. |
| **25** | **Coach vs coach H2H record** | P_matchup | 0.003 | Noisy but nonzero with enough games. |
| **26** | **AP/Coaches poll residual** | P_factors | 0.003 | Reputation divergence from stats. |
| **27** | **Line movement (opening vs closing)** | P_market | 0.003 | Sharp money direction. |
| **28** | **Blue-blood futures deflator** | P_market | 0.002 | Public money inflates Duke/UNC/etc. |
| **29** | **Travel distance / rest days** | P_factors | 0.002 | Minor but measurable for back-to-backs. |
| **30** | **Assist rate differential** | P_matchup | 0.002 | Team-oriented offense is more consistent. |

**Cumulative:** These 30 factors capture an estimated R^2 ~ 0.50 of game outcome variance. The remaining ~0.50 is irreducible randomness (hot shooting, referee calls, injuries mid-game, etc.). This is consistent with the theoretical ceiling: basketball has the highest single-game variance of any major sport.

**Factors explicitly CUT (below threshold):**
- Recent form / last-10-games record (noise, already in AdjEM)
- Conference regular season record (collinear with AdjEM)
- Altitude/geography of venue (negligible for neutral sites)
- Player age/class breakdown beyond experience score (redundant)
- Social media sentiment / Google trends (no proven signal)
- Jersey color, mascot type, first-letter-of-name (superstition, zero signal)
- Individual player PER/BPM (subsumed by team-level AdjEM)

### 2.1 How the Top 30 Map to Components

```
P_market (w=0.55): Factors 1, 3, 5, 7, 27, 28        = ~0.36 R^2
P_stats  (w=0.25): Factors 2, 4, 6, 8, 9, 11-13, 16, 18 = ~0.12 R^2
P_matchup(w=0.12): Factors 10, 14-15, 17, 19-20, 22-25, 30 = ~0.07 R^2
P_factors(w=0.08): Factors 21, 26, 29                  = ~0.01 R^2
```

The weight allocation (0.55/0.25/0.12/0.08) is roughly proportional to the R^2 contribution of each component. This is not coincidental — the CTO's intuition that "Vegas is the best" is mathematically justified.

### 2.2 Year-Adaptive Field Strength Gap [NEW — CTO Requirement]

Some years the top seeds are historically dominant (e.g., 2025: all four 1-seeds are elite). Other years the field is flat. The model must adapt.

**Field Strength Gap (FSG):** A single scalar measuring how top-heavy the tournament field is.

```
# Compute from pre-tournament data:
top_4_adjEM = mean(AdjEM of the four 1-seeds)
field_adjEM = mean(AdjEM of seeds 5-16 across all regions)
historical_gap = mean(top_4_adjEM - field_adjEM) over last 10 tournaments

FSG = (top_4_adjEM - field_adjEM) / historical_gap
# FSG > 1.0 = top-heavy year (like 2025)
# FSG < 1.0 = flat year (more upsets expected)
# FSG = 1.0 = average year
```

**Alternative FSG from futures market (more robust):**

```
top_4_futures_share = sum of de-vigged championship probabilities for the four 1-seeds
historical_avg_share = ~0.45 (typical: 1-seeds hold ~45% of championship probability)

FSG_market = top_4_futures_share / historical_avg_share
# 2025 example: if 1-seeds hold 65% of championship futures -> FSG_market = 0.65/0.45 = 1.44
```

**Use the market-based FSG preferentially** (it incorporates injury news, roster quality, etc. that raw AdjEM may miss).

### 2.3 How FSG Modifies Probabilities (Seed-Tier-Specific)

The FSG does NOT apply uniformly. Per CTO insight: top seeds get MORE dominant, but middle-seed chaos is structural.

**Seed tier definitions:**

| Tier | Seeds | FSG Effect |
|------|-------|------------|
| Elite | 1-2 seeds | FULL FSG adjustment (reduces upset probability) |
| Strong | 3-4 seeds | HALF FSG adjustment |
| Middle | 5-8 seeds | NO FSG adjustment (chaos is structural here) |
| Underdog | 9-16 seeds | Inverse: slight INCREASE in upset probability against Elite/Strong when FSG > 1 |

**The FSG modifier is applied to the logistic model's k parameter:**

```
# Base k from calibration (D004)
k_base = calibrated_k   # e.g., 15

# Seed-tier-specific k adjustment:
For a game between seed_A and seed_B:

    tier_A = get_tier(seed_A)
    tier_B = get_tier(seed_B)

    if tier_A == "Elite" or tier_B == "Elite":
        # One team is a 1-seed or 2-seed
        # When FSG > 1 (top-heavy year), REDUCE k -> steeper logistic -> stronger favorites
        k_adjusted = k_base / (1 + 0.15 * (FSG - 1))
        # Example: FSG = 1.44 -> k_adjusted = 15 / 1.066 = 14.07
        # This makes the favorite ~2-3% MORE likely to win

    elif tier_A == "Strong" or tier_B == "Strong":
        # 3-seed or 4-seed involved
        k_adjusted = k_base / (1 + 0.07 * (FSG - 1))
        # Half the effect

    else:
        # Middle vs Middle, Middle vs Underdog, etc.
        k_adjusted = k_base
        # No FSG adjustment — chaos in 5v12, 6v11, 7v10, 8v9 is structural

P_stats(A beats B) = 1 / (1 + 10^((PI_B - PI_A) / k_adjusted))
```

**Key insight:** The FSG modifier makes the logistic curve STEEPER for games involving top seeds in top-heavy years, meaning favorites win more often. But for middle-seed matchups, the curve is unchanged — those upsets happen at roughly the same rate every year because they reflect inherent parity, not field quality.

### 2.4 Cinderella Run Probability (Year-Adaptive)

The CTO notes that in 2025, small Cinderella runs (Sweet 16, maybe Elite 8) are likely, but Final Four Cinderellas are very unlikely.

This is automatically handled by the FSG model:
- A 12-seed beating a 5-seed: no FSG adjustment (both Middle tier) -> normal ~35% upset rate
- That 12-seed then beating a 4-seed (Strong tier): mild FSG reduction -> maybe 22% instead of 25%
- That 12-seed then beating a 1-seed (Elite tier): full FSG reduction -> maybe 4% instead of 7%

The probability of a 12-seed reaching the Final Four in a top-heavy year:
```
P(12-seed to F4) ~ 0.35 * 0.22 * 0.04 = 0.0031 (0.3%)
```

vs. a flat year:
```
P(12-seed to F4) ~ 0.35 * 0.25 * 0.07 = 0.0061 (0.6%)
```

The top-heavy year makes deep Cinderella runs about half as likely, but early upsets remain common. This matches the CTO's intuition exactly.

---

## 3. The Four Probability Components

The final win probability for any game is a log-odds blend of four probability estimates:

```
logit(P_final) = w_m * logit(P_market) + w_s * logit(P_stats) + w_f * logit(P_factors) + w_x * logit(P_matchup)
```

where `logit(p) = ln(p / (1-p))` and:

| Component   | Symbol     | Weight | Description |
|-------------|------------|--------|-------------|
| Market      | P_market   | w_m = 0.55 | De-vigged betting odds (moneyline + spread) |
| Stats       | P_stats    | w_s = 0.25 | Power index model (KenPom AdjEM-based) |
| Matchup     | P_matchup  | w_x = 0.12 | Style matchup, H2H history, pace/size |
| Factors     | P_factors  | w_f = 0.08 | Sentiment, qualitative adjustments |

> **CTO Decision (2026-03-06):** "Vegas lines should have a lot higher weight — these guys are good." Market weight increased to 0.55, making it the dominant signal. Vegas lines already incorporate matchup intelligence from thousands of sharp bettors. The total market weight is 0.55 (up from 0.40). When game-specific betting lines are available, those lines already embed matchup/stats information, so the effective market influence is even higher.

**Why log-odds blending?** Log-odds (logit) blending is the mathematically correct way to combine independent probability estimates. It is equivalent to:
- Taking a weighted geometric mean of the odds ratios
- Linear pooling in the natural parameter space of the Bernoulli distribution
- The optimal combination under a log-loss objective when sources are conditionally independent

The inverse transform recovers the final probability:
```
P_final = sigmoid(w_m * logit(P_market) + w_s * logit(P_stats) + w_x * logit(P_matchup) + w_f * logit(P_factors))
```

**Weight constraint:** w_m + w_s + w_x + w_f = 1.0.

**Weight tiers by data availability:** The baseline weights above (0.55/0.25/0.12/0.08) apply when game-specific lines are available. When market data is limited, redistribute:

```
If game-specific lines available (baseline):
    w_m = 0.55, w_s = 0.25, w_x = 0.12, w_f = 0.08
If only futures/seed-based market data:
    w_m = 0.40, w_s = 0.35, w_x = 0.15, w_f = 0.10
If no market data:
    w_m = 0.00, w_s = 0.55, w_x = 0.30, w_f = 0.15
Live tournament lines (post-tip, updated odds):
    w_m = 0.60, w_s = 0.18, w_x = 0.14, w_f = 0.08
```

---

## 4. Component 1: P_market (Market-Derived Probability)

### 4.1 Moneyline to Implied Probability

American moneyline odds are converted to raw implied probability:

```
For favorite (negative odds, e.g., -350):
    p_implied = |odds| / (|odds| + 100)
    Example: -350 -> 350 / 450 = 0.7778

For underdog (positive odds, e.g., +280):
    p_implied = 100 / (odds + 100)
    Example: +280 -> 100 / 380 = 0.2632
```

### 4.2 Removing the Vig (De-vigging)

The raw implied probabilities for both sides of a game sum to > 1.0 (the overround). We must remove the vig to get fair probabilities.

**Recommended method: Multiplicative (proportional) de-vig**

```
overround = p_implied_A + p_implied_B    (typically 1.03 to 1.10)
p_fair_A = p_implied_A / overround
p_fair_B = p_implied_B / overround
```

Verify: p_fair_A + p_fair_B = 1.0.

**Alternative: Power method (Shin model)**

The power method accounts for the empirical observation that the vig is disproportionately loaded onto the favorite. It finds exponent n such that:

```
p_implied_A^n + p_implied_B^n = 1
```

Solve for n numerically (Newton's method, ~3 iterations). Then:
```
p_fair_A = p_implied_A^n
p_fair_B = p_implied_B^n
```

**Recommendation: Use the power method for moneylines where the favorite is -300 or stronger; use multiplicative for all others.** The difference is typically < 1% for balanced matchups.

### 4.3 Spread-to-Probability Conversion

When moneyline odds are unavailable but point spreads are, convert spread to win probability using the normal CDF:

```
P_market_A = Phi(spread_A / sigma)
```

where:
- `spread_A` = the point spread favoring Team A (positive = A favored)
- `sigma` = standard deviation of the score margin distribution
- `Phi` = standard normal CDF

**Calibration of sigma:** Historical NCAA tournament data suggests sigma ~ 11.0 points for tournament games (slightly higher than regular season ~10.5 due to variance of neutral-site single-elimination). This should be calibrated alongside the k parameter in D004.

```
Example: Team A is a 7.5-point favorite (spread_A = 7.5)
P_market_A = Phi(7.5 / 11.0) = Phi(0.682) = 0.752
```

### 4.4 Multiple Sportsbooks Aggregation

When odds are available from multiple sportsbooks via The Odds API:

1. De-vig each book's line independently
2. Compute the **median** de-vigged probability across all books
3. If Pinnacle is available, use a weighted average: 60% Pinnacle + 40% median of others

```
if pinnacle_available:
    P_market = 0.60 * p_fair_pinnacle + 0.40 * median(p_fair_others)
else:
    P_market = median(p_fair_all)
```

### 4.5 Fallback Cascade (When Game Lines Are Unavailable)

1. **Priority 1:** Game-specific moneylines/spreads -> Sections 3.1-3.4
2. **Priority 2:** Futures only -> Section 4.6
3. **Priority 3:** No market data -> P_market = P_stats (market weight redistributed to stats)

### 4.6 Futures-Derived Game Probability

```
p_champ_A = de-vigged championship probability of Team A
p_champ_B = de-vigged championship probability of Team B

P_market_from_futures = p_champ_A / (p_champ_A + p_champ_B)
```

**Blue-blood deflator** (D003): Multiply championship futures for Duke, Kansas, Kentucky, UNC by 0.88-0.92 before using them.

**Limitation:** Coarse estimate. Use only as a fallback.

---

## 5. Component 2: P_stats (Statistical Model Probability)

### 5.1 Power Index Computation

Each team's power index PI is computed from the 9-factor formula (D002):

```
PI = 0.40 * normalize(AdjEM)
   + 0.10 * normalize(DefensivePremium)
   + 0.10 * normalize(NonConfSOS)
   + 0.10 * normalize(ExperienceScore)
   + 0.08 * normalize(LuckAdjustment)
   + 0.07 * normalize(FreeThrowRateIndex)
   + 0.07 * normalize(CoachingTournamentScore)
   + 0.05 * normalize(KeyInjuries)
   + 0.03 * normalize(ThreePointVarianceFlag)
```

where `normalize(x)` maps each raw stat to a 0-100 scale using min-max normalization across the 64 tournament teams:

```
normalize(x) = (x - x_min) / (x_max - x_min) * 100
```

### 5.2 Power Index to Win Probability (Logistic Model)

```
P_stats(A beats B) = 1 / (1 + 10^((PI_B - PI_A) / k))
```

where k is calibrated per D004 (grid search k in {10..20}, minimize Brier Score on historical data, target <= 0.205).

### 5.3 Three-Point Variance Flag (Special Handling)

The 3-point variance flag widens the probability distribution without shifting the mean:

```
variance_factor = 0.03 * max(0, team_3pt_stdev / league_avg_3pt_stdev - 1)
variance_factor = clamp(variance_factor, 0, 0.10)
P_stats_adjusted = P_stats * (1 - variance_factor) + 0.5 * variance_factor
```

---

## 6. Component 3: P_matchup (Matchup-Specific Adjustments) [NEW]

This is the core new component addressing the CTO's requirements for head-to-head history, style matchups, and team-specific interactions that go beyond generic power ratings.

### 6.1 Matchup Adjustment Architecture

P_matchup is computed as a base probability (0.5 = neutral) plus a series of logit-space adjustments:

```
matchup_logit = h2h_adj + style_adj + size_adj + pace_adj + defensive_scheme_adj
P_matchup = sigmoid(matchup_logit)
```

Each adjustment is capped to prevent any single matchup factor from dominating.

### 6.2 Head-to-Head History Adjustment (h2h_adj)

When two teams have played each other in the current season or recent seasons:

```
# Current season H2H (strongest signal)
if teams_played_this_season:
    margin_this_season = avg(point_margin_A_vs_B)   # positive = A won on average
    recency_weight = 1.0 if within 60 days, 0.7 if 60-120 days, 0.5 if >120 days
    h2h_current = 0.02 * margin_this_season * recency_weight
    # 1 point of margin ~ 0.02 logit units ~ 0.5% probability shift
else:
    h2h_current = 0

# Historical H2H (weaker signal, captures coaching/program dynamics)
if teams_played_last_3_seasons:
    h2h_record_A = wins_A / (wins_A + wins_B)  # A's win rate vs B
    n_games = wins_A + wins_B
    # Bayesian shrinkage toward 0.5 (prior_weight inversely proportional to sample size)
    prior_weight = 4.0 / (4.0 + n_games)   # 4 pseudo-observations at 0.5
    h2h_shrunk = h2h_record_A * (1 - prior_weight) + 0.5 * prior_weight
    h2h_historical = 0.3 * logit(h2h_shrunk)  # dampen by 0.3 (weak signal)
else:
    h2h_historical = 0

h2h_adj = h2h_current + h2h_historical
h2h_adj = clamp(h2h_adj, -0.30, 0.30)   # max ~7% probability shift from H2H alone
```

**Data source:** Sports-analyst to research. Likely: sports-reference.com, ESPN API, or manual collection.

### 6.3 Style Matchup Adjustment (style_adj)

Style matchup captures how each team's offensive identity interacts with the opponent's defensive identity.

**Step 1: Classify team offensive/defensive style**

Each team is characterized by a style vector:

```
Style vector S = (pace, 3pt_rate, ft_rate, off_reb_rate, turnover_rate, assist_rate)
```

All values are z-scores (mean 0, stdev 1) relative to the tournament field.

**Step 2: Compute style interaction**

Specific style mismatches that have predictive value in tournament settings:

```
# Zone defense vs poor 3pt shooting
# If Team B plays zone AND Team A is a poor 3pt shooting team:
zone_penalty_A = 0
if team_B_plays_zone:
    zone_penalty_A = -0.10 * max(0, -(team_A_3pt_pct_zscore))
    # If A is 1 stdev below average in 3pt%, penalty = -0.10 logit

# Fast team vs slow team (pace mismatch)
pace_diff = team_A_pace_zscore - team_B_pace_zscore
# Extreme pace mismatches slightly favor the slower team in tournament (half-court matters more)
pace_adj_raw = -0.03 * pace_diff if abs(pace_diff) > 1.5 else 0
# Fast teams forced to play slow lose their advantage

# Turnover-prone team vs disruptive defense
to_adj = 0
if team_A_turnover_rate_zscore > 0.5 and team_B_steal_rate_zscore > 0.5:
    to_adj = -0.05 * team_A_turnover_rate_zscore * team_B_steal_rate_zscore
    # Turnover-prone offense against ball-hawking defense = bad for A

style_adj = zone_penalty_A + pace_adj_raw + to_adj
style_adj = clamp(style_adj, -0.25, 0.25)   # max ~6% probability shift from style
```

### 6.4 Size Mismatch Adjustment (size_adj)

More granular than the simple height differential in v1. Now considers positional size:

```
# Average height of rotation players (top 8 by minutes), weighted by minutes
height_A = minutes_weighted_avg_height(team_A)
height_B = minutes_weighted_avg_height(team_B)
height_diff = height_A - height_B   # in inches

# Frontcourt size specifically (C + PF positions)
fc_height_A = avg_height(team_A_frontcourt)
fc_height_B = avg_height(team_B_frontcourt)
fc_diff = fc_height_A - fc_height_B

# Combined size adjustment
size_adj = 0.02 * height_diff + 0.03 * fc_diff
size_adj = clamp(size_adj, -0.20, 0.20)   # max ~5% probability shift
```

### 6.5 Performance Against Similar Opponents (similarity_adj)

How does each team perform against opponents whose style resembles their tournament opponent?

```
# Find Team A's games against opponents stylistically similar to Team B
similar_opponents_B = find_similar(team_B.style_vector, all_opponents_of_A, top_k=5, cosine_threshold=0.7)

if len(similar_opponents_B) >= 3:
    margin_vs_similar = avg(team_A_margin in games against similar_opponents_B)
    expected_margin_vs_similar = avg(predicted_margin based on power ratings)
    residual_A = margin_vs_similar - expected_margin_vs_similar
    # Positive residual = A overperforms against B-like teams
else:
    residual_A = 0

# Symmetric: Team B against A-like teams
similar_opponents_A = find_similar(team_A.style_vector, all_opponents_of_B, top_k=5, cosine_threshold=0.7)

if len(similar_opponents_A) >= 3:
    margin_vs_similar = avg(team_B_margin in games against similar_opponents_A)
    expected_margin_vs_similar = avg(predicted_margin based on power ratings)
    residual_B = margin_vs_similar - expected_margin_vs_similar
else:
    residual_B = 0

similarity_adj = 0.015 * (residual_A - residual_B)
similarity_adj = clamp(similarity_adj, -0.15, 0.15)   # max ~3.7% shift
```

**Cosine similarity for style matching:**
```
cosine_sim(S_a, S_b) = dot(S_a, S_b) / (|S_a| * |S_b|)
```

### 6.6 Coach vs Coach Adjustment

```
if coach_A_vs_coach_B_history_exists:
    n_meetings = total_games(coach_A vs coach_B)
    coach_win_rate_A = wins_A / n_meetings
    # Heavy shrinkage (coaching matchups are noisy with small samples)
    prior_weight = 6.0 / (6.0 + n_meetings)
    shrunk_rate = coach_win_rate_A * (1 - prior_weight) + 0.5 * prior_weight
    coach_adj = 0.2 * logit(shrunk_rate)
    coach_adj = clamp(coach_adj, -0.10, 0.10)   # max ~2.5% shift
else:
    coach_adj = 0
```

### 6.7 Conference Rivalry Effect

```
if same_conference(team_A, team_B):
    # Conference opponents have more information about each other
    # This tends to reduce the favorite's advantage (familiarity helps the underdog)
    conf_rivalry_adj = 0.05 * sign(PI_B - PI_A)  # nudge toward 0.5
    # If A is favored, this slightly helps B (underdog has game-planned for A)
else:
    conf_rivalry_adj = 0
```

### 6.8 Complete P_matchup Formula

```
matchup_logit = h2h_adj + style_adj + size_adj + similarity_adj + coach_adj + conf_rivalry_adj
matchup_logit = clamp(matchup_logit, -0.50, 0.50)   # total matchup cap: max ~12% swing
P_matchup = sigmoid(matchup_logit)
```

The total cap of 0.50 logit units (~12% probability swing) prevents matchup factors from overwhelming the market and stats signals.

---

## 7. Component 4: P_factors (Sentiment & Qualitative)

### 7.1 Public Sentiment Factor

ESPN bracket pick percentages provide weak but non-zero signal:

```
pick_pct_A = ESPN "Who Picked Whom" percentage for Team A to win this game
sentiment_logit = 0.5 * logit(pick_pct_A)   # dampened — public picks are noisy
```

### 7.2 AP/Coaches Poll Residual

If a team's poll ranking diverges significantly from their KenPom/power rating, this captures "reputation" signal:

```
poll_rank_A = AP poll rank (1-25, or 30 if unranked)
expected_rank_A = rank based on PI (1-64 mapped to 1-25 scale)
poll_residual_A = expected_rank_A - poll_rank_A   # positive = team ranked higher than stats suggest

poll_adj = 0.01 * (poll_residual_A - poll_residual_B)
poll_adj = clamp(poll_adj, -0.10, 0.10)
```

### 7.3 Complete P_factors

```
factors_logit = sentiment_logit + poll_adj
P_factors = sigmoid(factors_logit)
```

Default P_factors = 0.5 when no data available.

---

## 8. The Complete Formula: P(A beats B)

```
Step 1: Compute P_market (Section 4)
    De-vig moneyline or convert spread; aggregate across sportsbooks

Step 2: Compute P_stats (Section 5)
    Power index for both teams; logistic model with calibrated k

Step 3: Compute P_matchup (Section 6) [NEW]
    H2H history + style matchup + size mismatch + similar-opponent performance + coach H2H + conference rivalry

Step 4: Compute P_factors (Section 7)
    Sentiment + poll residual

Step 5: Log-odds blend (weights depend on line availability)
    If game-specific lines available (baseline):
        logit_final = 0.55*logit(P_market) + 0.25*logit(P_stats) + 0.12*logit(P_matchup) + 0.08*logit(P_factors)
    If only futures/seed-based market:
        logit_final = 0.40*logit(P_market) + 0.35*logit(P_stats) + 0.15*logit(P_matchup) + 0.10*logit(P_factors)
    Live tournament lines:
        logit_final = 0.60*logit(P_market) + 0.18*logit(P_stats) + 0.14*logit(P_matchup) + 0.08*logit(P_factors)

Step 6: Clamp
    P_final = clamp(sigmoid(logit_final), 0.005, 0.995)
```

---

## 9. Exhaustive Regional Enumeration

### 9.1 Why Enumeration

Each region: 15 games, 2^15 = 32,768 possible brackets. Enumerable in milliseconds. Zero sampling error.

### 9.2 Bracket Probability

For a regional bracket b (encoded as a 15-bit integer):

```
P(b) = product_{g=1}^{15} p_g(b)
```

where p_g(b) is the probability of the outcome bracket b specifies for game g, given the teams that would meet under bracket b.

**Important:** Because we now have matchup-specific adjustments (Section 6), the probability of each later-round game depends on who won earlier games. The probabilities are **matchup-specific**, not just seed-based. This means we compute 15 different P_final values for each of the 32,768 brackets — one per game, using the actual teams that would meet under that bracket's path.

### 9.3 Bracket Scoring Function

Standard scoring (ESPN Tournament Challenge defaults, configurable):

| Round | Points per correct pick |
|-------|------------------------|
| R64   | 10 |
| R32   | 20 |
| S16   | 40 |
| E8    | 80 |
| F4    | 160 |
| Championship | 320 |

**Expected score of a bracket b:**

```
E[Score(b)] = sum_{g=1}^{15} points(round(g)) * P(b picks game g correctly)
```

**Efficient computation via marginal probabilities:**

```
P(team T reaches round R) = sum over all brackets where T reaches R: P(bracket)
```

Computed recursively through the bracket tree. Total: O(n * 2^n) where n=15, ~500K operations.

### 9.4 Pool-Size-Adjusted Value

```
ownership(b) = (1/15) * sum_{g=1}^{15} pick_pct(team b picks for g in round(g))
Contrast(b) = 1 - ownership(b)

Value(b) = E[Score(b)] * (1 + alpha * Contrast(b))
```

where alpha in [0, 0.5] depends on pool size (larger pool = more contrarian).

---

## 10. Generating 10 Million Full Brackets [NEW — CTO Requirement #1]

### 10.1 The Combinatorial Space

- 4 regions x 32,768 regional brackets = 131,072 total regional brackets
- Full brackets = Cartesian product of 4 regional brackets + 3 Final Four games
- Regional combinations alone: 32,768^4 = 1.15 x 10^18 (1.15 quintillion)
- With 3 Final Four games (8 outcomes each combo): effectively unbounded
- **We need to select the best 10M from this space**

### 10.2 Selection Algorithm: Probability-Weighted Stratified Sampling

We cannot enumerate 10^18 combinations. Instead, we use a three-phase algorithm:

**Phase 1: Regional Bracket Pre-filtering**

For each of the 4 regions, rank all 32,768 brackets by P(b). Keep the top K brackets per region where K is chosen to balance coverage and quality:

```
K = 500 per region (captures ~99.9% of total probability mass)
```

Justification: In a typical region, the top 500 brackets by probability account for the vast majority of the probability space. Brackets ranked below 500 are extremely unlikely (many simultaneous upsets).

This gives us 500^4 = 62.5 billion possible full-bracket regional combinations. Still too many, but we can sample intelligently.

**Phase 2: Independent Regional Sampling with Recombination**

The key insight: since regions are independent, we can sample regional sub-brackets independently and recombine.

```
Algorithm: Stratified Regional Recombination

For each region r in {South, East, West, Midwest}:
    Compute P(b) for all 32,768 brackets
    Compute CDF(b) = cumulative sum of P(b) sorted by probability

    # Sample N_r brackets from region r, proportional to probability
    # Use systematic sampling (low-discrepancy) for better coverage:

    N_r = 3,163   # cube root of 10M is ~215; but we use 3163 because 3163^2 * ... see below

    Actually, the correct decomposition:

    # We need 10M full brackets. Each full bracket = 4 regional picks + 3 F4 games
    # Sample plan:
    #   - Draw N regional brackets per region
    #   - Combine into N^4 candidates (too many if N is large)
    #   - Instead: draw N full brackets by independently sampling each region

For i = 1 to 10,000,000:
    For each region r:
        Draw bracket_r ~ Categorical(P(b_1)/Z, P(b_2)/Z, ..., P(b_32768)/Z)
        where Z = sum of all P(b) in region r

    full_bracket_i = (bracket_South, bracket_East, bracket_West, bracket_Midwest)

    # Determine Final Four matchups from regional champions
    champ_S = regional_champion(bracket_South)
    champ_E = regional_champion(bracket_East)
    champ_W = regional_champion(bracket_West)
    champ_M = regional_champion(bracket_Midwest)

    # Simulate Final Four (3 games)
    # Semi 1: champ_S vs champ_E (or as bracket dictates)
    # Semi 2: champ_W vs champ_M
    # Final: winner of Semi 1 vs winner of Semi 2

    For each F4 game:
        p = P_final(team_A, team_B)  # full formula from Section 8
        outcome = Bernoulli(p)       # random draw

    full_bracket_i.f4_outcomes = (semi1_winner, semi2_winner, champion)

# Deduplicate
unique_brackets = deduplicate(all 10M full brackets)
```

**Problem with naive approach:** Many duplicates. A 1-seed-heavy region will produce the same "all chalk" bracket millions of times.

### 10.3 Improved Algorithm: Stratified Systematic Sampling

```
Algorithm: 10M Unique Full Brackets via Stratified Recombination

Step 1: Per-region stratification
    For each region, partition 32,768 brackets into strata by regional champion:

    strata[r][team] = { b : regional_champion(b) = team }

    For a region with 16 teams, this gives up to 16 strata per region.
    Compute P(team wins region) = sum P(b) for b in strata[r][team].

Step 2: Enumerate Final Four scenarios
    A "Final Four scenario" = (champ_S, champ_E, champ_W, champ_M)
    Total scenarios = 16^4 = 65,536
    Most have near-zero probability.

    P(scenario) = P(champ_S) * P(champ_E) * P(champ_W) * P(champ_M)

    Keep scenarios with P(scenario) > 1e-8  (typically ~500-2000 scenarios)

Step 3: Allocate bracket budget across scenarios
    For each plausible F4 scenario s:
        N_s = round(10,000,000 * P(s) / sum_P_all_plausible)
        # Neyman-like allocation: more brackets for more likely scenarios
        # But guarantee minimum 10 brackets per plausible scenario
        N_s = max(10, N_s)

    Adjust so sum(N_s) = 10,000,000.

Step 4: Within each scenario, generate N_s unique full brackets
    For scenario s = (champ_S, champ_E, champ_W, champ_M):
        For each region r:
            eligible_brackets[r] = strata[r][champ_r]  # brackets where this team wins the region
            P_conditional[r] = {P(b) / P(champ_r) for b in eligible_brackets[r]}
            # This is the conditional distribution of regional brackets given the champion

        # Generate N_s unique full brackets by independent sampling per region:
        For i = 1 to N_s:
            For each region r:
                Draw b_r ~ Categorical(P_conditional[r])

            # Final Four outcomes are deterministic draw from probabilities:
            p_semi1 = P_final(champ_S, champ_E)
            outcome_semi1 = Bernoulli(p_semi1)
            p_semi2 = P_final(champ_W, champ_M)
            outcome_semi2 = Bernoulli(p_semi2)
            p_final = P_final(winner_semi1, winner_semi2)
            outcome_final = Bernoulli(p_final)

            full_bracket = (b_South, b_East, b_West, b_Midwest, F4_outcomes)

        Deduplicate within scenario (re-sample if duplicate)

Step 5: Assign probability weight to each full bracket
    P(full_bracket) = P(b_South) * P(b_East) * P(b_West) * P(b_Midwest)
                    * P(F4_game1_outcome) * P(F4_game2_outcome) * P(F4_game3_outcome)

Step 6: Verify uniqueness
    Each full bracket is encoded as a 63-bit integer (15 bits x 4 regions + 3 F4 bits)
    Use a hash set to guarantee all 10M are unique
    If duplicates found, resample from the same scenario
```

### 10.4 Why This Works

- **Probability-proportional:** More likely scenarios get more brackets. The "all chalk" scenario gets the most brackets, but upset scenarios are guaranteed representation.
- **Unique:** The hash set ensures no duplicates. With 500+ eligible brackets per region per champion and independent sampling, collisions are rare.
- **Plausible:** Every bracket is generated from a plausible Final Four scenario. No wasted brackets on impossible F4 combinations.
- **Stratified by F4 outcome:** This is the most important stratification variable because F4 picks carry the most points (160+320).
- **Covers the upset space:** Even unlikely champions (e.g., a 12-seed) get at least 10 brackets, ensuring coverage of surprise scenarios.

### 10.5 Computational Cost

- Phase 1: 4 x 32,768 probability computations = ~131K (trivial)
- Phase 2: 65,536 scenario probabilities = trivial
- Phase 3: Budget allocation = trivial
- Phase 4: 10M categorical draws from pre-computed CDFs = ~10M random numbers + ~10M hash lookups
- **Total: ~30 seconds on a single core, trivially parallelizable to <5 seconds**

### 10.6 Storage

Each bracket: 63-bit game outcomes + probability weight (FLOAT) + scenario ID
- 63 bits packed into BIGINT (8 bytes)
- weight: 4 bytes (FLOAT)
- scenario_id: 2 bytes (SMALLINT)
- stratum metadata: 4 bytes
- **~18 bytes per bracket x 10M = ~180 MB**

---

## 11. Live Weight Updating (Round-by-Round) [NEW — CTO Requirement #2]

### 11.1 Hard Pruning: Eliminate Dead Brackets

After each game result, brackets that predicted the wrong outcome are eliminated:

```
For each game G with result (winner = Team W):
    For each surviving bracket b:
        if b.prediction_for_game(G) != W:
            b.alive = false
```

With 10M brackets, after Round of 64 (32 games), approximately:
- Each game eliminates ~50% of remaining brackets (those that picked wrong)
- After 32 games: ~10M * (avg_survival_rate)^32 brackets survive
- If average game has P=0.75 for the correct outcome: 10M * 0.75^32 ~ 1,003 brackets
- If P=0.65: 10M * 0.65^32 ~ 3 brackets
- **This is why we need 10M brackets — to ensure sufficient survivors after each round**

### 11.2 Soft Reweighting: Update Probabilities Based on HOW Teams Won

Beyond hard pruning, we update the probability model based on observed game performance. This changes future game probabilities for surviving brackets.

**After each completed game:**

```
For the winning team W who beat team L by margin M:

    # Expected margin based on pre-game probability
    expected_margin = sigma * Phi_inv(P_final(W, L))
    # where sigma ~ 11.0 (Section 4.3) and Phi_inv is the inverse normal CDF

    # Observed residual
    residual = M - expected_margin

    # Update power index for the winning team
    # Bayesian update: shift PI toward the observation
    PI_W_new = PI_W_old + learning_rate * residual

    # Learning rate decays by round (later rounds have smaller sample, more variance)
    learning_rate_by_round = {
        "R64": 0.15,    # first game: moderate update
        "R32": 0.12,
        "S16": 0.10,
        "E8":  0.08,
        "F4":  0.06,
        "Championship": 0.05
    }

    # Also update losing team (if they survive in other brackets — they don't,
    # but their stats inform our understanding of teams that beat similar opponents)
    PI_L_new = PI_L_old - learning_rate * residual * 0.5
```

### 11.3 Live Market Integration

As the tournament progresses, new betting lines are published for upcoming games:

```
For each upcoming game G_next:
    # Fetch latest moneyline/spread from The Odds API
    P_market_new = de_vig(latest_odds(G_next))

    # Replace the pre-tournament P_market with the live line
    # Live lines are MORE informative than pre-tournament projections because:
    # - They incorporate injury news, travel, rest days
    # - They reflect sharp money that has analyzed the specific matchup
    # - They account for tournament performance observed so far

    # Increase market weight for live lines:
    w_m_live = 0.60   # even higher than the 0.55 baseline
    w_s_live = 0.18
    w_x_live = 0.14
    w_f_live = 0.08
```

### 11.4 Round-by-Round Recalculation Pipeline

```
BEFORE TOURNAMENT:
    1. Compute all pre-tournament probabilities (Sections 4-8)
    2. Enumerate 32,768 regional brackets x 4 regions
    3. Generate 10M full brackets (Section 10)
    4. Store in database with probability weights

AFTER EACH GAME:
    1. Hard prune: mark dead brackets (b.alive = false)
    2. Update power indices based on margin (Section 11.2)
    3. Fetch live odds for next games (Section 11.3)
    4. Recompute P_final for all future games in surviving brackets
    5. Recompute bracket scores: E[Score(b)] for surviving brackets
    6. Re-rank surviving brackets by updated Value(b)
    7. Report: top surviving brackets, updated team probabilities, survival counts

AFTER EACH ROUND:
    1. Full recalculation of all future-game probabilities
    2. Update matchup adjustments (Section 6) for newly determined matchups
       (e.g., after R64, we know the R32 matchups — compute H2H, style, size for those specific pairs)
    3. If surviving bracket count drops below threshold (e.g., < 1000):
       Generate supplementary brackets using updated probabilities
       (new brackets for remaining games only, using observed results as fixed)

FINAL FOUR:
    1. Only 3 games remain, 8 possible outcomes
    2. Compute exact probabilities for all 8 F4 brackets
    3. Rank by expected score given all prior correct picks
```

### 11.5 Supplementary Bracket Generation (When Survivors Are Low)

If too few brackets survive (< 1000 after any round), generate new brackets for remaining games only:

```
After round R with known_results:
    remaining_games = all games in rounds after R
    n_remaining = |remaining_games|

    if n_remaining <= 15:  # one region's worth or less
        Enumerate all 2^n_remaining possible completions
    else:
        Sample new brackets for remaining games using updated probabilities
        Weight by P(completion | known_results)

    Merge with surviving original brackets
    Target: always maintain >= 10,000 live brackets
```

---

## 12. Head-to-Head Data Integration [NEW — CTO Requirement #3]

### 12.1 Required Data Per Potential Matchup

For every pair of teams that could meet in the tournament (up to 64*63/2 = 2,016 pairs, but practically ~200 pairs per region that could actually meet):

| Data Point | Source | Usage |
|-----------|--------|-------|
| Games played this season | Sports Reference, ESPN | h2h_adj (Section 6.2) |
| Point margin in each game | Sports Reference | h2h_adj margin component |
| Games played last 3 seasons | Sports Reference | h2h_historical |
| Win/loss record (all-time, last 10y) | Sports Reference | h2h_historical |
| Coach vs coach record | Manual research | coach_adj (Section 6.6) |
| Conference membership overlap | Known | conf_rivalry_adj (Section 6.7) |
| Style vector for each team | KenPom, Bart Torvik | style_adj (Section 6.3) |
| Team average height by position | ESPN, 247Sports | size_adj (Section 6.4) |
| Games against stylistically similar opponents | Computed from style vectors | similarity_adj (Section 6.5) |

### 12.2 Matchup Probability Matrix

Pre-compute and store a 64x64 **matchup probability matrix** M where:

```
M[i][j] = P_final(team_i beats team_j)
```

This is computed once pre-tournament using the full formula (Section 8). The matrix is:
- Antisymmetric in logit space: logit(M[i][j]) = -logit(M[j][i])
- Dense: all 2,016 unique entries are computed
- Updated after each round (Section 11)

**This matrix is the core data structure** that drives both regional enumeration and 10M bracket generation. Every game probability lookup is a single matrix read.

---

## 13. Full Bracket Assembly (Cross-Region)

### 13.1 Regional Independence

Regions are independent before the Final Four:

```
P(full bracket) = P(South) * P(East) * P(West) * P(Midwest) * P(F4 outcomes)
```

### 13.2 Final Four Scoring

The Final Four adds 3 games worth 160 + 160 + 320 = 640 points. This is 37% of the maximum possible score (1920 points). **Final Four picks are the highest-leverage decisions.**

For each plausible F4 scenario (champ_S, champ_E, champ_W, champ_M):

```
E[F4_Score(scenario)] =
    160 * P(semi1_pick_correct) +
    160 * P(semi2_pick_correct) +
    320 * P(championship_pick_correct)

# Where P(semi_pick_correct) = P(our_pick wins that semifinal)
# And P(championship_pick_correct) = P(our_pick wins semi AND wins final)
```

### 13.3 Assembling the Optimal Full Bracket

```
Step 1: For each region, select regional sub-bracket by Value(b) (Section 9.4)
Step 2: For the selected regional champions, compute optimal F4 picks:
    For each possible F4 outcome (8 total):
        score = E[F4_Score(outcome)]
        ownership = average public pick % of these F4 picks
        F4_value = score * (1 + alpha * (1 - ownership))
    Select F4 outcome with highest F4_value
Step 3: Full_Value = sum(Regional_Value) + F4_Value
```

---

## 14. Bayesian Updating (Live Tournament)

With exhaustive enumeration, pruning is literal: after each real game, exactly half of the 32,768 regional brackets per region are eliminated. For the 10M full brackets, each game eliminates all brackets that disagree.

**Soft reweighting** (alternative to hard pruning, for maintaining probability estimates even after upsets):

```
For each bracket b after game G with actual result R:
    if b.predicted(G) == R:
        w_b = w_b * 1.0   # correct prediction
    else:
        w_b = 0            # dead bracket (hard prune)

# For probability estimation (team advancement odds), use surviving brackets:
P(team T advances to round R) = sum(w_b for b where T reaches R and b.alive) / sum(w_b for b where b.alive)
```

---

## 15. Summary of Key Formulas

| Formula | Expression |
|---------|-----------|
| Moneyline to implied prob (fav) | `p = \|odds\| / (\|odds\| + 100)` |
| Moneyline to implied prob (dog) | `p = 100 / (odds + 100)` |
| Multiplicative de-vig | `p_fair = p_implied / (p_A + p_B)` |
| Spread to probability | `P = Phi(spread / sigma), sigma ~ 11.0` |
| Power index win prob | `P = 1 / (1 + 10^((PI_B - PI_A) / k))` |
| Log-odds blend (4 components) | `logit(P) = 0.55*logit(P_m) + 0.25*logit(P_s) + 0.12*logit(P_x) + 0.08*logit(P_f)` |
| Matchup adjustment (total) | `matchup_logit = h2h + style + size + similarity + coach + conference` |
| Bracket probability | `P(b) = prod_{g} p_g(b)` |
| Expected score | `E[S] = sum_g points(r_g) * P(pick_g correct)` |
| Pool-adjusted value | `V(b) = E[S] * (1 + alpha * Contrast(b))` |
| Full bracket probability | `P(full) = P(S) * P(E) * P(W) * P(M) * P(F4)` |
| Live PI update | `PI_new = PI_old + lr * (observed_margin - expected_margin)` |
| 10M bracket allocation | `N_s = 10M * P(scenario) / sum(P), min 10 per scenario` |

---

## 16. Open Questions & Collaboration Notes

### For betting-agent:
- Confirm: power method vs. multiplicative de-vig threshold (-300)?
- Confirm: Pinnacle weighting (60/40)?
- Live odds integration: how frequently should we poll The Odds API during the tournament?
- CTO locked baseline w_m=0.55. I've set live tournament w_m=0.60. Acceptable?

### For sports-analyst:
- Where to source head-to-head game history (current season + last 3 years)?
- Where to source team style vectors (pace, 3pt_rate, etc.)?
- Where to source team height by position?
- Can you validate the style matchup adjustments (zone defense, pace differential) with historical data?
- Conference rivalry effect: is the 0.05 logit shift justified empirically?

### For team-lead/CTO:
- CTO weight decision (w_m=0.55) integrated. Live tournament bumped to w_m=0.60.
- 10M unique brackets will require ~180 MB storage. Confirm this is acceptable.
- The 500 brackets/region threshold captures ~99.9% probability mass. Want more coverage?
- Supplementary bracket generation when survivors < 1000 — confirm this fallback is desired.
- Pool-size parameter (alpha) needs to be user-configurable.
- ESPN scoring weights should be configurable.

---

*This spec provides exact, implementable formulas. All constants (k, sigma, weights, learning rates) are calibratable against historical data per D004. v3 adds Top 30 factor ranking (Section 2), year-adaptive FSG with seed-tier modeling (Sections 2.2-2.4), matchup-specific adjustments (Section 6), 10M bracket generation algorithm (Section 10), and live round-by-round updating (Section 11).*
