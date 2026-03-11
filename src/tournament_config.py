"""
Tournament configuration for 2026 NCAA March Madness.

Central config file — change TOURNAMENT_YEAR here to switch everything.
All other modules import from this file.
"""

TOURNAMENT_YEAR = 2026

# Selection Sunday: March 15, 2026
# First Four: March 17-18, 2026
# R64: March 19-20, 2026
# R32: March 21-22, 2026
# S16: March 26-27, 2026
# E8: March 28-29, 2026
# F4: April 4, 2026
# Championship: April 6, 2026

REGIONS = ["South", "East", "West", "Midwest"]

# Simulation parameters
BRACKETS_PER_REGION = 3_000_000  # 3M per region, 12M total
TOTAL_BRACKETS = BRACKETS_PER_REGION * len(REGIONS)

# Minimum brackets per champion seed (coverage guarantee)
MIN_BRACKETS_PER_CHAMPION = 50_000

# Batch size for database COPY inserts
BATCH_SIZE = 100_000

# ESPN Tournament Challenge scoring
ROUND_POINTS = {
    "R64": 10,
    "R32": 20,
    "S16": 40,
    "E8": 80,
    "F4": 160,
    "Championship": 320,
}

# Sharpening: seeds that auto-advance R64
AUTO_ADVANCE_SEEDS = {1, 2}

# Weight tiers for probability blending
WEIGHT_TIERS = {
    "game_lines": {
        "market": 0.55, "rating": 0.25, "common_opp": 0.12, "factors": 0.08,
    },
    "futures_only": {
        "market": 0.10, "rating": 0.45, "common_opp": 0.25, "factors": 0.20,
    },
    "no_market": {
        "market": 0.00, "rating": 0.55, "common_opp": 0.30, "factors": 0.15,
    },
}

# Data source URLs (for research pipeline)
DATA_SOURCES = {
    "kenpom": "https://kenpom.com/",
    "torvik": "https://barttorvik.com/",
    "espn_bpi": "https://www.espn.com/mens-college-basketball/bpi",
    "net": "https://www.ncaa.com/rankings/basketball-men/d1/ncaa-mens-basketball-net-rankings",
    "vegas_spreads": "https://www.vegasinsider.com/college-basketball/odds/las-vegas/",
    "vegas_futures": "https://www.vegasinsider.com/college-basketball/odds/futures/",
    "sagarin": "https://sagarin.com/sports/cbsend.htm",
}
