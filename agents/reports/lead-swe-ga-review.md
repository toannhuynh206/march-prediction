# Lead SWE Review: Genetic Algorithm Computational Feasibility

**Author:** Lead Software Engineer Agent
**Date:** 2026-03-06
**Status:** REVIEW COMPLETE
**Subject:** Biology Agent's proposed GA overlay on Stratified IS bracket generation

---

## Executive Summary

The GA proposal is **computationally feasible** with the Island Model (per-region) approach, but requires careful implementation choices to stay within our performance and memory budgets. The key insight: because D001 locks us to 3M brackets per region (not 3M full brackets), the GA operates on 15-bit genomes per region, not 63-bit full brackets. This dramatically reduces the problem size and makes the GA practical.

**Verdict: CONDITIONALLY APPROVED** -- contingent on the implementation constraints below.

---

## 1. Memory Budget Analysis

### 1.1 Raw Bracket Storage

**Per-region genome (Island Model, which is the correct approach):**
- Each regional bracket = 15 games = 15 bits
- Stored as `int16` (2 bytes) per bracket -- already decided in D001
- 3M brackets x 2 bytes = **6 MB per region**
- 4 regions = **24 MB** for all bracket genomes

**Full 63-bit representation (if needed for final assembly):**
- 63 bits fits in `int64` (8 bytes)
- 3M brackets x 8 bytes = **24 MB per region**
- Not needed during GA evolution -- only at final assembly

### 1.2 Per-Bracket Metadata

Each bracket in the GA population carries:

| Field | Dtype | Bytes | 3M Total |
|-------|-------|-------|----------|
| Genome (regional) | int16 | 2 | 6 MB |
| Fitness score | float32 | 4 | 12 MB |
| Importance weight (from IS) | float32 | 4 | 12 MB |
| Stratum ID | int16 | 2 | 6 MB |
| **Subtotal per bracket** | | **12 bytes** | **36 MB** |

Per region: **36 MB**
All 4 regions: **144 MB**

### 1.3 Multi-Generation Memory

The GA does NOT need to keep multiple generations in memory simultaneously. Each generation overwrites the previous one (in-place evolution). We only need:

| Buffer | Purpose | Size (per region) |
|--------|---------|-------------------|
| Current population | Active generation | 36 MB |
| Offspring buffer | New generation being built | 36 MB |
| Elite archive | Top 10K brackets preserved | 120 KB |
| Fitness sort indices | argsort for selection | 24 MB (int64 index array) |
| Random number buffer | Per-round RNG | 12 MB |
| Tournament selection indices | k=5 indices for 3M brackets | 120 MB (5 x 3M x int64) |

**Peak per-region estimate: ~228 MB**
**Peak all-4-regions (sequential): ~228 MB** (process one region at a time)
**Peak all-4-regions (parallel): ~912 MB** (all 4 islands simultaneously)

### 1.4 RAM Verdict

| Scenario | Peak RAM | Fits 8GB? | Fits 16GB? |
|----------|----------|-----------|------------|
| Sequential islands (recommended) | ~300 MB + overhead | YES | YES |
| Parallel islands (4 processes) | ~1.2 GB + overhead | YES | YES |
| Sequential + existing sim pipeline | ~1.1 GB total | YES | YES |
| Parallel + existing sim pipeline | ~2.0 GB total | YES | YES |

**Conclusion: Memory is NOT a concern.** Even the most aggressive parallel configuration uses well under our 4GB peak RAM budget (from lead-swe-agent.md). The 15-bit regional genome is the key -- it's 4x smaller than a 63-bit full bracket genome would be.

---

## 2. Compute Budget Analysis

### 2.1 Fitness Evaluation (3M brackets)

The fitness function is: `P(bracket | power index model)` weighted by stratum importance weight.

For regional brackets (15 games), fitness = product of 15 game probabilities:

```python
# Vectorized: prob_matrix is precomputed (16x16 float32)
# matchups is (15, 2) array of team indices per round
# brackets is (3M, 15) boolean array of outcomes
#
# For each bracket, look up P(outcome) for each of 15 games
# fitness = product of 15 probabilities
game_probs = prob_matrix[team_a, team_b]  # (15,) array
# For each bracket, multiply relevant probs
fitness = np.prod(np.where(brackets, game_probs, 1 - game_probs), axis=1)
```

**Estimate:** 3M brackets x 15 games = 45M lookups + 3M products.
With NumPy vectorization: **~50-100ms per region.**

### 2.2 Tournament Selection (k=5, 3M population)

```python
# Generate 3M x 5 random indices
candidates = rng.integers(0, pop_size, size=(pop_size, k))  # (3M, 5)
# Look up fitness for each candidate
candidate_fitness = fitness[candidates]  # (3M, 5)
# Select winner (argmax along axis=1)
winners = candidates[np.arange(pop_size), np.argmax(candidate_fitness, axis=1)]
```

**Estimate:**
- RNG for 15M integers: ~30ms
- Advanced indexing (3M x 5): ~60ms
- Argmax: ~15ms
- **Total: ~100-150ms per region**

### 2.3 Crossover (Regional)

Since we're using the Island Model (per-region), "regional crossover" within a region becomes uniform or single-point crossover on 15-bit strings. This is trivially vectorized:

```python
# Single-point crossover on 3M bracket pairs
mask = np.arange(15) < crossover_points[:, None]  # (3M, 15) boolean
offspring = np.where(mask, parent_a, parent_b)
```

**Estimate:** ~20-30ms per region (just array slicing and masking).

For cross-region assembly (combining best regional sub-brackets into full brackets), this happens ONCE at the end, not per generation.

### 2.4 Mutation

Per-gene mutation with seed-specific rates:

```python
# mutation_probs is (15,) array of per-game mutation rates
# e.g., [0.013, 0.065, 0.15, ...] based on seed matchups
mutation_mask = rng.random((pop_size, 15)) < mutation_probs[None, :]
brackets ^= mutation_mask  # flip bits where mask is True
```

**Estimate:**
- RNG for 45M floats: ~90ms
- Comparison + XOR: ~30ms
- **Total: ~120ms per region**

**Cascade mutation** (flipping downstream games when an upstream game flips) is more complex but still vectorizable with careful indexing. Add ~50ms.

### 2.5 Total Time Per Generation

| Operation | Time (per region) |
|-----------|-------------------|
| Fitness evaluation | 100 ms |
| Tournament selection | 150 ms |
| Crossover | 30 ms |
| Mutation | 170 ms |
| Elite preservation | 10 ms |
| Diversity metrics | 50 ms |
| **Total per generation** | **~510 ms** |

### 2.6 Total GA Runtime

| Scenario | Calculation | Total Time |
|----------|-------------|------------|
| 50 generations, 1 region, sequential | 50 x 510ms | **25.5 seconds** |
| 50 generations, 4 regions, sequential | 4 x 25.5s | **102 seconds** |
| 50 generations, 4 regions, parallel (4 cores) | 25.5s | **~26 seconds** |
| 30 generations (early convergence) | 4 x 15.3s (seq) / 15.3s (par) | **61s / 15s** |

### 2.7 Performance Target Assessment

Current target: simulate 10M brackets (1 region) in <30 seconds.

D001 changed this to 3M brackets per region with stratified IS. So the real target is:
- **Generate 3M stratified IS brackets: ~10 seconds** (Generation 0)
- **Evolve 50 GA generations: ~25 seconds** (per region, parallelizable)
- **Total per region: ~35 seconds**
- **Total all regions (parallel): ~35 seconds**
- **Total all regions (sequential): ~112 seconds**

**Recommendation:** Run initial IS generation sequentially (low memory), then GA evolution in parallel (4 processes, one per region island). Total wall-clock: **~35-40 seconds** for the entire pipeline. This is acceptable.

---

## 3. Implementation Strategy

### 3.1 Data Structures

**Recommended: NumPy structured array or parallel arrays**

```python
# Option A: Parallel arrays (RECOMMENDED -- faster for vectorized ops)
genomes = np.zeros((pop_size, 15), dtype=np.bool_)  # or int8
fitness = np.zeros(pop_size, dtype=np.float32)
weights = np.zeros(pop_size, dtype=np.float32)
strata  = np.zeros(pop_size, dtype=np.int16)

# Option B: Bitpacked int16 (saves memory, slower ops)
genomes_packed = np.zeros(pop_size, dtype=np.int16)  # 15 bits packed
# Bit manipulation needed for crossover/mutation -- 2-3x slower
```

**Decision: Option A (parallel arrays).** The memory difference is negligible (45 MB vs 6 MB for genomes) and the performance gain from avoiding bit manipulation is significant. Bitpacking only makes sense for storage/DB, not computation.

### 3.2 GPU Acceleration (CuPy)

**Assessment: Not recommended for this workload.**

Reasons:
- 3M x 15 is a small problem for GPU. GPU overhead (kernel launch, memory transfer) would dominate.
- NumPy on CPU handles this in ~500ms/generation -- not worth the complexity.
- CuPy adds a dependency (CUDA toolkit) that complicates Docker deployment.
- GPU would only help if population were 100M+ or genome length were 1000+.

**Exception:** If we later add the AlphaFold-inspired attention mechanism (63x63 game interaction matrix applied to 3M brackets), that WOULD benefit from GPU. Flag for future consideration.

### 3.3 Island Model Parallelization

**Recommended: `multiprocessing.Pool` with 4 workers**

```python
from multiprocessing import Pool

def evolve_region(region_config):
    """Evolve one island (region) for N generations."""
    pop = generate_stratified_is_brackets(region_config)
    for gen in range(max_generations):
        fitness = evaluate_fitness(pop)
        parents = tournament_select(pop, fitness, k=5)
        offspring = crossover(parents)
        offspring = mutate(offspring, region_config.mutation_rates)
        pop = apply_elitism(pop, offspring, elite_count=10000)
        if check_convergence(pop, fitness):
            break
    return pop, fitness

with Pool(4) as pool:
    results = pool.map(evolve_region, [south_cfg, east_cfg, west_cfg, midwest_cfg])
```

**Why not threading:** GIL prevents true parallelism for CPU-bound NumPy ops. `multiprocessing` gives true parallelism.

**Why not `concurrent.futures`:** Either works; `multiprocessing.Pool` is simpler for this use case.

**Migration between islands:** Every 5 generations, exchange the top 5% (150K) brackets between regions via `multiprocessing.Queue`. This is cheap -- 150K x 12 bytes = 1.8 MB per migration event.

### 3.4 Integration with Stratified IS Pipeline

The GA is a **post-processing layer** on top of Generation 0 (the stratified IS brackets):

```
Pipeline:
1. [IS Generator] → 3M stratified brackets per region (Gen 0)
2. [GA Engine]    → Evolve 50 generations per region
3. [Assembler]    → Combine best regional sub-brackets into full 63-game brackets
4. [DB Loader]    → COPY evolved brackets to PostgreSQL
5. [SMC Updater]  → Bayesian weight updates as real games happen
```

**Critical constraint:** The GA must preserve stratum representation. After evolution, verify that each of the 30 canonical worlds still has adequate representation (minimum 50K brackets per champion seed, per D001). If selection pressure eliminates a stratum, inject fresh samples from that stratum.

```python
# Post-GA stratum verification
for stratum_id in range(30):
    count = np.sum(strata == stratum_id)
    if count < min_per_stratum:
        deficit = min_per_stratum - count
        # Replace lowest-fitness brackets with fresh IS samples from this stratum
        inject_stratum_samples(pop, fitness, stratum_id, deficit)
```

---

## 4. Architecture Concerns

### 4.1 Database Integration

**GA output feeds into PostgreSQL identically to MC brackets.** No schema changes needed.

The brackets table (per D001 and D006) already has:
- `bracket_encoded SMALLINT[4]` (15-bit per region, 4 regions)
- `weight FLOAT` (importance weight)
- `stratum_id INT` (world ID)
- `is_alive BOOLEAN`
- `region VARCHAR` (partition key)

GA-evolved brackets are just brackets with updated weights. The DB does not know or care whether they came from MC, IS, or GA.

**Bulk load:** COPY FROM remains the correct strategy. 3M brackets per region x 4 regions = 12M rows. Same as before.

### 4.2 Interaction with Bayesian Weight Update (SMC)

**This is the most architecturally delicate point.**

The SMC weight update (D001) works as follows:
1. Before tournament: each bracket has weight = importance weight from IS
2. After each real game: multiply weight by likelihood of observed result given bracket
3. Brackets consistent with reality get higher weights; inconsistent ones get lower weights
4. `is_alive` is the hard binary version (for user display); `weight` is the soft version (for stats)

**GA impact on SMC:**
- GA-evolved brackets have fitness-based weights, NOT pure importance sampling weights
- This breaks the IS variance reduction guarantee (Math Agent concern)
- **Resolution:** Store TWO weight columns:
  - `is_weight FLOAT` -- the original importance sampling weight (for statistical correctness)
  - `ga_fitness FLOAT` -- the GA fitness score (for bracket ranking/display)
  - SMC updates multiply `is_weight`, not `ga_fitness`

**Wait -- this means a schema change.** Adding `ga_fitness FLOAT` to the brackets table.

| Column | Type | Purpose | New? |
|--------|------|---------|------|
| `ga_fitness` | FLOAT | GA fitness score for ranking | YES |
| `ga_generation` | SMALLINT | Which generation this bracket is from | YES (optional) |

**Impact: minor.** Two nullable FLOAT columns on 12M rows = 96 MB additional storage. Acceptable.

### 4.3 Bracket Encoder (15-bit SMALLINT)

**No changes needed.** The GA operates on the same 15-bit regional representation that the encoder uses. GA genomes ARE the encoded brackets. Crossover and mutation operate directly on the encoded form.

```
Bracket encoder: 15 games → 15-bit integer → SMALLINT
GA genome:       15 genes  → 15-bit chromosome
These are the same thing.
```

### 4.4 API Impact

The pruning API (`pruner.py`) is unaffected. It operates on `is_alive` and the bitwise bracket encoding, neither of which changes.

New API endpoint consideration: `GET /api/ga/diversity` to expose population diversity metrics. Optional -- not blocking.

---

## 5. Performance Targets Summary

| Metric | Current Target | With GA | Verdict |
|--------|---------------|---------|---------|
| Generate 3M brackets (1 region) | <30s | ~10s (IS only) | PASS |
| GA evolution (1 region, 50 gen) | N/A | ~25s | ACCEPTABLE |
| Full pipeline (4 regions, parallel) | N/A | ~35-40s | ACCEPTABLE |
| Full pipeline (4 regions, sequential) | N/A | ~112s | ACCEPTABLE (not ideal) |
| Peak RAM | <800 MB | ~300 MB (sequential) | PASS |
| DB insert (12M rows, COPY) | <5 min | No change | PASS |
| API pruning query | <2s | No change | PASS |

### 5.1 Is the GA a Pre-Processing Step or Live?

**The GA is a PRE-PROCESSING step.** It runs once before the tournament starts (or once per day during the tournament when re-evolving with updated chaos multipliers).

**Timeline:**
1. **Pre-tournament (Selection Sunday):** Run full GA pipeline. ~40 seconds. Load 12M evolved brackets into DB.
2. **During tournament (after each round):** Two options:
   - **Option A (recommended):** SMC weight update only. No re-evolution. Fast (<10s).
   - **Option B (ambitious):** Re-run GA with adaptive mutation rates informed by observed chaos. ~40 seconds. Replace brackets in DB.

Option A is simpler and preserves IS statistical properties. Option B is the Biology Agent's full vision but risks invalidating IS weights. **Recommend Option A for v1, Option B for v2.**

---

## 6. Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| GA eliminates rare strata (e.g., 16-seed champions) | HIGH | Post-GA stratum verification + injection (Section 3.4) |
| GA fitness and IS weights are theoretically incompatible | MEDIUM | Separate columns; SMC uses IS weights only (Section 4.2) |
| Cascade mutation breaks bracket consistency | MEDIUM | Validate bracket consistency after mutation (no impossible matchups) |
| 50 generations is arbitrary; may over-converge | LOW | Add convergence detection (fitness plateau for 5 generations = stop) |
| Parallelization adds complexity | LOW | Start with sequential; parallelize only if needed for time budget |

---

## 7. Concrete Recommendations

1. **Start sequential, not parallel.** 112 seconds total is acceptable for a pre-processing step. Add multiprocessing later if needed.
2. **Use parallel NumPy arrays, not bitpacking.** Performance over memory savings.
3. **Do NOT use GPU/CuPy.** The problem is too small to benefit.
4. **Add `ga_fitness FLOAT` column to brackets table.** Keep IS weights separate.
5. **Implement convergence detection.** Don't blindly run 50 generations -- stop early if fitness plateaus.
6. **Post-GA stratum verification is MANDATORY.** Without it, the GA could eliminate the rare-event coverage that IS provides.
7. **GA is pre-processing only for v1.** Do not attempt live re-evolution during tournament in the first version.
8. **Reduce population size per generation.** Consider culling to 1M after Generation 10 and 500K after Generation 30. This accelerates later generations without losing much. The Biology Agent's suggestion of 3M throughout all 50 generations is wasteful -- most of the population is low-fitness noise after early generations.
9. **Profile before optimizing.** Build the naive vectorized version first, measure, then optimize bottlenecks.

---

## 8. Proposed File Structure

```
engine/
  bracket_generator.py    # Stratified IS bracket generation (Gen 0)
  ga_engine.py            # GA evolution loop (new file)
  ga_operators.py         # Selection, crossover, mutation operators (new file)
  fitness.py              # Fitness evaluation functions (new file)
  assembler.py            # Combine regional sub-brackets into full brackets (new file)
  db_loader.py            # COPY to PostgreSQL (existing, no changes)
```

---

**Review complete. The GA is feasible within our budgets. The Island Model per-region approach is the correct architecture. Main risk is stratum preservation -- this must be enforced programmatically.**

-- Lead SWE Agent
