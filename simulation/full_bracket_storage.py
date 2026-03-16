"""
PostgreSQL COPY bulk insert for full tournament brackets.

Inserts into the full_brackets table using psycopg2.copy_expert
with StringIO buffers. Designed for 206M rows in batched COPY operations.
"""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.constants import COPY_BATCH_SIZE, TOURNAMENT_YEAR
from db.connection import get_raw_connection, session_scope
from simulation.final_four_probs import REGION_NAMES
from sqlalchemy import text


# Column order for COPY
_COPY_COLUMNS = (
    "id, east_outcomes, south_outcomes, west_outcomes, midwest_outcomes, "
    "f4_outcomes, probability, weight, champion_seed, champion_region, "
    "total_upsets, is_alive, tournament_year"
)

_COPY_SQL = f"COPY full_brackets ({_COPY_COLUMNS}) FROM STDIN"


# =========================================================================
# Bulk insert
# =========================================================================

def insert_full_brackets_copy(
    east_outcomes: np.ndarray,
    south_outcomes: np.ndarray,
    west_outcomes: np.ndarray,
    midwest_outcomes: np.ndarray,
    f4_outcomes: np.ndarray,
    probabilities: np.ndarray,
    champion_seeds: np.ndarray,
    champion_region_idx: np.ndarray,
    total_upsets: np.ndarray,
    id_offset: int,
    year: int = TOURNAMENT_YEAR,
    batch_size: int = COPY_BATCH_SIZE,
) -> int:
    """Bulk insert full tournament brackets using PostgreSQL COPY.

    Args:
        east_outcomes: (N,) int16 packed regional outcomes.
        south_outcomes: (N,) int16.
        west_outcomes: (N,) int16.
        midwest_outcomes: (N,) int16.
        f4_outcomes: (N,) int8, 3-bit packed F4 outcomes.
        probabilities: (N,) float64 full bracket probability.
        champion_seeds: (N,) int16 tournament champion seed.
        champion_region_idx: (N,) int8 index into REGION_NAMES.
        total_upsets: (N,) int16 total R64 upsets across all regions.
        id_offset: Starting bracket ID (for global uniqueness).
        year: Tournament year.
        batch_size: Rows per COPY batch.

    Returns:
        Number of rows inserted.
    """
    n = len(east_outcomes)
    if n == 0:
        return 0

    conn = get_raw_connection()
    cursor = conn.cursor()
    total_inserted = 0

    try:
        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)

            buf = StringIO()
            for i in range(start, end):
                row_id = id_offset + i + 1
                region_name = REGION_NAMES[int(champion_region_idx[i])]
                buf.write(
                    f"{row_id}\t"
                    f"{int(east_outcomes[i])}\t"
                    f"{int(south_outcomes[i])}\t"
                    f"{int(west_outcomes[i])}\t"
                    f"{int(midwest_outcomes[i])}\t"
                    f"{int(f4_outcomes[i])}\t"
                    f"{float(probabilities[i]):.15e}\t"
                    f"1.0\t"
                    f"{int(champion_seeds[i])}\t"
                    f"{region_name}\t"
                    f"{int(total_upsets[i])}\t"
                    f"true\t"
                    f"{year}\n"
                )

            buf.seek(0)
            cursor.copy_expert(_COPY_SQL, buf)
            total_inserted += end - start

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

    return total_inserted


# =========================================================================
# Cleanup and counting
# =========================================================================

def clear_full_brackets(year: int = TOURNAMENT_YEAR) -> int:
    """Delete all full brackets for a tournament year. Returns count deleted."""
    with session_scope() as session:
        result = session.execute(text("""
            DELETE FROM full_brackets
            WHERE tournament_year = :year
        """), {"year": year})
        return result.rowcount


def get_full_bracket_count(year: int = TOURNAMENT_YEAR) -> int:
    """Count full brackets for a tournament year."""
    with session_scope() as session:
        result = session.execute(text("""
            SELECT COUNT(*) FROM full_brackets
            WHERE tournament_year = :year
        """), {"year": year})
        return result.scalar() or 0


def get_champion_distribution(year: int = TOURNAMENT_YEAR) -> list[dict]:
    """Get champion seed/region distribution for alive brackets."""
    with session_scope() as session:
        rows = session.execute(text("""
            SELECT champion_seed, champion_region,
                   COUNT(*) as count,
                   SUM(probability) as total_prob
            FROM full_brackets
            WHERE tournament_year = :year AND is_alive = TRUE
            GROUP BY champion_seed, champion_region
            ORDER BY total_prob DESC
        """), {"year": year}).fetchall()

    return [
        {
            "seed": int(r[0]),
            "region": r[1],
            "count": int(r[2]),
            "probability": float(r[3]),
        }
        for r in rows
    ]
