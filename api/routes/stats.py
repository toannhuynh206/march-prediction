"""Statistics endpoints: dashboard data, survival rates, champion odds."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from fastapi import APIRouter, HTTPException
from database import get_connection
from api.services.decoder import _load_region_teams, get_champion_name

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
async def get_stats():
    """Dashboard statistics: alive count, survival rate, champion odds, upset distribution."""
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM brackets").fetchone()[0]
        alive = conn.execute(
            "SELECT COUNT(*) FROM brackets WHERE is_alive = 1"
        ).fetchone()[0]

        results_entered = conn.execute(
            "SELECT COUNT(*) FROM matchups WHERE actual_winner_id IS NOT NULL"
        ).fetchone()[0]

        survival_rate = alive / total if total > 0 else 0

        # Champion odds: count brackets per champion among alive brackets
        champion_counts: dict[str, int] = {}
        if alive > 0:
            region_teams = _load_region_teams()
            rows = conn.execute(
                "SELECT outcomes FROM brackets WHERE is_alive = 1"
            ).fetchall()

            for row in rows:
                bracket_int = int.from_bytes(row["outcomes"], byteorder="big")
                champ_name, _ = get_champion_name(bracket_int, region_teams)
                champion_counts[champ_name] = champion_counts.get(champ_name, 0) + 1

        champion_odds = sorted(
            [
                {"team": name, "count": count, "percentage": round(count / alive * 100, 2) if alive > 0 else 0}
                for name, count in champion_counts.items()
            ],
            key=lambda x: x["count"],
            reverse=True,
        )

        # Upset distribution: count brackets by upset count
        upset_dist: dict[int, int] = {}
        if total > 0:
            rows = conn.execute(
                "SELECT outcomes FROM brackets WHERE is_alive = 1"
            ).fetchall()
            for row in rows:
                bracket_int = int.from_bytes(row["outcomes"], byteorder="big")
                upsets = bin(bracket_int).count("1")
                upset_dist[upsets] = upset_dist.get(upsets, 0) + 1

        upset_distribution = sorted(
            [{"upset_count": k, "bracket_count": v} for k, v in upset_dist.items()],
            key=lambda x: x["upset_count"],
        )

        return {
            "total_brackets": total,
            "alive_brackets": alive,
            "survival_rate": round(survival_rate, 6),
            "results_entered": results_entered,
            "champion_odds": champion_odds[:20],
            "upset_distribution": upset_distribution,
        }
    finally:
        conn.close()


@router.get("/stats/regions/{region}")
async def get_region_stats(region: str):
    """Region-specific survival statistics."""
    valid_regions = {"South", "East", "West", "Midwest"}
    if region not in valid_regions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid region. Must be one of: {', '.join(valid_regions)}",
        )

    conn = get_connection()
    try:
        # Get teams in this region with their stats
        teams = conn.execute(
            """SELECT t.name, t.seed, t.region, t.conference,
                      ts.adj_em, ts.tempo
               FROM teams t
               LEFT JOIN team_stats ts ON t.id = ts.team_id
               WHERE t.region = ?
               ORDER BY t.seed""",
            (region,),
        ).fetchall()

        # Get matchup results for this region
        matchups = conn.execute(
            """SELECT m.round, m.game_index, m.seed_a, m.seed_b,
                      ta.name as team_a, tb.name as team_b,
                      m.p_final, tw.name as winner
               FROM matchups m
               JOIN teams ta ON m.team_a_id = ta.id
               JOIN teams tb ON m.team_b_id = tb.id
               LEFT JOIN teams tw ON m.actual_winner_id = tw.id
               WHERE m.region = ?
               ORDER BY m.round, m.game_index""",
            (region,),
        ).fetchall()

        team_list = [
            {
                "name": t["name"],
                "seed": t["seed"],
                "conference": t["conference"],
                "adj_em": t["adj_em"],
                "tempo": t["tempo"],
            }
            for t in teams
        ]

        matchup_list = [
            {
                "round": m["round"],
                "game_index": m["game_index"],
                "team_a": m["team_a"],
                "seed_a": m["seed_a"],
                "team_b": m["team_b"],
                "seed_b": m["seed_b"],
                "p_final": m["p_final"],
                "winner": m["winner"],
            }
            for m in matchups
        ]

        return {
            "region": region,
            "teams": team_list,
            "matchups": matchup_list,
        }
    finally:
        conn.close()
