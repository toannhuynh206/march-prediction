"""
Validate proposed profile redesign against key metrics:
1. Hellinger distance > 0.10 between ALL profile pairs
2. 1-seed champion rate >= 40% (CLAUDE.md requirement)
3. ESS/N improvement over current profiles
"""

import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from simulation.temperature import (
    StrategyProfile,
    apply_temperature,
    compute_profile_budgets,
)


# =========================================================================
# Synthetic probability distribution (mimics real enumeration)
# =========================================================================

def make_synthetic_region(rng: np.random.Generator, n: int = 32768) -> tuple:
    """Create a synthetic probability distribution mimicking real enumeration.

    Returns (probs, champion_seeds, r64_upsets).
    """
    # Assign seeds: 8 matchups, 2 outcomes each = 2^8 first-round combos
    # Champion seeds follow roughly exponential decay from 1-seed
    champion_seeds = np.zeros(n, dtype=np.int16)
    seed_base_probs = {
        1: 0.45, 2: 0.18, 3: 0.12, 4: 0.08, 5: 0.05,
        6: 0.04, 7: 0.03, 8: 0.02, 9: 0.01, 10: 0.008,
        11: 0.006, 12: 0.004, 13: 0.003, 14: 0.002,
        15: 0.001, 16: 0.0005,
    }
    seeds = list(seed_base_probs.keys())
    seed_probs_arr = np.array([seed_base_probs[s] for s in seeds])
    seed_probs_arr /= seed_probs_arr.sum()
    champion_seeds = rng.choice(seeds, size=n, p=seed_probs_arr).astype(np.int16)

    # R64 upsets: higher seeds correlate with more upsets
    r64_upsets = np.clip(
        rng.poisson(lam=champion_seeds.astype(float) * 0.3, size=n),
        0, 8,
    ).astype(np.int8)

    # Probabilities: exponentially decaying with noise
    log_probs = -rng.exponential(scale=3.0, size=n)
    # Boost high-seed champions
    log_probs -= champion_seeds.astype(float) * 0.5
    probs = np.exp(log_probs)
    probs /= probs.sum()

    return probs, champion_seeds, r64_upsets


def hellinger_distance(p: np.ndarray, q: np.ndarray) -> float:
    """Hellinger distance between two distributions."""
    return float(np.sqrt(0.5 * np.sum((np.sqrt(p) - np.sqrt(q)) ** 2)))


def compute_mixed_distribution(
    true_probs: np.ndarray,
    profile: StrategyProfile,
) -> np.ndarray:
    """Compute the effective sampling distribution for a profile."""
    base = apply_temperature(true_probs, profile.base_temperature)

    if profile.p_upset > 0 and abs(profile.upset_temperature - profile.base_temperature) > 1e-10:
        upset = apply_temperature(true_probs, profile.upset_temperature)
        mixed = (1 - profile.p_upset) * base + profile.p_upset * upset
        mixed /= mixed.sum()
        return mixed
    return base


def compute_ess_ratio(true_probs: np.ndarray, sampling_probs: np.ndarray) -> float:
    """ESS/N for importance sampling from sampling_probs targeting true_probs."""
    weights = np.where(sampling_probs > 1e-30, true_probs / sampling_probs, 0.0)
    if weights.sum() < 1e-30:
        return 0.0
    w_norm = weights / weights.sum()
    ess = 1.0 / np.sum(w_norm ** 2) / len(true_probs)
    return float(ess)


def champion_seed_rate(
    true_probs: np.ndarray,
    sampling_probs: np.ndarray,
    champion_seeds: np.ndarray,
    target_seed: int = 1,
) -> float:
    """Fraction of sampled brackets with champion_seed == target_seed."""
    mask = champion_seeds == target_seed
    return float(sampling_probs[mask].sum())


# =========================================================================
# Profile sets to compare
# =========================================================================

CURRENT_PROFILES = (
    StrategyProfile("chalk",       0.7, 0.7, 0.0,  0.7, 0.30),
    StrategyProfile("standard",    1.0, 1.0, 0.0,  1.0, 0.30),
    StrategyProfile("mild_upset",  1.0, 1.8, 0.25, 1.0, 0.15),
    StrategyProfile("cinderella",  1.0, 4.0, 0.20, 1.0, 0.10),
    StrategyProfile("chaos",       1.5, 3.5, 0.50, 1.5, 0.10),
    StrategyProfile("max_chaos",   2.5, 5.0, 0.50, 2.0, 0.05),
)

PROPOSED_PROFILES = (
    # chalk: Very sharp. All regions favor favorites.
    StrategyProfile("chalk",       0.5, 0.5, 0.0,  0.5, 0.25),
    # standard: True probability. weight=1.0, perfect ESS.
    StrategyProfile("standard",    1.0, 1.0, 0.0,  1.0, 0.30),
    # mild_chaos: Uniform mild upset boost, NO mixing.
    # T=2.2 gives clear separation from both standard (1.0) and cinderella mix.
    StrategyProfile("mild_chaos",  2.2, 2.2, 0.0,  1.3, 0.20),
    # cinderella: ~1 region gets extreme upsets, 3 stay normal.
    # p_upset=0.30 → ~1.2 upset regions/bracket.
    # upset_T=6.0 makes upset branch nearly uniform.
    StrategyProfile("cinderella",  1.0, 6.0, 0.30, 1.0, 0.15),
    # chaos: ~2 regions extreme, 2 elevated. F4 also volatile.
    # Covers both moderate and extreme upset scenarios.
    StrategyProfile("chaos",       3.0, 8.0, 0.50, 2.5, 0.10),
)


def evaluate_profile_set(
    name: str,
    profiles: tuple[StrategyProfile, ...],
    true_probs: np.ndarray,
    champion_seeds: np.ndarray,
) -> None:
    """Full evaluation of a profile set."""
    print(f"\n{'='*70}")
    print(f"  {name}")
    print(f"{'='*70}")

    # Compute sampling distributions
    dists = {}
    for p in profiles:
        dists[p.name] = compute_mixed_distribution(true_probs, p)

    # 1. Hellinger distances
    print(f"\n  Pairwise Hellinger distances:")
    names = [p.name for p in profiles]
    min_hell = float("inf")
    min_pair = ("", "")
    problems = 0
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            h = hellinger_distance(dists[names[i]], dists[names[j]])
            status = "OK" if h >= 0.10 else "PROBLEM"
            if h < 0.10:
                problems += 1
            if h < min_hell:
                min_hell = h
                min_pair = (names[i], names[j])
            print(f"    {names[i]:>12s} vs {names[j]:<12s}: {h:.4f} {status}")

    print(f"\n  Min Hellinger: {min_hell:.4f} ({min_pair[0]} vs {min_pair[1]})")
    print(f"  Problems (< 0.10): {problems}")

    # 2. Per-profile metrics
    print(f"\n  Per-profile metrics:")
    print(f"    {'Profile':>12s}  {'1-seed%':>8s}  {'ESS/N':>8s}  {'Upsets(E)':>10s}")
    print(f"    {'-'*12}  {'-'*8}  {'-'*8}  {'-'*10}")

    portfolio_1seed = 0.0
    portfolio_ess_weighted = 0.0
    total_frac = 0.0

    for p in profiles:
        d = dists[p.name]
        ess = compute_ess_ratio(true_probs, d)
        s1_rate = champion_seed_rate(true_probs, d, champion_seeds, 1)

        # Expected upsets: brackets weighted by sampling prob where champion_seed > 2
        # Use upset seed distribution as proxy
        upset_rate = 1.0 - champion_seed_rate(true_probs, d, champion_seeds, 1) \
                         - champion_seed_rate(true_probs, d, champion_seeds, 2)

        print(f"    {p.name:>12s}  {s1_rate*100:>7.1f}%  {ess*100:>7.1f}%  {upset_rate*100:>9.1f}%")

        portfolio_1seed += p.fraction * s1_rate
        portfolio_ess_weighted += p.fraction * ess
        total_frac += p.fraction

    print(f"\n  Portfolio-weighted 1-seed champion rate: {portfolio_1seed*100:.1f}%"
          f" (target: >= 40%)")
    status = "PASS" if portfolio_1seed >= 0.40 else "FAIL"
    print(f"  Status: {status}")

    print(f"  Portfolio-weighted ESS/N: {portfolio_ess_weighted*100:.1f}%")

    # 3. Budget allocation
    budgets = compute_profile_budgets(206_000_000, profiles)
    print(f"\n  Budget allocation (206M total):")
    for p, b in budgets:
        print(f"    {p.name:>12s}: {b:>12,} ({p.fraction*100:.0f}%)")


def main() -> None:
    rng = np.random.default_rng(42)
    true_probs, champion_seeds, _ = make_synthetic_region(rng)

    print("Synthetic region: 32,768 brackets")
    print(f"  1-seed fraction: {(champion_seeds == 1).sum() / len(champion_seeds) * 100:.1f}%")
    print(f"  True prob mass on 1-seeds: "
          f"{true_probs[champion_seeds == 1].sum() * 100:.1f}%")

    evaluate_profile_set("CURRENT PROFILES", CURRENT_PROFILES, true_probs, champion_seeds)
    evaluate_profile_set("PROPOSED PROFILES", PROPOSED_PROFILES, true_probs, champion_seeds)

    # Summary comparison
    print(f"\n{'='*70}")
    print(f"  SUMMARY")
    print(f"{'='*70}")
    print(f"\n  Current min Hellinger: check above")
    print(f"  Proposed min Hellinger: check above")
    print(f"\n  Key changes:")
    print(f"    1. chalk: T=0.7 -> T=0.5 (sharper, boosts 1-seed rate)")
    print(f"    2. mild_upset -> mild_chaos: Remove mixing, use T=1.8 uniformly")
    print(f"       (eliminates compression with standard)")
    print(f"    3. cinderella: upset_T=4.0 -> 5.0, fraction 10% -> 15%")
    print(f"    4. chaos: base_T=1.5 -> 2.0, upset_T=3.5 -> 6.0 (wider gap)")
    print(f"    5. max_chaos: base_T=2.5 -> 4.0, upset_T=5.0 -> 8.0")
    print(f"    6. Budget: chalk 30%->25%, standard stays 30%, cinderella 10%->15%")


if __name__ == "__main__":
    main()
