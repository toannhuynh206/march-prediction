"""Bracket endpoints: list, detail, and tournament bracket view."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import text

from config.constants import TOURNAMENT_YEAR
from db.connection import get_engine
from api.services.decoder import (
    load_region_teams,
    decode_full_bracket,
    get_champion_name_from_db,
)

router = APIRouter(prefix="/api", tags=["brackets"])

# In-memory cache for region teams (64 teams, never changes mid-tournament)
_region_teams_cache: dict[int, dict] = {}


def _get_region_teams(year: int) -> dict:
    if year not in _region_teams_cache:
        _region_teams_cache[year] = load_region_teams(year)
    return _region_teams_cache[year]


@router.get("/bracket")
async def get_tournament_bracket(year: int = TOURNAMENT_YEAR):
    """Full tournament bracket: teams, seeds, matchups with probabilities."""
    engine = get_engine()
    with engine.connect() as conn:
        teams = conn.execute(
            text(
                "SELECT name, seed, region, conference, record "
                "FROM teams "
                "WHERE tournament_year = :year "
                "ORDER BY region, seed"
            ),
            {"year": year},
        ).fetchall()

        regions: dict[str, list] = {}
        for t in teams:
            region = t[2]
            if region not in regions:
                regions[region] = []
            regions[region].append({
                "name": t[0],
                "seed": t[1],
                "region": region,
                "conference": t[3],
                "record": t[4],
            })

        matchups = conn.execute(
            text(
                "SELECT m.game_index, m.round, m.region, "
                "  ta.name AS team_a, m.seed_a, "
                "  tb.name AS team_b, m.seed_b, "
                "  m.p_market, m.p_stats, m.p_matchup, m.p_factors, m.p_final "
                "FROM matchups m "
                "JOIN teams ta ON m.team_a_id = ta.id "
                "JOIN teams tb ON m.team_b_id = tb.id "
                "WHERE m.tournament_year = :year "
                "ORDER BY m.region, m.round, m.game_index"
            ),
            {"year": year},
        ).fetchall()

        matchup_list = [
            {
                "game_index": m[0],
                "round": m[1],
                "region": m[2],
                "team_a": m[3],
                "seed_a": m[4],
                "team_b": m[5],
                "seed_b": m[6],
                "p_market": m[7],
                "p_stats": m[8],
                "p_matchup": m[9],
                "p_factors": m[10],
                "p_final": m[11],
            }
            for m in matchups
        ]

    return {"year": year, "regions": regions, "matchups": matchup_list}


@router.get("/brackets")
async def list_brackets(
    cursor: str | None = Query(None, description="Cursor: 'value_id'"),
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("probability", pattern="^(score|probability)$"),
    status: str = Query("alive", pattern="^(all|alive|dead)$"),
    champion: str | None = Query(None, description="Filter by champion team name"),
    year: int = TOURNAMENT_YEAR,
):
    """Paginated bracket list with cursor-based (keyset) pagination.

    Sort by 'score' uses weight (importance sampling weight) as proxy.
    Sort by 'probability' uses the true bracket probability.
    """
    engine = get_engine()
    region_teams = _get_region_teams(year)

    with engine.connect() as conn:
        # Resolve champion name to seed + region if filter provided
        champ_seed = None
        champ_region = None
        if champion:
            team_row = conn.execute(
                text(
                    "SELECT seed, region FROM teams "
                    "WHERE name = :name AND tournament_year = :year"
                ),
                {"name": champion, "year": year},
            ).fetchone()
            if not team_row:
                return {
                    "brackets": [],
                    "cursor": None,
                    "has_more": False,
                    "total": 0,
                    "alive_count": 0,
                }
            champ_seed = team_row[0]
            champ_region = team_row[1]

        # Read counts from cache (instant) instead of scanning 206M rows
        cache = conn.execute(
            text(
                "SELECT total_brackets, alive_brackets "
                "FROM stats_cache WHERE tournament_year = :year"
            ),
            {"year": year},
        ).fetchone()
        total = cache[0] if cache else 0
        alive_count = cache[1] if cache else 0

        # Build query
        conditions = ["fb.tournament_year = :year"]
        params: dict = {"year": year, "lim": limit + 1}

        if champ_seed is not None:
            conditions.append(
                "fb.champion_seed = :champ_seed AND fb.champion_region = :champ_region"
            )
            params["champ_seed"] = champ_seed
            params["champ_region"] = champ_region

        sort_col = "fb.weight" if sort == "score" else "fb.probability"

        if cursor:
            parts = cursor.split("_", 1)
            if len(parts) == 2:
                cursor_val = float(parts[0])
                cursor_id = int(parts[1])
                conditions.append(
                    f"({sort_col} < :cursor_val "
                    f"OR ({sort_col} = :cursor_val AND fb.id > :cursor_id))"
                )
                params["cursor_val"] = cursor_val
                params["cursor_id"] = cursor_id

        where = " AND ".join(conditions)

        # JOIN against alive tables to filter only surviving brackets
        alive_joins = (
            "JOIN alive_outcomes_south   ao_s ON fb.south_outcomes   = ao_s.outcome_value "
            "JOIN alive_outcomes_east    ao_e ON fb.east_outcomes    = ao_e.outcome_value "
            "JOIN alive_outcomes_west    ao_w ON fb.west_outcomes    = ao_w.outcome_value "
            "JOIN alive_outcomes_midwest ao_m ON fb.midwest_outcomes = ao_m.outcome_value "
            "JOIN alive_outcomes_f4      ao_f ON fb.f4_outcomes      = ao_f.outcome_value "
        ) if status == "alive" else ""

        rows = conn.execute(
            text(
                f"SELECT fb.id, fb.weight, fb.probability, fb.champion_seed, "
                f"  fb.champion_region, fb.total_upsets, TRUE as is_alive, t.name "
                f"FROM full_brackets fb "
                f"{alive_joins}"
                f"LEFT JOIN teams t ON t.seed = fb.champion_seed "
                f"  AND t.region = fb.champion_region "
                f"  AND t.tournament_year = fb.tournament_year "
                f"WHERE {where} "
                f"ORDER BY {sort_col} DESC, fb.id ASC "
                f"LIMIT :lim"
            ),
            params,
        ).fetchall()

        has_more = len(rows) > limit
        rows = rows[:limit]

        brackets = [
            {
                "id": row[0],
                "rank": rank_offset + 1,
                "expected_score": round(float(row[1]), 4),
                "probability": float(row[2]),
                "upset_count": int(row[5]),
                "champion": row[7] or f"Seed {row[3]}",
                "champion_seed": int(row[3]),
                "is_alive": bool(row[6]),
            }
            for rank_offset, row in enumerate(rows)
        ]

        next_cursor = None
        if has_more and brackets:
            last = brackets[-1]
            sort_value = (
                last["expected_score"] if sort == "score" else last["probability"]
            )
            next_cursor = f"{sort_value}_{last['id']}"

    return {
        "brackets": brackets,
        "cursor": next_cursor,
        "has_more": has_more,
        "total": total,
        "alive_count": alive_count,
    }


@router.get("/brackets/{bracket_id}")
async def get_bracket_detail(bracket_id: int, year: int = TOURNAMENT_YEAR):
    """Full decoded bracket with all picks per region + Final Four."""
    engine = get_engine()
    region_teams = _get_region_teams(year)

    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id, east_outcomes, south_outcomes, west_outcomes, "
                "  midwest_outcomes, f4_outcomes, probability, weight "
                "FROM full_brackets "
                "WHERE id = :id AND tournament_year = :year"
            ),
            {"id": bracket_id, "year": year},
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Bracket not found")

    # Check if alive via alive tables
    with engine.connect() as conn:
        alive_check = conn.execute(
            text(
                "SELECT EXISTS("
                "  SELECT 1 FROM alive_outcomes_south WHERE outcome_value = :s"
                ") AND EXISTS("
                "  SELECT 1 FROM alive_outcomes_east WHERE outcome_value = :e"
                ") AND EXISTS("
                "  SELECT 1 FROM alive_outcomes_west WHERE outcome_value = :w"
                ") AND EXISTS("
                "  SELECT 1 FROM alive_outcomes_midwest WHERE outcome_value = :m"
                ") AND EXISTS("
                "  SELECT 1 FROM alive_outcomes_f4 WHERE outcome_value = :f"
                ")"
            ),
            {"s": row[2], "e": row[1], "w": row[3], "m": row[4], "f": row[5]},
        ).scalar()

    detail = decode_full_bracket(
        east_packed=int(row[1]),
        south_packed=int(row[2]),
        west_packed=int(row[3]),
        midwest_packed=int(row[4]),
        f4_packed=int(row[5]),
        region_teams=region_teams,
    )

    return {
        "id": row[0],
        "expected_score": round(float(row[7]), 4),
        "probability": float(row[6]),
        "is_alive": bool(alive_check),
        **detail,
    }
