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

    Returns list of dicts with: team_id, name, seed, power_index.
    """
    with session_scope() as session:
        rows = session.execute(text("""
            SELECT t.id, t.name, t.seed, ts.power_index
            FROM teams t
            JOIN team_stats ts ON t.id = ts.team_id
              AND ts.tournament_year = :year
            WHERE t.tournament_year = :year
              AND t.region = :region
            ORDER BY t.seed
        """), {"year": year, "region": region}).fetchall()

    return [
        {"team_id": r[0], "name": r[1], "seed": r[2],
         "power_index": float(r[3]) if r[3] is not None else 50.0}
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

def build_probability_matrix(
    teams: list[dict[str, Any]],
    k: float = LOGISTIC_K_INITIAL,
) -> np.ndarray:
    """Build 16×16 win probability matrix from team data.

    Args:
        teams: List of team dicts with 'seed' and 'power_index'.
        k: Logistic function parameter.

    Returns:
        prob_matrix: float32 array of shape (16, 16) where
        prob_matrix[i][j] = P(team at position i beats team at position j).
    """
    # Map seed → power_index
    seed_to_pi: dict[int, float] = {
        t["seed"]: t["power_index"] for t in teams
    }

    n = len(POSITION_TO_SEED)
    matrix = np.zeros((n, n), dtype=np.float32)

    for i in range(n):
        seed_i = POSITION_TO_SEED[i]
        pi_i = seed_to_pi.get(seed_i, 50.0)
        for j in range(n):
            if i == j:
                matrix[i, j] = 0.5  # self-play (unused)
                continue
            seed_j = POSITION_TO_SEED[j]
            pi_j = seed_to_pi.get(seed_j, 50.0)
            matrix[i, j] = logistic_prob(pi_i, pi_j, k)

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
