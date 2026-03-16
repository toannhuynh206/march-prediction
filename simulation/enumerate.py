"""
Full enumeration of all 2^15 = 32,768 possible regional brackets.

Instead of Monte Carlo sampling with duplicates, we compute the exact
probability of every possible bracket outcome. This is feasible because
each region has only 15 binary game outcomes.

P(bracket) = product of P(game_outcome) across all 15 games.
No randomness. No sampling. No approximation.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from simulation.bracket_structure import POSITION_TO_SEED, R64_GAMES
from simulation.encoder import decode_batch
from simulation.probability import RegionProbabilities

N_BRACKETS = 2 ** 15  # 32,768


# =========================================================================
# Result container
# =========================================================================

@dataclass(frozen=True)
class RegionEnumeration:
    """Complete enumeration of all possible brackets for one region."""

    region: str
    packed: np.ndarray          # (32768,) int16 — packed 15-bit outcomes
    probabilities: np.ndarray   # (32768,) float64 — exact P(bracket)
    champion_seeds: np.ndarray  # (32768,) int16 — champion seed per bracket
    r64_upsets: np.ndarray      # (32768,) int8 — R64 upset count

    @property
    def n_brackets(self) -> int:
        return len(self.packed)

    def champion_distribution(self) -> dict[int, float]:
        """Exact probability of each seed winning the region."""
        total = float(self.probabilities.sum())
        dist: dict[int, float] = {}
        for seed in range(1, 17):
            mask = self.champion_seeds == seed
            prob = float(self.probabilities[mask].sum())
            if prob > 0:
                dist[seed] = prob / total
        return dist

    def upset_distribution(self) -> dict[int, float]:
        """Exact probability of k R64 upsets."""
        total = float(self.probabilities.sum())
        dist: dict[int, float] = {}
        for k in range(9):
            mask = self.r64_upsets == k
            prob = float(self.probabilities[mask].sum())
            if prob > 0:
                dist[k] = prob / total
        return dist


# =========================================================================
# Position tracing
# =========================================================================

def _trace_advancing_positions(
    r64: np.ndarray,
    r32: np.ndarray,
    s16: np.ndarray,
    e8: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Trace which bracket positions advance through each round.

    Args:
        r64: (N, 8) int8 — R64 outcomes (0=top wins, 1=bottom wins)
        r32: (N, 4) int8 — R32 outcomes
        s16: (N, 2) int8 — S16 outcomes
        e8:  (N, 1) int8 — E8 outcome

    Returns:
        r64_adv: (N, 8) positions advancing from R64
        r32_adv: (N, 4) positions advancing from R32
        s16_adv: (N, 2) positions advancing from S16
        champion_pos: (N,) champion bracket position
    """
    n = r64.shape[0]

    # R64 → 8 advancing positions
    r64_adv = np.empty((n, 8), dtype=np.int16)
    for g in range(8):
        top_pos, bot_pos = R64_GAMES[g]
        upset = r64[:, g].astype(bool)
        r64_adv[:, g] = np.where(upset, bot_pos, top_pos)

    # R32 → 4 advancing positions
    r32_adv = np.empty((n, 4), dtype=np.int16)
    for g in range(4):
        pos_a = r64_adv[:, g * 2]
        pos_b = r64_adv[:, g * 2 + 1]
        upset = r32[:, g].astype(bool)
        r32_adv[:, g] = np.where(upset, pos_b, pos_a)

    # S16 → 2 advancing positions
    s16_adv = np.empty((n, 2), dtype=np.int16)
    for g in range(2):
        pos_a = r32_adv[:, g * 2]
        pos_b = r32_adv[:, g * 2 + 1]
        upset = s16[:, g].astype(bool)
        s16_adv[:, g] = np.where(upset, pos_b, pos_a)

    # E8 → champion
    pos_a = s16_adv[:, 0]
    pos_b = s16_adv[:, 1]
    upset = e8[:, 0].astype(bool)
    champion_pos = np.where(upset, pos_b, pos_a)

    return r64_adv, r32_adv, s16_adv, champion_pos


# =========================================================================
# Exact probability computation
# =========================================================================

def _compute_exact_probabilities(
    r64: np.ndarray,
    r32: np.ndarray,
    s16: np.ndarray,
    e8: np.ndarray,
    r64_probs: np.ndarray,
    prob_matrix: np.ndarray,
) -> np.ndarray:
    """Compute exact P(bracket) for every bracket.

    P(bracket) = product of P(game_outcome) across all 15 games.
    Uses log-space to avoid floating point underflow.

    Args:
        r64: (N, 8) R64 outcomes
        r32: (N, 4) R32 outcomes
        s16: (N, 2) S16 outcomes
        e8:  (N, 1) E8 outcome
        r64_probs: (8,) P(higher seed wins) per R64 game (from 4-layer blend)
        prob_matrix: (16, 16) P(position i beats position j) for R32+

    Returns:
        (N,) float64 — exact probability of each bracket
    """
    n = r64.shape[0]
    log_prob = np.zeros(n, dtype=np.float64)

    # R64: 8 games using precomputed blend probabilities
    for g in range(8):
        p_chalk = float(r64_probs[g])
        chalk = (r64[:, g] == 0)
        log_prob += np.where(
            chalk,
            np.log(max(p_chalk, 1e-15)),
            np.log(max(1.0 - p_chalk, 1e-15)),
        )

    # Trace positions for later rounds
    r64_adv, r32_adv, s16_adv, _ = _trace_advancing_positions(
        r64, r32, s16, e8,
    )

    # R32: 4 games
    for g in range(4):
        pos_a = r64_adv[:, g * 2]
        pos_b = r64_adv[:, g * 2 + 1]
        p_top = prob_matrix[pos_a, pos_b]
        chalk = (r32[:, g] == 0)
        log_prob += np.where(
            chalk,
            np.log(np.maximum(p_top, 1e-15)),
            np.log(np.maximum(1.0 - p_top, 1e-15)),
        )

    # S16: 2 games
    for g in range(2):
        pos_a = r32_adv[:, g * 2]
        pos_b = r32_adv[:, g * 2 + 1]
        p_top = prob_matrix[pos_a, pos_b]
        chalk = (s16[:, g] == 0)
        log_prob += np.where(
            chalk,
            np.log(np.maximum(p_top, 1e-15)),
            np.log(np.maximum(1.0 - p_top, 1e-15)),
        )

    # E8: 1 game
    pos_a = s16_adv[:, 0]
    pos_b = s16_adv[:, 1]
    p_top = prob_matrix[pos_a, pos_b]
    chalk = (e8[:, 0] == 0)
    log_prob += np.where(
        chalk,
        np.log(np.maximum(p_top, 1e-15)),
        np.log(np.maximum(1.0 - p_top, 1e-15)),
    )

    return np.exp(log_prob)


# =========================================================================
# Main enumeration function
# =========================================================================

def enumerate_region(region_probs: RegionProbabilities) -> RegionEnumeration:
    """Enumerate all 32,768 possible brackets with exact probabilities.

    For each of the 2^15 bit patterns:
      1. Decode into 15 game outcomes
      2. Trace bracket structure to determine round-by-round matchups
      3. P(bracket) = product of P(game_outcome) for all 15 games
      4. Extract champion seed

    No randomness. No sampling. Exact.

    Args:
        region_probs: Preloaded region probability data.

    Returns:
        RegionEnumeration with all 32,768 brackets and their exact probabilities.
    """
    # All 32,768 bit patterns
    packed = np.arange(N_BRACKETS, dtype=np.int16)

    # Decode to (32768, 15) outcome matrix
    outcomes = decode_batch(packed)

    r64 = outcomes[:, 0:8].astype(np.int8)
    r32 = outcomes[:, 8:12].astype(np.int8)
    s16 = outcomes[:, 12:14].astype(np.int8)
    e8 = outcomes[:, 14:15].astype(np.int8)

    # Exact probabilities
    probabilities = _compute_exact_probabilities(
        r64, r32, s16, e8,
        region_probs.r64_top_win_probs,
        region_probs.prob_matrix,
    )

    # Champion seeds
    _, _, _, champion_pos = _trace_advancing_positions(r64, r32, s16, e8)
    seed_by_pos = np.array(POSITION_TO_SEED, dtype=np.int16)
    champion_seeds = seed_by_pos[champion_pos]

    # R64 upset counts
    r64_upsets = r64.sum(axis=1).astype(np.int8)

    return RegionEnumeration(
        region=region_probs.region,
        packed=packed,
        probabilities=probabilities,
        champion_seeds=champion_seeds,
        r64_upsets=r64_upsets,
    )


# =========================================================================
# Summary printing
# =========================================================================

def print_enumeration_summary(enum: RegionEnumeration) -> None:
    """Print champion distribution and upset distribution."""
    total_prob = float(enum.probabilities.sum())

    print(f"\n{'='*60}")
    print(f" {enum.region} Region — Full Enumeration")
    print(f" {enum.n_brackets:,} brackets, P(total) = {total_prob:.10f}")
    print(f"{'='*60}")

    # Champion distribution
    champ_dist = enum.champion_distribution()
    print(f"\n  Champion Seed Distribution:")
    print(f"  {'Seed':>6s} {'Probability':>12s} {'Brackets':>10s}")
    print(f"  {'-'*6} {'-'*12} {'-'*10}")
    for seed in sorted(champ_dist.keys()):
        prob = champ_dist[seed]
        count = int((enum.champion_seeds == seed).sum())
        print(f"  {seed:>6d} {prob:>12.6f} {count:>10,}")

    # 1-seed check
    one_seed_pct = champ_dist.get(1, 0.0) * 100
    status = "PASS" if one_seed_pct >= 40 else "WARN"
    print(f"\n  1-seed check (>= 40%): {one_seed_pct:.1f}% [{status}]")

    # Upset distribution
    upset_dist = enum.upset_distribution()
    print(f"\n  R64 Upset Distribution:")
    print(f"  {'Upsets':>7s} {'Probability':>12s}")
    print(f"  {'-'*7} {'-'*12}")
    for k in range(9):
        prob = upset_dist.get(k, 0.0)
        if prob > 0:
            print(f"  {k:>7d} {prob:>12.6f}")

    # Top 5 most likely brackets
    top_5_idx = np.argsort(enum.probabilities)[-5:][::-1]
    print(f"\n  Top 5 Most Likely Brackets:")
    print(f"  {'Rank':>5s} {'Packed':>8s} {'P(bracket)':>14s} "
          f"{'Champ':>6s} {'Upsets':>7s}")
    print(f"  {'-'*5} {'-'*8} {'-'*14} {'-'*6} {'-'*7}")
    for rank, idx in enumerate(top_5_idx, 1):
        print(f"  {rank:>5d} {int(enum.packed[idx]):>8d} "
              f"{enum.probabilities[idx]:>14.10f} "
              f"{int(enum.champion_seeds[idx]):>6d} "
              f"{int(enum.r64_upsets[idx]):>7d}")


# =========================================================================
# Self-test
# =========================================================================

if __name__ == "__main__":
    print("Enumeration module loaded. Run via simulation.simulate.")
    print(f"Total brackets per region: {N_BRACKETS:,}")
    print(f"Total brackets all regions: {N_BRACKETS * 4:,}")
