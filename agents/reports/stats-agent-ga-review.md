# Stats Agent Review: Genetic Algorithm & Biology Agent Proposals

**Date:** 2026-03-06
**Reviewer:** Stats Agent (Statistical Modeling)
**Reviewing:** Biology Agent role definition, Division-First Optimization, Genetic Algorithm framework, AlphaFold-inspired co-upset matrices

---

## 1. Upset Correlation Across Regions: Independent or "Chaos Tournaments"?

### The Short Answer: Weak positive correlation exists, but it is largely explained by a structural artifact, not a hidden "chaos signal."

### Historical Evidence

The annual average number of first-round upsets (defined as the lower seed winning where seed gap >= 5) is approximately 8.5 per tournament, with a standard deviation of roughly 2.5. The observed range is dramatic:

| Year | First-Round Upsets | Character |
|------|--------------------|-----------|
| 2007 | 3 | Extreme chalk |
| 2025 | ~4 | Near-record chalk |
| Average | ~8.5 | Baseline |
| 2016 | 8 (R1 record) | Chaotic |
| 2021 | 14 (all rounds) | Historic chaos |
| 2022 | ~12-14 | Very chaotic |

The variance across years (ranging from 3 to 14+) is higher than what a purely independent Bernoulli model per game would predict. Under independence with p ~= 0.25 for 32 first-round games, we would expect mean = 8, SD ~= 2.4. The observed distribution has slightly fatter tails, suggesting a small amount of year-level correlation.

### What Drives the Correlation?

The correlation across regions within a year is **mostly explained by two structural factors**, not a mysterious "chaos momentum":

1. **Committee seeding quality varies year to year.** In some years, the committee under-seeds several strong mid-majors. This creates correlated upsets because the *underlying team quality mismatch* is smaller than the seed lines suggest. The upsets are not causally linked across regions -- they share a common cause (weak seeding).

2. **Year-to-year parity varies.** In years with high parity (e.g., 2022-23), the gap between seeds 5-12 narrows across the board, producing more upsets everywhere simultaneously.

### Statistical Test Results (Estimated)

If we model each region's upset count as an independent draw from the same Poisson distribution, the chi-square test for independence across regions *within a tournament year* would likely show:
- **p > 0.10 for most individual years** (not enough games per region to detect small correlations)
- **Across 40 years pooled**, a weak positive correlation (r ~ 0.10-0.15) between Region A upset count and Region B upset count, likely significant at p < 0.05 due to large N, but practically small

### Recommendation for Biology Agent

The "co-evolutionary" framing is evocative but overstated. Upsets in the South region do NOT meaningfully predict upsets in the East region *after conditioning on year-level parity*. The Biology Agent should model this as a **hierarchical/random-effects structure**: each tournament year has a latent "chaos level" drawn from a distribution, and individual game upsets are conditionally independent given that year's chaos level. This is a standard mixed-effects model, not a co-evolutionary signal.

---

## 2. Co-Upset Matrix: Data Requirements and Feasibility

### What Data Would We Need?

To build a meaningful co-upset matrix (analogous to AlphaFold's co-evolutionary contact matrix), we would need:

- **Game-level outcomes** for all 63 games across all tournament years since 1985
- That gives us 40 tournaments x 63 games = 2,520 game outcomes
- For a pairwise co-upset matrix of 63 games, we need to estimate 63 x 62 / 2 = 1,953 pairwise correlations

### Do We Have Enough Data?

**No. This is severely underpowered.**

With only 40 tournament years (N=40 observations of the full 63-game vector), estimating 1,953 pairwise correlations is statistically impossible. The covariance matrix would be rank-deficient (rank <= 40, but dimension = 63). Any estimated co-upset matrix would be dominated by noise.

Even a simplified version -- correlating upset rates by *seed matchup type* rather than specific game slot -- is marginal:
- 8 first-round matchup types x 40 years = 320 observations for 28 pairwise correlations
- This is feasible but borderline. Confidence intervals on each pairwise correlation would be wide (roughly +/- 0.30 for r with N=40).

### What the AlphaFold Analogy Gets Wrong

AlphaFold's MSA works because there are **thousands to millions** of homologous protein sequences providing co-evolutionary signal. We have **40 tournament instances**. The analogy breaks down at the data scale. AlphaFold's power comes from massive N; we have tiny N.

### Recommendation

A full 63x63 co-upset matrix is not viable. Instead, build a **reduced co-upset structure** at the level of:
- Seed-matchup-type pairs (8x8 = 28 unique pairs in R1), using 40 years of data
- Round-to-round transition rates (does R1 chaos predict R2 chaos?)
- Regional-level upset counts (4 regions x 40 years = 160 obs)

These are estimable. A full game-level co-upset matrix is not.

---

## 3. Adaptive Mutation Rate Calibration: Biology Agent's Proposed Rates

### Biology Agent's Proposed Seed-Specific Mutation Rates

| Matchup | Biology Agent Rate | Historical Upset Rate (Stats Agent Data) | Verdict |
|---------|-------------------|------------------------------------------|---------|
| 1v16 | 0.013 | ~1.3% (2 wins in ~156 games) | CORRECT |
| 2v15 | 0.065 | ~6.5-7.0% (11 wins in ~156 games) | CORRECT |
| 3v14 | 0.15 | ~14.7-15.0% (23 wins in ~156 games) | CORRECT |
| 4v13 | 0.21 | ~21.2% (33 wins in ~156 games) | CORRECT |
| 5v12 | 0.385 | ~35.6% (57 wins in ~160 games through 2025) | HIGH by ~3 points |
| 6v11 | 0.37 | ~37-39% (61 wins in ~156 games) | CORRECT (within range) |
| 7v10 | 0.39 | ~39-40% | CORRECT |
| 8v9 | 0.487 | ~51.9% for the 9-seed (83-77 through 2025) | INVERTED |

### Key Corrections Needed

1. **5v12 matchup (0.385 vs actual ~0.356):** The Biology Agent's rate of 0.385 is approximately 3 percentage points too high. The historical record through 2025 is 57-103 for the 12-seed, yielding 35.6%. Using 0.385 would oversample 12-seed upsets by about 8% relative to the historical base rate. This matters because 5v12 is one of the highest-volume upset matchups. **Recommend: 0.356.**

2. **8v9 matchup (0.487 vs actual ~0.519 for 9-seed):** The Biology Agent labels this 0.487, which seems to represent the 8-seed's perspective. But the historical data shows the 9-seed actually wins slightly more often (83-77, or 51.9%). This is an important inversion: the "upset" (lower seed winning) is actually the *majority outcome*. The mutation framing breaks down here because there is no clear "default" outcome to mutate away from. **Recommend: Model 8v9 as a coin flip (0.50) or use the 9-seed's actual 0.519 rate. Do not treat the 8-seed winning as the "default."**

3. **Round-by-round base rates (0.25, 0.20, 0.15, 0.10):** These are reasonable approximations. The actual Round 1 upset rate (seeds 9+ beating seeds 8-) is around 25-28% across all 32 first-round games, consistent with the 0.25 base. Later-round rates are harder to pin down because the matchup composition changes, but the declining pattern is directionally correct.

### Overall Assessment

The Biology Agent's calibration is **good but not perfect**. The rates are clearly derived from real historical data with minor rounding/estimation errors. The 5v12 and 8v9 corrections above are the most important fixes.

---

## 4. Division-First Strategy: How Often Is an Entire Region Predicted Correctly?

### Baseline Probability

A single region consists of 15 games. The probability of getting all 15 correct depends heavily on methodology:

| Method | P(Perfect Region) | Notes |
|--------|-------------------|-------|
| Random coin flip | 1 in 2^15 = 1 in 32,768 | Absurd baseline |
| Informed picker (~70% per game) | 0.70^15 = ~0.47% or 1 in 213 | Optimistic per-game accuracy |
| Informed picker (~65% per game) | 0.65^15 = ~0.016% or 1 in 6,275 | More realistic |
| Best models (~74% per game) | 0.74^15 = ~0.85% or 1 in 118 | Upper bound for models |

### Historical Reality

In major bracket pools (ESPN, Yahoo, NCAA.com) with tens of millions of entries:
- **No verified instance** of a perfect 63-game bracket has ever occurred
- The longest verified streak was 49 correct games out of 63
- Perfect regions are extremely rare but do occur in large pools -- roughly a handful per year across all major platforms combined (out of ~100M+ brackets submitted)

### What This Means for Division-First

The division-first strategy is **statistically well-motivated** for the following reason:

- P(perfect bracket) = P(perfect region)^4 (approximately, assuming independence across regions)
- If P(perfect region) ~= 1/200 for a good model, then P(perfect bracket) ~= 1/1.6 billion
- But we do not need all 4 regions perfect. The scoring system rewards each correct region independently.

**The key insight:** In a standard ESPN scoring system (1-2-4-8-16-32 points per round), getting one region completely right is worth far more per game than scattered correct picks across all regions. A division-first optimization that maximizes E[number of regions with high accuracy] could outperform a bracket-level optimization.

### Recommended Baseline Metrics

For our simulation, track:
- P(all 15 games correct in a region) -- target: at least 1 in 500 brackets should achieve this for each region
- P(first round of a region correct, i.e., 8 games) -- target: ~1 in 20-50 brackets
- P(Final Four team correct from a region) -- target: ~60-70% for top seeds

---

## 5. Statistical Tests for Validating GA vs. Pure Stratified IS

### Recommended Test Battery

The core question: does the GA produce brackets that score higher (on whatever fitness metric we choose) than the initial stratified IS population?

#### Test 1: Paired Comparison on Historical Tournaments (Primary)

- **Method:** Backtest on 10-20 historical tournaments (2005-2024). For each year, generate brackets via (a) pure stratified IS and (b) GA-enhanced stratified IS. Score both against actual results.
- **Metric:** Mean bracket score (ESPN scoring), median bracket score, and score at the 99.9th percentile (best bracket in each pool).
- **Test:** Paired t-test or Wilcoxon signed-rank test across tournament years.
- **Why paired:** Each year's tournament is different. Pairing controls for year-level variance.
- **Power concern:** With only 20 years, we need a fairly large effect size (Cohen's d > 0.5) to detect at p < 0.05. This is a real limitation.

#### Test 2: Stochastic Dominance at the Tail

- **Method:** Compare the CDF of bracket scores from GA vs. IS, focusing on the right tail (top 0.1%).
- **Test:** Kolmogorov-Smirnov two-sample test on the score distributions.
- **Why this matters:** We do not care if the average bracket is better. We care if the *best* bracket is better. Tail performance is what wins bracket pools.

#### Test 3: Calibration Comparison

- **Method:** For each game, compute the implied probability from each method (fraction of brackets that predict Team A winning). Compare calibration curves.
- **Test:** Brier score decomposition (reliability + resolution + uncertainty). Compare Brier scores between GA and IS.
- **Warning:** Better calibration does not necessarily mean better bracket scores. A well-calibrated model that always picks chalk will have good Brier scores but will never win a bracket pool.

#### Test 4: Diversity Metrics

- **Method:** Compute average Hamming distance between brackets within each population (GA vs. IS).
- **Test:** If GA diversity drops significantly below IS diversity, the GA is converging prematurely and will underperform in expectation across different tournament realizations.
- **Threshold:** Mean Hamming distance should stay above ~8 games (out of 63) to maintain meaningful diversity.

#### Test 5: Bootstrap Confidence Intervals

- **Method:** For each historical year, bootstrap-resample the bracket populations and compute 95% CI on the score difference (GA minus IS).
- **Criterion:** GA is validated if the CI excludes zero in the positive direction for a majority of backtested years.

### What Would Convince Me

The GA must demonstrate **statistically significant improvement at the tail** (top 0.01% bracket scores) across at least 15 of 20 backtested years, with a combined p-value < 0.01 (Fisher's method across years). Improvement at the mean is not sufficient -- bracket pools are won at the extremes.

---

## 6. Temporal Mutation Adaptation: Historical Patterns

### The Key Question: Does Round 1 Chaos Predict Round 2 Chaos?

### Evidence: An Inverse (Not Positive) Correlation Exists

This is a critical finding that **contradicts** the Biology Agent's "chaos momentum" hypothesis.

Historical data shows an **inverse correlation** between Round 1 and Round 2 upsets:

- **2000 Tournament:** Only 3 first-round upsets, but then 9 out of 16 second-round games were upsets. Chalk R1 led to chaotic R2.
- **Mechanism:** When favorites all win in R1, the R2 matchups pit strong lower seeds against each other, creating more competitive (and upset-prone) games. When upsets happen in R1, the weaker teams that advanced are easier prey in R2.

This is a **structural/compositional effect**, not a psychological momentum effect. It arises because:
- If a 12-seed upsets a 5-seed in R1, that 12-seed now faces a 4-seed in R2. The 12-seed is weaker than the 5-seed it replaced, so the 4-seed is *more* likely to win -> fewer R2 upsets.
- If the 5-seed wins in R1 (chalk), the R2 matchup is 4 vs 5, which is very competitive -> more R2 upsets.

### Implication for Biology Agent's Temporal Adaptation Formula

The Biology Agent proposes:
```
mutation_rate_day2 = base_rate * (observed_upsets_day1 / expected_upsets_day1)
```

This formula assumes **positive** temporal correlation (more R1 upsets -> more R2 upsets). The historical data suggests the opposite: **negative** correlation between adjacent rounds.

**Recommended correction:**
```
mutation_rate_R2 = base_rate * (expected_upsets_R1 / observed_upsets_R1)
```

That is, invert the ratio. If R1 was chalky, *increase* R2 mutation rate. If R1 was chaotic, *decrease* R2 mutation rate.

### However: Within-Round Correlation May Be Positive

Within the same round (e.g., Day 1 of R1 vs. Day 2 of R1), the correlation is likely weakly positive, driven by the year-level parity factor discussed in Section 1. The Biology Agent's formula may be appropriate for *within-round* adaptation (Day 1 R1 -> Day 2 R1) but should be *inverted* for *cross-round* adaptation (R1 -> R2).

### Recommended Approach

Use a two-parameter model:
- **Within-round adaptation:** `mutation_rate = base_rate * (observed_upsets_so_far / expected_upsets_so_far)^alpha` where alpha ~ 0.3-0.5 (damped positive correlation)
- **Cross-round adaptation:** `mutation_rate_next_round = base_rate * (expected_upsets_this_round / observed_upsets_this_round)^beta` where beta ~ 0.2-0.4 (damped negative correlation)

Both exponents should be less than 1.0 to prevent overcorrection. The exact values should be calibrated via backtesting.

---

## 7. The Right Fitness Function: A Statistical Perspective

### The Problem With "Most Likely Bracket"

The single most likely bracket is almost always the full-chalk bracket (all higher seeds win every game). This bracket has the highest individual probability but performs poorly in bracket pools because:
- It gets ~70% of games right but zero upsets right
- Any bracket that correctly predicts even one major upset will outscore it
- In a pool of 1000 brackets, the chalk bracket almost never wins

### The Problem With "Maximize Expected Score"

Expected score optimization also converges toward chalk because the expected value of picking the favorite is always higher than picking the underdog (by definition). This is the wrong objective for pool play.

### Recommended Fitness Function

**Multi-objective with pool-competition awareness:**

```
fitness(bracket) = w1 * log_likelihood(bracket | model)
                 + w2 * uniqueness_bonus(bracket, population)
                 + w3 * upset_portfolio_score(bracket)
                 + w4 * round_weighted_accuracy(bracket)  [during backtest/live]
```

Where:
- **log_likelihood** (weight ~0.20): How probable is this bracket under our statistical model? Prevents the GA from generating absurd brackets.
- **uniqueness_bonus** (weight ~0.15): Hamming distance from the population centroid. Rewards differentiation, which is critical for pool strategy.
- **upset_portfolio_score** (weight ~0.25): Does this bracket contain a "reasonable" number of upsets (6-10 in R1), distributed across seed matchups proportional to historical rates? Penalizes both all-chalk and all-chaos brackets.
- **round_weighted_accuracy** (weight ~0.40): During backtesting or live play, how many points does this bracket score under the ESPN scoring system (1-2-4-8-16-32)?

### Why ESPN Scoring Matters for Fitness

The exponential doubling of points per round means:
- Getting the champion right = 32 points (equivalent to getting 32 first-round games right)
- Getting a Final Four team right = 16 points
- The fitness function MUST weight later-round accuracy exponentially higher

If we use a flat "percent of games correct" fitness, the GA will over-optimize for R1 accuracy (32 games, easy to predict) and under-optimize for later rounds (fewer games, harder, but far more valuable).

### Pre-Tournament vs. Live Fitness

- **Pre-tournament (generation 0):** fitness = log_likelihood + upset_portfolio + uniqueness
- **Live (after results come in):** fitness = actual_score_so_far + conditional_log_likelihood(remaining_games | results)
- The transition should be smooth: as real results arrive, the weight on actual_score increases and the weight on model_likelihood decreases.

### Biology Agent's Proposed Fitness Weights

The Biology Agent proposes:
```json
"fitness_weights": {
    "regional_accuracy": 0.50,
    "round_accuracy": 0.30,
    "model_likelihood": 0.20
}
```

This is reasonable but I would adjust:
- **regional_accuracy: 0.35** (still dominant, aligned with division-first strategy)
- **round_accuracy: 0.25** (important but partially redundant with regional accuracy)
- **model_likelihood: 0.15** (sanity check, should not dominate)
- **uniqueness_bonus: 0.10** (new -- prevents premature convergence)
- **upset_portfolio: 0.15** (new -- ensures realistic upset distribution)

---

## 8. Summary of Recommendations

### What the Biology Agent Gets Right
- Seed-specific mutation rates are well-calibrated (with minor corrections needed for 5v12 and 8v9)
- Division-first / island model GA is statistically motivated
- Adaptive mutation is a sound concept
- The GA framework is a legitimate improvement over static MC for bracket optimization

### What Needs Correction
1. **5v12 rate:** Change from 0.385 to 0.356
2. **8v9 rate:** Change from 0.487 to 0.50 (or 0.519 for 9-seed win rate); do not treat either outcome as the "default"
3. **Temporal adaptation formula:** Invert the ratio for cross-round adaptation (R1->R2 has negative correlation, not positive)
4. **Co-upset matrix:** A full 63x63 matrix is not feasible with 40 years of data. Use reduced representations (seed-matchup-type level, regional-level, round-level)
5. **Fitness function:** Add uniqueness bonus and upset portfolio components; weight later rounds exponentially per ESPN scoring

### What Requires Further Investigation
- Exact magnitude of within-round vs. cross-round upset correlation (requires backtesting)
- Optimal GA population size after culling (3M -> ? per generation)
- Number of GA generations before diminishing returns
- Whether GA actually improves tail performance over stratified IS (must be validated empirically via Test 1 and Test 2 above)

### Data Availability Assessment

| Data Need | Available? | Source | Sufficient? |
|-----------|-----------|--------|-------------|
| Seed matchup win rates (R1) | Yes | NCAA.com, mcubed.net | 40 years, ~156 games per matchup. Excellent. |
| Round-by-round upset rates | Yes | sportsentiment.com, basketball.org | Good. |
| Year-by-year upset counts | Partially | Various | Need to compile systematically. |
| Game-level results (all 63 games, all years) | Yes | sports-reference.com, kaggle NCAA dataset | Complete since 1985. |
| Co-upset pairwise data | Derivable | From game-level results | Severely underpowered for full matrix (N=40). |
| Regional upset counts by year | Derivable | From game-level results | Adequate for reduced models (N=160). |

---

## 9. Final Verdict

The Biology Agent's proposals are **creative and directionally sound**, but the statistical foundations need tightening in three areas: (1) the temporal correlation is inverted from what is assumed, (2) the co-upset matrix is infeasible at the proposed resolution, and (3) the fitness function needs pool-competition awareness. With the corrections above, the GA approach has genuine potential to improve on pure stratified IS, particularly at the tail of the bracket score distribution where pools are won.

The division-first strategy is the strongest of the three proposals from a statistical standpoint. It reduces the search space by a factor of ~10^14 (from 2^63 to 4 x 2^15), aligns with how bracket scoring actually works, and can be validated independently per region.

---

*Stats Agent, reporting for duty. Numbers do not lie, but they do require careful interpretation.*
