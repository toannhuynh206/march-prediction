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
    (1, 16): 0.990,   # 158-2 (all-time 1985-2024) — only 2 upsets ever
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

# =========================================================================
# Seed-specific metric threshold scenarios (general, any year)
#
# From Reddit 10-year analysis: each seed matchup has specific metrics
# that predict upsets. When thresholds are met, historical upset rates
# deviate significantly from base rates.
#
# Thresholds are approximate conversions from BartTorvik rankings to
# raw stat values (e.g., "AdjDE top 25" ≈ adj_d < 92).
# =========================================================================

def compute_seed_scenario_adjustment(
    higher_team: dict[str, Any],
    lower_team: dict[str, Any],
    seed_h: int,
    seed_l: int,
) -> float | None:
    """Check metric-based upset vulnerability for a specific seed matchup.

    Uses 10-year (2015-2024) patterns: each seed matchup has "Scenario A"
    (higher seed vulnerable) and "Scenario B" (lower seed strong). When
    both scenarios are met, upset probability shifts dramatically.

    Args:
        higher_team: Stats dict for the higher seed (lower seed number).
        lower_team: Stats dict for the lower seed (higher seed number).
        seed_h: Higher seed number (e.g., 1 in a 1v16).
        seed_l: Lower seed number (e.g., 16 in a 1v16).

    Returns:
        P(higher seed wins) override if scenario is met, else None.
        Caller decides how much to weight this vs other signals.
    """
    matchup = (seed_h, seed_l)

    # --- 1v16: Slow tempo + can't force turnovers ---
    # Historical: 8-2 when Scenario A met, 30-0 when not met
    if matchup == (1, 16):
        tempo = higher_team.get("tempo") or 68.0
        steal_pct = higher_team.get("steal_pct") or 9.5
        # Slow tempo (<67) AND weak at forcing turnovers (steal% < 8)
        if tempo < 67.0 and steal_pct < 8.0:
            return 0.80  # 8-2 = 80% higher seed wins
        # Just slow tempo (one scenario)
        if tempo < 66.0:
            return 0.92  # Still favored but less so than 99% base

    # --- 2v15: Weak defense for a 2-seed ---
    # Historical: 2-seeds with AdjDE outside top 25 get upset ~15% of the time
    if matchup == (2, 15):
        adj_d = higher_team.get("adj_d") or 95.0
        # Higher adj_d = worse defense; "outside top 25" ≈ adj_d > 93
        if adj_d > 93.0:
            # Check if 15-seed has good defensive profile too
            lower_efg = lower_team.get("efg_pct") or 48.0
            lower_tpd = lower_team.get("three_pt_defense") or 33.0
            if lower_efg > 50.0 and lower_tpd < 31.0:
                return 0.78  # Both scenarios met
            return 0.85  # Just weak 2-seed defense

    # --- 3v14: Turnover battle ---
    # Historical: 0-3 for 3-seeds when BOTH scenarios met
    if matchup == (3, 14):
        to_pct_h = higher_team.get("to_pct") or 17.0
        steal_pct_l = lower_team.get("steal_pct") or 9.5
        to_pct_l = lower_team.get("to_pct") or 17.0
        # 3-seed careless (TOR outside top 200 ≈ to_pct > 18.5)
        scenario_a = to_pct_h > 18.5
        # 14-seed forces TOs (good steal%) AND protects ball (low TO%)
        scenario_b = steal_pct_l > 10.0 and to_pct_l < 16.0
        if scenario_a and scenario_b:
            return 0.55  # 0-3 historical, but small sample → moderate
        if scenario_a:
            return 0.78  # Just careless 3-seed

    # --- 4v13: Slow tempo 4-seed + efficient 13-seed ---
    # Historical: significant upset risk when pace favors underdog
    if matchup == (4, 13):
        tempo_h = higher_team.get("tempo") or 68.0
        efg_l = lower_team.get("efg_pct") or 48.0
        # Slow tempo 4-seed (<67) AND high-efficiency 13-seed (EFG% > 52)
        if tempo_h < 67.0 and efg_l > 52.0:
            return 0.65  # Both scenarios met
        if tempo_h < 66.0:
            return 0.73  # Just slow 4-seed

    # --- 5v12: TORD weakness + strong 12-seed defense ---
    # Historical: 3-7 for 5-seeds when both met
    if matchup == (5, 12):
        steal_pct_h = higher_team.get("steal_pct") or 9.5
        adj_d_l = lower_team.get("adj_d") or 95.0
        efg_l = lower_team.get("efg_pct") or 48.0
        # 5-seed can't force turnovers (steal% < 8.5)
        scenario_a = steal_pct_h < 8.5
        # 12-seed has good defense (adj_d < 96) or good efficiency
        scenario_b = adj_d_l < 96.0 or efg_l > 51.0
        if scenario_a and scenario_b:
            return 0.55  # 3-7 historical, moderated (model still favors 5-seed)
        if scenario_a:
            return 0.58  # Just weak TORD

    # --- 6v11: Turnover-prone 6-seed + experienced 11-seed coach ---
    # Historical: 1-7 for 6-seeds when both scenarios met
    if matchup == (6, 11):
        to_pct_h = higher_team.get("to_pct") or 17.0
        coach_l = lower_team.get("coaching_tourney_apps") or 0
        # 6-seed turns it over (TOR outside top ~150 ≈ to_pct > 18)
        scenario_a = to_pct_h > 18.0
        # 11-seed coach has tournament experience (proxy: 3+ appearances)
        scenario_b = coach_l >= 3
        if scenario_a and scenario_b:
            return 0.20  # 1-7 historical (12.5%), but moderate to 20%
        if scenario_a:
            return 0.38  # Just turnover-prone 6-seed (base is 47.5%)

    # --- 7v10: Inefficient 7-seed + defensive 10-seed ---
    # Historical: ~40% upset rate when scenarios met
    if matchup == (7, 10):
        efg_h = higher_team.get("efg_pct") or 50.0
        adj_d_l = lower_team.get("adj_d") or 95.0
        # 7-seed has poor shooting efficiency (EFG% < 49)
        scenario_a = efg_h < 49.0
        # 10-seed has good defense (adj_d < 95)
        scenario_b = adj_d_l < 95.0
        if scenario_a and scenario_b:
            return 0.50  # ~50-50 when both met
        if scenario_a:
            return 0.55  # Just inefficient 7-seed

    # --- 8v9: Slower tempo 9-seed + experienced coach ---
    # Historical: 0-10 for 8-seeds when both scenarios met
    if matchup == (8, 9):
        tempo_h = higher_team.get("tempo") or 68.0
        tempo_l = lower_team.get("tempo") or 68.0
        coach_l = lower_team.get("coaching_tourney_apps") or 0
        # 9-seed plays slower than 8-seed
        scenario_a = tempo_l < tempo_h - 1.0
        # 9-seed coach has S16 experience (proxy: 3+ tourney appearances)
        scenario_b = coach_l >= 3
        if scenario_a and scenario_b:
            return 0.15  # 0-10 historical → strong 9-seed advantage
        if scenario_a:
            return 0.40  # Just tempo advantage for 9-seed
        if scenario_b:
            return 0.42  # Just coaching advantage

    return None


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

    # Build seed → team stats lookup for scenario checks
    seed_to_team: dict[int, dict[str, Any]] = {t["seed"]: t for t in teams}

    for game_idx, (seed_h, seed_l) in enumerate(seed_matchups):
        p_model = float(r64_top_win_probs[game_idx])

        # Step 1: Historical shrinkage
        p_hist = HISTORICAL_R64_RATES.get((seed_h, seed_l), p_model)
        p_blended = model_weight * p_model + hist_weight * p_hist

        # Step 2: General metric-based scenario adjustment (any year)
        higher_team = seed_to_team.get(seed_h, {})
        lower_team = seed_to_team.get(seed_l, {})
        p_scenario_general = compute_seed_scenario_adjustment(
            higher_team, lower_team, seed_h, seed_l,
        )
        if p_scenario_general is not None:
            # Blend: 60% blended so far, 40% scenario evidence
            p_blended = 0.60 * p_blended + 0.40 * p_scenario_general

        # Step 3: 2026 hardcoded scenario overrides (take precedence)
        if year == 2026:
            name_h = seed_to_name.get(seed_h, "")
            name_l = seed_to_name.get(seed_l, "")
            scenario_key = (name_h, name_l)

            if scenario_key in SCENARIO_2026_R64:
                p_scenario = SCENARIO_2026_R64[scenario_key]
                # Hardcoded evidence is strongest — weight heavily
                p_blended = 0.30 * p_blended + 0.70 * p_scenario

        calibrated[game_idx] = np.clip(p_blended, 0.01, 0.99)

    return calibrated.astype(np.float32)


# =========================================================================
# Later-round probability matrix adjustment
# =========================================================================

def _compute_adj_oe_boost(team: dict[str, Any]) -> float:
    """Compute later-round AdjOE-based boost.

    Per Reddit analysis: AdjOE increasingly important for advancing past R32.
    Teams with top-tier offensive efficiency historically advance deeper.

    Returns multiplier >= 1.0 (no penalty, only boost).
    """
    adj_o = team.get("adj_o")
    if adj_o is None:
        return 1.00

    # Top ~10 AdjOE nationally ≈ adj_o > 122
    if adj_o > 122.0:
        return 1.05  # Strong offensive boost for later rounds
    # Top ~25 ≈ adj_o > 118
    if adj_o > 118.0:
        return 1.03
    # Top ~50 ≈ adj_o > 114
    if adj_o > 114.0:
        return 1.01
    return 1.00


def _compute_coaching_boost(team: dict[str, Any]) -> float:
    """Compute later-round coaching experience boost.

    Per Reddit analysis: coaching experience significantly predicts S16+
    advancement. Teams with experienced tournament coaches overperform
    seed expectations in later rounds.

    Returns multiplier >= 1.0.
    """
    apps = team.get("coaching_tourney_apps") or 0

    # Elite tournament coach (10+ appearances)
    if apps >= 10:
        return 1.04
    # Experienced (5-9 appearances)
    if apps >= 5:
        return 1.02
    # Some experience (3-4 appearances)
    if apps >= 3:
        return 1.01
    return 1.00


def adjust_prob_matrix(
    prob_matrix: np.ndarray,
    teams: list[dict[str, Any]],
    year: int = 2026,
) -> np.ndarray:
    """Apply seed-tier, team-specific, AdjOE, and coaching boosts to prob matrix.

    Four layers of adjustment:
      1. Seed-tier structural advantages (1-seeds get easiest path/venue)
      2. Team-specific advancement boosts (2026 BartTorvik scenarios)
      3. AdjOE-based later-round boost (offense increasingly important)
      4. Coaching experience later-round boost (experienced coaches advance)

    Args:
        prob_matrix: (16, 16) float32 pairwise win probabilities.
        teams: List of team dicts with 'name', 'seed', 'adj_o',
               'coaching_tourney_apps'.
        year: Tournament year.

    Returns:
        (16, 16) adjusted probability matrix (new array, not mutated).
    """
    from simulation.bracket_structure import SEED_TO_POSITION

    adjusted = np.copy(prob_matrix).astype(np.float64)
    seed_to_name: dict[int, str] = {t["seed"]: t["name"] for t in teams}
    seed_to_team: dict[int, dict[str, Any]] = {t["seed"]: t for t in teams}

    for seed in range(1, 17):
        pos = SEED_TO_POSITION.get(seed)
        if pos is None:
            continue

        team = seed_to_team.get(seed, {})

        # Layer 1: Seed-tier structural advantage (always applied)
        tier_boost = SEED_TIER_BOOSTS.get(seed, 1.00)

        # Layer 2: Team-specific boost (2026 only)
        team_boost = 1.00
        if year == 2026:
            name = seed_to_name.get(seed, "")
            team_boost = TEAM_PROB_MATRIX_BOOSTS_2026.get(name, 1.00)

        # Layer 3: AdjOE-based later-round boost (any year)
        adj_oe_boost = _compute_adj_oe_boost(team)

        # Layer 4: Coaching experience later-round boost (any year)
        coaching_boost = _compute_coaching_boost(team)

        total_boost = tier_boost * team_boost * adj_oe_boost * coaching_boost
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
