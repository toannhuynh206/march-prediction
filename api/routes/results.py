"""Game result submission endpoint (admin-only).

POST /api/results submits a game result, records it to the game_results
table, and triggers PostgreSQL bitwise bracket pruning.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text

from api.models import GameResultRequest, GameResultResponse
from api.services.pruner import prune_regional_game, prune_f4_game
from config.constants import TOURNAMENT_YEAR, F4_SEMI_PAIRINGS
from db.connection import get_engine
from simulation.bracket_structure import (
    R64_SEED_MATCHUPS,
    GAME_TREE,
    ROUND_GAME_INDICES,
)

router = APIRouter(prefix="/api", tags=["admin"])

ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "dev-admin-key-change-me")

VALID_REGIONS = frozenset({"South", "East", "West", "Midwest"})
REGIONAL_ROUNDS = frozenset({"R64", "R32", "S16", "E8"})


# ── helpers ──────────────────────────────────────────────────────────────


def _abs_to_round_game(abs_index: int) -> tuple[str, int]:
    """Map absolute game index (0-14) to (round_name, relative_index)."""
    for round_name, indices in ROUND_GAME_INDICES.items():
        for i, idx in enumerate(indices):
            if idx == abs_index:
                return round_name, i
    raise ValueError(f"Invalid absolute game index: {abs_index}")


def _get_winner_seed(conn, region: str, abs_index: int, year: int) -> int | None:
    """Look up the winner seed for a previously completed regional game."""
    round_name, relative_index = _abs_to_round_game(abs_index)
    row = conn.execute(
        text(
            "SELECT winner_seed FROM game_results "
            "WHERE tournament_year = :year AND region = :region "
            "AND round = :round AND game_number = :game_number"
        ),
        {
            "year": year,
            "region": region,
            "round": round_name,
            "game_number": relative_index,
        },
    ).fetchone()
    return int(row[0]) if row else None


def _compute_regional_bit(
    conn,
    region: str,
    round_name: str,
    game_index: int,
    winner_seed: int,
    year: int,
) -> tuple[int, int]:
    """Return (bit_position, expected_bit) for a regional game.

    bit_position: 0-14 (absolute index within the region column).
    expected_bit: 0 if "top" team won, 1 if "bottom" team won.
    """
    abs_index = ROUND_GAME_INDICES[round_name][game_index]

    if round_name == "R64":
        top_seed, bot_seed = R64_SEED_MATCHUPS[game_index]
        if winner_seed == top_seed:
            return abs_index, 0
        if winner_seed == bot_seed:
            return abs_index, 1
        raise HTTPException(
            status_code=400,
            detail=(
                f"winner_seed {winner_seed} doesn't match R64 game {game_index} "
                f"seeds ({top_seed}, {bot_seed})"
            ),
        )

    # R32+ — trace the game tree to find which seeds advanced
    src_a, src_b = GAME_TREE[abs_index]
    top_seed = _get_winner_seed(conn, region, src_a, year)
    bot_seed = _get_winner_seed(conn, region, src_b, year)

    if top_seed is None or bot_seed is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot determine matchup for {round_name} game {game_index}: "
                f"prerequisite games not yet recorded"
            ),
        )

    if winner_seed == top_seed:
        return abs_index, 0
    if winner_seed == bot_seed:
        return abs_index, 1
    raise HTTPException(
        status_code=400,
        detail=(
            f"winner_seed {winner_seed} doesn't match {round_name} game {game_index} "
            f"teams (seeds {top_seed}, {bot_seed})"
        ),
    )


def _record_game_result(conn, body: GameResultRequest, year: int) -> None:
    """Insert / upsert into game_results (idempotent via UNIQUE constraint)."""
    region = body.region if body.round in REGIONAL_ROUNDS else ""
    conn.execute(
        text(
            "INSERT INTO game_results "
            "  (tournament_year, region, round, game_number, "
            "   winner_seed, loser_seed, winner_name, loser_name) "
            "VALUES "
            "  (:year, :region, :round, :game_number, "
            "   :winner_seed, :loser_seed, :winner_name, :loser_name) "
            "ON CONFLICT (tournament_year, region, round, game_number) "
            "DO UPDATE SET "
            "  winner_seed = EXCLUDED.winner_seed, "
            "  loser_seed  = EXCLUDED.loser_seed, "
            "  winner_name = EXCLUDED.winner_name, "
            "  loser_name  = EXCLUDED.loser_name"
        ),
        {
            "year": year,
            "region": region,
            "round": body.round,
            "game_number": body.game_index,
            "winner_seed": body.winner_seed,
            "loser_seed": body.loser_seed,
            "winner_name": body.winner_name,
            "loser_name": body.loser_name,
        },
    )


def _game_description(body: GameResultRequest) -> str:
    """Build a human-readable game description string."""
    winner = body.winner_name or f"Seed {body.winner_seed}"
    loser = body.loser_name or f"Seed {body.loser_seed}"
    is_upset = body.loser_seed > 0 and body.winner_seed > body.loser_seed
    prefix = "UPSET: " if is_upset else ""
    return f"{prefix}({body.winner_seed}) {winner} beats ({body.loser_seed}) {loser}"


# ── F4 / Championship helpers ───────────────────────────────────────────


def _resolve_f4_semi_bit(
    conn, body: GameResultRequest, year: int,
) -> tuple[int, int]:
    """Determine (f4_bit_position, expected_bit) for a F4 semifinal."""
    if body.game_index not in (0, 1):
        raise HTTPException(
            status_code=400,
            detail="F4 game_index must be 0 (Semi1) or 1 (Semi2)",
        )
    semi_regions = F4_SEMI_PAIRINGS[body.game_index]

    # Fetch E8 winners for both regions
    champs = []
    for reg in semi_regions:
        row = conn.execute(
            text(
                "SELECT winner_seed, winner_name FROM game_results "
                "WHERE tournament_year = :year AND region = :region "
                "AND round = 'E8' AND game_number = 0"
            ),
            {"year": year, "region": reg},
        ).fetchone()
        if not row:
            raise HTTPException(
                status_code=400,
                detail=f"E8 result not yet recorded for region {reg}",
            )
        champs.append((int(row[0]), row[1]))

    seed_a, name_a = champs[0]
    seed_b, name_b = champs[1]

    # Disambiguate: try seed first, fall back to name
    if body.winner_seed == seed_a and body.winner_seed != seed_b:
        return body.game_index, 0
    if body.winner_seed == seed_b and body.winner_seed != seed_a:
        return body.game_index, 1
    # Seeds match — use winner_name
    if body.winner_name and body.winner_name == name_a:
        return body.game_index, 0
    if body.winner_name and body.winner_name == name_b:
        return body.game_index, 1
    raise HTTPException(
        status_code=400,
        detail=(
            f"Cannot determine F4 winner. Seeds: {seed_a} ({name_a}) vs "
            f"{seed_b} ({name_b}). Provide winner_name to disambiguate."
        ),
    )


def _resolve_championship_bit(
    conn, body: GameResultRequest, year: int,
) -> tuple[int, int]:
    """Determine (f4_bit_position=2, expected_bit) for the championship."""
    semis = []
    for gn in (0, 1):
        row = conn.execute(
            text(
                "SELECT winner_seed, winner_name FROM game_results "
                "WHERE tournament_year = :year AND region = '' "
                "AND round = 'F4' AND game_number = :gn"
            ),
            {"year": year, "gn": gn},
        ).fetchone()
        if not row:
            raise HTTPException(
                status_code=400,
                detail=f"F4 semifinal {gn + 1} result not yet recorded",
            )
        semis.append((int(row[0]), row[1]))

    seed_a, name_a = semis[0]
    seed_b, name_b = semis[1]

    if body.winner_seed == seed_a and body.winner_seed != seed_b:
        return 2, 0
    if body.winner_seed == seed_b and body.winner_seed != seed_a:
        return 2, 1
    if body.winner_name and body.winner_name == name_a:
        return 2, 0
    if body.winner_name and body.winner_name == name_b:
        return 2, 1
    raise HTTPException(
        status_code=400,
        detail=(
            f"Cannot determine champion. Seeds: {seed_a} ({name_a}) vs "
            f"{seed_b} ({name_b}). Provide winner_name to disambiguate."
        ),
    )


# ── main endpoint ────────────────────────────────────────────────────────


@router.post("/results", response_model=GameResultResponse)
async def submit_result(
    body: GameResultRequest,
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
):
    """Submit a game result and prune brackets.

    Requires X-Admin-Key header for authentication.

    Regional games: region + round (R64/R32/S16/E8) + game_index + winner_seed.
    F4 semifinals: round='F4', game_index 0 or 1, winner_seed + winner_name.
    Championship: round='Final', game_index 0, winner_seed + winner_name.
    """
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")

    year = TOURNAMENT_YEAR
    engine = get_engine()

    # ── Final Four / Championship ────────────────────────────────────
    if body.round in ("F4", "Final"):
        with engine.begin() as conn:
            if body.round == "F4":
                f4_bit, expected_bit = _resolve_f4_semi_bit(conn, body, year)
            else:
                f4_bit, expected_bit = _resolve_championship_bit(conn, body, year)
            _record_game_result(conn, body, year)

        eliminated, alive_remaining = prune_f4_game(
            f4_bit_position=f4_bit,
            expected_bit=expected_bit,
            year=year,
        )
        return GameResultResponse(
            eliminated=eliminated,
            alive_remaining=alive_remaining,
            game=_game_description(body),
        )

    # ── Regional games ───────────────────────────────────────────────
    if body.region not in VALID_REGIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid region. Must be one of: {', '.join(sorted(VALID_REGIONS))}",
        )
    if body.round not in REGIONAL_ROUNDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid round. Must be one of: {', '.join(sorted(REGIONAL_ROUNDS))}",
        )

    with engine.begin() as conn:
        bit_position, expected_bit = _compute_regional_bit(
            conn, body.region, body.round, body.game_index, body.winner_seed, year,
        )
        _record_game_result(conn, body, year)

    eliminated, alive_remaining = prune_regional_game(
        region=body.region,
        game_index=bit_position,
        expected_bit=expected_bit,
        year=year,
    )

    return GameResultResponse(
        eliminated=eliminated,
        alive_remaining=alive_remaining,
        game=_game_description(body),
    )
