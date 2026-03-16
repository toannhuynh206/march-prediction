"""
Stratified importance sampling: world definition and Neyman allocation.

A "world" = (r64_upset_count, champion_tier).
  - r64_upset_count ∈ {0, 1, ..., 8}
  - champion_tier ∈ {"1", "2-3", "4-6", "7+"}

Budget is allocated proportional to √P(world) (Neyman allocation),
with a minimum of MIN_BRACKETS_PER_CHAMPION_SEED per champion seed.
"""

from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.constants import (
    BRACKETS_PER_REGION,
    CHAMPION_TIERS,
    MIN_BRACKETS_PER_CHAMPION_SEED,
    R64_UPSET_RANGE,
)
from simulation.bracket_structure import (
    CHAMPION_TIER_SEEDS,
    R64_SEED_MATCHUPS,
    classify_champion_tier,
)


# =========================================================================
# World definition
# =========================================================================

class World:
    """A stratum in the simulation: (r64_upsets, champion_tier)."""

    __slots__ = (
        "r64_upsets", "champion_tier", "prior_prob",
        "target_count", "actual_count",
    )

    def __init__(
        self,
        r64_upsets: int,
        champion_tier: str,
        prior_prob: float = 0.0,
        target_count: int = 0,
    ) -> None:
        self.r64_upsets = r64_upsets
        self.champion_tier = champion_tier
        self.prior_prob = prior_prob
        self.target_count = target_count
        self.actual_count = 0


# =========================================================================
# Prior probability computation
# =========================================================================

def _compute_r64_upset_distribution(
    r64_probs: np.ndarray,
) -> np.ndarray:
    """Compute P(exactly k upsets in R64) for k = 0..8.

    Uses convolution: each game independently has upset prob = 1 - r64_probs[i].

    Args:
        r64_probs: Array of shape (8,) — P(top/higher seed wins) per game.

    Returns:
        Array of shape (9,) — P(k upsets) for k = 0..8.
    """
    # Dynamic programming: P(k upsets in first n games)
    n_games = len(r64_probs)
    dp = np.zeros(n_games + 1, dtype=np.float64)
    dp[0] = 1.0

    for i in range(n_games):
        p_chalk = float(r64_probs[i])
        p_upset = 1.0 - p_chalk
        # Process in reverse to avoid overwriting
        new_dp = np.zeros_like(dp)
        for k in range(i + 2):
            if k > 0:
                new_dp[k] += dp[k - 1] * p_upset
            new_dp[k] += dp[k] * p_chalk
        dp = new_dp

    return dp


def _estimate_champion_tier_probs(
    r64_probs: np.ndarray,
    prob_matrix: np.ndarray,
) -> dict[str, float]:
    """Estimate marginal P(champion_tier) via Monte Carlo pre-sampling.

    Runs a small simulation (~50K brackets) to estimate how often each
    champion tier wins the region.

    Args:
        r64_probs: Shape (8,) — P(higher seed wins) per R64 game.
        prob_matrix: Shape (16, 16) — pairwise win probabilities.

    Returns:
        {tier_string: probability}
    """
    from simulation.bracket_structure import (
        POSITION_TO_SEED,
        R64_GAMES,
    )

    rng = np.random.default_rng(seed=12345)
    n_samples = 50_000
    tier_counts: dict[str, int] = {t: 0 for t in CHAMPION_TIERS}

    for _ in range(n_samples):
        # R64
        r64_outcomes = (rng.random(8) > r64_probs).astype(np.int8)
        # Determine advancing positions
        advancing = []
        for g in range(8):
            top_pos, bot_pos = R64_GAMES[g]
            winner_pos = bot_pos if r64_outcomes[g] else top_pos
            advancing.append(winner_pos)

        # R32
        r32_winners = []
        for g in range(4):
            pos_a = advancing[g * 2]
            pos_b = advancing[g * 2 + 1]
            p_a = prob_matrix[pos_a, pos_b]
            winner = pos_b if rng.random() > p_a else pos_a
            r32_winners.append(winner)

        # S16
        s16_winners = []
        for g in range(2):
            pos_a = r32_winners[g * 2]
            pos_b = r32_winners[g * 2 + 1]
            p_a = prob_matrix[pos_a, pos_b]
            winner = pos_b if rng.random() > p_a else pos_a
            s16_winners.append(winner)

        # E8
        pos_a, pos_b = s16_winners
        p_a = prob_matrix[pos_a, pos_b]
        champion_pos = pos_b if rng.random() > p_a else pos_a
        champion_seed = POSITION_TO_SEED[champion_pos]
        tier = classify_champion_tier(champion_seed)
        tier_counts[tier] += 1

    return {t: c / n_samples for t, c in tier_counts.items()}


# =========================================================================
# Neyman allocation
# =========================================================================

def compute_world_priors(
    r64_probs: np.ndarray,
    prob_matrix: np.ndarray,
) -> list[World]:
    """Compute prior probabilities for all worlds and allocate budget.

    P(world) ≈ P(k upsets) × P(champion_tier)
    (Independence assumption — tiers are weakly correlated with upset count.)

    Budget allocation uses Neyman: n_s ∝ √P(world).
    """
    upset_dist = _compute_r64_upset_distribution(r64_probs)
    tier_probs = _estimate_champion_tier_probs(r64_probs, prob_matrix)

    worlds: list[World] = []
    for k in R64_UPSET_RANGE:
        for tier in CHAMPION_TIERS:
            prior = float(upset_dist[k]) * tier_probs.get(tier, 0.001)
            worlds.append(World(k, tier, prior_prob=max(prior, 1e-10)))

    return worlds


def allocate_budget(
    worlds: list[World],
    total_budget: int = BRACKETS_PER_REGION,
    min_per_champion_seed: int = MIN_BRACKETS_PER_CHAMPION_SEED,
) -> list[World]:
    """Allocate simulation budget to worlds using Neyman allocation.

    n_s ∝ √P(world), with minimum guarantees for rare champion seeds.

    Modifies worlds in-place (sets target_count) and returns them.
    """
    # Neyman allocation: proportional to sqrt(prior)
    sqrt_priors = np.array([np.sqrt(w.prior_prob) for w in worlds])
    raw_shares = sqrt_priors / sqrt_priors.sum()

    # Initial allocation
    raw_counts = (raw_shares * total_budget).astype(np.int64)

    # Enforce minimums per champion tier
    # Group by champion_tier and ensure each tier gets enough
    tier_totals: dict[str, int] = {}
    tier_world_indices: dict[str, list[int]] = {}
    for i, w in enumerate(worlds):
        tier_totals.setdefault(w.champion_tier, 0)
        tier_totals[w.champion_tier] += int(raw_counts[i])
        tier_world_indices.setdefault(w.champion_tier, []).append(i)

    # Check and fix minimums (scale proportionally for small budgets)
    seeds_per_tier = {
        "1": 1, "2-3": 2, "4-6": 3, "7+": 10,
    }
    budget_ratio = total_budget / BRACKETS_PER_REGION
    for tier, n_seeds in seeds_per_tier.items():
        scaled_min = max(1, int(min_per_champion_seed * n_seeds * budget_ratio))
        current = tier_totals.get(tier, 0)
        if current < scaled_min:
            deficit = scaled_min - current
            # Distribute deficit proportionally among worlds in this tier
            indices = tier_world_indices.get(tier, [])
            if indices:
                per_world = deficit // len(indices) + 1
                for idx in indices:
                    raw_counts[idx] += per_world

    # Re-normalize to hit exact budget
    total = raw_counts.sum()
    if total > 0:
        raw_counts = (raw_counts.astype(np.float64) / total * total_budget).astype(np.int64)

    # Fix rounding error on the largest stratum
    remainder = total_budget - raw_counts.sum()
    if remainder != 0:
        largest_idx = np.argmax(raw_counts)
        raw_counts[largest_idx] += remainder

    # Ensure no zeros (at least 1 bracket per world)
    for i in range(len(raw_counts)):
        if raw_counts[i] < 1:
            raw_counts[i] = 1

    # Assign
    for i, w in enumerate(worlds):
        w.target_count = int(raw_counts[i])

    return worlds


# =========================================================================
# Stratum weight computation
# =========================================================================

def compute_stratum_weight(
    world: World,
    total_budget: int = BRACKETS_PER_REGION,
) -> float:
    """Compute importance weight for brackets in a given world.

    weight = P(world) × N / n_world
    where N = total budget, n_world = brackets allocated to this world.

    All brackets in the same world share the same weight.
    """
    if world.target_count <= 0:
        return 0.0
    return world.prior_prob * total_budget / world.target_count


# =========================================================================
# Summary
# =========================================================================

def print_allocation_summary(worlds: list[World], region: str) -> None:
    """Print a human-readable summary of world allocations."""
    total = sum(w.target_count for w in worlds)
    print(f"\n{'='*70}")
    print(f" Stratified Allocation — {region} ({total:,} brackets)")
    print(f"{'='*70}")
    print(f" {'Upsets':>7s} {'Tier':>5s} {'P(world)':>10s} "
          f"{'Budget':>12s} {'Weight':>8s}")
    print(f" {'-'*7} {'-'*5} {'-'*10} {'-'*12} {'-'*8}")

    for w in sorted(worlds, key=lambda x: x.prior_prob, reverse=True)[:20]:
        weight = compute_stratum_weight(w, total)
        print(f" {w.r64_upsets:>7d} {w.champion_tier:>5s} "
              f"{w.prior_prob:>10.6f} {w.target_count:>12,} "
              f"{weight:>8.4f}")

    # Tier summary
    print(f"\n Champion tier totals:")
    for tier in CHAMPION_TIERS:
        tier_total = sum(w.target_count for w in worlds
                         if w.champion_tier == tier)
        tier_prob = sum(w.prior_prob for w in worlds
                        if w.champion_tier == tier)
        print(f"   {tier:>5s}: {tier_total:>12,} brackets "
              f"(P = {tier_prob:.4f})")
