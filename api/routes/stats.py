"""Statistics endpoints: dashboard data, champion odds, upset distribution.

Uses stats_cache table for instant responses. Cache is refreshed after each
pruning operation (see api/services/pruner.py).
"""

from __future__ import annotations

import json
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
    """Dashboard statistics from pre-computed cache. Instant response."""
    engine = get_engine()
    with engine.connect() as conn:
        # Read from cache (single row, instant)
        cache = conn.execute(
            text(
                "SELECT total_brackets, alive_brackets, champion_odds, "
                "  upset_distribution "
                "FROM stats_cache WHERE tournament_year = :year"
            ),
            {"year": year},
        ).fetchone()

        if not cache:
            return {
                "total": 0,
                "alive_count": 0,
                "games_played": 0,
                "upsets_so_far": 0,
                "champion_odds": [],
                "upset_distribution": [],
            }

        # Games played from game_results (tiny table, always fast)
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

    champion_odds = cache[2] if isinstance(cache[2], list) else json.loads(cache[2]) if cache[2] else []
    upset_distribution = cache[3] if isinstance(cache[3], list) else json.loads(cache[3]) if cache[3] else []

    return {
        "total": cache[0],
        "alive_count": cache[1],
        "games_played": game_stats[0],
        "upsets_so_far": game_stats[1],
        "champion_odds": champion_odds[:30],
        "upset_distribution": upset_distribution,
    }


@router.get("/stats/regions/{region}")
async def get_region_stats(region: str, year: int = TOURNAMENT_YEAR):
    """Region-specific team list with championship probability from cache."""
    valid_regions = {"South", "East", "West", "Midwest"}
    if region not in valid_regions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid region. Must be one of: {', '.join(valid_regions)}",
        )

    engine = get_engine()
    with engine.connect() as conn:
        # Teams in this region (64 rows total, instant)
        teams = conn.execute(
            text(
                "SELECT name, seed, region, conference, record "
                "FROM teams "
                "WHERE region = :region AND tournament_year = :year "
                "ORDER BY seed"
            ),
            {"region": region, "year": year},
        ).fetchall()

        # Get champion odds from cache and extract this region's rates
        cache = conn.execute(
            text(
                "SELECT champion_odds FROM stats_cache "
                "WHERE tournament_year = :year"
            ),
            {"year": year},
        ).fetchone()

        champion_odds = []
        if cache and cache[0]:
            champion_odds = cache[0] if isinstance(cache[0], list) else json.loads(cache[0])

        # Build seed -> probability lookup from cached champion odds
        # Champion odds has team names — match to seeds via teams list
        name_to_prob = {entry["name"]: entry["probability"] for entry in champion_odds}

        team_list = [
            {
                "name": t[0],
                "seed": t[1],
                "region": t[2],
                "conference": t[3],
                "survival_rate": name_to_prob.get(t[0], 0.0),
            }
            for t in teams
        ]

        # Game results for this region (tiny table)
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
