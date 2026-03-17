"""
Math primitives for March Madness bracket simulation.

Core probability functions: de-vig, spread conversion, log-odds blending,
power index win probability, and bracket encoding/scoring.

All formulas match the locked spec in agents/reports/math-model-spec.md v3.
"""

import math
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SIGMA_SPREAD = 11.0  # spread-to-probability conversion std dev
K_DEFAULT = 47.75    # logistic model scaling factor (calibrated 2026-03-15: Brier=0.1823 on 271 games)

# CTO-locked weight tiers
WEIGHT_TIERS = {
    "game_lines": {"w_m": 0.55, "w_s": 0.25, "w_x": 0.12, "w_f": 0.08},
    "futures_only": {"w_m": 0.40, "w_s": 0.35, "w_x": 0.15, "w_f": 0.10},
    "no_market": {"w_m": 0.00, "w_s": 0.55, "w_x": 0.30, "w_f": 0.15},
    "live_tournament": {"w_m": 0.60, "w_s": 0.18, "w_x": 0.14, "w_f": 0.08},
    # Spread-adaptive tiers: weight shifts based on how informative the spread is
    "locks":      {"w_m": 0.60, "w_s": 0.20, "w_x": 0.10, "w_f": 0.10},  # |spread| > 15
    "lean":       {"w_m": 0.45, "w_s": 0.25, "w_x": 0.15, "w_f": 0.15},  # |spread| 5-15
    "coin_flip":  {"w_m": 0.30, "w_s": 0.25, "w_x": 0.25, "w_f": 0.20},  # |spread| < 5
}

# ESPN Tournament Challenge scoring
ROUND_POINTS = {
    "R64": 10,
    "R32": 20,
    "S16": 40,
    "E8": 80,
    "F4": 160,
    "Championship": 320,
}

# ---------------------------------------------------------------------------
# Logit / Sigmoid helpers
# ---------------------------------------------------------------------------

def logit(p: float) -> float:
    """Log-odds: logit(p) = ln(p / (1-p)). Clamps to avoid infinity."""
    p = max(1e-12, min(1 - 1e-12, p))
    return math.log(p / (1 - p))


def sigmoid(x: float) -> float:
    """Inverse logit: sigmoid(x) = 1 / (1 + exp(-x))."""
    if x >= 500:
        return 1.0
    if x <= -500:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


# ---------------------------------------------------------------------------
# De-vig functions (Spec Section 4)
# ---------------------------------------------------------------------------

def moneyline_to_implied(odds: int) -> float:
    """Convert American moneyline odds to implied probability.

    Favorite (negative odds): p = |odds| / (|odds| + 100)
    Underdog (positive odds): p = 100 / (odds + 100)
    """
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    else:
        return 100 / (odds + 100)


def de_vig_multiplicative(p_a: float, p_b: float) -> tuple[float, float]:
    """Multiplicative (proportional) de-vig.

    Removes the vig by scaling implied probabilities proportionally
    so they sum to 1.0.

    Returns (fair_p_a, fair_p_b).
    """
    total = p_a + p_b
    if total == 0:
        return 0.5, 0.5
    return p_a / total, p_b / total


def de_vig_power(p_a: float, p_b: float, max_iter: int = 50) -> tuple[float, float]:
    """Power method (Shin model) de-vig.

    Finds exponent n such that p_a^n + p_b^n = 1.
    More accurate for heavy favorites (odds beyond -300).

    Returns (fair_p_a, fair_p_b).
    """
    if p_a + p_b <= 1.0:
        return p_a, p_b

    lo, hi = 0.5, 2.0
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        total = p_a ** mid + p_b ** mid
        if total > 1.0:
            lo = mid
        else:
            hi = mid
        if abs(total - 1.0) < 1e-10:
            break

    return p_a ** ((lo + hi) / 2), p_b ** ((lo + hi) / 2)


def de_vig(odds_a: int, odds_b: int, method: str = "auto") -> tuple[float, float]:
    """Full de-vig pipeline: moneyline -> implied -> fair probability.

    method: "multiplicative", "power", or "auto" (power if favorite > -300).
    Returns (fair_p_a, fair_p_b).
    """
    p_a = moneyline_to_implied(odds_a)
    p_b = moneyline_to_implied(odds_b)

    if method == "auto":
        # Use power method for heavy favorites
        method = "power" if min(odds_a, odds_b) < -300 else "multiplicative"

    if method == "power":
        return de_vig_power(p_a, p_b)
    else:
        return de_vig_multiplicative(p_a, p_b)


# ---------------------------------------------------------------------------
# Spread-to-probability conversion (Spec Section 4.3)
# ---------------------------------------------------------------------------

def _phi(x: float) -> float:
    """Standard normal CDF approximation (Abramowitz & Stegun)."""
    # Use math.erf for exact computation
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def spread_to_prob(spread: float, sigma: float = SIGMA_SPREAD) -> float:
    """Convert point spread to win probability.

    P = Phi(spread / sigma) where spread is from Team A's perspective
    (negative spread = A is favored).

    Convention: spread < 0 means A is favored, so P(A wins) > 0.5.
    We negate because a -5.5 spread means A wins by 5.5.
    """
    return _phi(-spread / sigma)


# ---------------------------------------------------------------------------
# Power Index win probability (Spec Section 5.2)
# ---------------------------------------------------------------------------

def power_index_prob(pi_a: float, pi_b: float, k: float = K_DEFAULT) -> float:
    """Logistic model: P(A beats B) = 1 / (1 + 10^((PI_B - PI_A) / k)).

    Higher PI = stronger team. k controls sensitivity (calibrate per D004).
    """
    exponent = (pi_b - pi_a) / k
    # Clamp to prevent overflow
    exponent = max(-10, min(10, exponent))
    return 1.0 / (1.0 + 10 ** exponent)


# ---------------------------------------------------------------------------
# Log-odds blend (Spec Section 8)
# ---------------------------------------------------------------------------

def log_odds_blend(
    p_market: float,
    p_stats: float,
    p_matchup: float = 0.5,
    p_factors: float = 0.5,
    tier: str = "game_lines",
) -> float:
    """Blend four probability components in logit space.

    Returns P_final = sigmoid(w_m*logit(P_m) + w_s*logit(P_s) + w_x*logit(P_x) + w_f*logit(P_f))
    Clamped to [0.005, 0.995].

    tier: one of "game_lines", "futures_only", "no_market", "live_tournament"
    """
    weights = WEIGHT_TIERS[tier]

    blended_logit = (
        weights["w_m"] * logit(p_market)
        + weights["w_s"] * logit(p_stats)
        + weights["w_x"] * logit(p_matchup)
        + weights["w_f"] * logit(p_factors)
    )

    p_final = sigmoid(blended_logit)
    return max(0.005, min(0.995, p_final))


def get_spread_adaptive_tier(spread: float) -> str:
    """Select weight tier based on spread magnitude.

    For R64 Day 1 optimization: coin-flip games (|spread| < 5) amplify
    non-market signals where vibes and matchup analysis have more alpha.
    Locks (|spread| > 15) let Vegas dominate since the market is highly informative.

    Returns tier name for use with log_odds_blend().
    """
    abs_spread = abs(spread)
    if abs_spread > 15:
        return "locks"
    elif abs_spread >= 5:
        return "lean"
    else:
        return "coin_flip"


# ---------------------------------------------------------------------------
# Power Index computation (Spec Section 5.1)
# ---------------------------------------------------------------------------

# Factor weights from spec (9-factor model)
PI_WEIGHTS = {
    "adj_efficiency_margin": 0.40,       # AdjEM (KenPom) — single most predictive
    "defensive_efficiency_premium": 0.10, # Defense > Offense in single-elim
    "non_conference_sos": 0.10,          # Quality vs external competition
    "experience_score": 0.10,            # Upperclassmen correlation (Bart Torvik)
    "luck_adjustment": 0.08,             # Pythagorean gap — overperformers regress
    "free_throw_rate_index": 0.07,       # Discriminator in close games
    "coaching_tournament_score": 0.07,   # 15+ tournament appearances = bonus
    "key_injuries": 0.05,               # Hard point adjustment
    "three_point_variance_flag": 0.03,   # Widens distribution, doesn't shift mean
}


def normalize(value: float, min_val: float, max_val: float) -> float:
    """Min-max normalize to 0-100 scale across tournament field."""
    if max_val == min_val:
        return 50.0
    return (value - min_val) / (max_val - min_val) * 100


def compute_power_index(factors: dict[str, float]) -> float:
    """Compute composite power index from normalized factor values.

    factors: dict mapping factor name -> normalized value (0-100 scale).
    Only factors present in PI_WEIGHTS are used.
    """
    pi = 0.0
    for factor, weight in PI_WEIGHTS.items():
        if factor in factors:
            pi += weight * factors[factor]
    return pi


# ---------------------------------------------------------------------------
# 63-bit bracket encoding (Spec Section 10, Task 2)
# ---------------------------------------------------------------------------
#
# Bracket layout: 63 games total
#   Region order: South (bits 0-14), East (bits 15-29), West (bits 30-44), Midwest (bits 45-59)
#   Final Four: Semi1 (bit 60), Semi2 (bit 61), Championship (bit 62)
#
# Within each region (15 games, 15 bits):
#   Round of 64: games 0-7  (8 games, 8 bits)
#   Round of 32: games 8-11 (4 games, 4 bits)
#   Sweet 16:    games 12-13 (2 games, 2 bits)
#   Elite 8:     game 14     (1 game, 1 bit)
#
# Bit value: 0 = higher seed (favorite) wins, 1 = lower seed (upset)
#
# Game ordering within each round follows the bracket structure:
#   R64 game 0: 1-seed vs 16-seed
#   R64 game 1: 8-seed vs 9-seed
#   R64 game 2: 5-seed vs 12-seed
#   R64 game 3: 4-seed vs 13-seed
#   R64 game 4: 6-seed vs 11-seed
#   R64 game 5: 3-seed vs 14-seed
#   R64 game 6: 7-seed vs 10-seed
#   R64 game 7: 2-seed vs 15-seed
#
#   R32 game 8:  winner of game 0 vs winner of game 1
#   R32 game 9:  winner of game 2 vs winner of game 3
#   R32 game 10: winner of game 4 vs winner of game 5
#   R32 game 11: winner of game 6 vs winner of game 7
#
#   S16 game 12: winner of game 8 vs winner of game 9
#   S16 game 13: winner of game 10 vs winner of game 11
#
#   E8 game 14:  winner of game 12 vs winner of game 13
#
# Final Four:
#   Semi1 (bit 60): South champion vs East champion
#   Semi2 (bit 61): West champion vs Midwest champion
#   Championship (bit 62): Semi1 winner vs Semi2 winner

REGION_NAMES = ["South", "East", "West", "Midwest"]
REGION_OFFSETS = {"South": 0, "East": 15, "West": 30, "Midwest": 45}

# R64 matchups by seed (higher seed listed first = "favorite")
R64_MATCHUPS = [
    (1, 16), (8, 9), (5, 12), (4, 13),
    (6, 11), (3, 14), (7, 10), (2, 15),
]

# Parent game indices for each game within a region
# Games 0-7 have no parents (R64)
# Game 8's participants come from games 0, 1
# Game 9's participants come from games 2, 3
# etc.
PARENT_GAMES = {
    8: (0, 1),
    9: (2, 3),
    10: (4, 5),
    11: (6, 7),
    12: (8, 9),
    13: (10, 11),
    14: (12, 13),
}

GAME_ROUND = {}
for g in range(8):
    GAME_ROUND[g] = "R64"
for g in range(8, 12):
    GAME_ROUND[g] = "R32"
for g in range(12, 14):
    GAME_ROUND[g] = "S16"
GAME_ROUND[14] = "E8"


def encode_bracket(regional_bits: dict[str, int], f4_bits: int) -> int:
    """Encode a full bracket as a 63-bit integer.

    regional_bits: dict mapping region name -> 15-bit integer
    f4_bits: 3-bit integer (bit 0 = semi1, bit 1 = semi2, bit 2 = championship)
    """
    result = 0
    for region, offset in REGION_OFFSETS.items():
        result |= (regional_bits[region] & 0x7FFF) << offset
    result |= (f4_bits & 0x7) << 60
    return result


def decode_bracket(bracket_int: int) -> tuple[dict[str, int], int]:
    """Decode a 63-bit integer into regional brackets and F4 bits.

    Returns (regional_bits_dict, f4_bits).
    """
    regional = {}
    for region, offset in REGION_OFFSETS.items():
        regional[region] = (bracket_int >> offset) & 0x7FFF
    f4_bits = (bracket_int >> 60) & 0x7
    return regional, f4_bits


def get_game_bit(regional_int: int, game_idx: int) -> int:
    """Get the outcome bit for a specific game within a regional bracket.

    Returns 0 (favorite wins) or 1 (upset).
    """
    return (regional_int >> game_idx) & 1


def get_regional_winner_seed(regional_int: int) -> int:
    """Determine which seed wins a region given a 15-bit regional bracket.

    Traces the bracket tree from R64 through E8 to find the champion's seed.
    """
    # Start with R64 seeds
    game_winners = {}

    # R64: determine winners of first 8 games
    for g in range(8):
        high_seed, low_seed = R64_MATCHUPS[g]
        bit = get_game_bit(regional_int, g)
        game_winners[g] = low_seed if bit == 1 else high_seed

    # R32 through E8: trace winners through the bracket
    for g in [8, 9, 10, 11, 12, 13, 14]:
        parent_a, parent_b = PARENT_GAMES[g]
        seed_a = game_winners[parent_a]
        seed_b = game_winners[parent_b]
        # Bit determines which parent's winner advances
        # bit=0: "higher seed" (lower number) wins; bit=1: "lower seed" wins
        bit = get_game_bit(regional_int, g)
        if bit == 0:
            game_winners[g] = min(seed_a, seed_b)
        else:
            game_winners[g] = max(seed_a, seed_b)

    return game_winners[14]


# ---------------------------------------------------------------------------
# Regional bracket probability and scoring (Spec Section 9)
# ---------------------------------------------------------------------------

def compute_regional_bracket_prob(
    regional_int: int,
    prob_matrix: dict[tuple[int, int], float],
) -> float:
    """Compute P(regional bracket) given matchup-specific probabilities.

    regional_int: 15-bit encoding of regional bracket outcomes
    prob_matrix: dict mapping (seed_a, seed_b) -> P(seed_a beats seed_b)
                 where seed_a is the higher seed (lower number).

    Returns the product of game probabilities along the bracket path.
    """
    game_winners = {}
    log_prob = 0.0

    # R64
    for g in range(8):
        high_seed, low_seed = R64_MATCHUPS[g]
        bit = get_game_bit(regional_int, g)
        p_fav = prob_matrix.get((high_seed, low_seed), 0.5)
        if bit == 0:
            log_prob += math.log(max(p_fav, 1e-15))
            game_winners[g] = high_seed
        else:
            log_prob += math.log(max(1 - p_fav, 1e-15))
            game_winners[g] = low_seed

    # R32 through E8
    for g in [8, 9, 10, 11, 12, 13, 14]:
        parent_a, parent_b = PARENT_GAMES[g]
        seed_a = game_winners[parent_a]
        seed_b = game_winners[parent_b]
        high_seed = min(seed_a, seed_b)
        low_seed = max(seed_a, seed_b)
        bit = get_game_bit(regional_int, g)

        p_fav = prob_matrix.get((high_seed, low_seed), 0.5)

        if bit == 0:
            # Higher seed wins
            log_prob += math.log(max(p_fav, 1e-15))
            game_winners[g] = high_seed
        else:
            log_prob += math.log(max(1 - p_fav, 1e-15))
            game_winners[g] = low_seed

    return math.exp(log_prob)


def enumerate_regional_brackets(
    prob_matrix: dict[tuple[int, int], float],
) -> list[tuple[int, float]]:
    """Enumerate all 32,768 regional brackets with their probabilities.

    prob_matrix: dict mapping (high_seed, low_seed) -> P(high_seed wins)

    Returns list of (regional_int, probability) sorted by probability descending.
    """
    results = []
    for b in range(32768):
        p = compute_regional_bracket_prob(b, prob_matrix)
        results.append((b, p))
    results.sort(key=lambda x: x[1], reverse=True)
    return results


def score_regional_bracket(
    regional_int: int,
    actual_int: int,
) -> int:
    """Score a regional bracket against actual results.

    Returns total points earned using ESPN Tournament Challenge scoring.
    """
    rounds = ["R64"] * 8 + ["R32"] * 4 + ["S16"] * 2 + ["E8"]
    score = 0
    for g in range(15):
        pred_bit = get_game_bit(regional_int, g)
        actual_bit = get_game_bit(actual_int, g)
        if pred_bit == actual_bit:
            score += ROUND_POINTS[rounds[g]]
    return score


def expected_score_regional(
    regional_int: int,
    prob_matrix: dict[tuple[int, int], float],
) -> float:
    """Compute E[Score] for a regional bracket.

    For each game, computes the probability that the bracket's pick is correct
    (marginalizing over the paths that lead to that game's specific matchup).

    Simplified version: assumes the bracket's path determines the matchup,
    and uses the probability of that specific outcome.
    """
    game_winners = {}
    expected = 0.0
    rounds = ["R64"] * 8 + ["R32"] * 4 + ["S16"] * 2 + ["E8"]

    # R64
    for g in range(8):
        high_seed, low_seed = R64_MATCHUPS[g]
        bit = get_game_bit(regional_int, g)
        p_fav = prob_matrix.get((high_seed, low_seed), 0.5)
        p_correct = p_fav if bit == 0 else (1 - p_fav)
        expected += ROUND_POINTS[rounds[g]] * p_correct
        game_winners[g] = high_seed if bit == 0 else low_seed

    # Later rounds
    for g in [8, 9, 10, 11, 12, 13, 14]:
        parent_a, parent_b = PARENT_GAMES[g]
        seed_a = game_winners[parent_a]
        seed_b = game_winners[parent_b]
        high_seed = min(seed_a, seed_b)
        low_seed = max(seed_a, seed_b)
        bit = get_game_bit(regional_int, g)

        p_fav = prob_matrix.get((high_seed, low_seed), 0.5)
        p_correct = p_fav if bit == 0 else (1 - p_fav)
        expected += ROUND_POINTS[rounds[g]] * p_correct
        game_winners[g] = high_seed if bit == 0 else low_seed

    return expected
