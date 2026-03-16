"""
Project-wide constants for the March Madness simulation engine.

All magic numbers live here. Import from this module, never hardcode.
"""

from __future__ import annotations

# =========================================================================
# Tournament structure
# =========================================================================

TOURNAMENT_YEAR = 2026

REGIONS = ("South", "East", "West", "Midwest")

ROUNDS = ("R64", "R32", "S16", "E8", "F4", "Final")

# Standard seed matchups for Round of 64
R64_SEED_MATCHUPS = (
    (1, 16), (8, 9), (5, 12), (4, 13),
    (6, 11), (3, 14), (7, 10), (2, 15),
)

# =========================================================================
# Power index weights (9-factor model from CLAUDE.md)
# =========================================================================

POWER_INDEX_WEIGHTS = {
    "adj_em":           0.40,   # AdjEM (KenPom)
    "def_efficiency":   0.10,   # Defensive efficiency premium
    "nonconf_sos":      0.10,   # Non-conference SOS
    "experience":       0.10,   # Experience score (Bart Torvik)
    "luck":             0.08,   # Luck adjustment
    "ft_rate":          0.07,   # Free throw rate index
    "coaching":         0.07,   # Coaching tournament score
    "injuries":         0.05,   # Key injuries (hard point adjustment)
    "three_pt_var":     0.03,   # 3-point variance flag
}

# =========================================================================
# Win probability blend weights (spread-adaptive tiers)
# =========================================================================

BLEND_TIERS = {
    "locks": {
        "condition": lambda spread: abs(spread) > 15,
        "w_market": 0.60,
        "w_stats": 0.20,
        "w_matchup": 0.10,
        "w_factors": 0.10,
    },
    "lean": {
        "condition": lambda spread: 5 <= abs(spread) <= 15,
        "w_market": 0.45,
        "w_stats": 0.25,
        "w_matchup": 0.15,
        "w_factors": 0.15,
    },
    "coin_flip": {
        "condition": lambda spread: abs(spread) < 5,
        "w_market": 0.30,
        "w_stats": 0.25,
        "w_matchup": 0.25,
        "w_factors": 0.20,
    },
}

# =========================================================================
# Simulation parameters
# =========================================================================

# Full enumeration: 2^15 = 32,768 brackets per region, 131,072 total
BRACKETS_PER_REGION = 2 ** 15  # 32,768

# Total brackets across all 4 regions
TOTAL_BRACKETS = BRACKETS_PER_REGION * len(REGIONS)  # 131,072

# Batch size for PostgreSQL COPY inserts
COPY_BATCH_SIZE = 100_000

# Full tournament bracket generation
FULL_TOURNAMENT_BUDGET = 206_000_000   # 206M full brackets
FULL_TOURNAMENT_BATCH_SIZE = 1_000_000 # brackets per sampling/insert batch

# Final Four semi-final pairings (region_a vs region_b)
# 2026: #1 overall (Duke/East) vs #4 overall (Florida/South) on same side
#        #2 overall (Arizona/West) vs #3 overall (Michigan/Midwest) on same side
F4_SEMI_PAIRINGS: tuple[tuple[str, str], ...] = (
    ("East", "South"),      # Semi 1: East champion vs South champion
    ("West", "Midwest"),    # Semi 2: West champion vs Midwest champion
)

# Minimum brackets per champion seed tier (used by stratifier)
MIN_BRACKETS_PER_CHAMPION_SEED = 50_000

# Strategy profiles are defined in simulation/temperature.py:
#   Each region independently flips p_upset to decide base_T vs upset_T.
#   chalk (25%), standard (30%), mild_chaos (20%), cinderella (15%), chaos (10%)
#   All pairwise Hellinger distances > 0.10 (validated).

# =========================================================================
# Stratified sampling — world dimensions (legacy, unused in enumeration)
# =========================================================================

# R64 upset count range (0 to 8 upsets per region)
R64_UPSET_RANGE = range(0, 9)

# Champion seed tiers
CHAMPION_TIERS = ("1", "2-3", "4-6", "7+")

# =========================================================================
# Blue-blood futures deflator
# =========================================================================

BLUE_BLOOD_TEAMS = {"Duke", "Kansas", "Kentucky", "North Carolina"}
BLUE_BLOOD_DEFLATOR_RANGE = (0.88, 0.92)

# =========================================================================
# Logistic function
# =========================================================================

# k is calibrated via grid search against historical seed win rates.
# Calibrated 2026-03-15: k=47.75, Brier=0.1823 (target ≤ 0.205)
LOGISTIC_K_INITIAL = 47.75
LOGISTIC_K_RANGE = (10.0, 60.0)

# Target Brier score
TARGET_BRIER_SCORE = 0.205

# =========================================================================
# Data types (memory efficiency)
# =========================================================================

PROB_DTYPE = "float32"
BRACKET_DTYPE = "int16"

# =========================================================================
# API performance targets
# =========================================================================

GET_STATS_TARGET_MS = 200
POST_RESULTS_TARGET_MS = 2000
