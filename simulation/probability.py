"""
Build per-region probability matrices from database team data.

Produces a 16×16 win probability matrix for each region where
prob_matrix[i][j] = P(team at bracket position i beats team at position j).

Also provides R64-specific probability vectors for fast simulation.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.constants import LOGISTIC_K_INITIAL, REGIONS
from db.connection import session_scope
from simulation.bracket_structure import POSITION_TO_SEED, R64_GAMES, R64_SEED_MATCHUPS
from simulation.historical_patterns import (
    adjust_prob_matrix,
    calibrate_r64_probabilities,
)
from sqlalchemy import text


# =========================================================================
# Logistic win probability
# =========================================================================

def logistic_prob(
    power_a: float,
    power_b: float,
    k: float = LOGISTIC_K_INITIAL,
) -> float:
    """P(A wins) = 1 / (1 + 10^((power_B - power_A) / k))"""
    exponent = (power_b - power_a) / k
    return 1.0 / (1.0 + 10.0 ** exponent)


# =========================================================================
# Region data loading
# =========================================================================

def _load_region_teams(year: int, region: str) -> list[dict[str, Any]]:
    """Load team data for a region, ordered by seed.

    Returns list of dicts with power_index + all style stats for matchup analysis.
    """
    with session_scope() as session:
        rows = session.execute(text("""
            SELECT t.id, t.name, t.seed, ts.power_index,
                   ts.three_pt_pct, ts.three_pt_defense, ts.three_pt_rate,
                   ts.steal_pct, ts.to_pct, ts.block_pct,
                   ts.ft_rate, ts.ft_pct, ts.efg_pct,
                   ts.adj_d, ts.tempo, ts.height_avg_inches, ts.orb_pct,
                   ts.adj_o, ts.coaching_tourney_apps
            FROM teams t
            JOIN team_stats ts ON t.id = ts.team_id
              AND ts.tournament_year = :year
            WHERE t.tournament_year = :year
              AND t.region = :region
            ORDER BY t.seed
        """), {"year": year, "region": region}).fetchall()

    return [
        {
            "team_id": r[0], "name": r[1], "seed": r[2],
            "power_index": float(r[3]) if r[3] is not None else 50.0,
            "three_pt_pct": r[4], "three_pt_defense": r[5],
            "three_pt_rate": r[6], "steal_pct": r[7],
            "to_pct": r[8], "block_pct": r[9],
            "ft_rate": r[10], "ft_pct": r[11], "efg_pct": r[12],
            "adj_d": r[13], "tempo": r[14],
            "height_avg_inches": r[15], "orb_pct": r[16],
            "adj_o": float(r[17]) if r[17] is not None else None,
            "coaching_tourney_apps": int(r[18]) if r[18] is not None else 0,
        }
        for r in rows
    ]


def _load_r64_probabilities(year: int, region: str) -> dict[int, float]:
    """Load precomputed p_final for R64 matchups in a region.

    Returns {game_index: P(top team wins)} where top team = higher seed.
    The game_index maps to the R64 game order (0-7).
    """
    with session_scope() as session:
        rows = session.execute(text("""
            SELECT seed_a, seed_b, p_final
            FROM matchups
            WHERE tournament_year = :year
              AND region = :region
              AND round = 'R64'
              AND p_final IS NOT NULL
        """), {"year": year, "region": region}).fetchall()

    # Build seed matchup → p_final mapping
    seed_probs: dict[tuple[int, int], float] = {}
    for r in rows:
        seed_a, seed_b, p_final = int(r[0]), int(r[1]), float(r[2])
        # p_final is P(team_a wins), where team_a is the lower seed number (higher seed)
        higher_seed = min(seed_a, seed_b)
        lower_seed = max(seed_a, seed_b)
        if seed_a == higher_seed:
            seed_probs[(higher_seed, lower_seed)] = p_final
        else:
            seed_probs[(higher_seed, lower_seed)] = 1.0 - p_final

    # Map to game indices
    r64_probs: dict[int, float] = {}
    for game_idx, (seed_h, seed_l) in enumerate(R64_SEED_MATCHUPS):
        r64_probs[game_idx] = seed_probs.get((seed_h, seed_l), 0.5)

    return r64_probs


# =========================================================================
# Full probability matrix
# =========================================================================

def _style_matchup_adjustment(team_a: dict[str, Any], team_b: dict[str, Any]) -> float:
    """Compute style-based matchup adjustment between two teams.

    Factors in how teams' offensive strengths interact with opponents'
    defensive weaknesses: EFG%, 3PT shooting vs 3PT defense, turnovers,
    interior defense, free throw exploitation, offensive efficiency.

    Returns adjustment centered at 0.0 (positive = team_a advantage).
    """
    adj = 0.0

    # EFG% differential — overall shooting efficiency (Reddit: key predictor
    # across all seed groups, especially 5-8 and 13-16 seeds)
    efg_a = team_a.get("efg_pct")
    efg_b = team_b.get("efg_pct")
    if efg_a and efg_b:
        # Each percentage point of EFG% edge ≈ 0.4% win prob shift
        adj += np.clip((efg_a - efg_b) * 0.004, -0.04, 0.04)

    # Offensive efficiency differential — stronger offense matters more
    # in later rounds (Reddit: AdjOE increasingly important for advancement)
    adj_o_a = team_a.get("adj_o")
    adj_o_b = team_b.get("adj_o")
    if adj_o_a and adj_o_b:
        # Each point of AdjOE edge ≈ 0.15% win prob shift
        adj += np.clip((adj_o_a - adj_o_b) * 0.0015, -0.03, 0.03)

    # 3PT shooting vs 3PT defense mismatch
    tpp_a = team_a.get("three_pt_pct")
    tpp_b = team_b.get("three_pt_pct")
    tpd_a = team_a.get("three_pt_defense")
    tpd_b = team_b.get("three_pt_defense")
    if tpp_a and tpp_b and tpd_a and tpd_b:
        a_exploits_b = (tpp_a - 33.0) + (tpd_b - 33.0)
        b_exploits_a = (tpp_b - 33.0) + (tpd_a - 33.0)
        adj += np.clip((a_exploits_b - b_exploits_a) * 0.002, -0.03, 0.03)

    # Turnover battle
    steal_a = team_a.get("steal_pct")
    steal_b = team_b.get("steal_pct")
    to_a = team_a.get("to_pct")
    to_b = team_b.get("to_pct")
    if steal_a and steal_b and to_a and to_b:
        a_forces_b = (steal_a - 9.5) + (to_b - 17.0)
        b_forces_a = (steal_b - 9.5) + (to_a - 17.0)
        adj += np.clip((a_forces_b - b_forces_a) * 0.0015, -0.02, 0.02)

    # Interior defense vs perimeter offense
    block_a = team_a.get("block_pct")
    block_b = team_b.get("block_pct")
    tpr_a = team_a.get("three_pt_rate") or team_a.get("three_pt_pct")
    tpr_b = team_b.get("three_pt_rate") or team_b.get("three_pt_pct")
    if block_a and block_b and tpr_a and tpr_b:
        a_interior_d = (block_a - 10.0)
        b_perimeter = (tpr_b - 35.0)
        b_interior_d = (block_b - 10.0)
        a_perimeter = (tpr_a - 35.0)
        a_edge = a_interior_d * max(0.5, 1.0 - b_perimeter * 0.03)
        b_edge = b_interior_d * max(0.5, 1.0 - a_perimeter * 0.03)
        adj += np.clip((a_edge - b_edge) * 0.0015, -0.015, 0.015)

    # Free throw exploitation
    ftr_a = team_a.get("ft_rate")
    ftr_b = team_b.get("ft_rate")
    ftp_a = team_a.get("ft_pct")
    ftp_b = team_b.get("ft_pct")
    if ftr_a and ftr_b and ftp_a and ftp_b:
        a_ft_value = (ftr_a - 32.0) * 0.5 + (ftp_a - 72.0) * 0.3
        b_ft_value = (ftr_b - 32.0) * 0.5 + (ftp_b - 72.0) * 0.3
        adj += np.clip((a_ft_value - b_ft_value) * 0.0015, -0.015, 0.015)

    return np.clip(adj, -0.10, 0.10)


def build_probability_matrix(
    teams: list[dict[str, Any]],
    k: float = LOGISTIC_K_INITIAL,
) -> np.ndarray:
    """Build 16×16 win probability matrix from team data.

    Uses logistic function from power index differential as base,
    then applies style-based matchup adjustments (3PT, turnovers,
    interior defense, free throws) for each pair.

    Args:
        teams: List of team dicts with 'seed', 'power_index', and style stats.
        k: Logistic function parameter.

    Returns:
        prob_matrix: float32 array of shape (16, 16) where
        prob_matrix[i][j] = P(team at position i beats team at position j).
    """
    # Map seed → team data (power_index + style stats)
    seed_to_team: dict[int, dict[str, Any]] = {t["seed"]: t for t in teams}

    n = len(POSITION_TO_SEED)
    matrix = np.zeros((n, n), dtype=np.float32)

    for i in range(n):
        seed_i = POSITION_TO_SEED[i]
        team_i = seed_to_team.get(seed_i, {"power_index": 50.0})
        pi_i = team_i.get("power_index", 50.0)
        for j in range(n):
            if i == j:
                matrix[i, j] = 0.5  # self-play (unused)
                continue
            seed_j = POSITION_TO_SEED[j]
            team_j = seed_to_team.get(seed_j, {"power_index": 50.0})
            pi_j = team_j.get("power_index", 50.0)

            # Base probability from logistic function
            p_base = logistic_prob(pi_i, pi_j, k)

            # Style matchup adjustment
            style_adj = _style_matchup_adjustment(team_i, team_j)
            matrix[i, j] = np.clip(p_base + style_adj, 0.01, 0.99)

    return matrix


# =========================================================================
# Region probability bundle
# =========================================================================

class RegionProbabilities:
    """All probability data needed to simulate one region."""

    __slots__ = (
        "region", "year", "teams", "prob_matrix",
        "r64_top_win_probs", "seed_by_position",
    )

    def __init__(
        self,
        region: str,
        year: int,
        teams: list[dict[str, Any]],
        prob_matrix: np.ndarray,
        r64_top_win_probs: np.ndarray,
    ) -> None:
        self.region = region
        self.year = year
        self.teams = teams
        self.prob_matrix = prob_matrix
        self.r64_top_win_probs = r64_top_win_probs
        self.seed_by_position = np.array(
            [POSITION_TO_SEED[i] for i in range(16)], dtype=np.int16
        )


def load_region_probabilities(
    year: int,
    region: str,
    k: float = LOGISTIC_K_INITIAL,
) -> RegionProbabilities:
    """Load all probability data for a single region.

    Pipeline:
      1. Load teams and build base prob_matrix from logistic function
      2. Load precomputed R64 p_final from 4-layer blend model
      3. Calibrate R64 against historical rates + 2026 scenario adjustments
      4. Apply later-round team advancement boosts to prob_matrix
    """
    teams = _load_region_teams(year, region)
    if len(teams) < 16:
        raise ValueError(
            f"Region {region} has {len(teams)} teams, expected 16"
        )

    # Base probability matrix from logistic function
    base_prob_matrix = build_probability_matrix(teams, k)

    # R64 probabilities: prefer precomputed p_final (4-layer blend),
    # fall back to logistic-only from the matrix.
    r64_db_probs = _load_r64_probabilities(year, region)

    r64_model = np.zeros(8, dtype=np.float32)
    for game_idx, (top_pos, bot_pos) in enumerate(R64_GAMES):
        if game_idx in r64_db_probs:
            r64_model[game_idx] = r64_db_probs[game_idx]
        else:
            r64_model[game_idx] = base_prob_matrix[top_pos, bot_pos]

    # Calibrate R64 probs with historical rates + 2026 scenarios
    r64_calibrated = calibrate_r64_probabilities(
        r64_model, R64_SEED_MATCHUPS, teams, year=year,
    )

    # Apply later-round team advancement boosts
    adjusted_matrix = adjust_prob_matrix(base_prob_matrix, teams, year=year)

    return RegionProbabilities(
        region=region,
        year=year,
        teams=teams,
        prob_matrix=adjusted_matrix,
        r64_top_win_probs=r64_calibrated,
    )


def load_all_region_probabilities(
    year: int,
    k: float = LOGISTIC_K_INITIAL,
) -> dict[str, RegionProbabilities]:
    """Load probability data for all 4 regions."""
    return {
        region: load_region_probabilities(year, region, k)
        for region in REGIONS
    }
