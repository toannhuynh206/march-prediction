"""
Vectorized bracket simulation engine.

Generates regional brackets using NumPy for speed. Each bracket is a
15-bit integer encoding game outcomes within a region.

Flow:
  1. Receive probability matrix for a region
  2. For each stratum (world), generate N brackets matching that world's constraints
  3. Pack results as (bracket_int, weight, stratum_id) tuples
  4. Return for bulk database insertion

Uses np.random.default_rng() per spec. Memory-efficient: generates
random numbers per-round, not all upfront.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from math_primitives import (
    R64_MATCHUPS,
    PARENT_GAMES,
    get_game_bit,
    get_regional_winner_seed,
)
from round_probability import UPSET_BOOST_BY_SEED_GAP
from stratifier import StratumAllocation, SEED_TO_TIER
from portfolio_strategy import (
    apply_temperature,
    ClusterBudget,
    allocate_cluster_budgets,
    TEMPERATURE_BY_ROUND,
)

# Pre-built lookup: seed gap -> logit boost (vectorized access)
_BOOST_LOOKUP = np.zeros(16, dtype=np.float32)
for _gap, _boost in UPSET_BOOST_BY_SEED_GAP.items():
    if _gap < 16:
        _BOOST_LOOKUP[_gap] = _boost


@dataclass(frozen=True)
class SimulatedBracket:
    """A single simulated regional bracket."""
    bracket_int: int       # 15-bit packed result
    weight: float          # importance sampling weight
    stratum_id: int        # which world this belongs to
    champion_seed: int     # seed that won the region
    upset_count_r64: int   # number of R64 upsets


def simulate_r64_games(
    prob_matrix: dict[tuple[int, int], float],
    n_brackets: int,
    rng: np.random.Generator,
    r64_tau: float = 1.0,
) -> np.ndarray:
    """Simulate R64 outcomes for n_brackets at once.

    Returns (n_brackets, 8) array of booleans.
    True = upset (lower seed wins), False = favorite wins.

    r64_tau: temperature for R64 round. <1 = concentrate on favorites,
    >1 = soften toward 50/50 (more upsets).
    """
    results = np.empty((n_brackets, 8), dtype=np.bool_)

    for g, (high_seed, low_seed) in enumerate(R64_MATCHUPS):
        p_fav = prob_matrix.get((high_seed, low_seed), 0.5)
        p_fav = apply_temperature(p_fav, r64_tau)
        # Random draw: upset if random > p_fav
        results[:, g] = rng.random(n_brackets) > p_fav

    return results


def get_r64_winners(r64_outcomes: np.ndarray) -> np.ndarray:
    """Convert R64 outcome booleans to winner seeds.

    Returns (n_brackets, 8) array of winner seed numbers.
    """
    n = r64_outcomes.shape[0]
    winners = np.empty((n, 8), dtype=np.int8)

    for g, (high_seed, low_seed) in enumerate(R64_MATCHUPS):
        winners[:, g] = np.where(r64_outcomes[:, g], low_seed, high_seed)

    return winners


def simulate_later_rounds(
    r64_winners: np.ndarray,
    prob_matrix: dict[tuple[int, int], float],
    rng: np.random.Generator,
    temp_schedule: dict[str, float] | None = None,
    apply_survivor_bias: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Simulate R32 through E8 given R64 winners.

    Returns (game_outcomes, game_winners, champion_seeds).
    game_outcomes is (n, 15) boolean array.
    game_winners is (n, 15) int8 array of seeds.
    champion_seeds is (n,) int8 array of region winners.

    temp_schedule: optional {round_name: tau} for per-round temperature.
    If None, uses tau=1.0 (no temperature adjustment).
    apply_survivor_bias: if True, upset winners get a small logit boost
    in their next game (from UPSET_BOOST_BY_SEED_GAP).
    """
    n = r64_winners.shape[0]

    # game_winners tracks the seed that won each game
    # game_losers tracks the seed that lost (for survivor bias)
    game_winners = np.empty((n, 15), dtype=np.int8)
    game_outcomes = np.empty((n, 15), dtype=np.bool_)
    game_losers = np.empty((n, 15), dtype=np.int8)

    # R64 results already known
    game_winners[:, :8] = r64_winners

    # R64 losers: matchup is (high_seed, low_seed), loser = other side
    for g, (high_seed, low_seed) in enumerate(R64_MATCHUPS):
        game_losers[:, g] = np.where(
            r64_winners[:, g] == high_seed, low_seed, high_seed,
        ).astype(np.int8)

    # Parent game mapping: game -> (parent_a, parent_b, round_name)
    parent_pairs = [
        (0, 1, "R32"), (2, 3, "R32"), (4, 5, "R32"), (6, 7, "R32"),
        (8, 9, "S16"), (10, 11, "S16"),
        (12, 13, "E8"),
    ]

    for i, (pa, pb, round_name) in enumerate(parent_pairs):
        game_idx = 8 + i
        seeds_a = game_winners[:, pa]
        seeds_b = game_winners[:, pb]

        # For each bracket, look up P(higher seed wins)
        high_seeds = np.minimum(seeds_a, seeds_b)
        low_seeds = np.maximum(seeds_a, seeds_b)

        # Get temperature for this round
        tau = 1.0
        if temp_schedule is not None:
            tau = temp_schedule.get(round_name, 1.0)

        # Build 17x17 lookup array for vectorized indexing
        unique_matchups = set(zip(high_seeds.tolist(), low_seeds.tolist()))
        prob_lookup = np.full((17, 17), 0.5, dtype=np.float32)
        for hs, ls in unique_matchups:
            base_p = prob_matrix.get((hs, ls), 0.5)
            prob_lookup[hs, ls] = apply_temperature(base_p, tau)

        probs = prob_lookup[high_seeds, low_seeds]

        # Survivor bias: boost upset winners' probability in their next game
        if apply_survivor_bias:
            losers_a = game_losers[:, pa]
            losers_b = game_losers[:, pb]

            # Seed gap (positive only when the team was an upset winner)
            gap_a = np.clip(seeds_a.astype(np.int16) - losers_a.astype(np.int16), 0, 15)
            gap_b = np.clip(seeds_b.astype(np.int16) - losers_b.astype(np.int16), 0, 15)

            boost_a = _BOOST_LOOKUP[gap_a]
            boost_b = _BOOST_LOOKUP[gap_b]

            # Apply in logit space: probs = P(high_seed wins)
            # Determine which side (a or b) is the high seed
            a_is_high = (seeds_a <= seeds_b)
            high_boost = np.where(a_is_high, boost_a, boost_b)
            low_boost = np.where(a_is_high, boost_b, boost_a)

            net_boost = high_boost - low_boost
            has_boost = net_boost != 0.0

            if np.any(has_boost):
                clamped = np.clip(probs, 1e-6, 1.0 - 1e-6)
                logit_p = np.log(clamped / (1.0 - clamped))
                logit_p += net_boost
                adjusted = 1.0 / (1.0 + np.exp(-logit_p))
                probs = np.where(has_boost, adjusted, probs)

        # Simulate: upset if random > p_fav
        is_upset = rng.random(n) > probs
        game_outcomes[:, game_idx] = is_upset

        # Winner is low_seed if upset, high_seed otherwise
        game_winners[:, game_idx] = np.where(is_upset, low_seeds, high_seeds)
        game_losers[:, game_idx] = np.where(is_upset, high_seeds, low_seeds)

    champion_seeds = game_winners[:, 14]
    return game_outcomes, game_winners, champion_seeds


def pack_regional_bracket(r64_outcomes: np.ndarray, later_outcomes: np.ndarray) -> np.ndarray:
    """Pack game outcomes into 15-bit integers.

    Bit i = 1 means upset in game i, 0 means favorite won.
    Returns array of int32.
    """
    n = r64_outcomes.shape[0]
    packed = np.zeros(n, dtype=np.int32)

    # R64 bits (0-7)
    for g in range(8):
        packed |= r64_outcomes[:, g].astype(np.int32) << g

    # Later round bits (8-14)
    for g in range(8, 15):
        packed |= later_outcomes[:, g].astype(np.int32) << g

    return packed


def count_r64_upsets(r64_outcomes: np.ndarray) -> np.ndarray:
    """Count R64 upsets per bracket. Returns (n,) int array."""
    return r64_outcomes.astype(np.int32).sum(axis=1)


# ---------------------------------------------------------------------------
# X-Factor: mutation rate (6% default)
# ---------------------------------------------------------------------------
# Any game where the base probability is in the 0.40-0.60 range (coin flip)
# has a chance of being randomly flipped. This models the chaos factor:
# buzzer beaters, bad ref calls, off nights. The mutation doesn't change
# locks (1v16) — only competitive games where anything can happen.

MUTATION_P_LOW = 0.40    # games with P below this are "locks" — no mutation
MUTATION_P_HIGH = 0.60   # games with P above this are also locks


def apply_mutation(
    outcomes: np.ndarray,
    prob_matrix: dict[tuple[int, int], float],
    rng: np.random.Generator,
    mutation_rate: float = 0.06,
    round_name: str = "R64",
) -> np.ndarray:
    """Apply X-factor mutation to R64 game outcomes.

    For each game where base P is in [0.40, 0.60], randomly flip the outcome
    with probability = mutation_rate. This injects chaos into coin-flip games.

    Returns new array. Does not mutate input.
    """
    mutated = outcomes.copy()
    n = outcomes.shape[0]

    for g, (high_seed, low_seed) in enumerate(R64_MATCHUPS):
        base_p = prob_matrix.get((high_seed, low_seed), 0.5)
        if MUTATION_P_LOW <= base_p <= MUTATION_P_HIGH:
            # This is a coin-flip game — eligible for mutation
            flip_mask = rng.random(n) < mutation_rate
            mutated[:, g] = np.where(flip_mask, ~outcomes[:, g], outcomes[:, g])

    return mutated


def apply_mutation_later_rounds(
    later_outcomes: np.ndarray,
    game_winners: np.ndarray,
    prob_matrix: dict[tuple[int, int], float],
    rng: np.random.Generator,
    mutation_rate: float = 0.06,
) -> np.ndarray:
    """Apply X-factor mutation to later-round game outcomes.

    Only flips games where the actual matchup probability falls in the
    coin-flip range [0.40, 0.60].

    Returns new array. Does not mutate input.
    """
    mutated = later_outcomes.copy()
    n = later_outcomes.shape[0]

    # Games 8-14 are later rounds
    for game_idx in range(8, 15):
        # Look up the matchup seeds for each bracket
        parent_pairs = [(0, 1), (2, 3), (4, 5), (6, 7),
                        (8, 9), (10, 11),
                        (12, 13)]
        pa, pb = parent_pairs[game_idx - 8]

        seeds_a = game_winners[:, pa]
        seeds_b = game_winners[:, pb]
        high_seeds = np.minimum(seeds_a, seeds_b)
        low_seeds = np.maximum(seeds_a, seeds_b)

        # Vectorized: build lookup, mask coin-flip games, batch-flip
        prob_lookup = np.full((17, 17), 0.5, dtype=np.float32)
        for (hs, ls), p in prob_matrix.items():
            prob_lookup[hs, ls] = p
        base_probs = prob_lookup[high_seeds, low_seeds]

        coin_flip_mask = (base_probs >= MUTATION_P_LOW) & (base_probs <= MUTATION_P_HIGH)
        flip_mask = coin_flip_mask & (rng.random(n) < mutation_rate)
        mutated[flip_mask, game_idx] = ~later_outcomes[flip_mask, game_idx]

    return mutated


def _recompute_winners_from_outcomes(
    r64_winners: np.ndarray,
    later_outcomes: np.ndarray,
    prob_matrix: dict[tuple[int, int], float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Recompute game winners after mutation flipped some outcomes.

    Returns (later_outcomes, game_winners, champion_seeds).
    """
    n = r64_winners.shape[0]
    game_winners = np.empty((n, 15), dtype=np.int8)
    game_winners[:, :8] = r64_winners

    parent_pairs = [(0, 1), (2, 3), (4, 5), (6, 7),
                    (8, 9), (10, 11),
                    (12, 13)]

    for i, (pa, pb) in enumerate(parent_pairs):
        game_idx = 8 + i
        seeds_a = game_winners[:, pa]
        seeds_b = game_winners[:, pb]
        high_seeds = np.minimum(seeds_a, seeds_b)
        low_seeds = np.maximum(seeds_a, seeds_b)

        is_upset = later_outcomes[:, game_idx]
        game_winners[:, game_idx] = np.where(is_upset, low_seeds, high_seeds)

    champion_seeds = game_winners[:, 14]
    return later_outcomes, game_winners, champion_seeds


def simulate_stratum(
    prob_matrix: dict[tuple[int, int], float],
    allocation: StratumAllocation,
    rng: np.random.Generator,
    temp_schedule: dict[str, float] | None = None,
    mutation_rate: float = 0.0,
    max_attempts_multiplier: int = 5,
) -> list[SimulatedBracket]:
    """Generate brackets for a single stratum/world.

    Rejection sampling: generate brackets, keep those matching the world's
    constraints (R64 upset count and champion seed tier).

    temp_schedule: per-round temperature {round_name: tau}
    mutation_rate: probability of flipping any coin-flip game (P in 0.40-0.60)
    max_attempts_multiplier: generate up to N x budget candidates to find
    enough matching brackets. If still short, accept what we have.
    """
    world = allocation.world
    target_count = allocation.bracket_count
    target_upsets = world.r64_upset_count
    target_tier = world.champion_seed_tier

    r64_tau = 1.0
    if temp_schedule is not None:
        r64_tau = temp_schedule.get("R64", 1.0)

    accepted = []
    # Scale attempts by inverse prior: rare worlds need more rejection sampling
    rarity_factor = max(1.0, 0.01 / max(world.prior_probability, 1e-9))
    effective_multiplier = int(max_attempts_multiplier * max(1, rarity_factor))
    max_attempts = target_count * effective_multiplier
    batch_size = min(target_count * 2, max_attempts)

    attempts = 0
    while len(accepted) < target_count and attempts < max_attempts:
        remaining = target_count - len(accepted)
        gen_count = min(batch_size, max_attempts - attempts)
        attempts += gen_count

        # Simulate R64 with temperature
        r64_outcomes = simulate_r64_games(prob_matrix, gen_count, rng, r64_tau=r64_tau)

        # Apply mutation to R64 coin-flip games
        if mutation_rate > 0:
            r64_outcomes = apply_mutation(
                r64_outcomes, prob_matrix, rng,
                mutation_rate=mutation_rate, round_name="R64",
            )

        r64_winners = get_r64_winners(r64_outcomes)
        upset_counts = count_r64_upsets(r64_outcomes)

        # Filter by R64 upset count
        upset_mask = upset_counts == target_upsets

        if not np.any(upset_mask):
            continue

        # Simulate later rounds only for matching R64s
        filtered_r64 = r64_outcomes[upset_mask]
        filtered_winners = r64_winners[upset_mask]

        later_outcomes, game_winners, champion_seeds = simulate_later_rounds(
            filtered_winners, prob_matrix, rng, temp_schedule=temp_schedule,
        )

        # Apply mutation to later rounds
        if mutation_rate > 0:
            later_outcomes = apply_mutation_later_rounds(
                later_outcomes, game_winners, prob_matrix, rng,
                mutation_rate=mutation_rate,
            )
            # Recompute winners after mutation
            _, game_winners, champion_seeds = _recompute_winners_from_outcomes(
                filtered_winners, later_outcomes, prob_matrix,
            )

        # Filter by champion seed tier
        tier_mask = np.array([
            SEED_TO_TIER.get(int(s), "cinderella") == target_tier
            for s in champion_seeds
        ])

        if not np.any(tier_mask):
            continue

        # Pack accepted brackets
        final_r64 = filtered_r64[tier_mask]
        final_later = later_outcomes[tier_mask]
        final_champions = champion_seeds[tier_mask]
        final_upsets = upset_counts[upset_mask][tier_mask]

        packed = pack_regional_bracket(final_r64, final_later)

        for i in range(min(len(packed), remaining)):
            accepted.append(SimulatedBracket(
                bracket_int=int(packed[i]),
                weight=allocation.weight,
                stratum_id=world.id,
                champion_seed=int(final_champions[i]),
                upset_count_r64=int(final_upsets[i]),
            ))

    return accepted


def simulate_region(
    prob_matrix: dict[tuple[int, int], float],
    allocations: tuple[StratumAllocation, ...],
    seed: int = 42,
    temp_schedule: dict[str, float] | None = None,
    mutation_rate: float = 0.06,
) -> list[SimulatedBracket]:
    """Simulate all brackets for a single region.

    prob_matrix: (high_seed, low_seed) -> P(high_seed wins)
    allocations: from stratifier.allocate_regional_budget()
    seed: random seed for reproducibility
    temp_schedule: per-round temperature {round_name: tau}
    mutation_rate: X-factor flip probability for coin-flip games (default 6%)

    Returns list of SimulatedBracket.
    """
    rng = np.random.default_rng(seed)
    all_brackets = []

    for alloc in allocations:
        brackets = simulate_stratum(
            prob_matrix, alloc, rng,
            temp_schedule=temp_schedule,
            mutation_rate=mutation_rate,
        )
        all_brackets.extend(brackets)

    return all_brackets


def simulation_summary(brackets: list[SimulatedBracket]) -> dict:
    """Compute summary statistics for simulated brackets."""
    if not brackets:
        return {"total": 0}

    total = len(brackets)
    champions = [b.champion_seed for b in brackets]
    upsets = [b.upset_count_r64 for b in brackets]

    # Champion distribution
    champ_counts = {}
    for seed in range(1, 17):
        count = sum(1 for c in champions if c == seed)
        if count > 0:
            champ_counts[seed] = count

    # Upset distribution
    upset_dist = {}
    for u in range(9):
        count = sum(1 for x in upsets if x == u)
        if count > 0:
            upset_dist[u] = count

    # Weighted champion probabilities
    weighted_champ = {}
    total_weight = sum(b.weight for b in brackets)
    for seed in range(1, 17):
        w = sum(b.weight for b in brackets if b.champion_seed == seed)
        if w > 0:
            weighted_champ[seed] = w / total_weight

    return {
        "total": total,
        "champion_counts": champ_counts,
        "weighted_champion_probs": weighted_champ,
        "upset_distribution": upset_dist,
        "mean_r64_upsets": sum(upsets) / total,
        "unique_brackets": len(set(b.bracket_int for b in brackets)),
    }


def print_simulation_report(brackets: list[SimulatedBracket]) -> None:
    """Print formatted simulation results."""
    stats = simulation_summary(brackets)

    print("=" * 60)
    print(f"REGIONAL SIMULATION -- {stats['total']:,} brackets")
    print(f"Unique brackets: {stats.get('unique_brackets', 0):,}")
    print(f"Mean R64 upsets: {stats.get('mean_r64_upsets', 0):.2f}")
    print("=" * 60)

    print("\nChampion seed distribution (weighted):")
    for seed, prob in sorted(stats.get("weighted_champion_probs", {}).items()):
        bar = "#" * int(prob * 100)
        print(f"  Seed {seed:2d}: {prob:6.3f} {bar}")

    print("\nR64 upset count distribution:")
    for upsets, count in sorted(stats.get("upset_distribution", {}).items()):
        pct = count / stats["total"] * 100
        print(f"  {upsets} upsets: {count:>8,} ({pct:5.1f}%)")


if __name__ == "__main__":
    from stratifier import allocate_regional_budget

    # Demo with a simple probability matrix
    demo_probs = {
        (1, 16): 0.99, (8, 9): 0.50, (5, 12): 0.64,
        (4, 13): 0.79, (6, 11): 0.63, (3, 14): 0.85,
        (7, 10): 0.61, (2, 15): 0.94,
        # R32+: use rough estimates
        (1, 8): 0.85, (1, 9): 0.88, (4, 5): 0.55, (4, 12): 0.70,
        (3, 6): 0.65, (3, 11): 0.75, (2, 7): 0.72, (2, 10): 0.78,
        (1, 4): 0.70, (1, 5): 0.78, (1, 12): 0.88, (1, 13): 0.92,
        (2, 3): 0.58, (2, 6): 0.68, (2, 11): 0.80, (3, 7): 0.62,
        (3, 10): 0.70, (6, 7): 0.52, (6, 10): 0.55, (1, 2): 0.60,
        (1, 3): 0.68, (1, 6): 0.80, (1, 7): 0.82, (1, 10): 0.88,
        (1, 11): 0.90, (2, 4): 0.62, (2, 5): 0.66, (2, 12): 0.85,
        (2, 13): 0.90, (3, 4): 0.55, (3, 5): 0.58, (3, 12): 0.80,
        (3, 13): 0.88, (4, 6): 0.56, (4, 7): 0.58, (4, 10): 0.62,
        (4, 11): 0.65, (5, 6): 0.48, (5, 7): 0.50, (5, 10): 0.52,
        (5, 11): 0.55, (5, 13): 0.75, (6, 12): 0.72, (6, 13): 0.80,
        (6, 14): 0.88, (7, 11): 0.55, (7, 12): 0.65, (7, 13): 0.75,
        (7, 14): 0.85, (8, 12): 0.60, (8, 13): 0.70, (9, 12): 0.58,
        (9, 13): 0.68, (10, 11): 0.50, (10, 12): 0.55, (10, 13): 0.65,
        (10, 14): 0.75, (11, 12): 0.52, (11, 13): 0.60, (11, 14): 0.70,
        (8, 4): 0.30, (8, 5): 0.35, (9, 4): 0.28, (9, 5): 0.32,
    }

    # Small demo (10K instead of 3M for speed)
    allocations = allocate_regional_budget(budget_per_region=10_000, min_per_world=10)
    brackets = simulate_region(demo_probs, allocations, seed=42)
    print_simulation_report(brackets)
