"""Bitwise bracket pruning service.

When a game result is entered, eliminates all brackets that picked
the wrong winner for that game using a single SQL UPDATE with
bitwise operations.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from math_primitives import REGION_OFFSETS
from database import get_connection, DB_PATH


def prune_brackets(
    region: str,
    game_index: int,
    winner_is_upset: bool,
    db_path: str = DB_PATH,
) -> tuple[int, int]:
    """Eliminate brackets that picked the wrong winner for a game.

    The bracket encoding uses bit=0 for favorite wins, bit=1 for upset.
    We check the specific bit position and eliminate brackets where
    the bit doesn't match the actual result.

    Args:
        region: Region name (South, East, West, Midwest)
        game_index: Game index within the region (0-14)
        winner_is_upset: True if the lower seed won (upset)
        db_path: Path to SQLite database

    Returns:
        (eliminated_count, alive_remaining)
    """
    offset = REGION_OFFSETS[region]
    bit_position = offset + game_index

    # The expected bit value: 0 = favorite wins, 1 = upset
    expected_bit = 1 if winner_is_upset else 0

    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Bracket outcomes are stored as BLOB. We need to extract the integer
    # and check the specific bit. SQLite doesn't have native 64-bit
    # bitwise ops on BLOBs, so we'll use a Python-side approach for
    # correctness, but batch it efficiently.
    #
    # For production with 10M rows, this would use PostgreSQL's bitwise
    # operators directly. For SQLite, we read alive bracket IDs in batches
    # and update them.

    # Count alive before
    alive_before = cursor.execute(
        "SELECT COUNT(*) FROM brackets WHERE is_alive = 1"
    ).fetchone()[0]

    # Read all alive bracket outcomes
    # For SQLite: outcomes is stored as an 8-byte big-endian integer blob
    rows = cursor.execute(
        "SELECT id, outcomes FROM brackets WHERE is_alive = 1"
    ).fetchall()

    ids_to_eliminate = []
    for row in rows:
        bracket_int = int.from_bytes(row["outcomes"], byteorder="big")
        actual_bit = (bracket_int >> bit_position) & 1
        if actual_bit != expected_bit:
            ids_to_eliminate.append(row["id"])

    # Batch eliminate
    if ids_to_eliminate:
        # SQLite max variables is 999, batch in chunks
        batch_size = 500
        for i in range(0, len(ids_to_eliminate), batch_size):
            batch = ids_to_eliminate[i : i + batch_size]
            placeholders = ",".join("?" * len(batch))
            cursor.execute(
                f"UPDATE brackets SET is_alive = 0 WHERE id IN ({placeholders})",
                batch,
            )

    conn.commit()

    alive_after = cursor.execute(
        "SELECT COUNT(*) FROM brackets WHERE is_alive = 1"
    ).fetchone()[0]

    conn.close()

    eliminated = alive_before - alive_after
    return eliminated, alive_after


def get_alive_count(db_path: str = DB_PATH) -> int:
    """Get the current count of alive brackets."""
    conn = get_connection(db_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM brackets WHERE is_alive = 1"
    ).fetchone()[0]
    conn.close()
    return count
