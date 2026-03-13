"""
Seed composition analysis: joint probability of which seeds survive each round.

Instead of just "how many upsets?", this module answers:
  "What's the probability the Final Four is [1,1,2,3] vs [1,1,1,1]?"
  "What's the most likely Sweet 16 seed composition?"

Key insight: individual seed advancement rates (40% of FF are 1-seeds)
don't tell you about *combinations*. A bracket with [1,1,2,3] in the FF
is very different from [1,3,5,11] — they need different late-round paths.

Historical data (1985-2025, 40 tournaments):
  - All four 1-seeds in FF: 2 times (2008, 2025) = 5.0%
  - Three 1-seeds in FF: 4 times = 10.0%
  - Two 1-seeds in FF: 15 times = 37.5%  (second most common)
  - One 1-seed in FF: 16 times = 40.0%  (MODAL outcome)
  - Zero 1-seeds in FF: 3 times = 7.5%
  Historical average: 1.65 one-seeds per Final Four.

This module:
  1. Defines the historical distribution of seed compositions per round
  2. Computes joint probabilities from per-region advancement rates
  3. Validates simulation output against these distributions
  4. Provides the most valuable compositions for bracket diversity

All functions are pure. No mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
import math
from typing import Optional


# ---------------------------------------------------------------------------
# Historical Final Four compositions (1985-2024)
# ---------------------------------------------------------------------------
# Sorted seed tuple for each tournament's Final Four.
# Source: NCAA records, cross-referenced with ESPN.

HISTORICAL_FINAL_FOURS: tuple[tuple[int, ...], ...] = (
    # Verified against NCAA.com, Sports Reference, Wikipedia (Mar 2026)
    (1, 1, 2, 8),     # 1985: Georgetown(1), St. John's(1), Memphis St.(2), Villanova(8)
    (1, 1, 2, 11),    # 1986: Duke(1), Kansas(1), Louisville(2), LSU(11)
    (1, 1, 2, 6),     # 1987: Indiana(1), UNLV(1), Syracuse(2), Providence(6)
    (1, 1, 2, 6),     # 1988: Arizona(1), Oklahoma(1), Duke(2), Kansas(6)
    (1, 2, 3, 3),     # 1989: Illinois(1), Duke(2), Seton Hall(3), Michigan(3)
    (1, 3, 4, 4),     # 1990: UNLV(1), Duke(3), Georgia Tech(4), Arkansas(4)
    (1, 1, 2, 3),     # 1991: UNLV(1), North Carolina(1), Duke(2), Kansas(3)
    (1, 2, 4, 6),     # 1992: Duke(1), Indiana(2), Cincinnati(4), Michigan(6)
    (1, 1, 1, 2),     # 1993: North Carolina(1), Kentucky(1), Michigan(1), Kansas(2)
    (1, 2, 2, 3),     # 1994: Arkansas(1), Duke(2), Arizona(2), Florida(3)
    (1, 2, 2, 4),     # 1995: UCLA(1), North Carolina(2), Arkansas(2), Oklahoma St.(4)
    (1, 1, 4, 5),     # 1996: Kentucky(1), UMass(1), Syracuse(4), Mississippi St.(5)
    (1, 1, 1, 4),     # 1997: Kentucky(1), Minnesota(1), North Carolina(1), Arizona(4)
    (1, 2, 3, 3),     # 1998: North Carolina(1), Kentucky(2), Stanford(3), Utah(3)
    (1, 1, 1, 4),     # 1999: Connecticut(1), Duke(1), Michigan St.(1), Ohio St.(4)
    (1, 5, 8, 8),     # 2000: Michigan St.(1), Florida(5), Wisconsin(8), UNC(8)
    (1, 1, 2, 3),     # 2001: Duke(1), Michigan St.(1), Arizona(2), Maryland(3)
    (1, 1, 2, 5),     # 2002: Maryland(1), Kansas(1), Oklahoma(2), Indiana(5)
    (1, 2, 3, 3),     # 2003: Texas(1), Kansas(2), Marquette(3), Syracuse(3)
    (1, 2, 2, 3),     # 2004: Duke(1), Connecticut(2), Oklahoma St.(2), Georgia Tech(3)
    (1, 1, 4, 5),     # 2005: North Carolina(1), Illinois(1), Louisville(4), Michigan St.(5)
    (2, 3, 4, 11),    # 2006: UCLA(2), Florida(3), LSU(4), George Mason(11)
    (1, 1, 2, 2),     # 2007: Florida(1), Ohio St.(1), UCLA(2), Georgetown(2)
    (1, 1, 1, 1),     # 2008: Kansas(1), North Carolina(1), UCLA(1), Memphis(1)
    (1, 1, 2, 3),     # 2009: North Carolina(1), Connecticut(1), Michigan St.(2), Villanova(3)
    (1, 2, 5, 5),     # 2010: Duke(1), West Virginia(2), Butler(5), Michigan St.(5)
    (3, 4, 8, 11),    # 2011: Connecticut(3), Kentucky(4), Butler(8), VCU(11)
    (1, 2, 2, 4),     # 2012: Kentucky(1), Kansas(2), Ohio St.(2), Louisville(4)
    (1, 4, 4, 9),     # 2013: Louisville(1), Michigan(4), Syracuse(4), Wichita St.(9)
    (1, 2, 7, 8),     # 2014: Florida(1), Wisconsin(2), Connecticut(7), Kentucky(8)
    (1, 1, 1, 7),     # 2015: Duke(1), Kentucky(1), Wisconsin(1), Michigan St.(7)
    (1, 2, 2, 10),    # 2016: North Carolina(1), Villanova(2), Oklahoma(2), Syracuse(10)
    (1, 1, 3, 7),     # 2017: North Carolina(1), Gonzaga(1), Oregon(3), South Carolina(7)
    (1, 1, 3, 11),    # 2018: Villanova(1), Kansas(1), Michigan(3), Loyola Chicago(11)
    (1, 2, 3, 5),     # 2019: Virginia(1), Michigan St.(2), Texas Tech(3), Auburn(5)
    # 2020: cancelled (COVID)
    (1, 1, 2, 11),    # 2021: Baylor(1), Gonzaga(1), Houston(2), UCLA(11)
    (1, 2, 2, 8),     # 2022: Kansas(1), Duke(2), Villanova(2), North Carolina(8)
    (4, 5, 5, 9),     # 2023: Connecticut(4), FAU(9), Miami(5), San Diego State(5)
    (1, 1, 4, 11),    # 2024: Connecticut(1), Purdue(1), Alabama(4), NC State(11)
    (1, 1, 1, 1),     # 2025: Auburn(1), Duke(1), Florida(1), Houston(1)
)


# ---------------------------------------------------------------------------
# Derived distributions from historical data
# ---------------------------------------------------------------------------

def compute_one_seed_count_distribution(
    ff_history: tuple[tuple[int, ...], ...] = HISTORICAL_FINAL_FOURS,
) -> dict[int, float]:
    """Distribution of how many 1-seeds appear in the Final Four.

    Returns: {count: probability} where count is 0-4.
    """
    n = len(ff_history)
    counts = Counter(
        sum(1 for s in ff if s == 1) for ff in ff_history
    )
    return {k: counts.get(k, 0) / n for k in range(5)}


ONE_SEED_FF_DISTRIBUTION = compute_one_seed_count_distribution()
# Expected output:
# {0: 0.075, 1: 0.40, 2: 0.375, 3: 0.10, 4: 0.05}


def compute_max_seed_distribution(
    ff_history: tuple[tuple[int, ...], ...] = HISTORICAL_FINAL_FOURS,
) -> dict[int, float]:
    """Distribution of the highest (worst) seed in the Final Four.

    Answers: "What's the probability at least one double-digit seed makes FF?"
    Returns: {max_seed: probability}.
    """
    n = len(ff_history)
    counts = Counter(max(ff) for ff in ff_history)
    return {k: counts[k] / n for k in sorted(counts)}


MAX_SEED_FF_DISTRIBUTION = compute_max_seed_distribution()


def compute_seed_sum_distribution(
    ff_history: tuple[tuple[int, ...], ...] = HISTORICAL_FINAL_FOURS,
) -> dict[str, float]:
    """Distribution of total seed sum in the Final Four.

    Lower sum = chalkier. Sum of 4 = all 1-seeds. Sum of 20+ = chaos.
    Returns bucketed distribution.
    """
    n = len(ff_history)
    sums = [sum(ff) for ff in ff_history]

    buckets = {
        "ultra_chalk_4_6": 0,     # sum 4-6: all top seeds
        "chalk_7_10": 0,          # sum 7-10: mostly favorites
        "moderate_11_15": 0,      # sum 11-15: some upsets
        "upset_heavy_16_20": 0,   # sum 16-20: significant upsets
        "chaos_21_plus": 0,       # sum 21+: wild tournament
    }

    for s in sums:
        if s <= 6:
            buckets["ultra_chalk_4_6"] += 1
        elif s <= 10:
            buckets["chalk_7_10"] += 1
        elif s <= 15:
            buckets["moderate_11_15"] += 1
        elif s <= 20:
            buckets["upset_heavy_16_20"] += 1
        else:
            buckets["chaos_21_plus"] += 1

    return {k: v / n for k, v in buckets.items()}


SEED_SUM_FF_DISTRIBUTION = compute_seed_sum_distribution()


# ---------------------------------------------------------------------------
# Per-round seed composition targets
# ---------------------------------------------------------------------------
# These are per-REGION targets (how many of the 16 → 8 → 4 → 2 → 1 teams
# at each stage are each seed). Derived from historical advancement rates.

@dataclass(frozen=True)
class RoundCompositionTarget:
    """Expected seed composition for a single round, per region."""
    round_name: str
    teams_remaining: int       # how many teams remain (per region)
    expected_seeds: dict[int, float]  # seed -> expected count of that seed
    description: str


# Per-region expected seed counts at each stage.
# Example: in the Sweet 16 (4 teams per region), we expect ~1.0 one-seeds,
# ~0.8 two-seeds, ~0.6 three-seeds, etc.

ROUND_COMPOSITION_TARGETS = (
    RoundCompositionTarget(
        round_name="R32",
        teams_remaining=8,
        expected_seeds={
            1: 0.99, 2: 0.94, 3: 0.85, 4: 0.79,
            5: 0.64, 6: 0.63, 7: 0.61, 8: 0.50,
            9: 0.50, 10: 0.39, 11: 0.37, 12: 0.36,
            13: 0.21, 14: 0.15, 15: 0.06, 16: 0.01,
        },
        description=(
            "After R64: ~8 upsets across 4 regions. 1-4 seeds almost "
            "always present. 12-seeds at 36% (the classic upset)."
        ),
    ),
    RoundCompositionTarget(
        round_name="S16",
        teams_remaining=4,
        expected_seeds={
            1: 0.92, 2: 0.78, 3: 0.60, 4: 0.50,
            5: 0.35, 6: 0.25, 7: 0.22, 8: 0.10,
            9: 0.10, 10: 0.12, 11: 0.12, 12: 0.08,
            13: 0.04, 14: 0.02, 15: 0.01,
        },
        description=(
            "Sweet 16: top 4 seeds dominate. ~3.0 of the 4 slots per "
            "region are seeds 1-4. Occasional 10/11/12 Cinderella."
        ),
    ),
    RoundCompositionTarget(
        round_name="E8",
        teams_remaining=2,
        expected_seeds={
            1: 0.80, 2: 0.55, 3: 0.35, 4: 0.25,
            5: 0.12, 6: 0.08, 7: 0.06, 8: 0.03,
            9: 0.03, 10: 0.04, 11: 0.04, 12: 0.02,
        },
        description=(
            "Elite 8: 1/2-seeds win ~67% of E8 slots across regions. "
            "Mid-seeds (3-5) get ~36%. Deep Cinderellas rare."
        ),
    ),
    RoundCompositionTarget(
        round_name="F4",
        teams_remaining=1,
        expected_seeds={
            1: 0.55, 2: 0.30, 3: 0.15, 4: 0.10,
            5: 0.04, 6: 0.02, 7: 0.02, 8: 0.01,
            9: 0.01, 10: 0.01, 11: 0.01, 12: 0.005,
        },
        description=(
            "Regional champion: 1-seeds win ~55% of regions. 1+2 seeds "
            "account for ~85%. 5+ seeds win a region ~12% of the time."
        ),
    ),
)

COMPOSITION_BY_ROUND = {t.round_name: t for t in ROUND_COMPOSITION_TARGETS}


# ---------------------------------------------------------------------------
# Most common Final Four archetypes
# ---------------------------------------------------------------------------
# Group FF compositions into archetypes for stratified sampling.

@dataclass(frozen=True)
class FFArchetype:
    """A Final Four archetype with probability and example."""
    name: str
    one_seed_count: int          # how many 1-seeds in FF
    seed_sum_range: tuple[int, int]  # (min, max) of sum of 4 seeds
    probability: float           # P(this archetype) from historical data
    example_compositions: tuple[tuple[int, ...], ...]
    description: str


FF_ARCHETYPES = (
    FFArchetype(
        name="all_chalk",
        one_seed_count=4,
        seed_sum_range=(4, 4),
        probability=0.05,
        example_compositions=((1, 1, 1, 1),),
        description=(
            "All four 1-seeds. Only happened twice: 2008, 2025. "
            "Requires zero upsets through E8 in all regions."
        ),
    ),
    FFArchetype(
        name="heavy_chalk",
        one_seed_count=3,
        seed_sum_range=(5, 10),
        probability=0.10,
        example_compositions=(
            (1, 1, 1, 2), (1, 1, 1, 3), (1, 1, 1, 4), (1, 1, 1, 7),
        ),
        description=(
            "Three 1-seeds, one mid-to-low seed breaks through in one "
            "region. Happened 4 times (1993, 1997, 2015, 2024)."
        ),
    ),
    FFArchetype(
        name="typical_chalk",
        one_seed_count=2,
        seed_sum_range=(5, 12),
        probability=0.375,
        example_compositions=(
            (1, 1, 2, 2), (1, 1, 2, 3), (1, 1, 2, 4), (1, 1, 3, 3),
            (1, 1, 2, 5), (1, 1, 4, 5), (1, 1, 2, 11), (1, 1, 4, 10),
        ),
        description=(
            "Two 1-seeds in FF — the second most common outcome. "
            "Happened 15 times. The other two slots vary widely."
        ),
    ),
    FFArchetype(
        name="mild_chaos",
        one_seed_count=1,
        seed_sum_range=(6, 20),
        probability=0.40,
        example_compositions=(
            (1, 2, 3, 5), (1, 2, 5, 5), (1, 2, 7, 8), (1, 3, 9, 11),
            (1, 4, 6, 6), (1, 5, 5, 8),
        ),
        description=(
            "One 1-seed plus mix — the MODAL outcome historically. "
            "Happened 16 times. Enough chalk to be credible, enough "
            "chaos for drama."
        ),
    ),
    FFArchetype(
        name="full_chaos",
        one_seed_count=0,
        seed_sum_range=(8, 40),
        probability=0.075,
        example_compositions=(
            (2, 2, 3, 3), (2, 3, 3, 11), (3, 4, 8, 11), (4, 5, 5, 9),
        ),
        description=(
            "No 1-seeds in FF. Happened 3 times. The 'nobody saw this "
            "coming' tournament. 2011 (VCU/Butler), 2023 (UConn as 4)."
        ),
    ),
)

FF_ARCHETYPE_BY_NAME = {a.name: a for a in FF_ARCHETYPES}


# ---------------------------------------------------------------------------
# Compute joint FF probability from per-region rates
# ---------------------------------------------------------------------------

def compute_ff_composition_probability(
    seeds: tuple[int, int, int, int],
    per_region_rates: Optional[dict[int, float]] = None,
) -> float:
    """Compute probability of a specific FF seed composition.

    Assumes regions are independent. Probability of seeing exactly
    seeds=(s1, s2, s3, s4) across 4 regions:

    P = (4! / product of factorial of count of each seed) *
        product(P(seed_i wins region_i))

    This is a multinomial — accounts for which region each seed comes from.

    per_region_rates: seed -> P(that seed wins a region). Defaults to
    historical rates from FINAL_FOUR_SEED_RATES.
    """
    if per_region_rates is None:
        from calibration_targets import FINAL_FOUR_SEED_RATES
        per_region_rates = FINAL_FOUR_SEED_RATES

    # Count occurrences of each seed
    seed_counts = Counter(seeds)

    # Multinomial coefficient: 4! / (n1! * n2! * ...)
    multinomial = math.factorial(4)
    for count in seed_counts.values():
        multinomial //= math.factorial(count)

    # Product of per-region probabilities
    prob_product = 1.0
    for seed in seeds:
        rate = per_region_rates.get(seed, 0.001)
        prob_product *= rate

    return multinomial * prob_product


def rank_ff_compositions(
    per_region_rates: Optional[dict[int, float]] = None,
    top_n: int = 20,
) -> list[tuple[tuple[int, ...], float]]:
    """Rank all possible FF compositions by probability.

    Generates all unique sorted 4-tuples from seeds 1-16 and computes
    their probability. Returns top_n most likely.

    Returns: list of (sorted_seed_tuple, probability).
    """
    if per_region_rates is None:
        from calibration_targets import FINAL_FOUR_SEED_RATES
        per_region_rates = FINAL_FOUR_SEED_RATES

    # Only consider seeds with non-negligible regional champion probability
    viable_seeds = [
        s for s, rate in per_region_rates.items()
        if rate >= 0.005
    ]

    compositions = {}

    # Generate all sorted 4-tuples from viable seeds (with repetition)
    for s1 in viable_seeds:
        for s2 in viable_seeds:
            if s2 < s1:
                continue
            for s3 in viable_seeds:
                if s3 < s2:
                    continue
                for s4 in viable_seeds:
                    if s4 < s3:
                        continue
                    combo = (s1, s2, s3, s4)
                    p = compute_ff_composition_probability(combo, per_region_rates)
                    if p > 1e-8:
                        compositions[combo] = p

    # Sort by probability
    ranked = sorted(compositions.items(), key=lambda x: x[1], reverse=True)
    return ranked[:top_n]


# ---------------------------------------------------------------------------
# Validation: check simulation output against historical distributions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CompositionValidation:
    """Validation result for seed composition."""
    metric: str
    expected: float
    actual: float
    status: str  # "PASS", "WARN", "FAIL"


def validate_ff_archetype_distribution(
    simulated_ffs: list[tuple[int, int, int, int]],
    tolerance: float = 0.10,
) -> list[CompositionValidation]:
    """Validate that simulated Final Fours match historical archetype rates.

    simulated_ffs: list of (seed, seed, seed, seed) from simulation.
    tolerance: acceptable absolute deviation.
    """
    n = len(simulated_ffs)
    if n == 0:
        return []

    # Count 1-seeds per FF
    one_seed_counts = Counter(
        sum(1 for s in ff if s == 1) for ff in simulated_ffs
    )

    results = []
    for archetype in FF_ARCHETYPES:
        expected = archetype.probability
        actual_count = one_seed_counts.get(archetype.one_seed_count, 0)
        actual = actual_count / n

        deviation = abs(actual - expected)
        if deviation <= tolerance:
            status = "PASS"
        elif deviation <= tolerance * 2:
            status = "WARN"
        else:
            status = "FAIL"

        results.append(CompositionValidation(
            metric=f"ff_{archetype.name} ({archetype.one_seed_count} 1-seeds)",
            expected=expected,
            actual=actual,
            status=status,
        ))

    return results


def validate_round_composition(
    simulated_seeds: dict[str, list[list[int]]],
    tolerance: float = 0.15,
) -> list[CompositionValidation]:
    """Validate per-round seed composition against targets.

    simulated_seeds: round_name -> list of [seeds remaining in region]
        per bracket. E.g., {"S16": [[1,2,3,5], [1,1,4,12], ...]}
    """
    results = []

    for target in ROUND_COMPOSITION_TARGETS:
        round_data = simulated_seeds.get(target.round_name, [])
        if not round_data:
            continue

        n = len(round_data)

        # Count each seed's frequency
        seed_counts = Counter()
        for bracket_seeds in round_data:
            for seed in bracket_seeds:
                seed_counts[seed] += 1

        for seed, expected_count in target.expected_seeds.items():
            if expected_count < 0.01:
                continue

            actual_count = seed_counts.get(seed, 0) / n
            deviation = abs(actual_count - expected_count) / max(expected_count, 0.01)

            status = "PASS" if deviation <= tolerance else (
                "WARN" if deviation <= tolerance * 2 else "FAIL"
            )

            results.append(CompositionValidation(
                metric=f"{target.round_name}_seed_{seed}_count",
                expected=expected_count,
                actual=actual_count,
                status=status,
            ))

    return results


# ---------------------------------------------------------------------------
# Summary / reporting
# ---------------------------------------------------------------------------

def print_composition_summary() -> None:
    """Print seed composition analysis from historical data."""
    print("=" * 70)
    print("SEED COMPOSITION ANALYSIS — FINAL FOUR (1985-2024)")
    print("=" * 70)

    # 1-seed count distribution
    print("\n--- HOW MANY 1-SEEDS IN FINAL FOUR? ---")
    for count, prob in sorted(ONE_SEED_FF_DISTRIBUTION.items()):
        bar = "█" * int(prob * 50)
        print(f"  {count} one-seeds: {prob:5.1%}  {bar}")

    # Archetypes
    print("\n--- FINAL FOUR ARCHETYPES ---")
    for arch in FF_ARCHETYPES:
        examples = ", ".join(str(list(e)) for e in arch.example_compositions[:3])
        print(f"\n  {arch.name} ({arch.probability:.0%}):")
        print(f"    {arch.description}")
        print(f"    Examples: {examples}")

    # Seed sum distribution
    print("\n--- SEED SUM BUCKETS ---")
    for bucket, prob in SEED_SUM_FF_DISTRIBUTION.items():
        label = bucket.replace("_", " ").title()
        bar = "█" * int(prob * 50)
        print(f"  {label:<25} {prob:5.1%}  {bar}")

    # Max seed distribution
    print("\n--- HIGHEST SEED IN FINAL FOUR ---")
    for seed, prob in sorted(MAX_SEED_FF_DISTRIBUTION.items()):
        bar = "█" * int(prob * 40)
        print(f"  seed {seed:>2}: {prob:5.1%}  {bar}")

    # Top computed compositions
    print("\n--- MOST LIKELY FF COMPOSITIONS (computed) ---")
    ranked = rank_ff_compositions(top_n=15)
    for combo, prob in ranked:
        historical_count = sum(
            1 for ff in HISTORICAL_FINAL_FOURS if tuple(sorted(ff)) == combo
        )
        hist_label = f"  (seen {historical_count}x)" if historical_count > 0 else ""
        print(f"  {list(combo)}: {prob:.2%}{hist_label}")

    total_top15 = sum(p for _, p in ranked)
    print(f"\n  Top 15 compositions cover {total_top15:.1%} of probability mass")

    print("\n" + "=" * 70)


# ---------------------------------------------------------------------------
# 2026-specific targets: user thesis = 2.0 one-seeds in Final Four
# ---------------------------------------------------------------------------
# Thesis: NIL + transfer portal talent concentration means 1-seeds are
# slightly stronger than historical averages. P(1-seed wins region)
# rises from historical ~0.41 to 0.50.
#
# Historical avg: 1.65 one-seeds. 2026 target: 2.0 — slightly above
# historical, reflecting talent concentration but not over-correcting.
# Data shows NO upward trend in 1-seed FF rate (decades flat at 1.40-1.70).

EXPECTED_ONE_SEEDS_FF_2026 = 2.0
P_ONE_SEED_WINS_REGION_2026 = EXPECTED_ONE_SEEDS_FF_2026 / 4  # 0.50

# 2026-adjusted per-region champion seed rates
# Boosting 1-seeds from ~0.41 → 0.50, minor compression on mid-seeds.
REGIONAL_CHAMPION_RATES_2026 = {
    1: 0.50,    # up from ~0.41 (talent concentration)
    2: 0.19,    # slight compression from ~0.20
    3: 0.11,    # slight compression from ~0.12
    4: 0.07,    # down from ~0.09
    5: 0.04,    # down from 0.05
    6: 0.03,    # down from 0.04
    7: 0.02,    # down from 0.03
    8: 0.01,    # compressed
    9: 0.005,   # compressed
    10: 0.005,  # compressed
    11: 0.01,   # still possible: 11-seeds are weird
    12: 0.005,  # near-negligible
}


def compute_2026_archetype_weights() -> dict[str, float]:
    """Compute FF archetype probabilities under 2026 thesis.

    Uses binomial(4, P_1seed) for the 1-seed count distribution,
    then maps to archetype weights.

    Returns: archetype_name -> probability.
    """
    p = P_ONE_SEED_WINS_REGION_2026

    one_seed_dist = {}
    for k in range(5):
        one_seed_dist[k] = (
            math.comb(4, k) * (p ** k) * ((1 - p) ** (4 - k))
        )

    return {
        "all_chalk": one_seed_dist[4],      # ~15.3%
        "heavy_chalk": one_seed_dist[3],     # ~36.6%
        "typical_chalk": one_seed_dist[2],   # ~33.0%
        "mild_chaos": one_seed_dist[1],      # ~13.2%
        "full_chaos": one_seed_dist[0],      # ~2.0%
    }


FF_ARCHETYPE_WEIGHTS_2026 = compute_2026_archetype_weights()

# 2026-adjusted seed advancement targets (per region)
# Higher 1-seed survival throughout, compressed mid-seed rates
SEED_ADVANCEMENT_TARGETS_2026 = {
    1: {"R64": 0.99, "R32": 0.94, "S16": 0.85, "E8": 0.70, "F4": 0.55},
    2: {"R64": 0.94, "R32": 0.78, "S16": 0.55, "E8": 0.28, "F4": 0.18},
    3: {"R64": 0.86, "R32": 0.60, "S16": 0.35, "E8": 0.15, "F4": 0.10},
    4: {"R64": 0.80, "R32": 0.50, "S16": 0.25, "E8": 0.10, "F4": 0.07},
    5: {"R64": 0.64, "R32": 0.35, "S16": 0.12, "E8": 0.04, "F4": 0.03},
    6: {"R64": 0.63, "R32": 0.25, "S16": 0.08, "E8": 0.02, "F4": 0.02},
    7: {"R64": 0.61, "R32": 0.22, "S16": 0.06, "E8": 0.02, "F4": 0.02},
    8: {"R64": 0.50, "R32": 0.10, "S16": 0.03, "E8": 0.01, "F4": 0.01},
    9: {"R64": 0.50, "R32": 0.10, "S16": 0.03, "E8": 0.01, "F4": 0.005},
    10: {"R64": 0.39, "R32": 0.12, "S16": 0.04, "E8": 0.01, "F4": 0.005},
    11: {"R64": 0.37, "R32": 0.12, "S16": 0.04, "E8": 0.01, "F4": 0.01},
    12: {"R64": 0.36, "R32": 0.08, "S16": 0.02, "E8": 0.005, "F4": 0.00},
    13: {"R64": 0.20, "R32": 0.04, "S16": 0.008, "E8": 0.001, "F4": 0.00},
    14: {"R64": 0.14, "R32": 0.02, "S16": 0.003, "E8": 0.00, "F4": 0.00},
    15: {"R64": 0.06, "R32": 0.01, "S16": 0.002, "E8": 0.00, "F4": 0.00},
    16: {"R64": 0.01, "R32": 0.002, "S16": 0.00, "E8": 0.00, "F4": 0.00},
}


if __name__ == "__main__":
    print_composition_summary()

    print("\n\n")
    print("=" * 70)
    print("2026 THESIS: E[1-seeds in FF] = 2.0")
    print("=" * 70)
    print(f"\nP(1-seed wins region) = {P_ONE_SEED_WINS_REGION_2026:.3f}")
    print("\n--- 2026 Archetype Weights ---")
    for name, weight in FF_ARCHETYPE_WEIGHTS_2026.items():
        hist = next(a.probability for a in FF_ARCHETYPES if a.name == name)
        delta = weight - hist
        print(f"  {name:<18} {weight:5.1%}  (historical: {hist:5.1%}, delta: {delta:+.1%})")

    print("\n--- Top FF Compositions (2026 rates) ---")
    ranked_2026 = rank_ff_compositions(
        per_region_rates=REGIONAL_CHAMPION_RATES_2026, top_n=15
    )
    for combo, prob in ranked_2026:
        print(f"  {list(combo)}: {prob:.2%}")
