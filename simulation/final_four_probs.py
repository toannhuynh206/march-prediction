"""
Final Four probability computation.

Computes P(team_a beats team_b) for cross-region matchups using the
logistic function on power index differentials.

F4 encoding (3 bits packed into int8):
  Bit 0: Semi 1 outcome (0 = first region wins, 1 = second region wins)
  Bit 1: Semi 2 outcome (0 = first region wins, 1 = second region wins)
  Bit 2: Championship  (0 = Semi 1 winner wins, 1 = Semi 2 winner wins)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.constants import F4_SEMI_PAIRINGS, LOGISTIC_K_INITIAL


# =========================================================================
# Seed → power index lookup
# =========================================================================

def build_seed_pi_lookup(teams: list[dict[str, Any]]) -> np.ndarray:
    """Build a seed → power_index lookup array for one region.

    Returns array of length 17 (index 0 unused, seeds 1-16).
    """
    lookup = np.full(17, 50.0, dtype=np.float64)
    for t in teams:
        lookup[t["seed"]] = t["power_index"]
    return lookup


# =========================================================================
# Vectorized logistic probability
# =========================================================================

def logistic_prob_vec(
    pi_a: np.ndarray,
    pi_b: np.ndarray,
    k: float = LOGISTIC_K_INITIAL,
) -> np.ndarray:
    """Vectorized P(A wins) = 1 / (1 + 10^((pi_b - pi_a) / k)).

    Args:
        pi_a: (N,) power indices for team A.
        pi_b: (N,) power indices for team B.
        k: Logistic scaling parameter.

    Returns:
        (N,) float64 probabilities.
    """
    exponent = (pi_b - pi_a) / k
    return 1.0 / (1.0 + np.power(10.0, exponent))


# =========================================================================
# F4 outcome probability
# =========================================================================

def compute_f4_outcome_probability(
    semi1_result: np.ndarray,
    semi2_result: np.ndarray,
    champ_result: np.ndarray,
    p_semi1: np.ndarray,
    p_semi2: np.ndarray,
    p_champ: np.ndarray,
) -> np.ndarray:
    """Compute P(F4 outcome) for each bracket.

    Each result array is 0 or 1. p_ arrays are P(team_a wins).
    Result=0 means team_a won, result=1 means team_b won.

    Returns:
        (N,) float64 probability of the sampled F4 outcome.
    """
    p_s1 = np.where(semi1_result == 0, p_semi1, 1.0 - p_semi1)
    p_s2 = np.where(semi2_result == 0, p_semi2, 1.0 - p_semi2)
    p_ch = np.where(champ_result == 0, p_champ, 1.0 - p_champ)
    return p_s1 * p_s2 * p_ch


def pack_f4_outcomes(
    semi1: np.ndarray,
    semi2: np.ndarray,
    champ: np.ndarray,
) -> np.ndarray:
    """Pack 3 F4 game outcomes into a single int8.

    Bit 0 = semi1, bit 1 = semi2, bit 2 = championship.
    """
    return (
        semi1.astype(np.int8)
        | (semi2.astype(np.int8) << 1)
        | (champ.astype(np.int8) << 2)
    )


def unpack_f4_outcomes(
    packed: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Unpack 3-bit F4 outcomes into (semi1, semi2, champ) arrays."""
    semi1 = (packed & 1).astype(np.int8)
    semi2 = ((packed >> 1) & 1).astype(np.int8)
    champ = ((packed >> 2) & 1).astype(np.int8)
    return semi1, semi2, champ


# =========================================================================
# Champion resolution
# =========================================================================

# Region name → integer index for fast vectorized lookup
REGION_NAMES = ("South", "East", "West", "Midwest")
REGION_TO_IDX: dict[str, int] = {r: i for i, r in enumerate(REGION_NAMES)}


def resolve_tournament_champion(
    semi1_result: np.ndarray,
    semi2_result: np.ndarray,
    champ_result: np.ndarray,
    champ_seeds: dict[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    """Determine tournament champion seed and region for each bracket.

    Args:
        semi1_result: (N,) 0=semi1_a wins, 1=semi1_b wins.
        semi2_result: (N,) 0=semi2_a wins, 1=semi2_b wins.
        champ_result: (N,) 0=semi1 winner wins, 1=semi2 winner wins.
        champ_seeds: region_name → (N,) champion seed arrays.

    Returns:
        (champion_seeds, champion_region_idx): both (N,) int16/int8 arrays.
        champion_region_idx maps to REGION_NAMES tuple.
    """
    semi1_a, semi1_b = F4_SEMI_PAIRINGS[0]
    semi2_a, semi2_b = F4_SEMI_PAIRINGS[1]

    # Semi 1 winner
    s1_winner_seed = np.where(
        semi1_result == 0, champ_seeds[semi1_a], champ_seeds[semi1_b],
    )
    s1_winner_region = np.where(
        semi1_result == 0,
        REGION_TO_IDX[semi1_a],
        REGION_TO_IDX[semi1_b],
    ).astype(np.int8)

    # Semi 2 winner
    s2_winner_seed = np.where(
        semi2_result == 0, champ_seeds[semi2_a], champ_seeds[semi2_b],
    )
    s2_winner_region = np.where(
        semi2_result == 0,
        REGION_TO_IDX[semi2_a],
        REGION_TO_IDX[semi2_b],
    ).astype(np.int8)

    # Overall champion
    champion_seed = np.where(
        champ_result == 0, s1_winner_seed, s2_winner_seed,
    ).astype(np.int16)
    champion_region_idx = np.where(
        champ_result == 0, s1_winner_region, s2_winner_region,
    ).astype(np.int8)

    return champion_seed, champion_region_idx
