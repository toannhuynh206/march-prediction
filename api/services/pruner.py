"""Bitwise bracket pruning — PostgreSQL native bitwise operations.

Single SQL UPDATE per game result. No Python-side filtering.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.constants import TOURNAMENT_YEAR
from db.connection import get_engine
from sqlalchemy import text


# Region name → full_brackets column name
REGION_COLUMN: dict[str, str] = {
    "South": "south_outcomes",
    "East": "east_outcomes",
    "West": "west_outcomes",
    "Midwest": "midwest_outcomes",
}


def prune_regional_game(
    region: str,
    game_index: int,
    expected_bit: int,
    year: int = TOURNAMENT_YEAR,
) -> tuple[int, int]:
    """Eliminate brackets with wrong outcome for a regional game.

    Uses a single SQL UPDATE with PostgreSQL bitwise operators.

    Args:
        region: Region name (South, East, West, Midwest).
        game_index: Bit position within the region column (0-14).
        expected_bit: 0 = top team won, 1 = bottom team won.
        year: Tournament year.

    Returns:
        (eliminated_count, alive_remaining).
    """
    column = REGION_COLUMN[region]
    engine = get_engine()

    with engine.begin() as conn:
        alive_before = conn.execute(
            text(
                "SELECT COUNT(*) FROM full_brackets "
                "WHERE is_alive = TRUE AND tournament_year = :year"
            ),
            {"year": year},
        ).scalar()

        # Single UPDATE: eliminate where the bit doesn't match
        # Column name is from a hardcoded dict — safe from injection
        result = conn.execute(
            text(
                f"UPDATE full_brackets "
                f"SET is_alive = FALSE "
                f"WHERE is_alive = TRUE "
                f"AND tournament_year = :year "
                f"AND ({column} >> :bit_pos) & 1 != :expected_bit"
            ),
            {"year": year, "bit_pos": game_index, "expected_bit": expected_bit},
        )
        eliminated = result.rowcount
        alive_after = alive_before - eliminated

    return eliminated, alive_after


def prune_f4_game(
    f4_bit_position: int,
    expected_bit: int,
    year: int = TOURNAMENT_YEAR,
) -> tuple[int, int]:
    """Eliminate brackets with wrong F4 outcome.

    Args:
        f4_bit_position: 0 = Semi1, 1 = Semi2, 2 = Championship.
        expected_bit: 0 or 1.
        year: Tournament year.

    Returns:
        (eliminated_count, alive_remaining).
    """
    engine = get_engine()

    with engine.begin() as conn:
        alive_before = conn.execute(
            text(
                "SELECT COUNT(*) FROM full_brackets "
                "WHERE is_alive = TRUE AND tournament_year = :year"
            ),
            {"year": year},
        ).scalar()

        result = conn.execute(
            text(
                "UPDATE full_brackets "
                "SET is_alive = FALSE "
                "WHERE is_alive = TRUE "
                "AND tournament_year = :year "
                "AND (f4_outcomes >> :bit_pos) & 1 != :expected_bit"
            ),
            {"year": year, "bit_pos": f4_bit_position, "expected_bit": expected_bit},
        )
        eliminated = result.rowcount
        alive_after = alive_before - eliminated

    return eliminated, alive_after


def get_alive_count(year: int = TOURNAMENT_YEAR) -> int:
    """Get current count of alive brackets."""
    engine = get_engine()
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT COUNT(*) FROM full_brackets "
                "WHERE is_alive = TRUE AND tournament_year = :year"
            ),
            {"year": year},
        ).scalar()
