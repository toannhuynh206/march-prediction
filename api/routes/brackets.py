"""Bracket endpoints: list, detail, and tournament bracket view."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from fastapi import APIRouter, Query, HTTPException
from database import get_connection, DB_PATH
from api.services.decoder import (
    decode_bracket_detail,
    get_champion_name,
    count_upsets,
    _load_region_teams,
)

router = APIRouter(prefix="/api", tags=["brackets"])


@router.get("/bracket")
async def get_tournament_bracket():
    """Full tournament bracket: teams, seeds, matchups with probabilities."""
    conn = get_connection()
    try:
        # Load teams by region
        teams = conn.execute(
            """SELECT t.name, t.seed, t.region, t.conference, t.record
               FROM teams t ORDER BY t.region, t.seed"""
        ).fetchall()

        regions: dict[str, list] = {}
        for t in teams:
            region = t["region"]
            if region not in regions:
                regions[region] = []
            regions[region].append({
                "name": t["name"],
                "seed": t["seed"],
                "region": region,
                "conference": t["conference"],
                "record": t["record"],
            })

        # Load matchups with probabilities
        matchups = conn.execute(
            """SELECT m.game_index, m.round, m.region,
                      ta.name as team_a, m.seed_a,
                      tb.name as team_b, m.seed_b,
                      m.p_market, m.p_stats, m.p_matchup, m.p_factors, m.p_final
               FROM matchups m
               JOIN teams ta ON m.team_a_id = ta.id
               JOIN teams tb ON m.team_b_id = tb.id
               ORDER BY m.region, m.round, m.game_index"""
        ).fetchall()

        matchup_list = [
            {
                "game_index": m["game_index"],
                "round": m["round"],
                "region": m["region"],
                "team_a": m["team_a"],
                "seed_a": m["seed_a"],
                "team_b": m["team_b"],
                "seed_b": m["seed_b"],
                "p_market": m["p_market"],
                "p_stats": m["p_stats"],
                "p_matchup": m["p_matchup"],
                "p_factors": m["p_factors"],
                "p_final": m["p_final"],
            }
            for m in matchups
        ]

        return {"year": 2025, "regions": regions, "matchups": matchup_list}
    finally:
        conn.close()


@router.get("/brackets")
async def list_brackets(
    cursor: str | None = Query(None, description="Cursor for keyset pagination: 'score_id'"),
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("score", pattern="^(score|probability|upsets)$"),
    alive_only: bool = Query(False),
    region: str | None = Query(None),
):
    """Paginated bracket list with cursor-based (keyset) pagination."""
    conn = get_connection()
    try:
        region_teams = _load_region_teams()

        # Build WHERE clause
        conditions = []
        params = []

        if alive_only:
            conditions.append("b.is_alive = 1")

        # Parse cursor for keyset pagination
        if cursor:
            parts = cursor.split("_", 1)
            if len(parts) == 2:
                cursor_score = float(parts[0])
                cursor_id = int(parts[1])
                conditions.append(
                    "(b.expected_score < ? OR (b.expected_score = ? AND b.id > ?))"
                )
                params.extend([cursor_score, cursor_score, cursor_id])

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Sort
        order = "b.expected_score DESC, b.id ASC"
        if sort == "probability":
            order = "b.probability DESC, b.id ASC"

        # Count totals
        total = conn.execute("SELECT COUNT(*) FROM brackets").fetchone()[0]
        alive_count = conn.execute(
            "SELECT COUNT(*) FROM brackets WHERE is_alive = 1"
        ).fetchone()[0]

        # Fetch page
        query = f"""
            SELECT b.id, b.outcomes, b.expected_score, b.probability,
                   b.pool_value, b.is_alive,
                   b.south_score, b.east_score, b.west_score, b.midwest_score
            FROM brackets b
            {where}
            ORDER BY {order}
            LIMIT ?
        """
        params.append(limit + 1)  # fetch one extra to determine has_more
        rows = conn.execute(query, params).fetchall()

        has_more = len(rows) > limit
        rows = rows[:limit]

        # Build response
        brackets = []
        for rank_offset, row in enumerate(rows):
            bracket_int = int.from_bytes(row["outcomes"], byteorder="big")
            champ_name, champ_seed = get_champion_name(bracket_int, region_teams)
            upsets = count_upsets(bracket_int)

            brackets.append({
                "id": row["id"],
                "rank": rank_offset + 1,  # relative rank on this page
                "expected_score": round(row["expected_score"] or 0, 1),
                "probability": row["probability"] or 0,
                "pool_value": row["pool_value"],
                "upset_count": upsets,
                "champion": champ_name,
                "champion_seed": champ_seed,
                "is_alive": bool(row["is_alive"]),
                "region_scores": {
                    "South": round(row["south_score"] or 0, 1),
                    "East": round(row["east_score"] or 0, 1),
                    "West": round(row["west_score"] or 0, 1),
                    "Midwest": round(row["midwest_score"] or 0, 1),
                },
            })

        # Build next cursor
        next_cursor = None
        if has_more and brackets:
            last = brackets[-1]
            next_cursor = f"{last['expected_score']}_{last['id']}"

        return {
            "brackets": brackets,
            "cursor": next_cursor,
            "has_more": has_more,
            "total": total,
            "alive_count": alive_count,
        }
    finally:
        conn.close()


@router.get("/brackets/{bracket_id}")
async def get_bracket_detail(bracket_id: int):
    """Full decoded bracket with all 63 picks."""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT id, outcomes, expected_score, probability, is_alive
               FROM brackets WHERE id = ?""",
            (bracket_id,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Bracket not found")

        bracket_int = int.from_bytes(row["outcomes"], byteorder="big")
        detail = decode_bracket_detail(bracket_int)

        return {
            "id": row["id"],
            "expected_score": round(row["expected_score"] or 0, 1),
            "probability": row["probability"] or 0,
            "is_alive": bool(row["is_alive"]),
            **detail,
        }
    finally:
        conn.close()
