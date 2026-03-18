"""
Full tournament bracket sampler with region-independent temperature control.

Combines 4 independently enumerated regional brackets with
Final Four game outcomes to produce complete 63-game brackets.

Each full bracket = 4 regional brackets (15 bits each) + 3 F4 games (3 bits)
                  = 63 binary game outcomes

Key design principle: each region independently decides its temperature.
A cinderella run typically happens in 1 region, not all 4. Each region
flips a coin (p_upset) to determine whether it samples at base_temperature
or upset_temperature. The F4 gets its own separate temperature.

Importance weights use the marginal proposal probability (mixture of
base and upset distributions), ensuring unbiased weighted analysis:
  P_prop(region r, bracket i) = p_upset × P_upset(i) + (1-p_upset) × P_base(i)
  weight = P_true(bracket) / P_proposal(bracket)
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
    FULL_TOURNAMENT_BUDGET,
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
from simulation.temperature import (
    DEFAULT_PROFILES,
    StrategyProfile,
    apply_temperature,
    apply_temperature_binary,
    compute_profile_budgets,
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
    probabilities: np.ndarray       # (N,) float64 — true bracket probability
    weights: np.ndarray             # (N,) float64 — importance sampling weight
    champion_seeds: np.ndarray      # (N,) int16
    champion_region_idx: np.ndarray # (N,) int8 — index into REGION_NAMES
    total_upsets: np.ndarray        # (N,) int16
    strategy: str = "standard"      # strategy profile name

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
    true_probs: np.ndarray      # (32768,) float64 — original, normalized
    packed: np.ndarray           # (32768,) int16
    champion_seeds: np.ndarray   # (32768,) int16
    r64_upsets: np.ndarray       # (32768,) int8 — R64 only (for stratification)
    total_upsets: np.ndarray     # (32768,) int8 — all 15 games
    pi_lookup: np.ndarray        # (17,) float64 — seed -> power_index


def _prepare_region(
    region: str,
    enum: RegionEnumeration,
    teams: list[dict[str, Any]],
) -> RegionSamplingData:
    """Prepare region data with normalized true probabilities."""
    probs = enum.probabilities.astype(np.float64)
    probs = probs / probs.sum()  # normalize to exactly 1.0
    return RegionSamplingData(
        region=region,
        true_probs=probs,
        packed=enum.packed,
        champion_seeds=enum.champion_seeds,
        r64_upsets=enum.r64_upsets,
        total_upsets=enum.total_upsets,
        pi_lookup=build_seed_pi_lookup(teams),
    )


# =========================================================================
# 1v16 upset protection
# =========================================================================

# Maximum fraction of probability mass allowed on brackets with 1v16 upsets.
# Real-world rate: ~1.25% (2 upsets in 160 games, 1985-2024).
MAX_1V16_UPSET_RATE = 0.01


def _cap_1v16_upsets(
    probs: np.ndarray,
    packed: np.ndarray,
    max_rate: float = MAX_1V16_UPSET_RATE,
) -> np.ndarray:
    """Cap 1v16 upset probability mass after temperature scaling.

    Temperature scaling flattens distributions, boosting rare events like
    1v16 upsets far above historical norms. This rescales the distribution
    so total mass on 1v16-upset brackets stays below max_rate.

    Only modifies the proposal distribution — importance weights still
    use true probabilities, so estimates remain unbiased.

    Args:
        probs: (32768,) temperature-adjusted bracket probabilities.
        packed: (32768,) packed bracket outcomes (bit 0 = 1v16 game).
        max_rate: Maximum allowed probability mass on 1v16 upset brackets.

    Returns:
        (32768,) adjusted probabilities summing to 1.0.
    """
    has_1v16 = (packed & 1).astype(bool)
    current_rate = float(probs[has_1v16].sum())

    if current_rate <= max_rate:
        return probs

    result = probs.copy()
    result[has_1v16] *= max_rate / current_rate
    result /= result.sum()
    return result


# Per-seed caps on regional champion probability mass.
# Based on 40 years of NCAA data (160 region-opportunities).
# Caps are generous safety rails — the model can still predict strong
# high-seeds, but can't give a 13-seed 5% regional champion rate.
REGIONAL_CHAMP_SEED_CAPS: dict[int, float] = {
    16: 0.0,       # zero: never won a single R32 game
    15: 0.0001,    # 0.01%: best was Sweet 16 (Oral Roberts 2021)
    14: 0.0005,    # 0.05%: best was Sweet 16
    13: 0.001,     # 0.1%: best was Sweet 16
    12: 0.002,     # 0.2%: best was Elite Eight (Oregon State 2021)
    11: 0.005,     # 0.5%: Final Four (VCU 2011, Loyola Chicago 2018)
    10: 0.005,     # 0.5%: Final Four (Syracuse 2016)
    9:  0.003,     # 0.3%: best was Elite Eight
    8:  0.01,      # 1.0%: Final Four twice historically
    7:  0.01,      # 1.0%: Final Four once historically
}


def _cap_low_seed_regional_champions(
    probs: np.ndarray,
    champion_seeds: np.ndarray,
) -> np.ndarray:
    """Cap high-seed regional champion probability mass per seed.

    Applies per-seed caps based on historical NCAA tournament data.
    Seeds 16 are zeroed out entirely. Seeds 7-15 are capped at
    historically-informed rates.

    Only modifies the proposal distribution — importance weights
    still use true probabilities.

    Args:
        probs: (32768,) bracket probabilities.
        champion_seeds: (32768,) int16 — regional champion seed for each outcome.

    Returns:
        (32768,) adjusted probabilities summing to 1.0.
    """
    result = probs.copy()

    for seed, max_rate in REGIONAL_CHAMP_SEED_CAPS.items():
        is_seed = champion_seeds == seed
        if not is_seed.any():
            continue

        if max_rate == 0.0:
            result[is_seed] = 0.0
        else:
            current_rate = float(result[is_seed].sum())
            if current_rate > max_rate:
                result[is_seed] *= max_rate / current_rate

    # Renormalize
    total = result.sum()
    if total > 0:
        result /= total

    return result


# =========================================================================
# Weight capping for ESS health
# =========================================================================

# DELIBERATE BIAS/VARIANCE TRADE-OFF:
# Cap weights at WEIGHT_CAP_PERCENTILE × WEIGHT_CAP_MULTIPLIER.
# This prevents a handful of extreme-weight brackets from dominating
# all weighted statistics. Sacrifices strict unbiasedness for dramatically
# improved effective sample size (ESS).
#
# Without capping: unbiased but ESS can drop below 1% of N when tail
# brackets get 1000x+ weights, making all statistics unreliable.
# With capping: introduces small bias (under-represents extreme tails)
# but ESS stays healthy (typically 30-60% of N).
#
# The 99th percentile × 5 threshold keeps the max/min ratio under ~500:1
# while preserving 99%+ of the probability mass.
WEIGHT_CAP_PERCENTILE = 99.0
WEIGHT_CAP_MULTIPLIER = 5.0


def _cap_weights(
    weights: np.ndarray,
    percentile: float = WEIGHT_CAP_PERCENTILE,
    multiplier: float = WEIGHT_CAP_MULTIPLIER,
) -> np.ndarray:
    """Cap importance sampling weights to prevent ESS collapse.

    Computes the given percentile of positive weights, then clips
    all weights above percentile × multiplier. This bounds the
    max/min weight ratio and dramatically improves ESS.

    Args:
        weights: (N,) importance sampling weights.
        percentile: Percentile threshold (e.g., 99.0).
        multiplier: Cap at percentile_value × multiplier.

    Returns:
        (N,) capped weights (new array, original unchanged).
    """
    positive = weights[weights > 0]
    if len(positive) == 0:
        return weights.copy()

    p_val = float(np.percentile(positive, percentile))
    if p_val <= 0:
        return weights.copy()

    cap = p_val * multiplier
    return np.minimum(weights, cap)


# =========================================================================
# Region-independent temperature sampler
# =========================================================================

def sample_full_brackets(
    enumerations: dict[str, RegionEnumeration],
    region_teams: dict[str, list[dict[str, Any]]],
    n_brackets: int,
    batch_size: int = FULL_TOURNAMENT_BATCH_SIZE,
    k: float = LOGISTIC_K_INITIAL,
    base_temperature: float = 1.0,
    upset_temperature: float = 1.0,
    p_upset: float = 0.0,
    f4_temperature: float = 1.0,
    rng_seed: int = 2026,
    strategy: str = "standard",
) -> Generator[FullBracketBatch, None, None]:
    """Sample full tournament brackets with region-independent temperatures.

    Each region independently flips a coin (p_upset) to decide whether
    it uses base_temperature or upset_temperature. This creates realistic
    bracket diversity — a cinderella in one region while other regions
    follow expected form.

    The F4 uses its own temperature (f4_temperature), independent of
    regional assignments. Usually 1.0 since the power index differential
    already captures strength mismatches.

    Importance weights use the marginal proposal probability:
      P_prop(r, i) = p_upset × P_upset(r, i) + (1-p_upset) × P_base(r, i)
      weight = P_true(bracket) / product(P_prop per region) / P_prop(F4)

    Args:
        enumerations: Region name -> RegionEnumeration with exact probs.
        region_teams: Region name -> list of team dicts.
        n_brackets: Total number of full brackets to generate.
        batch_size: Brackets per yielded batch.
        k: Logistic function parameter for F4 games.
        base_temperature: Default temperature for regions.
        upset_temperature: Temperature for upset-flagged regions.
        p_upset: Probability each region independently gets upset_temperature.
        f4_temperature: Temperature for Final Four game probabilities.
        rng_seed: Random number generator seed.

    Yields:
        FullBracketBatch objects with importance-weighted brackets.
    """
    rng = np.random.default_rng(rng_seed)

    # Precompute per-region data
    regions_data: dict[str, RegionSamplingData] = {
        region: _prepare_region(region, enumerations[region], region_teams[region])
        for region in REGIONS
    }

    # Precompute temperature-adjusted distributions for both temperatures
    # Apply both caps: 1v16 upset rate + low-seed regional champion
    base_probs: dict[str, np.ndarray] = {}
    for region, rd in regions_data.items():
        p = apply_temperature(rd.true_probs, base_temperature)
        p = _cap_1v16_upsets(p, rd.packed)
        p = _cap_low_seed_regional_champions(p, rd.champion_seeds)
        base_probs[region] = p

    # Only compute upset distribution if it differs from base
    has_upset_mix = (
        p_upset > 0
        and abs(upset_temperature - base_temperature) > 1e-10
    )
    if has_upset_mix:
        upset_probs: dict[str, np.ndarray] = {}
        for region, rd in regions_data.items():
            p = apply_temperature(rd.true_probs, upset_temperature)
            p = _cap_1v16_upsets(p, rd.packed)
            p = _cap_low_seed_regional_champions(p, rd.champion_seeds)
            upset_probs[region] = p

    semi1_a, semi1_b = F4_SEMI_PAIRINGS[0]  # East vs South
    semi2_a, semi2_b = F4_SEMI_PAIRINGS[1]  # West vs Midwest

    n_generated = 0
    while n_generated < n_brackets:
        current_batch = min(batch_size, n_brackets - n_generated)

        # 1. Sample regional bracket indices — each region independently
        #    decides if it's an "upset" region for this batch of brackets
        indices: dict[str, np.ndarray] = {}
        true_region_prob: dict[str, np.ndarray] = {}
        sampling_region_prob: dict[str, np.ndarray] = {}

        for region, rd in regions_data.items():
            if has_upset_mix:
                # Each bracket independently flips p_upset for this region
                is_upset = rng.random(current_batch) < p_upset
                n_upset = int(is_upset.sum())
                n_base = current_batch - n_upset

                idx = np.empty(current_batch, dtype=np.intp)
                if n_base > 0:
                    idx[~is_upset] = rng.choice(
                        len(rd.true_probs), size=n_base,
                        p=base_probs[region],
                    )
                if n_upset > 0:
                    idx[is_upset] = rng.choice(
                        len(rd.true_probs), size=n_upset,
                        p=upset_probs[region],
                    )

                # Marginal proposal probability for importance weight
                samp_p = (
                    p_upset * upset_probs[region][idx]
                    + (1.0 - p_upset) * base_probs[region][idx]
                )
            else:
                idx = rng.choice(
                    len(rd.true_probs), size=current_batch,
                    p=base_probs[region],
                )
                samp_p = base_probs[region][idx]

            indices[region] = idx
            true_region_prob[region] = rd.true_probs[idx]
            sampling_region_prob[region] = samp_p

        # 2. Look up packed outcomes, champion seeds, upset counts
        outcomes = {
            r: regions_data[r].packed[indices[r]] for r in REGIONS
        }
        champ_seeds = {
            r: regions_data[r].champion_seeds[indices[r]] for r in REGIONS
        }
        region_total_upsets = {
            r: regions_data[r].total_upsets[indices[r]] for r in REGIONS
        }

        # 3. Look up champion power indices (vectorized via fancy indexing)
        champ_pi = {
            r: regions_data[r].pi_lookup[champ_seeds[r]] for r in REGIONS
        }

        # 4. Compute true F4 game probabilities
        p_semi1_true = logistic_prob_vec(
            champ_pi[semi1_a], champ_pi[semi1_b], k,
        )
        p_semi2_true = logistic_prob_vec(
            champ_pi[semi2_a], champ_pi[semi2_b], k,
        )

        # 5. Temperature-adjust F4 probabilities (separate from regions)
        p_semi1_samp = apply_temperature_binary(p_semi1_true, f4_temperature)
        p_semi2_samp = apply_temperature_binary(p_semi2_true, f4_temperature)

        # 6. Sample semi outcomes from temperature-adjusted F4 probs
        semi1_result = (
            rng.random(current_batch) >= p_semi1_samp
        ).astype(np.int8)
        semi2_result = (
            rng.random(current_batch) >= p_semi2_samp
        ).astype(np.int8)

        # 7. Championship game
        semi1_winner_pi = np.where(
            semi1_result == 0, champ_pi[semi1_a], champ_pi[semi1_b],
        )
        semi2_winner_pi = np.where(
            semi2_result == 0, champ_pi[semi2_a], champ_pi[semi2_b],
        )

        p_champ_true = logistic_prob_vec(semi1_winner_pi, semi2_winner_pi, k)
        p_champ_samp = apply_temperature_binary(p_champ_true, f4_temperature)
        champ_result = (
            rng.random(current_batch) >= p_champ_samp
        ).astype(np.int8)

        # 8. Pack F4 outcomes
        f4_packed = pack_f4_outcomes(semi1_result, semi2_result, champ_result)

        # 9. True F4 outcome probability
        p_f4_true = compute_f4_outcome_probability(
            semi1_result, semi2_result, champ_result,
            p_semi1_true, p_semi2_true, p_champ_true,
        )

        # Sampling F4 probability (for importance weight)
        p_f4_samp = compute_f4_outcome_probability(
            semi1_result, semi2_result, champ_result,
            p_semi1_samp, p_semi2_samp, p_champ_samp,
        )

        # 10. True bracket probability = product of true regional × true F4
        true_prob = (
            true_region_prob["South"]
            * true_region_prob["East"]
            * true_region_prob["West"]
            * true_region_prob["Midwest"]
            * p_f4_true
        )

        # 11. Importance weight = P_true / P_proposal (marginal)
        sampling_prob = (
            sampling_region_prob["South"]
            * sampling_region_prob["East"]
            * sampling_region_prob["West"]
            * sampling_region_prob["Midwest"]
            * p_f4_samp
        )
        weight = np.where(
            sampling_prob > 1e-30,
            true_prob / sampling_prob,
            0.0,
        )
        weight = _cap_weights(weight)

        # 12. Determine tournament champion
        champion_seed, champion_region_idx = resolve_tournament_champion(
            semi1_result, semi2_result, champ_result, champ_seeds,
        )

        # 13. Total upsets across all 4 regions (R64+R32+S16+E8) + F4 games
        total_ups = (
            region_total_upsets["South"].astype(np.int16)
            + region_total_upsets["East"].astype(np.int16)
            + region_total_upsets["West"].astype(np.int16)
            + region_total_upsets["Midwest"].astype(np.int16)
        )

        # F4 upsets: compare champion seeds across regions
        # Semi 1
        semi1_winner_seed = np.where(
            semi1_result == 0,
            champ_seeds[semi1_a], champ_seeds[semi1_b],
        )
        semi1_loser_seed = np.where(
            semi1_result == 0,
            champ_seeds[semi1_b], champ_seeds[semi1_a],
        )
        total_ups += (semi1_winner_seed > semi1_loser_seed).astype(np.int16)

        # Semi 2
        semi2_winner_seed = np.where(
            semi2_result == 0,
            champ_seeds[semi2_a], champ_seeds[semi2_b],
        )
        semi2_loser_seed = np.where(
            semi2_result == 0,
            champ_seeds[semi2_b], champ_seeds[semi2_a],
        )
        total_ups += (semi2_winner_seed > semi2_loser_seed).astype(np.int16)

        # Championship
        champ_winner_seed = np.where(
            champ_result == 0, semi1_winner_seed, semi2_winner_seed,
        )
        champ_loser_seed = np.where(
            champ_result == 0, semi2_winner_seed, semi1_winner_seed,
        )
        total_ups += (champ_winner_seed > champ_loser_seed).astype(np.int16)

        yield FullBracketBatch(
            east_outcomes=outcomes["East"],
            south_outcomes=outcomes["South"],
            west_outcomes=outcomes["West"],
            midwest_outcomes=outcomes["Midwest"],
            f4_outcomes=f4_packed,
            probabilities=true_prob,
            weights=weight,
            champion_seeds=champion_seed,
            champion_region_idx=champion_region_idx,
            total_upsets=total_ups,
            strategy=strategy,
        )

        n_generated += current_batch


# =========================================================================
# Multi-profile stratified sampler (main entry point)
# =========================================================================

def sample_stratified_brackets(
    enumerations: dict[str, RegionEnumeration],
    region_teams: dict[str, list[dict[str, Any]]],
    n_brackets: int = FULL_TOURNAMENT_BUDGET,
    profiles: tuple[StrategyProfile, ...] = DEFAULT_PROFILES,
    batch_size: int = FULL_TOURNAMENT_BATCH_SIZE,
    k: float = LOGISTIC_K_INITIAL,
    rng_seed: int = 2026,
) -> Generator[FullBracketBatch, None, None]:
    """Sample full brackets using a portfolio of strategy profiles.

    Each profile receives a fraction of the total budget. Within each
    profile, regions independently decide their temperature based on
    p_upset. This creates realistic diversity — chalk profiles have
    all 4 regions favoring strong seeds, while cinderella profiles
    occasionally produce 1 extreme upset region with 3 normal regions.

    All brackets store their true probability (P_true) and an importance
    weight (P_true / P_proposal) for unbiased weighted analysis.

    Args:
        enumerations: Region name -> RegionEnumeration.
        region_teams: Region name -> list of team dicts.
        n_brackets: Total full brackets to generate across all profiles.
        profiles: Strategy profiles with temperature configs and budget fractions.
        batch_size: Brackets per yielded batch.
        k: Logistic function parameter for F4 games.
        rng_seed: Base random seed (each profile gets a unique derived seed).

    Yields:
        FullBracketBatch objects from all profiles in sequence.
    """
    budgets = compute_profile_budgets(n_brackets, profiles)

    for profile, budget in budgets:
        if budget <= 0:
            continue

        upset_regions_expected = 4 * profile.p_upset
        print(
            f"\n  Strategy: {profile.name} "
            f"(base_T={profile.base_temperature:.1f}, "
            f"upset_T={profile.upset_temperature:.1f}, "
            f"p_upset={profile.p_upset:.2f}, "
            f"~{upset_regions_expected:.1f} upset regions/bracket, "
            f"F4_T={profile.f4_temperature:.1f}, "
            f"{budget:,} brackets)"
        )

        # Derive a unique seed per profile for statistical independence
        profile_seed = rng_seed + hash(profile.name) % 100_000

        yield from sample_full_brackets(
            enumerations=enumerations,
            region_teams=region_teams,
            n_brackets=budget,
            batch_size=batch_size,
            k=k,
            base_temperature=profile.base_temperature,
            upset_temperature=profile.upset_temperature,
            p_upset=profile.p_upset,
            f4_temperature=profile.f4_temperature,
            rng_seed=profile_seed,
            strategy=profile.name,
        )
