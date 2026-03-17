"""
PostgreSQL COPY bulk insert for bracket storage.

Uses psycopg2.copy_expert with StringIO buffers for maximum throughput.
Batches inserts in COPY_BATCH_SIZE chunks (100K per batch).
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
from sqlalchemy import text


# =========================================================================
# Bracket COPY insert
# =========================================================================

def insert_brackets_copy(
    packed_outcomes: np.ndarray,
    probabilities: np.ndarray,
    weights: np.ndarray | float,
    region: str,
    stratum_id: int,
    cluster: str,
    year: int = TOURNAMENT_YEAR,
    id_offset: int = 0,
    batch_size: int = COPY_BATCH_SIZE,
) -> int:
    """Bulk insert brackets using PostgreSQL COPY.

    Args:
        packed_outcomes: Shape (N,), dtype int16. Packed 15-bit outcomes.
        probabilities: Shape (N,), dtype float32. Bracket probabilities.
        weights: Scalar or shape (N,). Importance sampling weight.
        region: Region name (South, East, West, Midwest).
        stratum_id: Stratum ID from strata table.
        cluster: Portfolio cluster ("chalk" or "gamble").
        year: Tournament year.
        id_offset: Starting ID for this batch.
        batch_size: Rows per COPY batch.

    Returns:
        Number of rows inserted.
    """
    n = len(packed_outcomes)
    if n == 0:
        return 0

    # Scalar weight → broadcast
    if isinstance(weights, (int, float)):
        weight_arr = np.full(n, weights, dtype=np.float64)
    else:
        weight_arr = weights.astype(np.float64)

    conn = get_raw_connection()
    cursor = conn.cursor()
    total_inserted = 0

    try:
        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            batch_n = end - start

            buf = StringIO()
            for i in range(start, end):
                row_id = id_offset + i + 1
                outcome = int(packed_outcomes[i])
                weight = float(weight_arr[i])
                prob = float(probabilities[i])
                # Tab-separated: id, region, outcomes, weight, stratum_id,
                #                 cluster, probability, expected_score,
                #                 is_alive, tournament_year
                buf.write(
                    f"{row_id}\t{region}\t{outcome}\t{weight:.8f}\t"
                    f"{stratum_id}\t{cluster}\t{prob:.10e}\t"
                    f"0.0\ttrue\t{year}\n"
                )

            buf.seek(0)
            cursor.copy_expert(
                f"COPY brackets (id, region, outcomes, weight, stratum_id, "
                f"cluster, probability, expected_score, is_alive, "
                f"tournament_year) FROM STDIN",
                buf,
            )
            total_inserted += batch_n

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

    return total_inserted


# =========================================================================
# Strata insert
# =========================================================================

def insert_strata(
    worlds: list,
    region: str,
    year: int = TOURNAMENT_YEAR,
) -> dict[tuple[int, str], int]:
    """Insert world definitions into the strata table.

    Returns mapping of (r64_upsets, champion_tier) → stratum_id.
    """
    stratum_ids: dict[tuple[int, str], int] = {}

    with session_scope() as session:
        # Clear existing strata for this region/year
        session.execute(text("""
            DELETE FROM strata
            WHERE tournament_year = :year AND region = :region
        """), {"year": year, "region": region})

        for w in worlds:
            result = session.execute(text("""
                INSERT INTO strata
                    (tournament_year, region, r64_upsets, champion_tier,
                     prior_prob, target_count, actual_count)
                VALUES (:year, :region, :upsets, :tier,
                        :prior, :target, :actual)
                RETURNING id
            """), {
                "year": year,
                "region": region,
                "upsets": w.r64_upsets,
                "tier": w.champion_tier,
                "prior": w.prior_prob,
                "target": w.target_count,
                "actual": w.actual_count,
            })
            stratum_id = result.scalar()
            stratum_ids[(w.r64_upsets, w.champion_tier)] = stratum_id

    return stratum_ids


def update_stratum_actual_count(
    stratum_id: int,
    actual_count: int,
) -> None:
    """Update the actual_count for a stratum after simulation."""
    with session_scope() as session:
        session.execute(text("""
            UPDATE strata SET actual_count = :count WHERE id = :sid
        """), {"count": actual_count, "sid": stratum_id})


# =========================================================================
# Cleanup
# =========================================================================

def clear_brackets(region: str, year: int = TOURNAMENT_YEAR) -> int:
    """Delete all brackets for a region/year. Returns count deleted."""
    with session_scope() as session:
        result = session.execute(text("""
            DELETE FROM brackets
            WHERE region = :region AND tournament_year = :year
        """), {"region": region, "year": year})
        return result.rowcount


def get_bracket_count(region: str, year: int = TOURNAMENT_YEAR) -> int:
    """Count brackets for a region/year."""
    with session_scope() as session:
        result = session.execute(text("""
            SELECT COUNT(*) FROM brackets
            WHERE region = :region AND tournament_year = :year
        """), {"region": region, "year": year})
        return result.scalar() or 0


# =========================================================================
# Enumerated bracket insert
# =========================================================================

def insert_enumerated_brackets(
    packed_outcomes: np.ndarray,
    probabilities: np.ndarray,
    region: str,
    year: int = TOURNAMENT_YEAR,
) -> int:
    """Bulk insert all enumerated brackets for a region using COPY.

    All 32,768 brackets are inserted with:
      - weight = probability (exact, no importance sampling)
      - stratum_id = NULL (no stratification)
      - cluster = 'enumerated'
      - is_alive = TRUE
      - expected_score = 0.0

    Args:
        packed_outcomes: Shape (N,), dtype int16. Packed 15-bit outcomes.
        probabilities: Shape (N,), dtype float64. Exact bracket probabilities.
        region: Region name.
        year: Tournament year.

    Returns:
        Number of rows inserted.
    """
    n = len(packed_outcomes)
    if n == 0:
        return 0

    conn = get_raw_connection()
    cursor = conn.cursor()

    try:
        buf = StringIO()
        for i in range(n):
            row_id = i + 1
            outcome = int(packed_outcomes[i])
            prob = float(probabilities[i])
            # Tab-separated: id, region, outcomes, weight, stratum_id,
            #                 cluster, probability, expected_score,
            #                 is_alive, tournament_year
            buf.write(
                f"{row_id}\t{region}\t{outcome}\t{prob:.15e}\t"
                f"\\N\tenumerated\t{prob:.15e}\t"
                f"0.0\ttrue\t{year}\n"
            )

        buf.seek(0)
        cursor.copy_expert(
            "COPY brackets (id, region, outcomes, weight, stratum_id, "
            "cluster, probability, expected_score, is_alive, "
            "tournament_year) FROM STDIN",
            buf,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

    return n
