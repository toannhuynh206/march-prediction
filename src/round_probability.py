"""
Round-adaptive win probability engine for March Madness simulation.

R64: Uses actual Vegas spreads/moneylines (highest confidence data).
R32+: Generates P(A beats B) for any hypothetical matchup using a
multi-signal algorithm that adapts weights by tournament round.

Signals for later rounds:
  1. Rating differential (KenPom AdjEM, Torvik, aggregated models)
  2. Head-to-head results (if teams played this season)
  3. Common opponent analysis (transitive margin comparison)
  4. Historical seed matchup rates (prior from 1985-2024)
  5. Round adjustment (defense/experience premium in later rounds)

Borrowed from OddsGods: Elo with cross-conference boost, isotonic calibration.
Our additions: aggregator blending, sharpening rules, 12M stratified sampling.
"""

import math
from typing import Optional

from math_primitives import logit, sigmoid, spread_to_prob, SIGMA_SPREAD


# ---------------------------------------------------------------------------
# Historical seed-vs-seed win rates (higher seed wins %)
# Source: 1985-2024 NCAA tournament data
# ---------------------------------------------------------------------------

SEED_WIN_RATES = {
    # R64 matchups
    (1, 16): 0.987, (2, 15): 0.935, (3, 14): 0.850, (4, 13): 0.790,
    (5, 12): 0.644, (6, 11): 0.630, (7, 10): 0.610, (8, 9): 0.481,
    # Common R32 matchups
    (1, 8): 0.800, (1, 9): 0.830, (2, 7): 0.710, (2, 10): 0.740,
    (3, 6): 0.620, (3, 11): 0.680, (4, 5): 0.560, (4, 12): 0.680,
    # Common S16 matchups
    (1, 4): 0.700, (1, 5): 0.750, (2, 3): 0.580, (2, 6): 0.650,
    (1, 12): 0.820, (1, 13): 0.870, (2, 11): 0.700, (3, 7): 0.600,
    (3, 10): 0.640,
    # Common E8 matchups
    (1, 2): 0.560, (1, 3): 0.620, (1, 6): 0.700, (1, 7): 0.720,
    (2, 4): 0.590, (2, 5): 0.610, (3, 4): 0.540, (3, 5): 0.560,
    # F4 / Championship (less seed-dependent, more talent)
    (1, 1): 0.500, (2, 2): 0.500, (1, 11): 0.750, (1, 10): 0.760,
}


# ---------------------------------------------------------------------------
# Round-specific weight profiles
# ---------------------------------------------------------------------------
# As the tournament progresses, different signals matter differently.
# R64: market odds dominate (we have actual lines).
# R32: ratings are primary, h2h and common opponents start to matter.
# S16+: seed history and defensive metrics gain weight.

ROUND_WEIGHTS = {
    "R64": {
        "rating": 0.25,       # secondary to market in R64
        "h2h": 0.05,
        "common_opp": 0.05,
        "seed_history": 0.05,
        "defense_exp": 0.05,
        "market": 0.55,       # Vegas dominates
    },
    "R32": {
        "rating": 0.45,       # primary signal
        "h2h": 0.10,
        "common_opp": 0.10,
        "seed_history": 0.15,
        "defense_exp": 0.10,
        "market": 0.10,       # futures only, less precise
    },
    "S16": {
        "rating": 0.40,
        "h2h": 0.10,
        "common_opp": 0.12,
        "seed_history": 0.18,
        "defense_exp": 0.12,
        "market": 0.08,
    },
    "E8": {
        "rating": 0.35,
        "h2h": 0.08,
        "common_opp": 0.12,
        "seed_history": 0.20,
        "defense_exp": 0.15,
        "market": 0.10,
    },
    "F4": {
        "rating": 0.35,
        "h2h": 0.05,
        "common_opp": 0.10,
        "seed_history": 0.20,
        "defense_exp": 0.20,
        "market": 0.10,
    },
    "Championship": {
        "rating": 0.35,
        "h2h": 0.05,
        "common_opp": 0.10,
        "seed_history": 0.20,
        "defense_exp": 0.20,
        "market": 0.10,
    },
}

# Defensive efficiency and experience premium by round
# Later rounds favor teams with better defense and more tourney experience
DEFENSE_PREMIUM = {
    "R64": 0.0, "R32": 0.02, "S16": 0.04, "E8": 0.06, "F4": 0.08, "Championship": 0.10,
}

EXPERIENCE_PREMIUM = {
    "R64": 0.0, "R32": 0.01, "S16": 0.03, "E8": 0.05, "F4": 0.07, "Championship": 0.08,
}


# ---------------------------------------------------------------------------
# Team data container
# ---------------------------------------------------------------------------

class TeamProfile:
    """Immutable team profile for probability computation."""

    __slots__ = (
        "name", "seed", "region",
        "adj_em", "adj_o", "adj_d", "tempo",
        "kenpom_rank", "torvik_rank", "bpi_rank", "net_rank",
        "elo", "defensive_rating", "experience_score",
        "conference", "tourney_appearances",
        "season_results",  # list of (opponent_name, margin, location)
    )

    def __init__(self, **kwargs):
        for slot in self.__slots__:
            setattr(self, slot, kwargs.get(slot))


# ---------------------------------------------------------------------------
# Signal computation functions
# ---------------------------------------------------------------------------

def compute_rating_signal(team_a: TeamProfile, team_b: TeamProfile) -> float:
    """Rating differential signal from aggregated model outputs.

    Combines KenPom AdjEM, Torvik, and BPI rankings into a single
    normalized differential. Converts to logit-scale signal.

    Returns: logit-scale value (positive = A favored).
    """
    # Primary: AdjEM differential (most predictive single metric)
    em_diff = (team_a.adj_em or 0) - (team_b.adj_em or 0)

    # Secondary: aggregate rank differential (lower rank = better)
    # Convert ranks to a differential, normalize
    rank_signals = []
    for rank_attr in ("kenpom_rank", "torvik_rank", "bpi_rank", "net_rank"):
        rank_a = getattr(team_a, rank_attr, None)
        rank_b = getattr(team_b, rank_attr, None)
        if rank_a is not None and rank_b is not None:
            # Negative = A is ranked higher (better)
            rank_signals.append(rank_b - rank_a)

    avg_rank_diff = sum(rank_signals) / len(rank_signals) if rank_signals else 0

    # Blend: AdjEM is calibrated in points, rank diff needs scaling
    # ~1 rank = ~0.3 AdjEM points (empirical approximation)
    combined_diff = em_diff * 0.7 + avg_rank_diff * 0.3 * 0.3

    # Convert to logit using spread-to-prob with sigma=11
    # This maps AdjEM differential to a probability-like signal
    p = spread_to_prob(-combined_diff, sigma=SIGMA_SPREAD)
    return logit(p)


def compute_h2h_signal(team_a: TeamProfile, team_b: TeamProfile) -> float:
    """Head-to-head signal: did these teams play this season?

    If they played, uses the margin (adjusted for home court) as a signal.
    If they didn't play, returns 0 (no information).

    Returns: logit-scale value (positive = A favored).
    """
    if not team_a.season_results or not team_b.season_results:
        return 0.0

    # Find games where A played B
    margins = []
    for opp_name, margin, location in (team_a.season_results or []):
        if opp_name == team_b.name:
            # Adjust for home court: ~3.5 points advantage
            if location == "home":
                adjusted_margin = margin - 3.5
            elif location == "away":
                adjusted_margin = margin + 3.5
            else:  # neutral
                adjusted_margin = margin
            margins.append(adjusted_margin)

    if not margins:
        return 0.0

    # Average margin across all meetings
    avg_margin = sum(margins) / len(margins)

    # Discount: single game has high variance, cap influence
    # One game: use 60% of signal. Two games: 80%. Three+: 90%
    discount = min(0.9, 0.4 + 0.2 * len(margins))

    # Convert margin to logit signal
    p = spread_to_prob(-avg_margin * discount, sigma=SIGMA_SPREAD)
    return logit(p)


def compute_common_opponent_signal(
    team_a: TeamProfile,
    team_b: TeamProfile,
) -> float:
    """Common opponent analysis: transitive margin comparison.

    For each opponent both teams played, compare their margins.
    If A beat opponent X by 10 and B beat X by 5, A gets +5 signal.

    Returns: logit-scale value (positive = A favored).
    """
    if not team_a.season_results or not team_b.season_results:
        return 0.0

    # Build margin lookup: opponent -> list of (margin, location)
    def build_margins(results):
        opp_margins = {}
        for opp_name, margin, location in results:
            # Normalize to neutral court
            if location == "home":
                adj = margin - 3.5
            elif location == "away":
                adj = margin + 3.5
            else:
                adj = margin
            opp_margins.setdefault(opp_name, []).append(adj)
        return {k: sum(v) / len(v) for k, v in opp_margins.items()}

    margins_a = build_margins(team_a.season_results)
    margins_b = build_margins(team_b.season_results)

    # Find common opponents (exclude each other)
    common = set(margins_a.keys()) & set(margins_b.keys())
    common.discard(team_a.name)
    common.discard(team_b.name)

    if not common:
        return 0.0

    # Average margin differential against common opponents
    diffs = [margins_a[opp] - margins_b[opp] for opp in common]
    avg_diff = sum(diffs) / len(diffs)

    # Discount based on number of common opponents (more = more reliable)
    # 1-3 common: 40%, 4-6: 60%, 7+: 75%
    n = len(common)
    discount = min(0.75, 0.25 + 0.05 * n)

    p = spread_to_prob(-avg_diff * discount, sigma=SIGMA_SPREAD)
    return logit(p)


def compute_seed_history_signal(seed_a: int, seed_b: int) -> float:
    """Historical seed matchup prior from 1985-2024 data.

    Returns: logit-scale value (positive = A favored, where A is higher seed).
    """
    high_seed = min(seed_a, seed_b)
    low_seed = max(seed_a, seed_b)

    p = SEED_WIN_RATES.get((high_seed, low_seed))

    if p is None:
        # Fallback: estimate from seed gap
        seed_gap = low_seed - high_seed
        p = sigmoid(seed_gap * 0.15)  # rough approximation

    # If team_a is NOT the higher seed, flip
    if seed_a > seed_b:
        p = 1.0 - p

    return logit(p)


def compute_defense_experience_signal(
    team_a: TeamProfile,
    team_b: TeamProfile,
    tournament_round: str,
) -> float:
    """Defense and experience premium for later rounds.

    Later rounds favor:
    - Teams with elite defense (AdjD)
    - Teams with tournament experience (appearances, coach history)

    Returns: logit-scale value (positive = A favored).
    """
    defense_prem = DEFENSE_PREMIUM.get(tournament_round, 0)
    experience_prem = EXPERIENCE_PREMIUM.get(tournament_round, 0)

    signal = 0.0

    # Defensive efficiency comparison
    adj_d_a = team_a.adj_d or 100
    adj_d_b = team_b.adj_d or 100
    # Lower AdjD = better defense
    # Normalize: diff of 5 in AdjD is significant
    defense_diff = (adj_d_b - adj_d_a) / 5.0  # positive = A has better defense
    signal += defense_diff * defense_prem

    # Experience: tourney appearances (rough proxy)
    exp_a = team_a.tourney_appearances or 0
    exp_b = team_b.tourney_appearances or 0
    exp_diff = (exp_a - exp_b) / 5.0  # normalize
    signal += exp_diff * experience_prem

    # Experience: Elo as a proxy for program strength
    elo_a = team_a.elo or 1500
    elo_b = team_b.elo or 1500
    elo_diff = (elo_a - elo_b) / 400.0  # Elo scale
    signal += elo_diff * experience_prem * 0.5

    return signal  # already in logit-ish scale


def compute_market_signal(
    team_a: TeamProfile,
    team_b: TeamProfile,
    spread: Optional[float] = None,
    futures_a: Optional[float] = None,
    futures_b: Optional[float] = None,
) -> float:
    """Market signal from Vegas spreads or futures odds.

    R64: uses actual game spreads (most accurate).
    R32+: uses futures odds differential as a proxy.

    Returns: logit-scale value (positive = A favored).
    """
    if spread is not None:
        # Direct spread available (R64)
        p = spread_to_prob(-spread, sigma=SIGMA_SPREAD)
        return logit(p)

    if futures_a is not None and futures_b is not None:
        # Futures odds: convert to implied probabilities
        # Higher futures prob = more likely to go deep = stronger
        # Use log ratio as signal
        if futures_a > 0 and futures_b > 0:
            log_ratio = math.log(futures_a / futures_b)
            # Scale: a 2x ratio in futures ≈ 3-4 point spread
            implied_spread = log_ratio * 5.0
            p = spread_to_prob(-implied_spread, sigma=SIGMA_SPREAD)
            return logit(p)

    return 0.0  # no market data


# ---------------------------------------------------------------------------
# Main probability computation
# ---------------------------------------------------------------------------

def compute_win_probability(
    team_a: TeamProfile,
    team_b: TeamProfile,
    tournament_round: str,
    spread: Optional[float] = None,
    futures_a: Optional[float] = None,
    futures_b: Optional[float] = None,
) -> float:
    """Compute P(A beats B) using round-adaptive signal weighting.

    For R64: market signal dominates (actual Vegas lines).
    For R32+: blends rating, h2h, common opponents, seed history,
    defense/experience, and futures (if available).

    Returns: probability in [0.005, 0.995].
    """
    weights = ROUND_WEIGHTS.get(tournament_round, ROUND_WEIGHTS["R32"])

    # Compute all signals (logit scale)
    signals = {
        "rating": compute_rating_signal(team_a, team_b),
        "h2h": compute_h2h_signal(team_a, team_b),
        "common_opp": compute_common_opponent_signal(team_a, team_b),
        "seed_history": compute_seed_history_signal(
            team_a.seed, team_b.seed,
        ),
        "defense_exp": compute_defense_experience_signal(
            team_a, team_b, tournament_round,
        ),
        "market": compute_market_signal(
            team_a, team_b, spread, futures_a, futures_b,
        ),
    }

    # Weighted blend in logit space
    blended_logit = sum(
        weights[key] * signals[key] for key in weights
    )

    p = sigmoid(blended_logit)
    return max(0.005, min(0.995, p))


# ---------------------------------------------------------------------------
# Probability matrix builder for simulation
# ---------------------------------------------------------------------------

def build_probability_matrix(
    teams: dict[int, TeamProfile],
    tournament_round: str,
    spreads: Optional[dict[tuple[str, str], float]] = None,
    futures: Optional[dict[str, float]] = None,
) -> dict[tuple[int, int], float]:
    """Build P(A beats B) for all possible matchups in a round.

    teams: dict mapping seed -> TeamProfile (within one region)
    tournament_round: "R64", "R32", etc.
    spreads: optional dict of (team_a_name, team_b_name) -> spread
    futures: optional dict of team_name -> championship probability

    Returns: dict mapping (seed_a, seed_b) -> P(seed_a beats seed_b)
             where seed_a < seed_b (higher seed first).
    """
    if spreads is None:
        spreads = {}
    if futures is None:
        futures = {}

    prob_matrix = {}
    seeds = sorted(teams.keys())

    for i, seed_a in enumerate(seeds):
        for seed_b in seeds[i + 1:]:
            team_a = teams[seed_a]
            team_b = teams[seed_b]

            # Look up spread (if available)
            spread = spreads.get((team_a.name, team_b.name))
            if spread is None:
                # Try reverse
                rev_spread = spreads.get((team_b.name, team_a.name))
                if rev_spread is not None:
                    spread = -rev_spread

            # Look up futures
            fut_a = futures.get(team_a.name)
            fut_b = futures.get(team_b.name)

            p = compute_win_probability(
                team_a, team_b, tournament_round,
                spread=spread,
                futures_a=fut_a,
                futures_b=fut_b,
            )

            prob_matrix[(seed_a, seed_b)] = p

    return prob_matrix


def build_full_tournament_matrices(
    regions: dict[str, dict[int, TeamProfile]],
    spreads: Optional[dict[tuple[str, str], float]] = None,
    futures: Optional[dict[str, float]] = None,
) -> dict[str, dict[str, dict[tuple[int, int], float]]]:
    """Build probability matrices for all rounds and regions.

    Returns nested dict: region -> round -> (seed_a, seed_b) -> P(A wins).
    For R64, uses spreads. For R32+, uses the adaptive algorithm.
    """
    if spreads is None:
        spreads = {}
    if futures is None:
        futures = {}

    rounds = ["R64", "R32", "S16", "E8"]
    all_matrices = {}

    for region_name, teams in regions.items():
        region_matrices = {}
        for rnd in rounds:
            matrix = build_probability_matrix(
                teams, rnd,
                spreads=spreads,
                futures=futures,
            )
            region_matrices[rnd] = matrix
        all_matrices[region_name] = region_matrices

    return all_matrices
