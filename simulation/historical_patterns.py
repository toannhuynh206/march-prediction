"""
Historical pattern adjustments from 10-year (2015-2024) tournament data.

Encodes:
  1. Historical R64 seed win rates (anchor/regularization)
  2. 2026-specific scenario adjustments (BartTorvik metrics)
  3. Later-round team advancement boosts

Source: "Making Sense of the Madness 2026" Parts 1 & 2
  - 10 years of data, 40 games per seed matchup in R64
  - Scenario-based upset prediction using BartTorvik metrics
  - Round-specific metric importance (defense early, offense late)
"""

from __future__ import annotations

from typing import Any

import numpy as np


# =========================================================================
# Historical R64 higher-seed win rates (2015-2024, 10 years, 40 games each)
# =========================================================================

HISTORICAL_R64_RATES: dict[tuple[int, int], float] = {
    (1, 16): 0.950,   # 38-2
    (2, 15): 0.900,   # 36-4
    (3, 14): 0.875,   # 35-5
    (4, 13): 0.800,   # 32-8
    (5, 12): 0.675,   # 27-13
    (6, 11): 0.475,   # 19-21 — 6-seeds LOSE more than they win
    (7, 10): 0.625,   # 25-15
    (8, 9):  0.450,   # 18-22 — 8-seeds are underdogs
}


# =========================================================================
# 2026 scenario-based R64 adjustments
#
# Each entry: (higher_seed_name, lower_seed_name) → P(higher seed wins)
# Based on BartTorvik metric thresholds from Reddit analysis.
# =========================================================================

SCENARIO_2026_R64: dict[tuple[str, str], float] = {
    # Louisville(6) vs South Florida(11): BOTH upset scenarios met
    # Scenario A: Louisville AdjDE/3P%D/3PRD outside thresholds
    # Scenario B: South Florida defensive metrics + tempo profile
    # Historical when both scenarios met: 6-seeds are 1-7 (12.5%)
    ("Louisville", "South Florida"): 0.150,

    # Michigan State(3) vs NDSU(14): Scenario A met (TOR outside top 200)
    # When only scenario A met for 3-seeds: ~78% (vs 87.5% base)
    ("Michigan State", "North Dakota State"): 0.780,

    # Wisconsin(5) vs High Point(12): TORD ranked 324th (scenario A met)
    # Worst BARTHAG among 5-seeds
    # When scenario A met for 5-seeds: ~58% (vs 67.5% base)
    ("Wisconsin", "High Point"): 0.580,

    # Clemson(8) vs Iowa(9): Iowa is strong 9-seed meeting S16 criteria
    # Strong 9-seeds historically beat 8-seeds ~60% of the time
    ("Clemson", "Iowa"): 0.380,

    # Villanova(8) vs Utah State(9): Utah State meets advancement criteria
    # Strong 9-seed profile
    ("Villanova", "Utah State"): 0.400,

    # Tennessee(6) vs SMU(11): Model at 77.8% is massively overcalibrated
    # Tennessee has strong defense but 6v11 historical rate is 47.5%
    # No specific both-scenarios-met data, but model-vs-historical gap is huge
    # No scenario override identified → will be corrected by historical shrinkage
}

# No 1v16 or 4v13 upset scenarios were met in 2026 → chalk holds.
# 2v15 matchups: no specific red flags → historical rate applies.


# =========================================================================
# Later-round advancement boosts (prob_matrix multipliers)
#
# Applied as multipliers to a team's win probability in the 16×16 matrix.
# Source: round-by-round historical advancement rates from Reddit analysis.
# =========================================================================

# Seed-tier structural advantages for later rounds.
# 1-seeds have: easiest bracket path, closest venue, weakest opponents.
# These factors aren't captured in power index but matter historically.
SEED_TIER_BOOSTS: dict[int, float] = {
    1: 1.08,    # Strong structural advantage
    2: 1.03,    # Moderate structural advantage
    3: 1.01,    # Slight advantage
    4: 1.00,    # Neutral
}

# Team-specific advancement boosts (on top of seed-tier boosts).
# These reflect team-level historical patterns from BartTorvik scenarios.
TEAM_PROB_MATRIX_BOOSTS_2026: dict[str, float] = {
    # Houston(2-South): AdjDE+AdjOE both top 20 → 13/13 S16 historically
    # Strong S16 reliability, but tempered — represents S16 reach, not championship
    "Houston": 1.04,

    # UCLA(7-East): 3P% top 50 + AdjOE top 20 → 4/5 S16 historically
    "UCLA": 1.06,

    # Gonzaga(3-West): TOR top 30 + TORD top 130 → 3/3 E8 historically
    "Gonzaga": 1.06,

    # Duke(1-East): Best champion metrics match of any team
    # AdjOE top 5, 3+ players averaging 10+ ppg, no 20+ ppg scorer
    # Additional boost beyond 1-seed tier (champion profile)
    "Duke": 1.04,

    # Arizona(1-West): Meets both E8 advancement scenarios → 23/29
    # Additional boost beyond 1-seed tier
    "Arizona": 1.03,

    # Michigan(1-Midwest): Meets both E8 scenarios → 23/29
    # Additional boost beyond 1-seed tier
    "Michigan": 1.03,
}


# =========================================================================
# Historical R64 calibration
# =========================================================================

def calibrate_r64_probabilities(
    r64_top_win_probs: np.ndarray,
    seed_matchups: tuple[tuple[int, int], ...],
    teams: list[dict[str, Any]],
    year: int = 2026,
    model_weight: float = 0.50,
) -> np.ndarray:
    """Blend model R64 probabilities with historical base rates.

    Step 1: Shrink model toward historical rates (regularization).
    Step 2: Override with 2026 scenario adjustments where applicable.

    Args:
        r64_top_win_probs: (8,) P(higher seed wins) from 4-layer blend model.
        seed_matchups: 8 tuples of (higher_seed, lower_seed) per R64 game.
        teams: List of team dicts with 'name' and 'seed' keys.
        year: Tournament year (scenario adjustments only apply for 2026).
        model_weight: Weight on model probability vs historical (0-1).

    Returns:
        (8,) calibrated P(higher seed wins) array.
    """
    calibrated = np.copy(r64_top_win_probs).astype(np.float64)
    hist_weight = 1.0 - model_weight

    # Build seed → name lookup
    seed_to_name: dict[int, str] = {t["seed"]: t["name"] for t in teams}

    for game_idx, (seed_h, seed_l) in enumerate(seed_matchups):
        p_model = float(r64_top_win_probs[game_idx])

        # Step 1: Historical shrinkage
        p_hist = HISTORICAL_R64_RATES.get((seed_h, seed_l), p_model)
        p_blended = model_weight * p_model + hist_weight * p_hist

        # Step 2: 2026 scenario overrides
        if year == 2026:
            name_h = seed_to_name.get(seed_h, "")
            name_l = seed_to_name.get(seed_l, "")
            scenario_key = (name_h, name_l)

            if scenario_key in SCENARIO_2026_R64:
                p_scenario = SCENARIO_2026_R64[scenario_key]
                # Scenario evidence is strong — weight heavily
                p_blended = 0.30 * p_blended + 0.70 * p_scenario

        calibrated[game_idx] = np.clip(p_blended, 0.01, 0.99)

    return calibrated.astype(np.float32)


# =========================================================================
# Later-round probability matrix adjustment
# =========================================================================

def adjust_prob_matrix(
    prob_matrix: np.ndarray,
    teams: list[dict[str, Any]],
    year: int = 2026,
) -> np.ndarray:
    """Apply seed-tier and team-specific boosts to the 16×16 probability matrix.

    Two layers of adjustment:
      1. Seed-tier structural advantages (1-seeds get easiest path/venue)
      2. Team-specific advancement boosts (2026 BartTorvik scenarios)

    Args:
        prob_matrix: (16, 16) float32 pairwise win probabilities.
        teams: List of team dicts with 'name' and 'seed'.
        year: Tournament year.

    Returns:
        (16, 16) adjusted probability matrix (new array, not mutated).
    """
    from simulation.bracket_structure import SEED_TO_POSITION

    adjusted = np.copy(prob_matrix).astype(np.float64)
    seed_to_name: dict[int, str] = {t["seed"]: t["name"] for t in teams}

    for seed in range(1, 17):
        pos = SEED_TO_POSITION.get(seed)
        if pos is None:
            continue

        # Layer 1: Seed-tier structural advantage (always applied)
        tier_boost = SEED_TIER_BOOSTS.get(seed, 1.00)

        # Layer 2: Team-specific boost (2026 only)
        team_boost = 1.00
        if year == 2026:
            name = seed_to_name.get(seed, "")
            team_boost = TEAM_PROB_MATRIX_BOOSTS_2026.get(name, 1.00)

        total_boost = tier_boost * team_boost
        if total_boost == 1.00:
            continue

        # Apply combined boost to all win probabilities for this position
        for opp_pos in range(16):
            if opp_pos == pos:
                continue
            p_old = adjusted[pos, opp_pos]
            p_new = min(0.98, p_old * total_boost)
            adjusted[pos, opp_pos] = p_new
            adjusted[opp_pos, pos] = 1.0 - p_new

    return adjusted.astype(np.float32)
