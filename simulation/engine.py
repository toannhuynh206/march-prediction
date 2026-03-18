"""
Vectorized NumPy bracket simulation engine.

Generates brackets for a specific world (r64_upsets, champion_tier)
using conditional sampling + rejection for champion tier matching.
Round-by-round generation (never pre-generate all random numbers).
"""

from __future__ import annotations

from itertools import combinations

import numpy as np

from simulation.bracket_structure import (
    CHAMPION_TIER_SEEDS,
    POSITION_TO_SEED,
    R64_GAMES,
    classify_champion_tier,
)
from simulation.encoder import encode_batch
from simulation.probability import RegionProbabilities
from simulation.stratifier import World


# =========================================================================
# R64 upset pattern precomputation
# =========================================================================

def precompute_upset_patterns(
    k: int,
    r64_probs: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Precompute all C(8,k) upset patterns and their conditional probabilities.

    Args:
        k: Number of upsets required.
        r64_probs: Shape (8,) — P(higher seed wins) per R64 game.

    Returns:
        pattern_matrix: Shape (n_patterns, 8), dtype int8. 1 = upset.
        pattern_probs: Shape (n_patterns,), dtype float64. Normalized.
    """
    if k == 0:
        return (
            np.zeros((1, 8), dtype=np.int8),
            np.array([1.0], dtype=np.float64),
        )
    if k == 8:
        return (
            np.ones((1, 8), dtype=np.int8),
            np.array([1.0], dtype=np.float64),
        )

    n_games = 8
    patterns = list(combinations(range(n_games), k))

    log_chalk = np.log(np.maximum(r64_probs, 1e-15).astype(np.float64))
    log_upset = np.log(np.maximum(1.0 - r64_probs, 1e-15).astype(np.float64))

    log_probs = np.zeros(len(patterns), dtype=np.float64)
    pattern_matrix = np.zeros((len(patterns), n_games), dtype=np.int8)

    for i, upset_games in enumerate(patterns):
        upset_set = set(upset_games)
        lp = 0.0
        for g in range(n_games):
            if g in upset_set:
                lp += log_upset[g]
                pattern_matrix[i, g] = 1
            else:
                lp += log_chalk[g]
        log_probs[i] = lp

    # Normalize via log-sum-exp
    max_lp = np.max(log_probs)
    probs = np.exp(log_probs - max_lp)
    probs /= probs.sum()

    return pattern_matrix, probs


# =========================================================================
# Forward simulation (R32 → S16 → E8)
# =========================================================================

def _simulate_forward(
    rng: np.random.Generator,
    r64_outcomes: np.ndarray,
    prob_matrix: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Simulate R32, S16, E8 given R64 outcomes.

    Args:
        rng: NumPy random generator.
        r64_outcomes: Shape (N, 8), dtype int8. 1 = upset (bottom wins).
        prob_matrix: Shape (16, 16), float32. prob_matrix[i][j] = P(i beats j).

    Returns:
        r32_outcomes: Shape (N, 4), dtype int8.
        s16_outcomes: Shape (N, 2), dtype int8.
        e8_outcomes:  Shape (N, 1), dtype int8.
    """
    n = r64_outcomes.shape[0]

    # Determine R64 advancing positions (bracket positions, not seeds)
    r64_advancing = np.empty((n, 8), dtype=np.int16)
    for g in range(8):
        top_pos, bot_pos = R64_GAMES[g]
        upset = r64_outcomes[:, g].astype(bool)
        r64_advancing[:, g] = np.where(upset, bot_pos, top_pos)

    # --- R32: 4 games ---
    r32_outcomes = np.empty((n, 4), dtype=np.int8)
    r32_advancing = np.empty((n, 4), dtype=np.int16)
    for g in range(4):
        pos_a = r64_advancing[:, g * 2]      # top entry
        pos_b = r64_advancing[:, g * 2 + 1]  # bottom entry
        # Look up probabilities via advanced indexing
        p_top_wins = prob_matrix[pos_a, pos_b]
        upset = (rng.random(n, dtype=np.float32) > p_top_wins)
        r32_outcomes[:, g] = upset.astype(np.int8)
        r32_advancing[:, g] = np.where(upset, pos_b, pos_a)

    # --- S16: 2 games ---
    s16_outcomes = np.empty((n, 2), dtype=np.int8)
    s16_advancing = np.empty((n, 2), dtype=np.int16)
    for g in range(2):
        pos_a = r32_advancing[:, g * 2]
        pos_b = r32_advancing[:, g * 2 + 1]
        p_top_wins = prob_matrix[pos_a, pos_b]
        upset = (rng.random(n, dtype=np.float32) > p_top_wins)
        s16_outcomes[:, g] = upset.astype(np.int8)
        s16_advancing[:, g] = np.where(upset, pos_b, pos_a)

    # --- E8: 1 game ---
    pos_a = s16_advancing[:, 0]
    pos_b = s16_advancing[:, 1]
    p_top_wins = prob_matrix[pos_a, pos_b]
    upset = (rng.random(n, dtype=np.float32) > p_top_wins)
    e8_outcomes = upset.astype(np.int8).reshape(n, 1)

    return r32_outcomes, s16_outcomes, e8_outcomes


def _get_champion_positions(
    r64_outcomes: np.ndarray,
    r32_outcomes: np.ndarray,
    s16_outcomes: np.ndarray,
    e8_outcomes: np.ndarray,
) -> np.ndarray:
    """Extract the champion bracket position for each bracket.

    Returns:
        champion_positions: Shape (N,), dtype int16.
    """
    n = r64_outcomes.shape[0]

    # R64 → advancing positions
    r64_advancing = np.empty((n, 8), dtype=np.int16)
    for g in range(8):
        top_pos, bot_pos = R64_GAMES[g]
        upset = r64_outcomes[:, g].astype(bool)
        r64_advancing[:, g] = np.where(upset, bot_pos, top_pos)

    # R32 → advancing
    r32_advancing = np.empty((n, 4), dtype=np.int16)
    for g in range(4):
        pos_a = r64_advancing[:, g * 2]
        pos_b = r64_advancing[:, g * 2 + 1]
        upset = r32_outcomes[:, g].astype(bool)
        r32_advancing[:, g] = np.where(upset, pos_b, pos_a)

    # S16 → advancing
    s16_advancing = np.empty((n, 2), dtype=np.int16)
    for g in range(2):
        pos_a = r32_advancing[:, g * 2]
        pos_b = r32_advancing[:, g * 2 + 1]
        upset = s16_outcomes[:, g].astype(bool)
        s16_advancing[:, g] = np.where(upset, pos_b, pos_a)

    # E8 → champion
    pos_a = s16_advancing[:, 0]
    pos_b = s16_advancing[:, 1]
    upset = e8_outcomes[:, 0].astype(bool)
    return np.where(upset, pos_b, pos_a)


# =========================================================================
# Bracket probability computation
# =========================================================================

def _compute_bracket_probabilities(
    r64_outcomes: np.ndarray,
    r32_outcomes: np.ndarray,
    s16_outcomes: np.ndarray,
    e8_outcomes: np.ndarray,
    r64_probs: np.ndarray,
    prob_matrix: np.ndarray,
) -> np.ndarray:
    """Compute unconditional probability of each bracket.

    P(bracket) = product of P(game outcome) across all 15 games.

    Returns:
        probabilities: Shape (N,), dtype float64.
    """
    n = r64_outcomes.shape[0]
    log_prob = np.zeros(n, dtype=np.float64)

    # R64 contribution
    for g in range(8):
        p_chalk = float(r64_probs[g])
        chalk_mask = (r64_outcomes[:, g] == 0)
        log_prob += np.where(
            chalk_mask,
            np.log(max(p_chalk, 1e-15)),
            np.log(max(1.0 - p_chalk, 1e-15)),
        )

    # R32 contribution — need to know which positions met
    r64_advancing = np.empty((n, 8), dtype=np.int16)
    for g in range(8):
        top_pos, bot_pos = R64_GAMES[g]
        upset = r64_outcomes[:, g].astype(bool)
        r64_advancing[:, g] = np.where(upset, bot_pos, top_pos)

    r32_advancing = np.empty((n, 4), dtype=np.int16)
    for g in range(4):
        pos_a = r64_advancing[:, g * 2]
        pos_b = r64_advancing[:, g * 2 + 1]
        p_a_wins = prob_matrix[pos_a, pos_b]
        chalk_mask = (r32_outcomes[:, g] == 0)
        log_prob += np.where(
            chalk_mask,
            np.log(np.maximum(p_a_wins, 1e-15)),
            np.log(np.maximum(1.0 - p_a_wins, 1e-15)),
        )
        upset = r32_outcomes[:, g].astype(bool)
        r32_advancing[:, g] = np.where(upset, pos_b, pos_a)

    # S16 contribution
    s16_advancing = np.empty((n, 2), dtype=np.int16)
    for g in range(2):
        pos_a = r32_advancing[:, g * 2]
        pos_b = r32_advancing[:, g * 2 + 1]
        p_a_wins = prob_matrix[pos_a, pos_b]
        chalk_mask = (s16_outcomes[:, g] == 0)
        log_prob += np.where(
            chalk_mask,
            np.log(np.maximum(p_a_wins, 1e-15)),
            np.log(np.maximum(1.0 - p_a_wins, 1e-15)),
        )
        upset = s16_outcomes[:, g].astype(bool)
        s16_advancing[:, g] = np.where(upset, pos_b, pos_a)

    # E8 contribution
    pos_a = s16_advancing[:, 0]
    pos_b = s16_advancing[:, 1]
    p_a_wins = prob_matrix[pos_a, pos_b]
    chalk_mask = (e8_outcomes[:, 0] == 0)
    log_prob += np.where(
        chalk_mask,
        np.log(np.maximum(p_a_wins, 1e-15)),
        np.log(np.maximum(1.0 - p_a_wins, 1e-15)),
    )

    return np.exp(log_prob)  # float64 — no downcast to preserve tail precision


# =========================================================================
# Main simulation function
# =========================================================================

def simulate_world(
    rng: np.random.Generator,
    world: World,
    region_probs: RegionProbabilities,
    batch_size: int = 100_000,
    max_attempts_factor: int = 50,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Generate brackets for a specific world until target_count is met.

    Uses conditional R64 sampling (exact k upsets) + rejection for champion tier.

    Args:
        rng: NumPy random generator.
        world: World specification with target_count.
        region_probs: Preloaded region probability data.
        batch_size: Brackets to generate per iteration.
        max_attempts_factor: Max total attempts = target_count * factor.

    Returns:
        packed_outcomes: Shape (target_count,), dtype int16.
        probabilities: Shape (target_count,), dtype float64.
        weight: Importance sampling weight for this world.
    """
    target = world.target_count
    target_seeds = CHAMPION_TIER_SEEDS[world.champion_tier]

    # Precompute upset patterns for this world's k
    pattern_matrix, pattern_probs = precompute_upset_patterns(
        world.r64_upsets, region_probs.r64_top_win_probs
    )

    seed_by_pos = np.array(POSITION_TO_SEED, dtype=np.int16)
    prob_matrix = region_probs.prob_matrix
    r64_probs = region_probs.r64_top_win_probs

    # Accumulate accepted brackets
    accepted_packed: list[np.ndarray] = []
    accepted_probs: list[np.ndarray] = []
    total_accepted = 0
    total_generated = 0
    max_total = target * max_attempts_factor

    while total_accepted < target and total_generated < max_total:
        remaining = target - total_accepted
        # Overshoot batch size to account for rejection
        current_batch = min(batch_size, remaining * 5)

        # 1. Sample R64 patterns (exact k upsets)
        pattern_indices = rng.choice(
            len(pattern_probs), size=current_batch, p=pattern_probs
        )
        r64_outcomes = pattern_matrix[pattern_indices]  # (batch, 8)

        # 2. Forward simulate R32, S16, E8
        r32, s16, e8 = _simulate_forward(rng, r64_outcomes, prob_matrix)

        # 3. Get champion seeds
        champ_positions = _get_champion_positions(r64_outcomes, r32, s16, e8)
        champ_seeds = seed_by_pos[champ_positions]

        # 4. Filter by champion tier
        tier_mask = np.isin(champ_seeds, list(target_seeds))
        valid_indices = np.nonzero(tier_mask)[0]

        if len(valid_indices) == 0:
            total_generated += current_batch
            continue

        # Trim to not overshoot target
        take = min(len(valid_indices), remaining)
        valid_indices = valid_indices[:take]

        # 5. Assemble full outcomes matrix (N, 15)
        n_valid = len(valid_indices)
        full_outcomes = np.empty((n_valid, 15), dtype=np.int8)
        full_outcomes[:, 0:8] = r64_outcomes[valid_indices]
        full_outcomes[:, 8:12] = r32[valid_indices]
        full_outcomes[:, 12:14] = s16[valid_indices]
        full_outcomes[:, 14:15] = e8[valid_indices]

        # 6. Pack and compute probabilities
        packed = encode_batch(full_outcomes)
        probs = _compute_bracket_probabilities(
            r64_outcomes[valid_indices],
            r32[valid_indices],
            s16[valid_indices],
            e8[valid_indices],
            r64_probs,
            prob_matrix,
        )

        accepted_packed.append(packed)
        accepted_probs.append(probs)
        total_accepted += n_valid
        total_generated += current_batch

    if total_accepted < target:
        print(f"  Warning: only generated {total_accepted}/{target} "
              f"for world (upsets={world.r64_upsets}, tier={world.champion_tier})")

    # Concatenate results
    if accepted_packed:
        all_packed = np.concatenate(accepted_packed)[:target]
        all_probs = np.concatenate(accepted_probs)[:target]
    else:
        all_packed = np.empty(0, dtype=np.int16)
        all_probs = np.empty(0, dtype=np.float64)

    world.actual_count = len(all_packed)

    # Compute importance weight
    from simulation.stratifier import compute_stratum_weight
    weight = compute_stratum_weight(world)

    return all_packed, all_probs, weight
