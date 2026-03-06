# Math Agent Review: Genetic Algorithm & Evolutionary Proposals

**Author:** Math Agent (Mathematical Optimization Agent)
**Date:** 2026-03-06
**Status:** Critical Review of Biology Agent Proposals

---

## Executive Summary

The Biology Agent proposes three strategic additions: (1) Division-First Optimization via an Island Model GA, (2) a Genetic Algorithm layered on top of our 3M stratified importance sampling (IS) brackets, and (3) AlphaFold-inspired attention mechanisms. After rigorous mathematical analysis, my verdict is mixed. The GA approach has genuine potential but introduces serious risks to the variance reduction properties we carefully built into the IS framework. Several of the proposals are mathematically sound in isolation but become problematic when composed together. This review details exactly where the math works and where it breaks.

---

## 1. Is Layering GA on Top of Stratified IS Mathematically Sound?

### Short Answer: Not automatically. It requires careful design or the IS properties are destroyed.

### The Core Tension

Stratified importance sampling works because every sample carries a **weight** w_i = P_true(bracket_i) / Q(bracket_i), where Q is our proposal distribution (the stratified sampler). The unbiased estimator for any quantity of interest (e.g., "probability team X wins the tournament") is:

```
E[f] = (1/N) * sum_i [ f(bracket_i) * w_i ]
```

This estimator is **unbiased** regardless of Q, as long as Q has support everywhere P_true does. The variance reduction comes from choosing Q to oversample important regions.

**The problem:** A GA applies selection, crossover, and mutation. These operators transform the population in ways that have no clear relationship to the importance weights.

### What Selection Does to IS Weights

When we apply tournament selection or roulette wheel selection, we are **resampling** the population according to fitness. This is mathematically equivalent to applying a second round of importance weighting:

```
w_i_new = w_i_old * (1 / selection_probability_i)
```

But selection probability in a GA depends on the fitness function, which is a design choice — not a probabilistic quantity derived from the target distribution. The result is that **post-selection, the importance weights no longer correspond to a valid importance sampling estimator** unless the fitness function is specifically chosen to be proportional to P_true(bracket) / Q(bracket).

### What Crossover Does

Crossover creates **new brackets that were never sampled from Q**. These offspring have no valid importance weight. You cannot assign them w = P_true / Q because they were not drawn from Q — they were constructed by a deterministic/stochastic recombination operator.

This is the most fundamental mathematical problem with the proposal. After one generation of crossover, you no longer have an importance sampling population. You have a heuristically constructed population with no formal statistical guarantees.

### What Mutation Does

Mutation is slightly less destructive. A single-gene flip on bracket b_i produces bracket b_i'. In principle, you could compute w_i' = P_true(b_i') / Q(b_i'), but Q(b_i') is the probability that the original IS sampler would have generated b_i', which is non-trivial to compute for stratified samplers. It is possible but expensive.

### Verdict on IS + GA Composition

**The GA destroys the unbiased estimation property of IS.** After even one generation of selection + crossover, the population no longer constitutes a valid importance sampling estimator. You can still use the brackets as point predictions, but you lose:

- Unbiased probability estimates for team advancement
- Valid confidence intervals
- The variance reduction guarantees of stratified IS

### Recommended Fix: Two-Population Architecture

Maintain **two separate populations**:

1. **IS Population (untouched):** The original 3M stratified IS brackets per region, preserved exactly as sampled, with their importance weights intact. Use these for all probability estimation, survival curves, and statistical inference.

2. **GA Population (evolved):** A separate population initialized from the IS brackets but evolved via GA. Use these for generating high-fitness "best bracket" candidates. These brackets are heuristic predictions — they carry no valid importance weights.

This cleanly separates the statistical inference engine (IS) from the optimization engine (GA). The GA can freely explore without corrupting the IS estimator.

---

## 2. How Do Importance Weights Interact with GA Fitness?

### The Proposed Fitness Function

The Biology Agent proposes:
```
fitness = P(bracket | power index model) weighted by stratum importance weight
```

This conflates two different things:

- **P(bracket | model):** The probability of the bracket under our generative model. This is well-defined: it is the product of individual game probabilities along the bracket path.
- **Importance weight:** w_i = P_true(b_i) / Q(b_i). This corrects for the non-uniform sampling of Q. It is a **statistical correction factor**, not a quality measure.

Using the importance weight as part of fitness is mathematically confused. A bracket with a large importance weight is one that was **undersampled** by Q relative to its true probability — it does not mean the bracket is "better." Conversely, a bracket in a heavily oversampled stratum will have a low weight, even if it is a highly probable bracket.

### Correct Fitness Function

If the goal is to find the single most probable bracket, fitness should simply be:

```
fitness(b) = P(b | model) = product over all games g in b of P(outcome_g)
```

If the goal is to find brackets that maximize expected score in a bracket pool (which weights later rounds more heavily), fitness should be:

```
fitness(b) = sum over rounds r of [ round_weight(r) * expected_correct_games_in_round_r(b) ]
```

The importance weight should not appear in the fitness function at all. It belongs exclusively in the IS estimator.

---

## 3. Is the Division-First / Island Model Mathematically Justified?

### Short Answer: Yes, with a significant caveat.

### Independence Between Regions

The Island Model treats each region as an independent optimization problem. This is mathematically justified **if and only if** regional outcomes are statistically independent. In the standard March Madness bracket model, this is approximately true:

- Each region's games are determined by the teams in that region and their matchups.
- There is no direct causal mechanism by which a game in the South region affects a game in the East region (before the Final Four).
- Our generative model (logistic win probability) treats games as conditionally independent given power ratings.

**However**, the Biology Agent's own "co-upset matrix" proposal contradicts this independence assumption. If there are correlated upsets across regions (e.g., "chaos years" where upsets cluster everywhere), then the Island Model loses information by treating regions independently.

### The Math of Independence

If regions are independent:
```
P(full bracket) = P(South) * P(East) * P(West) * P(Midwest)
```

Then optimizing each region separately and assembling the best regional sub-brackets is **provably optimal** — the Cartesian product of regional optima is the global optimum.

If regions are correlated:
```
P(full bracket) != P(South) * P(East) * P(West) * P(Midwest)
```

Then independent optimization can miss joint configurations that are collectively more probable than the product of marginal optima.

### Practical Assessment

The correlation between regions is likely weak. Historical data shows that "upset years" do exist, but the signal is noisy. For our purposes, the **computational advantage** of the Island Model (reducing search space from 2^63 to 4 x 2^15) far outweighs the small information loss from ignoring cross-regional correlations.

**Recommendation:** Use the Island Model for the GA population, but keep the full-bracket IS population for any analyses that require cross-regional joint probabilities. If the co-upset matrix analysis (proposed by Biology Agent) reveals strong cross-regional correlations, consider a light migration mechanism between islands — but keep it minimal.

### Search Space Reduction

The search space reduction is dramatic and mathematically justified:
- Full bracket: 2^63 = 9.2 x 10^18
- Per region: 2^15 = 32,768
- Four regions independently: 4 x 32,768 = 131,072 evaluations to exhaustively search

At the regional level, the search space is small enough that a GA is actually overkill — you could **enumerate all 32,768 possible regional brackets** and evaluate each one directly. This is a key insight the Biology Agent may have missed. A GA is a heuristic search method designed for spaces too large to enumerate. At 2^15, enumeration is trivial.

**Critical recommendation:** For regional optimization, skip the GA entirely and use exhaustive enumeration. Reserve the GA (if used at all) for the full 63-game bracket optimization, or for the post-assembly Final Four optimization where you are combining 4 regional winners.

---

## 4. Optimal Population Management Strategy

### The Proposed Pipeline: 3M initial -> ??? survivors per generation

The Biology Agent proposes starting with 3M brackets per region but does not specify a rigorous culling strategy. Here is the mathematical analysis:

### Population Sizing Theory

For combinatorial optimization GAs, the population size should be large enough to maintain diversity across the solution space but small enough for selection pressure to drive convergence. The Schema Theorem (Holland, 1975) suggests:

```
N_min >= 2^k / (epsilon * delta)
```

where k is the schema order (number of fixed positions), epsilon is the allowable error, and delta is the confidence parameter. For our 15-bit regional problem, this gives extremely small minimum populations (order of hundreds).

### Recommended Strategy

Given that the regional search space is only 2^15 = 32,768:

- **Do not use a GA for regional optimization.** Enumerate all 32,768 brackets, compute fitness for each, rank them. Done in milliseconds.
- **For full 63-game bracket optimization** (if pursued): Start with 3M, apply selection to retain ~100K-300K per generation, run 20-50 generations. The 3M initial population provides excellent coverage of the schema space.

### If a GA Is Used Despite the Above

| Parameter | Recommended Value | Rationale |
|-----------|------------------|-----------|
| Initial population | 3,000,000 | Given from IS sampler |
| Survivors per generation | 100,000 - 300,000 | ~3-10% survival rate; maintains diversity while applying selection pressure |
| Elite preservation | 1,000 - 5,000 | Top 0.03-0.17%; prevents loss of best solutions |
| Generations | 20-50 | Diminishing returns beyond ~30 for this problem size |
| Convergence criterion | Hamming distance of top 1000 brackets < 2 bits on average | Population has functionally converged |

### Population Decline Schedule

A common approach is geometric decline:
```
N_g = max(N_min, N_0 * decay_rate^g)
```

With N_0 = 3M, decay_rate = 0.7, N_min = 100K:
- Gen 0: 3,000,000
- Gen 1: 2,100,000
- Gen 2: 1,470,000
- Gen 3: 1,029,000
- Gen 5: 504,210
- Gen 10: 84,884 -> clamped to 100,000

This is aggressive. A gentler schedule (decay_rate = 0.85) keeps more diversity longer:
- Gen 5: 1,328,602
- Gen 10: 590,490
- Gen 15: 262,440
- Gen 20: 116,602 -> clamped to 100,000

---

## 5. Adaptive Mutation Rate Formula Analysis

### The Proposed Formula

```
mutation_rate_day2 = base_rate * (observed_upsets_day1 / expected_upsets_day1)
```

### Mathematical Assessment

This formula is a simple **scaling rule** based on observed vs. expected upset frequency. Let me evaluate its properties:

**Desirable Properties:**
- If Day 1 matches expectations (observed = expected), the rate stays at base_rate. Good.
- If Day 1 is more chaotic, rate increases. Intuitively sensible.
- If Day 1 is chalky, rate decreases. Also sensible.
- The formula is easy to compute and interpret.

**Mathematical Problems:**

1. **Unbounded above.** If expected_upsets = 4 and observed_upsets = 12, the multiplier is 3x. If observed = 16 (every game is an upset), the multiplier is 4x. A mutation rate of 0.25 * 4 = 1.0 means every gene flips, which is effectively random search. The formula needs a **cap**.

   Fix: `mutation_rate_day2 = base_rate * min(cap, observed / expected)` where cap = 2.0 or 2.5.

2. **Unbounded below.** If Day 1 has zero upsets (all chalk), mutation_rate = 0. Zero mutation means the population is frozen and can never explore new brackets. This is catastrophic for a GA.

   Fix: `mutation_rate_day2 = max(floor, base_rate * observed / expected)` where floor = 0.05 or base_rate * 0.25.

3. **Small sample problem.** Day 1 of the tournament has 16 games per day (first round is split across Thursday/Friday). With expected upsets around 4 per day, the variance in the ratio observed/expected is substantial. The standard deviation of the ratio is approximately:

   ```
   SD(observed/expected) = sqrt(p*(1-p)/n) / p
   ```

   For p = 0.25, n = 16: SD = sqrt(0.25*0.75/16) / 0.25 = 0.108 / 0.25 = 0.43

   So the multiplier has a standard deviation of ~0.43 around 1.0. A single-day observation is noisy.

   Fix: Use a **Bayesian shrinkage estimator** instead of the raw ratio:
   ```
   multiplier = (observed_upsets + prior_strength * expected_upsets) / ((1 + prior_strength) * expected_upsets)
   ```
   With prior_strength = 1, this shrinks the observed ratio halfway toward 1.0, reducing noise.

4. **No round-specificity.** The formula uses aggregate upsets across all matchup types. But a 12-5 upset and a 16-1 upset carry very different information. A more principled approach would compute the multiplier per seed-matchup type, though sample sizes become even smaller.

### Improved Formula

```
chaos_ratio = observed_upsets / expected_upsets
shrunk_ratio = (chaos_ratio + prior_weight) / (1 + prior_weight)    # prior_weight = 1.0
clamped_ratio = clamp(shrunk_ratio, 0.25, 2.5)
mutation_rate_day2 = base_rate * clamped_ratio
```

This addresses all four problems above.

### Does "Chaos Momentum" Exist?

The claim that "upset-heavy tournaments tend to stay upset-heavy" is an empirical assertion that requires validation. Looking at this from a mathematical perspective:

- If upsets are driven by **systemic factors** (e.g., the committee underseeded several teams, or a particular conference is underrated), then chaos momentum is real because those factors persist across days.
- If upsets are driven by **random variance** (hot shooting, referee calls), then Day 1 upsets are uninformative about Day 2.
- The truth is likely a mixture. The Stats Agent should provide a serial correlation estimate from historical data. My prior is that the correlation is positive but weak (r ~ 0.1-0.3).

---

## 6. Alternative Evolutionary Computation Approaches

### CMA-ES (Covariance Matrix Adaptation Evolution Strategy)

**Applicability:** Poor. CMA-ES is designed for continuous optimization in R^n. Our bracket space is discrete (binary strings). CMA-ES would require relaxing the binary constraint to continuous [0,1] probabilities and then rounding, which loses information and introduces discretization artifacts. Not recommended.

### Differential Evolution (DE)

**Applicability:** Poor for the same reason — DE operates on continuous vectors. Discrete variants exist (e.g., discrete DE with XOR-based mutation) but are non-standard and less well-studied.

### Estimation of Distribution Algorithms (EDAs)

**Applicability:** Excellent. EDAs (e.g., PBIL, UMDA, BOA) replace crossover/mutation with explicit probability model updates. Instead of evolving brackets directly, you evolve a **probability vector** over the 15 (or 63) game outcomes.

For our problem:
- Maintain a probability vector p = (p_1, ..., p_15) where p_i = P(upset in game i).
- Each generation: sample N brackets from the probability vector, evaluate fitness, update probabilities toward the fittest brackets.
- This naturally maintains a generative model, which is conceptually aligned with our IS framework.

**Advantages over GA:**
- No crossover operator needed (eliminates the weight-invalidation problem).
- The probability vector is interpretable — it tells you the model's belief about each game.
- Can be initialized from our IS proposal distribution Q, maintaining continuity.
- Converges smoothly without the discrete jumps of crossover.

**Recommendation: If evolutionary optimization is desired, use an EDA (specifically PBIL or CGA) instead of a traditional GA.** It is more mathematically principled for this problem.

### Simulated Annealing

**Applicability:** Good for single-bracket optimization. Start from the most probable bracket, flip games probabilistically, accept worse solutions with decreasing probability. Simple, well-understood, good for finding high-quality single brackets. Does not maintain a population, so less useful for coverage/diversity goals.

### Particle Swarm Optimization (PSO)

**Applicability:** Moderate. Binary PSO exists and could work on the bracket space. However, it offers no clear advantage over an EDA or even exhaustive search (at the regional level).

---

## 7. AlphaFold-Inspired Attention: Mathematical Assessment

### Co-Upset Matrix

The proposal to build a co-upset matrix from historical data is mathematically sound in principle. This is essentially computing a **pairwise correlation matrix** C where:

```
C_{ij} = corr(upset_i, upset_j)
```

over historical tournaments. The matrix captures whether certain upsets tend to co-occur.

**Concerns:**
- **Sample size.** We have ~40 years of tournament data = ~40 observations per cell. For a 15x15 matrix (regional) or 63x63 matrix (full bracket), this is severely underpowered. With 63 games, the correlation matrix has 63*62/2 = 1,953 off-diagonal entries estimated from ~40 tournaments. Many correlations will be noise.
- **Multiple testing.** With ~2,000 correlations and 40 observations, random chance will produce many apparently significant correlations. Correction (Bonferroni, FDR) will wipe out most signals.
- **Non-stationarity.** The tournament format, seeding algorithms, and team compositions change over 40 years. Correlations from the 1990s may not apply in 2026.

**Verdict:** The co-upset matrix is a reasonable exploratory analysis but should not be treated as a reliable signal unless specific correlations are validated with out-of-sample testing. Use it as a soft prior, not a hard constraint.

### Attention Mechanism Over Games

Modeling pairwise game interactions with attention weights is conceptually appealing but practically questionable for our use case:

- The main pairwise interaction in brackets is **structural**: the winner of game A plays the winner of game B. This is already captured by the bracket tree structure.
- "Fatigue" and "momentum" effects are speculative and hard to quantify from limited data.
- A full attention mechanism over 63 games is a machine learning model that needs to be trained. With ~40 historical tournaments, we do not have nearly enough data to train an attention model without severe overfitting.

**Verdict:** The attention mechanism is overengineered for our data regime. The bracket tree structure already encodes game dependencies. Additional pairwise interactions (if they exist) are better captured by simple adjustments to the logistic model (e.g., fatigue discount for back-to-back games) than by a learned attention matrix.

### Iterative Refinement

The analogy between AlphaFold's iterative refinement and GA generations is apt but not novel — this is just the GA itself. Each generation is a refinement pass. The AlphaFold terminology adds no new mathematical content here.

---

## 8. Mathematical Risks and Pitfalls

### Risk 1: Premature Convergence

A GA with strong selection pressure on 3M brackets will rapidly converge to a small neighborhood of the fitness landscape. For bracket prediction, this means converging on "chalk" (all favorites win) because those brackets have the highest individual probability. The GA will systematically eliminate upset-containing brackets, which is exactly wrong for a bracket pool — you need some upsets to differentiate from the field.

**Mitigation:** Multi-objective fitness (probability + uniqueness), niching, or explicit diversity maintenance.

### Risk 2: Losing the IS Estimator

As detailed in Section 1, applying GA operators to IS samples destroys the unbiased estimation property. If we lose the ability to compute valid probability estimates, we lose the ability to:
- Generate survival curves
- Estimate confidence intervals on team advancement
- Perform Bayesian updating when real results arrive

**Mitigation:** Two-population architecture (Section 1).

### Risk 3: Overfitting to Model

The GA fitness function depends on our power index model. If the model is wrong (and all models are wrong), the GA will confidently optimize toward the wrong answer. Naive Monte Carlo, by contrast, samples broadly and includes many "wrong" brackets that may turn out to be right.

**Mitigation:** Use model uncertainty in the fitness function. Penalize extreme confidence. Maintain a "contrarian" sub-population.

### Risk 4: Computational Waste on a Solvable Problem

At the regional level (2^15 = 32,768), the problem is small enough for exhaustive enumeration. Running a GA on this space is like using a neural network to add single-digit numbers — it works, but it is a waste of engineering effort and introduces unnecessary complexity.

**Mitigation:** Enumerate regional brackets exhaustively. Apply the GA (or better, an EDA) only to the full 63-game bracket assembly problem if cross-regional optimization is needed.

### Risk 5: The Adaptive Mutation Formula Is Underpowered

As shown in Section 5, the raw observed/expected ratio has high variance from small sample sizes. Acting aggressively on noisy Day 1 data could make the population worse, not better.

**Mitigation:** Bayesian shrinkage, as recommended in Section 5.

---

## 9. Summary of Recommendations

| Proposal | Math Verdict | Recommendation |
|----------|-------------|----------------|
| GA on top of stratified IS | Destroys IS properties if naively applied | Use two-population architecture: IS for inference, GA for optimization |
| Importance weights in GA fitness | Mathematically incorrect usage | Remove IS weights from fitness; use raw model probability instead |
| Island Model (division-first) | Mathematically sound if regions are independent | Approved, but consider exhaustive enumeration instead of GA at 2^15 |
| 3M -> GA population management | Oversized for the problem | For regions: enumerate all 32,768. For full bracket: 100K-300K with geometric decay |
| Adaptive mutation rate formula | Correct intuition, flawed execution | Add Bayesian shrinkage, floor (0.05), and ceiling (2.5x) |
| AlphaFold attention | Overengineered for available data | Skip the attention mechanism; use simple co-occurrence analysis as a soft prior only |
| Co-upset matrix | Sound but underpowered (n=40) | Exploratory analysis only; do not hard-code into the model |
| Overall evolutionary approach | GA is suboptimal choice | Prefer EDA (PBIL/CGA) over traditional GA for this discrete optimization problem |

---

## 10. Open Questions for Other Agents

### For Stats Agent:
- What is the serial correlation of upset rates between Day 1 and Day 2 of historical tournaments? (Needed to validate "chaos momentum.")
- Provide the co-upset correlation matrix from historical data with significance levels.
- What is the empirical distribution of "total upsets per tournament"? Is it overdispersed relative to binomial?

### For Biology Agent:
- Would you accept EDA (PBIL) as a replacement for traditional GA? It achieves the same evolutionary goals with cleaner mathematical properties.
- The regional search space of 2^15 can be exhaustively enumerated. Does this change your proposed architecture?
- Can you specify the multi-objective Pareto front more precisely? What are the exact objectives and their tradeoff weights?

### For Lead SWE:
- Can we afford to maintain two populations (IS + GA/EDA) in memory simultaneously?
- What is the computational cost of evaluating fitness for all 32,768 regional brackets per region? (Should be trivial — microseconds per bracket.)

---

*This review is intended to be constructively critical. The Biology Agent's proposals show creative thinking about optimization, but several need mathematical corrections before implementation. The core insight — that we should optimize bracket quality, not just sample broadly — is sound. The execution needs refinement.*
