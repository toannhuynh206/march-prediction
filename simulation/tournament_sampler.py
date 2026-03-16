"""
Full tournament bracket sampler.

Combines 4 independently enumerated regional brackets with
Final Four game outcomes to produce complete 63-game brackets.

Each full bracket = 4 regional brackets (15 bits each) + 3 F4 games (3 bits)
                  = 63 binary game outcomes

Sampling pipeline per batch:
  1. Draw regional bracket indices from exact probability distributions
  2. Look up regional champion seeds and power indices
  3. Compute F4 game probabilities via logistic function
  4. Sample F4 outcomes (semi1, semi2, championship)
  5. Compute full bracket probability = ∏(regional) × P(F4 outcome)
  6. Yield batch for bulk DB insertion
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generator

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.constants import (
    F4_SEMI_PAIRINGS,
    FULL_TOURNAMENT_BATCH_SIZE,
    LOGISTIC_K_INITIAL,
    REGIONS,
)
from simulation.enumerate import RegionEnumeration
from simulation.final_four_probs import (
    build_seed_pi_lookup,
    compute_f4_outcome_probability,
    logistic_prob_vec,
    pack_f4_outcomes,
    resolve_tournament_champion,
)


# =========================================================================
# Batch container
# =========================================================================

@dataclass(frozen=True)
class FullBracketBatch:
    """One batch of full tournament brackets ready for DB insertion."""

    east_outcomes: np.ndarray       # (N,) int16 — packed 15-bit
    south_outcomes: np.ndarray      # (N,) int16
    west_outcomes: np.ndarray       # (N,) int16
    midwest_outcomes: np.ndarray    # (N,) int16
    f4_outcomes: np.ndarray         # (N,) int8 — 3-bit packed
    probabilities: np.ndarray       # (N,) float64
    champion_seeds: np.ndarray      # (N,) int16
    champion_region_idx: np.ndarray # (N,) int8 — index into REGION_NAMES
    total_upsets: np.ndarray        # (N,) int16

    @property
    def size(self) -> int:
        return len(self.east_outcomes)


# =========================================================================
# Precomputed region data
# =========================================================================

@dataclass(frozen=True)
class RegionSamplingData:
    """Precomputed data for sampling one region's brackets."""

    region: str
    probs: np.ndarray           # (32768,) float64 — normalized
    packed: np.ndarray          # (32768,) int16
    champion_seeds: np.ndarray  # (32768,) int16
    r64_upsets: np.ndarray      # (32768,) int8
    pi_lookup: np.ndarray       # (17,) float64 — seed → power_index


def _prepare_region(
    region: str,
    enum: RegionEnumeration,
    teams: list[dict[str, Any]],
) -> RegionSamplingData:
    """Prepare region data for fast sampling."""
    probs = enum.probabilities.astype(np.float64)
    probs = probs / probs.sum()  # normalize to exactly 1.0
    return RegionSamplingData(
        region=region,
        probs=probs,
        packed=enum.packed,
        champion_seeds=enum.champion_seeds,
        r64_upsets=enum.r64_upsets,
        pi_lookup=build_seed_pi_lookup(teams),
    )


# =========================================================================
# Main sampler
# =========================================================================

def sample_full_brackets(
    enumerations: dict[str, RegionEnumeration],
    region_teams: dict[str, list[dict[str, Any]]],
    n_brackets: int,
    batch_size: int = FULL_TOURNAMENT_BATCH_SIZE,
    k: float = LOGISTIC_K_INITIAL,
    rng_seed: int = 2026,
) -> Generator[FullBracketBatch, None, None]:
    """Sample full tournament brackets from enumerated regional distributions.

    Regions are sampled independently (correct because regional outcomes
    are independent given the probability model). F4 outcomes are then
    sampled conditional on the 4 regional champions.

    Args:
        enumerations: Region name → RegionEnumeration with exact probabilities.
        region_teams: Region name → list of team dicts (name, seed, power_index).
        n_brackets: Total number of full brackets to generate.
        batch_size: Brackets per yielded batch.
        k: Logistic function parameter for F4 games.
        rng_seed: Random number generator seed.

    Yields:
        FullBracketBatch objects, each containing batch_size brackets
        (last batch may be smaller).
    """
    rng = np.random.default_rng(rng_seed)

    # Precompute per-region sampling data
    regions_data: dict[str, RegionSamplingData] = {
        region: _prepare_region(region, enumerations[region], region_teams[region])
        for region in REGIONS
    }

    semi1_a, semi1_b = F4_SEMI_PAIRINGS[0]  # East vs South
    semi2_a, semi2_b = F4_SEMI_PAIRINGS[1]  # West vs Midwest

    n_generated = 0
    while n_generated < n_brackets:
        current_batch = min(batch_size, n_brackets - n_generated)

        # 1. Sample regional bracket indices independently
        indices = {
            region: rng.choice(
                len(rd.probs), size=current_batch, p=rd.probs,
            )
            for region, rd in regions_data.items()
        }

        # 2. Look up packed outcomes, champion seeds, upset counts
        outcomes = {
            r: regions_data[r].packed[indices[r]] for r in REGIONS
        }
        champ_seeds = {
            r: regions_data[r].champion_seeds[indices[r]] for r in REGIONS
        }
        upsets = {
            r: regions_data[r].r64_upsets[indices[r]] for r in REGIONS
        }
        region_prob = {
            r: regions_data[r].probs[indices[r]] for r in REGIONS
        }

        # 3. Look up champion power indices (vectorized via fancy indexing)
        champ_pi = {
            r: regions_data[r].pi_lookup[champ_seeds[r]] for r in REGIONS
        }

        # 4. Compute F4 game probabilities
        p_semi1 = logistic_prob_vec(champ_pi[semi1_a], champ_pi[semi1_b], k)
        p_semi2 = logistic_prob_vec(champ_pi[semi2_a], champ_pi[semi2_b], k)

        # 5. Sample semi outcomes
        semi1_result = (rng.random(current_batch) >= p_semi1).astype(np.int8)
        semi2_result = (rng.random(current_batch) >= p_semi2).astype(np.int8)

        # Determine semi winners' power indices for championship game
        semi1_winner_pi = np.where(
            semi1_result == 0, champ_pi[semi1_a], champ_pi[semi1_b],
        )
        semi2_winner_pi = np.where(
            semi2_result == 0, champ_pi[semi2_a], champ_pi[semi2_b],
        )

        # Championship probability and sampling
        p_champ = logistic_prob_vec(semi1_winner_pi, semi2_winner_pi, k)
        champ_result = (rng.random(current_batch) >= p_champ).astype(np.int8)

        # 6. Pack F4 outcomes
        f4_packed = pack_f4_outcomes(semi1_result, semi2_result, champ_result)

        # 7. Compute F4 outcome probability
        p_f4 = compute_f4_outcome_probability(
            semi1_result, semi2_result, champ_result,
            p_semi1, p_semi2, p_champ,
        )

        # 8. Full bracket probability = ∏(regional probs) × P(F4 outcome)
        full_prob = (
            region_prob["South"]
            * region_prob["East"]
            * region_prob["West"]
            * region_prob["Midwest"]
            * p_f4
        )

        # 9. Determine tournament champion
        champion_seed, champion_region_idx = resolve_tournament_champion(
            semi1_result, semi2_result, champ_result, champ_seeds,
        )

        # 10. Total R64 upsets across all 4 regions
        total_ups = (
            upsets["South"].astype(np.int16)
            + upsets["East"].astype(np.int16)
            + upsets["West"].astype(np.int16)
            + upsets["Midwest"].astype(np.int16)
        )

        yield FullBracketBatch(
            east_outcomes=outcomes["East"],
            south_outcomes=outcomes["South"],
            west_outcomes=outcomes["West"],
            midwest_outcomes=outcomes["Midwest"],
            f4_outcomes=f4_packed,
            probabilities=full_prob,
            champion_seeds=champion_seed,
            champion_region_idx=champion_region_idx,
            total_upsets=total_ups,
        )

        n_generated += current_batch
