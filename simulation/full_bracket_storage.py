"""
PostgreSQL COPY bulk insert for full tournament brackets.

Inserts into the full_brackets table using psycopg2.copy_expert
with StringIO buffers. Designed for 206M rows in batched COPY operations.
"""

from __future__ import annotations

import sys
from io import BytesIO
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
    "total_upsets, strategy, is_alive, tournament_year"
)

_COPY_SQL = f"COPY full_brackets ({_COPY_COLUMNS}) FROM STDIN"

# Pre-encode region names to bytes for fast lookup
_REGION_BYTES = [name.encode("ascii") for name in REGION_NAMES]


# =========================================================================
# Vectorized COPY buffer builder
# =========================================================================

def _build_copy_buffer(
    ids: np.ndarray,
    east: np.ndarray,
    south: np.ndarray,
    west: np.ndarray,
    midwest: np.ndarray,
    f4: np.ndarray,
    probs: np.ndarray,
    wts: np.ndarray,
    champ_seeds: np.ndarray,
    champ_region_idx: np.ndarray,
    upsets: np.ndarray,
    strategy: bytes,
    year: bytes,
) -> BytesIO:
    """Build COPY buffer using numpy savetxt for maximum throughput.

    Stacks all columns into a single 2D array and writes via np.savetxt
    with tab delimiter. ~10-20x faster than per-row Python string loops.
    """
    n = len(ids)
    region_lut = np.array(REGION_NAMES, dtype="U10")
    col_region = region_lut[champ_region_idx.astype(np.intp)]

    strat = strategy.decode("ascii")
    yr = year.decode("ascii")

    # Build a structured array of all columns as strings for np.savetxt
    # Integer columns
    c_id = ids.astype(np.int64)
    c_east = east.astype(np.int32)
    c_south = south.astype(np.int32)
    c_west = west.astype(np.int32)
    c_midwest = midwest.astype(np.int32)
    c_f4 = f4.astype(np.int32)
    c_champ = champ_seeds.astype(np.int32)
    c_upsets = upsets.astype(np.int32)

    # Write numeric columns with savetxt, then patch in string columns
    # Actually fastest: build a 2D object array and join
    table = np.empty((n, 14), dtype=object)
    table[:, 0] = c_id
    table[:, 1] = c_east
    table[:, 2] = c_south
    table[:, 3] = c_west
    table[:, 4] = c_midwest
    table[:, 5] = c_f4
    table[:, 6] = probs   # will be formatted below
    table[:, 7] = wts
    table[:, 8] = c_champ
    table[:, 9] = col_region
    table[:, 10] = c_upsets
    table[:, 11] = strat
    table[:, 12] = "true"
    table[:, 13] = yr

    # Format: use np.savetxt with custom fmt for each column
    buf = BytesIO()
    np.savetxt(
        buf, table,
        delimiter="\t",
        fmt=["%d", "%d", "%d", "%d", "%d", "%d",
             "%.15e", "%.15e",
             "%d", "%s", "%d", "%s", "%s", "%s"],
        newline="\n",
    )
    buf.seek(0)
    return buf


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
    weights: np.ndarray,
    champion_seeds: np.ndarray,
    champion_region_idx: np.ndarray,
    total_upsets: np.ndarray,
    id_offset: int,
    strategy: str = "standard",
    year: int = TOURNAMENT_YEAR,
    batch_size: int = COPY_BATCH_SIZE,
) -> int:
    """Bulk insert full tournament brackets using PostgreSQL COPY.

    Uses vectorized buffer building and commits per batch to avoid
    transaction bloat at scale (206M rows).

    Args:
        east_outcomes: (N,) int16 packed regional outcomes.
        south_outcomes: (N,) int16.
        west_outcomes: (N,) int16.
        midwest_outcomes: (N,) int16.
        f4_outcomes: (N,) int8, 3-bit packed F4 outcomes.
        probabilities: (N,) float64 full bracket probability.
        weights: (N,) float64 importance sampling weights.
        champion_seeds: (N,) int16 tournament champion seed.
        champion_region_idx: (N,) int8 index into REGION_NAMES.
        total_upsets: (N,) int16 total R64 upsets across all regions.
        id_offset: Starting bracket ID (for global uniqueness).
        strategy: Strategy profile name.
        year: Tournament year.
        batch_size: Rows per COPY batch.

    Returns:
        Number of rows inserted.
    """
    n = len(east_outcomes)
    if n == 0:
        return 0

    strategy_b = strategy.encode("ascii")
    year_b = str(year).encode("ascii")
    total_inserted = 0

    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        sl = slice(start, end)

        ids = np.arange(id_offset + start + 1, id_offset + end + 1)

        buf = _build_copy_buffer(
            ids,
            east_outcomes[sl], south_outcomes[sl],
            west_outcomes[sl], midwest_outcomes[sl],
            f4_outcomes[sl], probabilities[sl], weights[sl],
            champion_seeds[sl], champion_region_idx[sl],
            total_upsets[sl], strategy_b, year_b,
        )

        # Commit per batch to avoid transaction bloat
        conn = get_raw_connection()
        cursor = conn.cursor()
        try:
            cursor.copy_expert(_COPY_SQL, buf)
            conn.commit()
            total_inserted += end - start
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
