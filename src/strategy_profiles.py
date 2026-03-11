"""
Bracket generation strategy profiles.

Each profile defines a weighting function over the 32,768 enumerated
regional brackets (and cross-region combinations) to produce targeted
bracket batches optimized for different pool strategies.

The 10 core strategies:
  1. Contrarian Ownership — maximize EV = P(win) / ownership%
  2. Injury Alpha — exploit slow-to-price injury news
  3. Coaching Pedigree — overweight elite March coaches
  4. Correlated Upset Chains — model cascading upsets in a region
  5. Seed Historical Exploitation — exploit 5/12, 6/11 base rates
  6. Champion Diversification — spread champion picks across seeds
  7. Defense-First Filter — championship teams play top-30 AdjD
  8. Path-of-Least-Resistance — find easiest bracket paths
  9. Momentum / Peaking — teams on win streaks entering tournament
  10. Portfolio Theory — Core (60%) / Satellite (30%) / Moon (10%)

All functions are pure: they take data and return new objects.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional
import math

from calibration_targets import (
    FINAL_FOUR_SEED_RATES,
    CHAMPION_SEED_RATES,
    R64_UPSET_COUNT_DISTRIBUTIONS,
    MOST_LIKELY_R64_COMPOSITION,
)


# ---------------------------------------------------------------------------
# Profile definition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StrategyProfile:
    """Immutable bracket generation strategy.

    weight_fn: callable(bracket_int, region_data) -> float multiplier
        Applied to each of 32,768 regional brackets to re-weight them.
        Returns a multiplier >= 0. Higher = more likely to be selected.

    champion_bias: dict mapping seed -> multiplier for champion selection.
        E.g., {1: 0.8, 5: 2.0} = de-weight 1-seeds, boost 5-seeds as champions.

    upset_targets: set of (high_seed, low_seed) tuples to boost.
        These matchups get their upset probability multiplied by upset_boost.

    upset_boost: float multiplier for upset_targets.

    description: human-readable strategy description.
    """
    name: str
    description: str
    portfolio_tier: str  # "core", "satellite", "moon"
    champion_bias: dict = field(default_factory=dict)
    upset_targets: frozenset = field(default_factory=frozenset)
    upset_boost: float = 1.0
    defense_threshold_rank: Optional[int] = None  # require champion AdjD rank <= N
    coaching_boost_teams: frozenset = field(default_factory=frozenset)
    coaching_boost_factor: float = 1.0
    injury_downgrades: dict = field(default_factory=dict)  # team -> factor (< 1.0)
    momentum_boosts: dict = field(default_factory=dict)  # team -> factor (> 1.0)
    ownership_penalty_exponent: float = 0.0  # 0 = no penalty, 1.0 = full 1/ownership


# ---------------------------------------------------------------------------
# Probability adjustment functions
# ---------------------------------------------------------------------------

def apply_injury_adjustments(
    prob_matrix: dict[tuple[int, int], float],
    injury_map: dict[int, float],
    seed_to_team: dict[int, str],
    team_to_seed: dict[str, int],
) -> dict[tuple[int, int], float]:
    """Apply injury-based probability adjustments.

    injury_map: team_name -> downgrade_factor (0.0 to 1.0).
        0.5 means team's win probability is halved.

    Returns new probability matrix (no mutation).
    """
    updated = dict(prob_matrix)

    for matchup_key, p_fav in prob_matrix.items():
        seed_a, seed_b = matchup_key
        team_a = seed_to_team.get(seed_a, "")
        team_b = seed_to_team.get(seed_b, "")

        factor_a = injury_map.get(team_a, 1.0)
        factor_b = injury_map.get(team_b, 1.0)

        if factor_a != 1.0 or factor_b != 1.0:
            # Adjust: multiply fav prob by their factor, divide by opponent factor
            adjusted_p = p_fav * factor_a / max(factor_b, 0.01)
            updated[matchup_key] = max(0.005, min(0.995, adjusted_p))

    return updated


def apply_coaching_boost(
    prob_matrix: dict[tuple[int, int], float],
    boosted_seeds: frozenset[int],
    boost_factor: float,
) -> dict[tuple[int, int], float]:
    """Boost win probability for teams with elite March coaches.

    Returns new probability matrix.
    """
    updated = dict(prob_matrix)

    for matchup_key, p_fav in prob_matrix.items():
        seed_a, seed_b = matchup_key
        # seed_a is the higher seed (lower number = favorite)
        a_boosted = seed_a in boosted_seeds
        b_boosted = seed_b in boosted_seeds

        if a_boosted and not b_boosted:
            # Boost favorite
            boosted_p = min(0.995, p_fav * boost_factor)
            updated[matchup_key] = boosted_p
        elif b_boosted and not a_boosted:
            # Boost underdog (reduce favorite's probability)
            boosted_p = max(0.005, p_fav / boost_factor)
            updated[matchup_key] = boosted_p

    return updated


def apply_upset_boosts(
    prob_matrix: dict[tuple[int, int], float],
    upset_targets: frozenset[tuple[int, int]],
    boost_factor: float,
) -> dict[tuple[int, int], float]:
    """Boost upset probability for targeted matchups.

    upset_targets: set of (high_seed, low_seed) matchups to boost.
    boost_factor: multiplier for upset probability (> 1.0 = more upsets).

    Returns new probability matrix.
    """
    updated = dict(prob_matrix)

    for matchup_key in upset_targets:
        if matchup_key in prob_matrix:
            p_fav = prob_matrix[matchup_key]
            p_upset = 1.0 - p_fav
            boosted_upset = min(0.995, p_upset * boost_factor)
            updated[matchup_key] = 1.0 - boosted_upset

    return updated


def apply_ownership_penalty(
    bracket_prob: float,
    bracket_ownership_pct: float,
    exponent: float,
) -> float:
    """Compute contrarian EV = P(bracket) / ownership^exponent.

    Higher exponent = more contrarian.
    exponent=0 → pure probability maximization.
    exponent=1 → full Brier EV (P/ownership).
    """
    if exponent == 0.0:
        return bracket_prob
    if bracket_ownership_pct <= 0:
        # Unknown ownership — treat as average
        return bracket_prob
    return bracket_prob / (bracket_ownership_pct ** exponent)


# ---------------------------------------------------------------------------
# Strategy profile factory
# ---------------------------------------------------------------------------

def build_profile_modified_matrix(
    base_prob_matrix: dict[tuple[int, int], float],
    profile: StrategyProfile,
    seed_to_team: dict[int, str],
    team_to_seed: dict[str, int],
) -> dict[tuple[int, int], float]:
    """Apply all strategy profile adjustments to a base probability matrix.

    Returns a new probability matrix. Does not mutate the original.
    """
    modified = dict(base_prob_matrix)

    # 1. Injury downgrades
    if profile.injury_downgrades:
        modified = apply_injury_adjustments(
            modified, profile.injury_downgrades, seed_to_team, team_to_seed
        )

    # 2. Coaching boosts
    if profile.coaching_boost_teams and profile.coaching_boost_factor != 1.0:
        # Convert team names to seeds for this region
        boosted_seeds = frozenset(
            team_to_seed[t] for t in profile.coaching_boost_teams
            if t in team_to_seed
        )
        modified = apply_coaching_boost(
            modified, boosted_seeds, profile.coaching_boost_factor
        )

    # 3. Upset target boosts
    if profile.upset_targets and profile.upset_boost != 1.0:
        modified = apply_upset_boosts(
            modified, profile.upset_targets, profile.upset_boost
        )

    return modified


# ---------------------------------------------------------------------------
# Pre-built strategy profiles (2026 tournament)
# ---------------------------------------------------------------------------

# Injury data from injuries_2026.json
INJURY_DOWNGRADES_2026 = {
    "Duke": 0.75,        # Foster OUT (starting PG), Ngongba uncertain
    "UNC": 0.55,         # Wilson OUT (19.8 PPG, 9.4 RPG) — devastating
    "Texas Tech": 0.50,  # Toppin OUT (21.8/10.8, All-America)
    "BYU": 0.40,         # 6 players out including Saunders (18.8 PPG)
    "Gonzaga": 0.70,     # Huff (17.8 PPG) tight return timeline
    "Villanova": 0.65,   # Hodge ACL (starting F)
    "USC": 0.45,         # Baker-Mazara dismissed + Rice OUT
    "Arkansas": 0.90,    # Acuff ankle — probable but nagging
    "Tennessee": 0.85,   # Ament high ankle — probable but limited
}

# Elite March coaches from coaching_records_2026.json
ELITE_MARCH_COACHES_2026 = frozenset({
    "Michigan State",  # Izzo: 59-26, 8 Final Fours
    "UConn",           # Hurley: 15-5, 2 titles, defending champ dynasty
    "Houston",         # Sampson: strong March record
    "Kansas",          # Self: 57-24, 2 titles
    "Arkansas",        # Calipari: 59-23, 1 title, 6 Final Fours
    "Kentucky",        # Pope new but program culture
    "Florida",         # Golden: 12-1, defending champ
})

# Historical upset targets (seeds that consistently over-perform)
HISTORICAL_UPSET_TARGETS = frozenset({
    (5, 12),   # 35.6% upset rate — almost a coin flip
    (6, 11),   # 37.0% upset rate
    (7, 10),   # 39.0% upset rate
    (8, 9),    # 51.9% — 9-seeds actually win more often
    (3, 14),   # 15.0% — occasional Cinderella
    (4, 13),   # 21.0% — Sister Jean territory
})


STRATEGY_CHALK = StrategyProfile(
    name="chalk",
    description="Favorites win everything. All 1-seeds to Final Four. Minimal upsets.",
    portfolio_tier="core",
    champion_bias={1: 1.5, 2: 1.2, 3: 0.5, 4: 0.3},
)

STRATEGY_CONTRARIAN = StrategyProfile(
    name="contrarian_ownership",
    description="Maximize EV = P(correct) / Public_ownership%. Fade the public.",
    portfolio_tier="satellite",
    ownership_penalty_exponent=0.8,
    champion_bias={1: 0.6, 2: 0.8, 3: 1.5, 4: 1.8, 5: 2.0},
    upset_targets=HISTORICAL_UPSET_TARGETS,
    upset_boost=1.3,
)

STRATEGY_INJURY_ALPHA = StrategyProfile(
    name="injury_alpha",
    description="Exploit slow-to-price injury news. Downgrade injured teams, upgrade opponents.",
    portfolio_tier="satellite",
    injury_downgrades=INJURY_DOWNGRADES_2026,
    champion_bias={
        1: 0.9,  # Duke dinged
    },
)

STRATEGY_COACHING = StrategyProfile(
    name="coaching_pedigree",
    description="Overweight teams with elite March coaches (Izzo, Hurley, Self, Calipari).",
    portfolio_tier="satellite",
    coaching_boost_teams=ELITE_MARCH_COACHES_2026,
    coaching_boost_factor=1.15,
)

STRATEGY_CHAOS = StrategyProfile(
    name="correlated_chaos",
    description="Model cascading upsets. When one upset hits, the region goes haywire.",
    portfolio_tier="moon",
    upset_targets=HISTORICAL_UPSET_TARGETS,
    upset_boost=1.8,
    champion_bias={1: 0.3, 2: 0.5, 3: 1.5, 4: 2.0, 5: 2.5, 6: 2.0, 7: 1.5},
)

STRATEGY_SEED_EXPLOITER = StrategyProfile(
    name="seed_historical",
    description="Exploit seed matchup base rates. Heavy on 12/5, 11/6, 10/7 upsets.",
    portfolio_tier="satellite",
    upset_targets=frozenset({(5, 12), (6, 11), (7, 10), (8, 9)}),
    upset_boost=1.4,
    champion_bias={1: 1.0, 2: 1.0, 3: 1.2, 4: 1.3},
)

STRATEGY_CHAMPION_DIVERSITY = StrategyProfile(
    name="champion_diversity",
    description="Spread champion picks across seeds 1-6. No bracket pool should have all 1-seed champs.",
    portfolio_tier="core",
    champion_bias={1: 0.7, 2: 1.0, 3: 1.5, 4: 1.8, 5: 1.5, 6: 1.2},
)

STRATEGY_DEFENSE_FIRST = StrategyProfile(
    name="defense_first",
    description="Championship teams play top-30 AdjD defense. Filter out poor defensive teams.",
    portfolio_tier="core",
    defense_threshold_rank=30,
    champion_bias={1: 1.2, 2: 1.1},  # top seeds tend to have best D
)

STRATEGY_EASY_PATH = StrategyProfile(
    name="path_of_least_resistance",
    description="Find bracket paths where injuries/weakness create easy roads to Final Four.",
    portfolio_tier="satellite",
    injury_downgrades=INJURY_DOWNGRADES_2026,
    coaching_boost_teams=ELITE_MARCH_COACHES_2026,
    coaching_boost_factor=1.10,
    champion_bias={1: 1.0, 2: 1.3, 3: 1.5},
)

STRATEGY_MOMENTUM = StrategyProfile(
    name="momentum_peaking",
    description="Teams on 8+ game win streaks entering tournament get a boost.",
    portfolio_tier="satellite",
    momentum_boosts={
        "Florida": 1.15,      # 10-game win streak, fully healthy
        "Michigan": 1.10,     # 29-2, dominant season
        "Iowa State": 1.08,   # Strong late-season run
    },
)

# Polacheck Method: Historical base-rate composition (calibration anchor)
# Uses 40-year tournament data to build the statistically "most common" bracket.
# Serves as a Core tier anchor — the bracket most likely to match historical norms.
STRATEGY_BASE_RATE = StrategyProfile(
    name="historical_base_rate",
    description=(
        "Polacheck Method: build brackets matching the statistically most common "
        "tournament composition. 62.8% of champions are 1-seeds. The most common "
        "R64 has exactly 8 upsets. Final Four is typically 1-1-2-3."
    ),
    portfolio_tier="core",
    # Champion bias derived from CHAMPION_SEED_RATES (historical)
    champion_bias={
        1: 1.3,   # 62.8% historical — slight boost (already favored by model)
        2: 1.1,   # 17.1% — near fair
        3: 0.9,   # 8.6% — slight fade
        4: 0.5,   # 2.9% — significant fade
        5: 0.2,   # never won — heavy fade
        6: 0.3,   # extremely rare
        7: 0.3,   # UConn 2014 anomaly
        8: 0.3,   # Villanova 1985
    },
    # Target: the "most common" upset pattern from Polacheck
    # 2 upsets in 5v12 + 2 upsets in 6v11 = ~4 "expected" upsets at these seeds
    upset_targets=frozenset({(5, 12), (6, 11), (8, 9)}),
    upset_boost=1.15,  # gentle boost toward historical base rates
)


# All profiles indexed by name
ALL_PROFILES = {
    p.name: p for p in [
        STRATEGY_CHALK,
        STRATEGY_CONTRARIAN,
        STRATEGY_INJURY_ALPHA,
        STRATEGY_COACHING,
        STRATEGY_CHAOS,
        STRATEGY_SEED_EXPLOITER,
        STRATEGY_CHAMPION_DIVERSITY,
        STRATEGY_DEFENSE_FIRST,
        STRATEGY_EASY_PATH,
        STRATEGY_MOMENTUM,
        STRATEGY_BASE_RATE,
    ]
}

# Portfolio allocation
PORTFOLIO_ALLOCATION = {
    "core": 0.60,       # chalk + champion_diversity + defense_first + base_rate
    "satellite": 0.30,  # contrarian + injury + coaching + seed + path + momentum
    "moon": 0.10,       # correlated_chaos
}

CORE_PROFILES = [p for p in ALL_PROFILES.values() if p.portfolio_tier == "core"]
SATELLITE_PROFILES = [p for p in ALL_PROFILES.values() if p.portfolio_tier == "satellite"]
MOON_PROFILES = [p for p in ALL_PROFILES.values() if p.portfolio_tier == "moon"]
