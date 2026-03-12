"""
Stratified importance sampling for bracket generation.

Defines "worlds" -- distinct tournament scenarios characterized by
(R1 upset count, champion seed tier). Allocates the 3M-per-region
bracket budget across worlds using Neyman allocation.

Key insight: naive Monte Carlo would produce ~20K brackets with a
12-seed champion out of 12M. That's too sparse for reliable statistics.
Stratified sampling guarantees 50K brackets per possible champion seed.

All functions are pure. No mutation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class World:
    """A distinct tournament scenario for stratified sampling."""
    id: int
    r64_upset_count: int      # 0-12 upsets in R64 (per region: 0-8)
    champion_seed_tier: str   # "top" (1-2), "mid" (3-5), "low" (6-8), "cinderella" (9+)
    prior_probability: float  # P(this world occurs) based on historical data
    description: str


@dataclass(frozen=True)
class StratumAllocation:
    """Budget allocation for a single world/stratum."""
    world: World
    bracket_count: int        # number of brackets to generate for this world
    weight: float             # importance weight = P(world) / Q(world) where Q is sampling distribution


# Historical priors for R64 upset counts (per region, 8 games)
# Derived from calibration_targets.py MOST_LIKELY_R64_COMPOSITION
R64_UPSET_COUNT_PRIORS = {
    0: 0.02,   # all chalk -- extremely rare
    1: 0.08,   # one upset (e.g., just an 8v9)
    2: 0.20,   # two upsets -- common (the 5v12 + 8v9 combo)
    3: 0.30,   # three upsets -- most likely (modal outcome)
    4: 0.22,   # four upsets -- still common
    5: 0.12,   # five upsets -- getting chaotic
    6: 0.04,   # six upsets -- rare
    7: 0.015,  # seven upsets -- very rare
    8: 0.005,  # all upsets -- near impossible
}

# Champion seed tier priors (per region)
CHAMPION_SEED_TIER_PRIORS = {
    "top": 0.60,         # 1-2 seeds win region ~60%
    "mid": 0.28,         # 3-5 seeds win ~28%
    "low": 0.10,         # 6-8 seeds win ~10%
    "cinderella": 0.02,  # 9+ seeds win ~2%
}

SEED_TO_TIER = {}
for s in range(1, 3):
    SEED_TO_TIER[s] = "top"
for s in range(3, 6):
    SEED_TO_TIER[s] = "mid"
for s in range(6, 9):
    SEED_TO_TIER[s] = "low"
for s in range(9, 17):
    SEED_TO_TIER[s] = "cinderella"


def build_worlds() -> tuple[World, ...]:
    """Generate all possible worlds (R64 upset count x champion seed tier).

    Returns tuple of World objects with prior probabilities.
    Total worlds: 9 upset counts x 4 seed tiers = 36.
    """
    worlds = []
    world_id = 0

    for upset_count, upset_prior in R64_UPSET_COUNT_PRIORS.items():
        for tier, tier_prior in CHAMPION_SEED_TIER_PRIORS.items():
            prior = upset_prior * tier_prior  # assume independence
            worlds.append(World(
                id=world_id,
                r64_upset_count=upset_count,
                champion_seed_tier=tier,
                prior_probability=prior,
                description=f"{upset_count} R64 upsets, {tier}-seed champion",
            ))
            world_id += 1

    return tuple(worlds)


ALL_WORLDS = build_worlds()


def neyman_allocation(
    worlds: tuple[World, ...],
    total_budget: int,
    min_per_world: int = 1000,
) -> tuple[StratumAllocation, ...]:
    """Allocate bracket budget across worlds using Neyman allocation.

    Budget for world_i is proportional to sqrt(P(world_i)).

    This over-samples rare worlds (like cinderella champions) relative to
    their probability, ensuring we have enough brackets in every scenario
    for reliable statistics.

    Guarantees at least min_per_world brackets per stratum.
    """
    # Compute sqrt(P) for each world
    sqrt_priors = tuple(math.sqrt(w.prior_probability) for w in worlds)
    total_sqrt = sum(sqrt_priors)

    # Initial allocation proportional to sqrt(P)
    raw_allocations = []
    for w, sq in zip(worlds, sqrt_priors):
        raw_count = max(min_per_world, int(total_budget * sq / total_sqrt))
        raw_allocations.append(raw_count)

    # Adjust to hit exact budget
    allocated = sum(raw_allocations)
    if allocated < total_budget:
        # Distribute remainder to highest-prior worlds
        remainder = total_budget - allocated
        sorted_indices = sorted(range(len(worlds)), key=lambda i: worlds[i].prior_probability, reverse=True)
        for i in range(remainder):
            raw_allocations[sorted_indices[i % len(sorted_indices)]] += 1
    elif allocated > total_budget:
        # Trim from lowest-prior worlds (but respect minimum)
        excess = allocated - total_budget
        sorted_indices = sorted(range(len(worlds)), key=lambda i: worlds[i].prior_probability)
        for i in range(len(sorted_indices)):
            if excess <= 0:
                break
            idx = sorted_indices[i]
            can_trim = raw_allocations[idx] - min_per_world
            trim = min(can_trim, excess)
            if trim > 0:
                raw_allocations[idx] -= trim
                excess -= trim

    # Compute importance weights
    allocations = []
    for w, count in zip(worlds, raw_allocations):
        q_world = count / total_budget  # sampling probability
        weight = w.prior_probability / max(q_world, 1e-12)
        allocations.append(StratumAllocation(
            world=w,
            bracket_count=count,
            weight=weight,
        ))

    return tuple(allocations)


def allocate_regional_budget(
    budget_per_region: int = 51_500_000,
    min_per_world: int = 10_000,
) -> tuple[StratumAllocation, ...]:
    """Allocate 51.5M brackets per region across all worlds.

    Returns allocation plan for one region.
    Total across 4 regions = 206M brackets.
    """
    return neyman_allocation(ALL_WORLDS, budget_per_region, min_per_world)


def get_champion_seed_guarantee(
    allocations: tuple[StratumAllocation, ...],
) -> dict[str, int]:
    """Check minimum bracket count per champion seed tier.

    Returns dict of tier -> total bracket count.
    Spec requires 50K minimum per possible champion seed.
    """
    tier_counts = {"top": 0, "mid": 0, "low": 0, "cinderella": 0}
    for alloc in allocations:
        tier = alloc.world.champion_seed_tier
        tier_counts[tier] += alloc.bracket_count
    return tier_counts


def validate_allocation(
    allocations: tuple[StratumAllocation, ...],
    total_budget: int = 3_000_000,
    min_champion_guarantee: int = 50_000,
) -> tuple[bool, list[str]]:
    """Validate that allocation meets all constraints.

    Returns (is_valid, list of issues).
    """
    issues = []

    # Check total
    actual_total = sum(a.bracket_count for a in allocations)
    if actual_total != total_budget:
        issues.append(f"Total brackets {actual_total} != budget {total_budget}")

    # Check champion guarantee
    tier_counts = get_champion_seed_guarantee(allocations)
    for tier, count in tier_counts.items():
        if count < min_champion_guarantee:
            issues.append(f"Champion tier '{tier}' has {count} brackets < {min_champion_guarantee} minimum")

    # Check weights are positive
    for alloc in allocations:
        if alloc.weight <= 0:
            issues.append(f"World {alloc.world.id} has non-positive weight {alloc.weight}")

    return len(issues) == 0, issues


def print_allocation_summary(allocations: tuple[StratumAllocation, ...]) -> None:
    """Print a formatted allocation summary."""
    total = sum(a.bracket_count for a in allocations)

    print("=" * 80)
    print(f"STRATIFIED SAMPLING ALLOCATION -- {total:,} brackets")
    print("=" * 80)
    print(f"{'WORLD':<45} {'COUNT':>10} {'WEIGHT':>8} {'PRIOR':>8}")
    print("-" * 80)

    for alloc in sorted(allocations, key=lambda a: a.bracket_count, reverse=True)[:20]:
        w = alloc.world
        print(f"  {w.description:<43} {alloc.bracket_count:>10,} {alloc.weight:>8.3f} {w.prior_probability:>8.4f}")

    if len(allocations) > 20:
        print(f"  ... and {len(allocations) - 20} more worlds")

    tier_counts = get_champion_seed_guarantee(allocations)
    print(f"\nChampion seed guarantees:")
    for tier, count in tier_counts.items():
        status = "PASS" if count >= 50_000 else "FAIL"
        print(f"  {status} {tier}: {count:,} brackets")

    is_valid, issues = validate_allocation(allocations, total)
    print(f"\nValidation: {'PASS' if is_valid else 'FAIL'}")
    for issue in issues:
        print(f"  FAIL {issue}")


if __name__ == "__main__":
    allocations = allocate_regional_budget()
    print_allocation_summary(allocations)
