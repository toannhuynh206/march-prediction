"""Statistics endpoints: dashboard data, champion odds, upset distribution."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from config.constants import TOURNAMENT_YEAR
from db.connection import get_engine

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
async def get_stats(year: int = TOURNAMENT_YEAR):
    """Dashboard statistics: counts, champion odds, upset distribution."""
    engine = get_engine()
    with engine.connect() as conn:
        # Total and alive counts
        counts = conn.execute(
            text(
                "SELECT "
                "  COUNT(*) AS total, "
                "  COUNT(*) FILTER (WHERE is_alive = TRUE) AS alive "
                "FROM full_brackets "
                "WHERE tournament_year = :year"
            ),
            {"year": year},
        ).fetchone()
        total = counts[0]
        alive = counts[1]

        # Games played and upsets from game_results
        game_stats = conn.execute(
            text(
                "SELECT "
                "  COUNT(*) AS games_played, "
                "  COUNT(*) FILTER (WHERE winner_seed > loser_seed) AS upsets "
                "FROM game_results "
                "WHERE tournament_year = :year"
            ),
            {"year": year},
        ).fetchone()
        games_played = game_stats[0]
        upsets_so_far = game_stats[1]

        # Champion odds — weighted among alive brackets
        # JOIN with teams to get champion name
        champion_rows = conn.execute(
            text(
                "SELECT t.name, fb.champion_seed, fb.champion_region, "
                "  SUM(fb.weight) AS total_weight "
                "FROM full_brackets fb "
                "JOIN teams t ON t.seed = fb.champion_seed "
                "  AND t.region = fb.champion_region "
                "  AND t.tournament_year = fb.tournament_year "
                "WHERE fb.is_alive = TRUE AND fb.tournament_year = :year "
                "GROUP BY t.name, fb.champion_seed, fb.champion_region "
                "ORDER BY total_weight DESC"
            ),
            {"year": year},
        ).fetchall()

        total_weight = sum(float(r[3]) for r in champion_rows) if champion_rows else 1.0
        champion_odds = [
            {
                "name": r[0],
                "probability": float(r[3]) / total_weight,
            }
            for r in champion_rows
        ]

        # Upset distribution — count of alive brackets by total_upsets
        upset_rows = conn.execute(
            text(
                "SELECT total_upsets, COUNT(*) "
                "FROM full_brackets "
                "WHERE is_alive = TRUE AND tournament_year = :year "
                "GROUP BY total_upsets "
                "ORDER BY total_upsets"
            ),
            {"year": year},
        ).fetchall()

        upset_distribution = [
            {"upsets": int(r[0]), "count": int(r[1])}
            for r in upset_rows
        ]

    return {
        "total": total,
        "alive_count": alive,
        "games_played": games_played,
        "upsets_so_far": upsets_so_far,
        "champion_odds": champion_odds[:30],
        "upset_distribution": upset_distribution,
    }


@router.get("/stats/regions/{region}")
async def get_region_stats(region: str, year: int = TOURNAMENT_YEAR):
    """Region-specific team list with championship probability."""
    valid_regions = {"South", "East", "West", "Midwest"}
    if region not in valid_regions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid region. Must be one of: {', '.join(valid_regions)}",
        )

    engine = get_engine()
    with engine.connect() as conn:
        # Teams in this region
        teams = conn.execute(
            text(
                "SELECT name, seed, region, conference, record "
                "FROM teams "
                "WHERE region = :region AND tournament_year = :year "
                "ORDER BY seed"
            ),
            {"region": region, "year": year},
        ).fetchall()

        # Total weight across all alive brackets
        total_weight = conn.execute(
            text(
                "SELECT COALESCE(SUM(weight), 1.0) FROM full_brackets "
                "WHERE is_alive = TRUE AND tournament_year = :year"
            ),
            {"year": year},
        ).scalar()

        # Championship probability per seed from this region
        champion_rates = conn.execute(
            text(
                "SELECT champion_seed, SUM(weight) AS total_weight "
                "FROM full_brackets "
                "WHERE is_alive = TRUE AND tournament_year = :year "
                "  AND champion_region = :region "
                "GROUP BY champion_seed"
            ),
            {"year": year, "region": region},
        ).fetchall()

        seed_rate = {int(r[0]): float(r[1]) / float(total_weight) for r in champion_rates}

        team_list = [
            {
                "name": t[0],
                "seed": t[1],
                "region": t[2],
                "conference": t[3],
                "survival_rate": seed_rate.get(t[1], 0.0),
            }
            for t in teams
        ]

        # Game results for this region
        results = conn.execute(
            text(
                "SELECT round, game_number, winner_name, loser_name, "
                "  winner_seed, loser_seed "
                "FROM game_results "
                "WHERE region = :region AND tournament_year = :year "
                "ORDER BY entered_at"
            ),
            {"region": region, "year": year},
        ).fetchall()

        result_list = [
            {
                "round": r[0],
                "game_number": r[1],
                "winner": r[2],
                "loser": r[3],
                "upset": int(r[4]) > int(r[5]),
            }
            for r in results
        ]

    return {
        "region": region,
        "teams": team_list,
        "results": result_list,
    }
