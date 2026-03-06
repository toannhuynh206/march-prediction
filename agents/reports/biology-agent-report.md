# Biology Agent Research Report

**Agent:** Biology Agent (Evolutionary Computation & AlphaFold Analogies)
**Date:** 2026-03-06
**Status:** COMPLETE

---

## Table of Contents

1. [Genetic Algorithms for Combinatorial Optimization](#1-genetic-algorithms-for-combinatorial-optimization)
2. [AlphaFold Analogies: Honest Assessment](#2-alphafold-analogies-honest-assessment)
3. [Evolutionary Strategies for Tournament Prediction](#3-evolutionary-strategies-for-tournament-prediction)
4. [Adaptive Mutation Rate Literature](#4-adaptive-mutation-rate-literature)
5. [Island Model GA Performance](#5-island-model-ga-performance)
6. [Computational Feasibility Analysis](#6-computational-feasibility-analysis)
7. [Concrete Recommendations](#7-concrete-recommendations)
8. [Sources](#8-sources)

---

## 1. Genetic Algorithms for Combinatorial Optimization

### 1.1 Literature Consensus on GA Parameters

The GA literature converges on the following parameter ranges for combinatorial optimization problems:

| Parameter | Typical Range | Recommended for Brackets |
|-----------|--------------|--------------------------|
| Population size | 100-1,000 for standard combinatorial problems | See Section 1.3 below |
| Crossover rate | 0.6-0.9 | 0.70-0.80 |
| Mutation rate | 0.001-0.1 (or 1/N where N = chromosome length) | 1/63 ~ 0.016 as base; see adaptive scheme |
| Elitism | 1-5% of population | 0.3% (10,000 of 3M) |
| Tournament size k | 2-7 | 5 |
| Generations | Problem-dependent; diminishing returns typical after 50-100 | 50 (with early stopping) |

**Key finding:** There is no one-size-fits-all parameter set. The literature strongly recommends adaptive tuning over static parameters (Hassanat et al., 2019). For binary chromosomes specifically, the classic 1/N mutation rate (where N = chromosome length) is a well-established starting point. For our 63-bit brackets, that yields 1/63 ~ 0.016 per bit.

**Important distinction:** The 1/N mutation rate is the per-gene (per-bit) flip probability. This is different from the per-bracket mutation rate in our role definition (0.20), which represents the probability that a bracket undergoes *any* mutation at all. Both are valid framings, but we must be consistent. I recommend: per-bracket mutation probability = 1.0 (always mutate), per-gene flip probability = adaptive (see Section 4).

### 1.2 Crossover Operators for Bracket Problems

For our bracket genome (63-bit string with hierarchical structure), three crossover types are relevant:

- **Regional crossover (recommended primary):** Swap entire 15-bit regional sub-brackets. This respects the separable structure of our problem -- regions are largely independent until the Final Four. Literature on building block preservation supports this: crossover should respect problem decomposition (Whitley et al., 1999).
- **Round crossover:** Swap all Round 1 picks vs later rounds. Less theoretically motivated but could help explore different "chaos levels."
- **Uniform crossover:** Per-gene random inheritance. Standard but does not exploit bracket structure. Use as secondary operator only.

### 1.3 Population Size: The 3M Question

Our situation is unusual: we start with 3M brackets from stratified importance sampling (IS), not a randomly initialized population. Standard GA literature assumes populations of 100-1,000. Our 3M initial population is orders of magnitude larger.

**Recommendation: Two-phase approach.**

- **Phase 1 -- Selection/Culling:** From 3M IS brackets, use fitness-proportional selection to cull down to a working population of 50,000-100,000. This preserves the top brackets while remaining computationally tractable. The IS importance weights serve as initial fitness.
- **Phase 2 -- Evolution:** Run the GA on the 50K-100K working population for 50 generations. This is well within literature norms for combinatorial problems.
- **Rationale:** Running GA operators on 3M individuals per generation is computationally expensive (see Section 6) and unnecessary. The IS sampling already provides excellent coverage; the GA's job is to refine, not to explore from scratch.

**Alternative: Keep 3M but run only 5-10 "light" generations.** Each generation applies mutation only (no crossover) to all 3M brackets, re-evaluates fitness, and culls the bottom 10%. This is closer to a "mutation-selection balance" model from population genetics than a classical GA. Computationally cheaper per generation.

---

## 2. AlphaFold Analogies: Honest Assessment

I will rate each analogy on a **Strength Scale**: Strong (directly transferable), Moderate (conceptually useful, requires adaptation), Weak (inspirational only, do not over-engineer).

### 2.1 Multiple Sequence Alignment (MSA) --> Co-Upset Matrix

**Analogy Strength: MODERATE**

| AlphaFold | Bracket System |
|-----------|---------------|
| Thousands of homologous protein sequences | 40 years of historical tournament brackets |
| Co-evolution: residue i and residue j mutate together because they're spatially close | Co-upsets: upset in game i and upset in game j co-occur because of shared causal factors |
| MSA reveals evolutionary constraints | Historical bracket alignment reveals structural constraints on upsets |

**What transfers well:**
- The idea of building a co-occurrence matrix from historical data is sound. If 12-5 upsets in the South region correlate with 12-5 upsets in the East (perhaps because Selection Committee bias creates underseeded mid-majors in clusters), this is genuinely useful information.
- The "outer product mean" concept -- deriving pairwise game interactions from sequence-level (bracket-level) information -- could inform our fitness function.

**What is a stretch:**
- AlphaFold's MSA works because there are thousands of homologous sequences with genuine evolutionary relationships. We have ~40 tournament years, which is a tiny sample. Statistical power for detecting co-upset correlations is very limited.
- Protein co-evolution is driven by physical proximity constraints. Tournament co-upsets may be largely noise with weak correlations.

**Concrete recommendation:** Build the co-upset matrix from historical data. If correlations are statistically significant (p < 0.05 after Bonferroni correction for ~2000 game pairs), incorporate them as mutation correlation structure. If not significant, do not force this analogy.

### 2.2 Evoformer's Dual-Track Architecture --> Bracket Dual Representation

**Analogy Strength: WEAK**

AlphaFold2's Evoformer has 48 blocks, each maintaining two representations:
- **MSA representation** (sequence-level): updated via row-wise and column-wise gated self-attention
- **Pair representation** (residue-residue): updated via triangular multiplicative updates and triangular self-attention

The two representations communicate: pair representation biases MSA attention, and MSA feeds pair representation via outer product mean. This happens 96 times across 48 blocks.

**Why this is mostly a stretch for brackets:**
- The Evoformer's power comes from modeling geometric constraints (triangle inequality on distances). Brackets have hierarchical constraints (winner of game A plays in game B) but not geometric ones.
- The dual-track architecture is justified by the dual nature of protein structure (sequence + 3D geometry). Brackets do not have a natural second representation that is as rich.
- Implementing a 48-block transformer for 63 games would be massive over-engineering.

**What minimally transfers:**
- The idea of maintaining two views of the bracket -- (1) a flat 63-bit genome and (2) a pairwise "game interaction" matrix -- and letting them inform each other during evolution. But this can be implemented simply as a correlation-aware mutation operator, not a neural architecture.

### 2.3 Iterative Refinement (Recycling) --> GA Generations

**Analogy Strength: STRONG**

AlphaFold2 performs 3 recycling passes during inference, feeding predictions back into the network to refine the structure. This maps directly to the GA generational loop.

| AlphaFold | GA for Brackets |
|-----------|----------------|
| Recycling pass 1: rough fold | Generation 0: IS-sampled brackets (diverse but unrefined) |
| Recycling pass 2: corrected secondary structure | Generation 10-20: selection has removed worst brackets, crossover has combined good regions |
| Recycling pass 3: final refinement | Generation 40-50: convergence on high-fitness brackets |

**What transfers well:**
- The principle that iterative refinement with feedback improves quality is universal and well-validated.
- AlphaFold's approach of feeding outputs back as inputs maps to using current-generation fitness information to guide next-generation mutation rates and selection pressure.
- The idea of starting rough and progressively refining is exactly what GA does.

**Concrete recommendation:** This analogy validates the GA approach but does not add new algorithmic ideas. It is more of a "yes, iterative refinement works in biology too" confirmation.

### 2.4 Confidence (pLDDT) --> Game Confidence Scores

**Analogy Strength: MODERATE**

AlphaFold produces per-residue confidence scores (pLDDT, 0-100) indicating how certain the model is about each residue's position. High-confidence residues are "locked in" while low-confidence ones may need more refinement.

**What transfers well:**
- Each of our 63 games has a natural confidence score: the win probability from the power index model. A 1v16 game has ~99% confidence; an 8v9 game has ~51% confidence.
- **Confidence-weighted mutation:** Only mutate low-confidence games (those near 50/50). High-confidence games should have very low mutation rates. This is genuinely useful and well-motivated by both the AlphaFold analogy and standard GA practice.
- This maps directly to the seed-specific mutation rates in our role definition.

**Concrete recommendation:** Implement per-gene mutation rate as `mutation_prob(game_i) = f(1 - |2*p_i - 1|)` where `p_i` is the win probability for game i. Games near 50/50 get high mutation; games near 0% or 100% get very low mutation. This is the single most valuable AlphaFold-inspired idea.

### 2.5 Summary: AlphaFold Analogy Scorecard

| Analogy | Strength | Implement? | Engineering Cost |
|---------|----------|------------|-----------------|
| MSA --> Co-upset matrix | Moderate | Yes, if data supports it | Low (correlation matrix) |
| Evoformer dual-track --> Dual bracket representation | Weak | No | High (over-engineering) |
| Iterative refinement --> GA generations | Strong | Yes (it IS the GA) | Zero (inherent) |
| pLDDT --> Confidence-weighted mutation | Moderate | Yes | Low (per-gene mutation rates) |
| Triangle updates --> Game dependency structure | Weak | No | High (no clear geometric analog) |

---

## 3. Evolutionary Strategies for Tournament Prediction

### 3.1 Published Work

**Finding: There is very little published work applying genetic algorithms specifically to March Madness bracket prediction.** The literature search turned up:

- **Machine learning dominates:** Kaggle's "March Machine Learning Mania" competitions (running since 2014) are overwhelmingly dominated by gradient boosting (XGBoost, LightGBM), logistic regression, and neural networks. No top entries appear to use GAs.
- **GA for sports prediction generally:** Tsakonas & Dounias (2002) used genetic programming for football (soccer) predictions. Bunker & Thabtah (2019) surveyed ML in sport and found GAs used primarily for feature selection, not direct prediction.
- **GA for tournament brackets specifically:** No published papers found. This is a genuine gap in the literature.
- **Efficient tournament probability computation:** Brandes, Marmulla & Smokovic (2025) showed exact computation of tournament winning probabilities can be done two orders of magnitude faster than simulation by exploiting bracket structure -- relevant to our fitness evaluation.

**Implication:** We are in novel territory. This is both a risk (no proven approach to follow) and an opportunity (potential for genuine innovation). The lack of GA work on brackets likely reflects that (a) ML practitioners default to supervised learning, and (b) the bracket prediction community focuses on per-game probabilities rather than full-bracket optimization.

### 3.2 Why GAs Might Work Here

Despite the lack of precedent, the bracket problem has properties that suit GAs well:

1. **Binary genome:** Brackets are naturally 63-bit strings. GAs were designed for binary optimization.
2. **Separable sub-problems:** Regions are largely independent (until Final Four), enabling the island model.
3. **Rugged fitness landscape:** Many local optima exist (many "pretty good" brackets). GAs handle rugged landscapes better than gradient-based methods.
4. **No gradient available:** The fitness function (bracket scoring) is not differentiable, ruling out gradient descent. GAs are gradient-free.
5. **Population-based search:** We want diverse brackets, not a single "best" bracket. GAs naturally maintain populations.

---

## 4. Adaptive Mutation Rate Literature

### 4.1 Taxonomy of Adaptation Methods

The literature classifies mutation rate adaptation into four categories (Eiben et al., 1999):

1. **Static:** Fixed mutation rate throughout the run. Simple but suboptimal.
2. **Deterministic dynamic:** Mutation rate changes on a pre-set schedule (e.g., linearly decrease over generations). Does not respond to search state.
3. **Adaptive:** Mutation rate responds to feedback from the search (e.g., fitness improvement rate). The Rechenberg 1/5 success rule falls here.
4. **Self-adaptive:** Mutation rate is encoded in the genome itself and co-evolves with the solution. Each individual carries its own mutation rate.

### 4.2 Rechenberg's 1/5 Success Rule

Ingo Rechenberg (1973) derived the 1/5 success rule for (1+1) evolution strategies:

> The mutation step size is optimal when approximately 1 in 5 mutations is successful (improves fitness).

- If success rate > 1/5: **increase** step size (mutations are too conservative, landscape is smooth)
- If success rate < 1/5: **decrease** step size (mutations are too disruptive, near an optimum)

The rule was derived for unimodal, smooth, noiseless fitness landscapes (hyperspheres and ridges) with large dimensionality. It was never intended for multimodal or noisy landscapes, which our bracket problem has.

**Applicability to brackets:** Limited but inspirational. We can track what fraction of mutations improve fitness and adjust accordingly, but the 1/5 threshold specifically does not apply.

### 4.3 The Vanishing Mutation Rate Problem

Self-adaptive mutation rates (SAMR) -- where each individual's mutation rate is encoded in its genome -- suffer from a well-documented pathology: **mutation rates decay to zero** (Helmuth & Spector, 2020; Lalejini et al., 2024). The mechanism:

1. Most mutations in hard problems are deleterious.
2. Individuals with lower mutation rates produce more copies of themselves (they are less likely to be destroyed by harmful mutations).
3. Natural selection thus favors ever-lower mutation rates.
4. Eventually, mutation rates approach zero, halting evolution = premature convergence.

**Solutions from the literature:**

- **Group Elite Selection of Mutation Rates (GESMR):** Co-evolve a separate population of mutation rates; assign each rate to a group of solutions; select rates based on the best outcome in the group (Helmuth & Kelly, 2022). Avoids vanishing because the rare beneficial mutation gets credit.
- **Bandit-based adaptive control:** Use a multi-armed bandit to select mutation rates, with maximum-value-based credit assignment (not average). This allows occasionally beneficial high mutation rates to be retained even when most mutations are harmful (Lalejini et al., 2024).
- **Floor constraint:** Simply enforce a minimum mutation rate (e.g., never drop below 0.005 per gene). Crude but effective.

### 4.4 Recommended Adaptive Mutation Scheme for Brackets

Based on the literature, I recommend a **three-level adaptive mutation system**:

**Level 1 -- Per-gene base rate (confidence-weighted):**
```
base_rate(game_i) = alpha * (1 - |2*p_i - 1|)
```
Where `p_i` is the win probability for game i, and `alpha` is a scaling factor (~0.15). This yields:
- 1v16 (p=0.987): base_rate = 0.15 * (1 - |2*0.987 - 1|) = 0.15 * 0.026 = 0.004
- 8v9 (p=0.513): base_rate = 0.15 * (1 - |2*0.513 - 1|) = 0.15 * 0.974 = 0.146
- 5v12 (p=0.615): base_rate = 0.15 * (1 - |2*0.615 - 1|) = 0.15 * 0.770 = 0.116

**Level 2 -- Tournament chaos multiplier (temporal adaptation):**
```
chaos_mult = observed_upsets_so_far / expected_upsets_so_far
```
Applied multiplicatively to base rates for upcoming games. If Day 1 is upset-heavy, all mutation rates increase for Day 2.

**Level 3 -- Diversity-responsive adjustment:**
```
if avg_hamming_distance(population) < diversity_floor:
    global_mult *= 1.5   # boost mutation to restore diversity
if avg_hamming_distance(population) > diversity_ceiling:
    global_mult *= 0.7   # reduce mutation, increase exploitation
```

**Floor constraint:** Per-gene mutation rate never drops below 0.002 (prevents vanishing).
**Ceiling constraint:** Per-gene mutation rate never exceeds 0.30 (prevents random search).

---

## 5. Island Model GA Performance

### 5.1 Literature Findings

The island model (multi-population GA with periodic migration) is well-studied:

**When island model outperforms single-population:**
- **Separable or partially separable problems:** When the problem can be decomposed into sub-problems (Whitley, Rana & Heckendorn, 1999). Our bracket problem is partially separable -- regions are independent until Final Four.
- **Multimodal fitness landscapes:** Island model maintains diversity better, avoiding premature convergence to a single local optimum.
- **Parallel hardware available:** Island model is embarrassingly parallel.

**When island model does NOT help:**
- Strongly coupled problems where all variables interact.
- Very small total populations where splitting reduces per-island diversity.

**Our bracket problem is an ideal candidate for the island model** because regions are genuinely separable for the first 4 rounds (15 of 16 games per region are independent of other regions).

### 5.2 Recommended Migration Parameters

From the literature (Algorithm Afternoon, 2024; Whitley et al., 1999; Gong & Fukunaga, 2011):

| Parameter | Recommended | Our Setting |
|-----------|------------|-------------|
| Number of islands | 5-10 typical; 4 natural for brackets | **4** (one per region) + **1** for Final Four |
| Migration rate | 5-10% of island population | **5%** (conservative; regions are mostly independent) |
| Migration frequency | Every 10-20 generations | **Every 10 generations** |
| Migration topology | Ring for simplicity | **Ring** (South-->East-->West-->Midwest-->South) |
| Migration selection | Best individuals from source island | **Top-k** (send best, replace worst) |

### 5.3 Island Model Architecture for Brackets

```
Phase 1: Regional Islands (Generations 1-40)
  Island 1 (South):  15-bit sub-brackets, independent evolution
  Island 2 (East):   15-bit sub-brackets, independent evolution
  Island 3 (West):   15-bit sub-brackets, independent evolution
  Island 4 (Midwest): 15-bit sub-brackets, independent evolution
  Migration: minimal (5% every 10 gen) -- share "chaos level" info, not individuals

Phase 2: Assembly + Final Four (Generations 41-50)
  Combine best regional sub-brackets into full 63-bit brackets
  Island 5 (Final Four): 3-bit sub-brackets (4 semifinal + final games)
  Run 10 more generations on full brackets with Final Four crossover
```

**Rationale:** Since regions are independent for 60 of 63 games, evolving them separately is mathematically justified. The Final Four (3 games) can be optimized after regional evolution is complete.

---

## 6. Computational Feasibility Analysis

### 6.1 Memory Requirements

**Scenario A: Full 3M population GA**

| Component | Calculation | Memory |
|-----------|------------|--------|
| Population (3M x 63 bits as bool) | 3,000,000 x 63 x 1 byte (numpy bool) | ~189 MB |
| Population (3M x 63 bits as packed uint64) | 3,000,000 x 8 bytes | ~24 MB |
| Fitness array (3M x float64) | 3,000,000 x 8 bytes | ~24 MB |
| Offspring array (same as population) | Same as above | ~24-189 MB |
| **Total (packed)** | | **~72 MB** |
| **Total (bool)** | | **~402 MB** |

**Verdict:** Memory is NOT a bottleneck. Even the unoptimized bool representation fits comfortably in RAM.

### 6.2 Computational Cost Per Generation

For a 3M population with 63-bit chromosomes:

**Fitness evaluation:** The dominant cost. If fitness = P(bracket | power index model), this requires computing 63 game probabilities per bracket. With numpy vectorization: ~3M x 63 multiplications = ~189M floating-point ops. At 1 GFLOPS (conservative for numpy): **~0.2 seconds**.

**Tournament selection (k=5):** Generate 5 random indices per bracket = 15M random integers. Numpy can generate this in **~0.1 seconds**.

**Crossover (regional, rate=0.70):** 2.1M crossover operations, each swapping a 15-bit block. Vectorized with numpy slicing: **~0.05 seconds**.

**Mutation (per-gene, avg rate ~0.05):** 3M x 63 x 0.05 = ~9.5M bit flips. Generate random mask and XOR: **~0.1 seconds**.

**Cascade repair (if lower-round flip invalidates upper rounds):** This is the expensive part. Each mutated lower-round game may cascade through 1-4 upper-round games. Worst case: ~9.5M mutations x 2 avg cascade steps = ~19M additional operations. **~0.2 seconds**.

**Estimated total per generation: ~0.7-1.0 seconds** with well-optimized numpy.

### 6.3 Total Runtime Estimates

| Scenario | Population | Generations | Time/Gen | Total Time |
|----------|-----------|-------------|----------|------------|
| Full 3M, 50 gen | 3,000,000 | 50 | ~1.0 sec | **~50 sec** |
| Full 3M, 100 gen | 3,000,000 | 100 | ~1.0 sec | **~100 sec** |
| Culled 100K, 50 gen | 100,000 | 50 | ~0.03 sec | **~1.5 sec** |
| Culled 100K, 100 gen | 100,000 | 100 | ~0.03 sec | **~3 sec** |
| Island model (4x25K), 50 gen | 4 x 25,000 | 50 | ~0.03 sec | **~1.5 sec** |

**Key insight from benchmarks:** The FastGeneticAlgorithm project (Brownlee, 2024) achieved 0.308 seconds for 500 generations on population=100, bitstring=1000. Scaling linearly to our problem: population 100K is 1000x larger, bitstring 63 is 16x smaller, net ~62x slower per generation = ~0.04 seconds/generation. This confirms our estimates.

With Cython or Numba JIT compilation, an additional 10-20x speedup is achievable, bringing the full 3M/100-generation scenario down to ~5-10 seconds.

### 6.4 Feasibility Verdict

**YES, this is entirely feasible on a single machine.**

- Even the most aggressive scenario (3M population, 100 generations, pure numpy) completes in under 2 minutes.
- The recommended scenario (island model with 4x25K populations, 50 generations) completes in under 2 seconds.
- Memory requirements (72-400 MB) are trivial for any modern machine.
- Numba/Cython optimization can bring runtimes down to single-digit seconds even for the full 3M scenario.

**Recommendation:** Start with numpy-vectorized implementation. Profile. Only add Numba if the cascade repair step is a bottleneck.

---

## 7. Concrete Recommendations

### 7.1 Recommended GA Configuration

```json
{
  "ga_config": {
    "initial_population": 3000000,
    "working_population": 100000,
    "culling_method": "fitness_proportional_from_IS_weights",
    "elite_count": 1000,
    "elite_pct": 0.01,
    "crossover_rate": 0.75,
    "crossover_type": "regional",
    "selection_method": "tournament",
    "tournament_k": 5,
    "max_generations": 50,
    "convergence_threshold": 0.001,
    "convergence_window": 5
  },
  "island_model": {
    "enabled": true,
    "islands": 4,
    "island_population": 25000,
    "migration_rate": 0.05,
    "migration_interval_generations": 10,
    "migration_topology": "ring",
    "migration_selection": "top_k",
    "final_four_island": true,
    "final_four_generations": 10
  },
  "adaptive_mutation": {
    "scheme": "three_level",
    "level1_per_gene_confidence_weighted": {
      "formula": "alpha * (1 - |2*p_i - 1|)",
      "alpha": 0.15,
      "floor": 0.002,
      "ceiling": 0.30
    },
    "level2_chaos_multiplier": {
      "formula": "observed_upsets / expected_upsets",
      "update_frequency": "after_each_real_round"
    },
    "level3_diversity_responsive": {
      "metric": "avg_hamming_distance",
      "diversity_floor": 0.25,
      "diversity_ceiling": 0.65,
      "boost_factor": 1.5,
      "dampen_factor": 0.7
    },
    "seed_specific_base_rates": {
      "1v16": 0.004,
      "2v15": 0.020,
      "3v14": 0.045,
      "4v13": 0.063,
      "5v12": 0.116,
      "6v11": 0.111,
      "7v10": 0.117,
      "8v9": 0.146
    }
  },
  "fitness_function": {
    "pre_tournament": {
      "bracket_likelihood": 0.50,
      "regional_balance": 0.30,
      "stratum_importance_weight": 0.20
    },
    "during_tournament": {
      "bayesian_posterior": 0.60,
      "regional_accuracy": 0.25,
      "round_accuracy": 0.15
    }
  }
}
```

### 7.2 What to Implement vs What to Skip

**Implement (high value, low cost):**
1. Confidence-weighted per-gene mutation rates (AlphaFold pLDDT analogy)
2. Island model with 4 regional islands
3. Regional crossover operator
4. Diversity-responsive mutation rate adjustment
5. Tournament selection with k=5
6. Elitism (top 1% preserved)

**Implement if data supports it (moderate value, low cost):**
7. Co-upset correlation matrix from historical data (MSA analogy) -- but only if correlations are statistically significant
8. Chaos multiplier from real-time tournament results

**Skip (low value or high cost):**
9. Evoformer-style dual-track architecture (over-engineering)
10. Triangle multiplicative updates (no geometric analog)
11. Self-adaptive mutation rates (vanishing rate problem not worth the complexity)
12. Attention mechanisms over games (insufficient data to train)

### 7.3 Integration with Other Agents' Decisions

**With Math Agent (D001 - Stratified IS):**
- The GA operates ON TOP of the IS samples. IS provides Generation 0 with importance weights. GA refines from there.
- Importance weights from IS become initial fitness scores for GA selection.
- GA crossover and mutation may break the stratification structure. This is acceptable -- the GA is finding new high-fitness brackets that IS may have missed, not preserving IS properties.
- The Bayesian soft-likelihood weight update (SMC-style from D001) should happen BETWEEN GA generations when real results arrive, not within the GA loop.

**With Stats Agent (D002 - Power Index):**
- Win probabilities from the 9-factor power index formula feed directly into the confidence-weighted mutation rates.
- Historical seed matchup data (from Stats Agent) calibrates the seed-specific base rates.

**With Betting Agent (D003 - Market Signal Integration):**
- The blended probability `P_final` (40% stats + 45% market + 15% factors) should be used as `p_i` in the mutation rate formula, not raw stats-only probabilities.
- Sharp line movements should trigger targeted mutation rate increases for specific games (e.g., if a line moves 3+ points, double the mutation rate for that game).

---

## 8. Sources

### Genetic Algorithm Parameters and Best Practices
- [Choosing Mutation and Crossover Ratios for Genetic Algorithms -- A Review with a New Dynamic Approach (Hassanat et al., 2019)](https://www.mdpi.com/2078-2489/10/12/390)
- [Best Practices for Tuning Genetic Algorithm Parameters (Woodruff, 2024)](https://www.woodruff.dev/day-31-best-practices-for-tuning-genetic-algorithm-parameters/)
- [Genetic Algorithm with a New Round-Robin Based Tournament Selection (PLOS One, 2022)](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0274456)
- [Tournament Selection in Genetic Algorithms (Baeldung)](https://www.baeldung.com/cs/ga-tournament-selection)
- [Fast Genetic Algorithm in Python (Brownlee, 2024)](https://github.com/Jason2Brownlee/FastGeneticAlgorithm)

### AlphaFold Architecture
- [AlphaFold2 and its Applications in Biology and Medicine (PMC, 2023)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10011802/)
- [AlphaFold 2: Attention Mechanism for Predicting 3D Protein Structures](https://piip.co.kr/en/blog/AlphaFold2_Architecture_Improvements)
- [The Illustrated AlphaFold (Simon, 2024)](https://elanapearl.github.io/blog/2024/the-illustrated-alphafold/)
- [AlphaFold Architecture (UVIO)](https://www.uvio.bio/alphafold-architecture/)

### Adaptive Mutation Rates
- [Effective Adaptive Mutation Rates for Program Synthesis (Lalejini et al., 2024)](https://arxiv.org/html/2406.15976v1)
- [Effective Mutation Rate Adaptation through Group Elite Selection (Helmuth & Kelly, 2022)](https://dl.acm.org/doi/10.1145/3512290.3528706)
- [Adaptive Mutation Using Statistics Mechanism for Genetic Algorithms (Springer)](https://link.springer.com/chapter/10.1007/978-0-85729-412-8_2)
- [Self-Adaptation in Genetic Algorithms (ResearchGate)](https://www.researchgate.net/publication/2577226_Self--Adaptation_in_Genetic_Algorithms)
- [Evolution Strategies under the 1/5 Success Rule (MDPI, 2023)](https://www.mdpi.com/2227-7390/11/1/201)

### Island Model GAs
- [Island Genetic Algorithms (Algorithm Afternoon, 2024)](https://algorithmafternoon.com/genetic/island_genetic_algorithms/)
- [The Island Model Genetic Algorithm: On Separability, Population Size and Convergence (Whitley et al., 1999)](https://www.researchgate.net/publication/2244494_The_Island_Model_Genetic_Algorithm_On_Separability_Population_Size_and_Convergence)
- [On the Behavior of Parallel Island Models (ScienceDirect, 2023)](https://www.sciencedirect.com/science/article/abs/pii/S1568494623008980)
- [Distributed Island-Model Genetic Algorithms (Gong & Fukunaga, 2011)](https://www.metahack.org/gong-fukunaga-island-model-cec2011.pdf)

### Sports Prediction with Evolutionary Methods
- [Sports Games Modeling and Prediction using Genetic Programming (IEEE, 2020)](https://ieeexplore.ieee.org/document/9185917/)
- [Efficient Computation of Tournament Winning Probabilities (Brandes et al., 2025)](https://journals.sagepub.com/doi/10.1177/22150218251313905)
- [GA for Prediction of Football Results (Academia)](https://www.academia.edu/825946/An_investigation_into_genetic_algorithms_for_the_prediction_of_football_results_to_aid_computerised_gambling)
- [March Machine Learning Mania (Kaggle, 2025)](https://www.kaggle.com/competitions/march-machine-learning-mania-2025)

### Computational Performance
- [NumPy Boolean Array Efficiency Issue (GitHub)](https://github.com/numpy/numpy/issues/14821)
- [Cythonize the Genetic Algorithm (Paperspace)](https://blog.paperspace.com/genetic-algorithm-python-cython-speed-increase/)
- [Optimize Genetic Algorithms in Python (Intel)](https://www.intel.com/content/www/us/en/developer/articles/technical/optimize-genetic-algorithms-python.html)
