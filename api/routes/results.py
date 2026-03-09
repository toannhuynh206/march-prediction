"""Game result submission endpoint (admin-only).

POST /api/results submits a game result, triggers bracket pruning,
and returns the number of eliminated brackets.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from fastapi import APIRouter, Header, HTTPException
from database import get_connection
from api.models import GameResultRequest, GameResultResponse
from api.services.pruner import prune_brackets

router = APIRouter(prefix="/api", tags=["admin"])

ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "dev-admin-key-change-me")


@router.post("/results", response_model=GameResultResponse)
async def submit_result(
    body: GameResultRequest,
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
):
    """Submit a game result and prune brackets.

    Requires X-Admin-Key header for authentication.
    """
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")

    # Validate region
    valid_regions = {"South", "East", "West", "Midwest"}
    if body.region not in valid_regions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid region. Must be one of: {', '.join(valid_regions)}",
        )

    # Find the matchup
    conn = get_connection()
    try:
        matchup = conn.execute(
            """SELECT m.id, m.seed_a, m.seed_b,
                      ta.name as team_a, tb.name as team_b,
                      ta.id as team_a_id, tb.id as team_b_id
               FROM matchups m
               JOIN teams ta ON m.team_a_id = ta.id
               JOIN teams tb ON m.team_b_id = tb.id
               WHERE m.region = ? AND m.round = ? AND m.game_index = ?""",
            (body.region, body.round, body.game_index),
        ).fetchone()

        if not matchup:
            raise HTTPException(
                status_code=404,
                detail=f"Matchup not found: {body.region} {body.round} game {body.game_index}",
            )

        # Determine winner
        if body.winner_seed == matchup["seed_a"]:
            winner_id = matchup["team_a_id"]
            winner_name = matchup["team_a"]
            loser_name = matchup["team_b"]
            winner_is_upset = False  # Higher seed (lower number) = favorite
        elif body.winner_seed == matchup["seed_b"]:
            winner_id = matchup["team_b_id"]
            winner_name = matchup["team_b"]
            loser_name = matchup["team_a"]
            winner_is_upset = True  # Lower seed (higher number) = upset
        else:
            raise HTTPException(
                status_code=400,
                detail=f"winner_seed {body.winner_seed} doesn't match either team "
                       f"(seeds: {matchup['seed_a']}, {matchup['seed_b']})",
            )

        # Record the result
        conn.execute(
            "UPDATE matchups SET actual_winner_id = ? WHERE id = ?",
            (winner_id, matchup["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    # Prune brackets
    eliminated, alive_remaining = prune_brackets(
        region=body.region,
        game_index=body.game_index,
        winner_is_upset=winner_is_upset,
    )

    game_desc = f"({matchup['seed_a']}) {winner_name} beats ({matchup['seed_b']}) {loser_name}"
    if winner_is_upset:
        game_desc = f"({matchup['seed_b']}) {winner_name} upsets ({matchup['seed_a']}) {loser_name}"

    return GameResultResponse(
        eliminated=eliminated,
        alive_remaining=alive_remaining,
        game=game_desc,
    )
