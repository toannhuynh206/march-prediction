"""Validity Bitmap pruning — instant pruning via alive outcome tables.

The 206M full_brackets table is NEVER modified. Instead, 5 tiny
"alive_outcomes" tables (one per region + F4) track which packed
outcome values are still valid. Pruning = DELETE from these tiny
tables using bit math. A bracket is alive if all 5 of its outcome
values exist in the alive tables.

Prune speed: < 1ms (operates on 32,768 rows max, not 206M).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.constants import TOURNAMENT_YEAR
from db.connection import get_engine
from sqlalchemy import text


# Region name → alive table name + full_brackets column name
REGION_CONFIG: dict[str, dict[str, str]] = {
    "South":   {"alive_table": "alive_outcomes_south",   "column": "south_outcomes"},
    "East":    {"alive_table": "alive_outcomes_east",    "column": "east_outcomes"},
    "West":    {"alive_table": "alive_outcomes_west",    "column": "west_outcomes"},
    "Midwest": {"alive_table": "alive_outcomes_midwest", "column": "midwest_outcomes"},
}


def prune_regional_game(
    region: str,
    game_index: int,
    expected_bit: int,
    year: int = TOURNAMENT_YEAR,
) -> tuple[int, int]:
    """Prune a single regional game by removing dead values from alive table.

    Deletes from alive_outcomes_{region} where the bit doesn't match.
    The full_brackets table is never touched.

    Returns (eliminated_estimate, alive_remaining_estimate).
    """
    config = REGION_CONFIG[region]
    return _prune_alive_table(
        table=config["alive_table"],
        condition=f"(outcome_value >> {game_index}) & 1 != {expected_bit}",
        game_details=[{
            "region": region,
            "game_index": game_index,
            "expected_bit": expected_bit,
        }],
        year=year,
    )


def prune_f4_game(
    f4_bit_position: int,
    expected_bit: int,
    year: int = TOURNAMENT_YEAR,
) -> tuple[int, int]:
    """Prune a Final Four game."""
    return _prune_alive_table(
        table="alive_outcomes_f4",
        condition=f"(outcome_value >> {f4_bit_position}) & 1 != {expected_bit}",
        game_details=[{
            "round": "F4",
            "bit_position": f4_bit_position,
            "expected_bit": expected_bit,
        }],
        year=year,
    )


def prune_batch(
    games: list[dict],
    year: int = TOURNAMENT_YEAR,
) -> tuple[int, int]:
    """Batch prune multiple game results at once.

    Each game dict has: region, game_index, expected_bit
    (or round='F4'/'Final' for F4 games).

    Groups games by region, issues one DELETE per region.
    All deletes happen in one transaction.

    Returns (total_values_deleted, estimated_alive_brackets).
    """
    engine = get_engine()
    t_start = time.time()
    total_deleted = 0

    # Group games by region
    regional_games: dict[str, list[tuple[int, int]]] = {}
    f4_games: list[tuple[int, int]] = []

    for game in games:
        if game.get("round") in ("F4", "Final"):
            f4_games.append((game["bit_position"], game["expected_bit"]))
        else:
            region = game["region"]
            if region not in regional_games:
                regional_games[region] = []
            regional_games[region].append((game["game_index"], game["expected_bit"]))

    with engine.begin() as conn:
        # Prune each region
        for region, region_game_list in regional_games.items():
            config = REGION_CONFIG[region]
            conditions = [
                f"(outcome_value >> {gi}) & 1 != {eb}"
                for gi, eb in region_game_list
            ]
            combined = " OR ".join(conditions)
            result = conn.execute(
                text(f"DELETE FROM {config['alive_table']} WHERE {combined}")
            )
            total_deleted += result.rowcount

        # Prune F4
        if f4_games:
            conditions = [
                f"(outcome_value >> {bp}) & 1 != {eb}"
                for bp, eb in f4_games
            ]
            combined = " OR ".join(conditions)
            result = conn.execute(
                text(f"DELETE FROM alive_outcomes_f4 WHERE {combined}")
            )
            total_deleted += result.rowcount

    duration_ms = int((time.time() - t_start) * 1000)

    # Log the prune
    _log_prune(games, total_deleted, duration_ms, year)

    # Refresh stats cache
    refresh_stats_cache(year)

    alive = get_alive_count(year)
    return total_deleted, alive


def _prune_alive_table(
    table: str,
    condition: str,
    game_details: list[dict],
    year: int,
) -> tuple[int, int]:
    """Delete dead values from an alive table and log it.

    Returns (brackets_eliminated, brackets_remaining) — actual bracket
    counts from the stats cache, not alive table value counts.
    """
    before_alive = get_alive_count(year)
    engine = get_engine()
    t_start = time.time()

    with engine.begin() as conn:
        result = conn.execute(text(f"DELETE FROM {table} WHERE {condition}"))
        deleted = result.rowcount

    duration_ms = int((time.time() - t_start) * 1000)
    _log_prune(game_details, deleted, duration_ms, year)

    if deleted > 0:
        refresh_stats_cache(year)

    after_alive = get_alive_count(year)
    brackets_eliminated = before_alive - after_alive
    return brackets_eliminated, after_alive


def _log_prune(
    game_details: list[dict],
    values_deleted: int,
    duration_ms: int,
    year: int,
) -> None:
    """Record the prune operation in prune_log."""
    engine = get_engine()

    # Get current alive counts per region for the log
    alive_info = get_alive_summary(year)

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO prune_log "
                "(tournament_year, games_submitted, game_details, "
                " brackets_before, brackets_deleted, brackets_remaining, prune_duration_ms) "
                "VALUES (:year, :n, CAST(:details AS jsonb), "
                " :before, :deleted, :remaining, :ms)"
            ),
            {
                "year": year,
                "n": len(game_details),
                "details": json.dumps(game_details),
                "before": alive_info["total_alive_values"],
                "deleted": values_deleted,
                "remaining": alive_info["total_alive_values"] - values_deleted,
                "ms": duration_ms,
            },
        )


def get_alive_summary(year: int = TOURNAMENT_YEAR) -> dict:
    """Get alive value counts for each region."""
    engine = get_engine()
    with engine.connect() as conn:
        counts = {}
        for region, config in REGION_CONFIG.items():
            c = conn.execute(
                text(f"SELECT COUNT(*) FROM {config['alive_table']}")
            ).scalar()
            counts[region] = c

        f4_count = conn.execute(
            text("SELECT COUNT(*) FROM alive_outcomes_f4")
        ).scalar()
        counts["F4"] = f4_count

    return {
        "regions": counts,
        "total_alive_values": sum(counts.values()),
    }


def get_alive_count(year: int = TOURNAMENT_YEAR) -> int:
    """Get alive bracket count from stats cache."""
    engine = get_engine()
    with engine.connect() as conn:
        cached = conn.execute(
            text("SELECT alive_brackets FROM stats_cache WHERE tournament_year = :year"),
            {"year": year},
        ).scalar()
        return cached or 0


def refresh_stats_cache(year: int = TOURNAMENT_YEAR) -> None:
    """Recompute stats by JOINing full_brackets against alive tables.

    After games are played, alive tables shrink → JOINs filter most
    rows → queries get progressively faster.
    """
    engine = get_engine()
    t = time.time()

    with engine.connect() as conn:
        # Total brackets = immutable count from full_brackets table.
        # Try cache first (fast), fall back to COUNT(*) on first run.
        total = conn.execute(
            text("SELECT total_brackets FROM stats_cache WHERE tournament_year = :year"),
            {"year": year},
        ).scalar() or 0
        if total == 0:
            total = conn.execute(
                text("SELECT COUNT(*) FROM full_brackets WHERE tournament_year = :year"),
                {"year": year},
            ).scalar() or 0

        # Count alive brackets via 5-way JOIN
        alive = conn.execute(
            text(
                "SELECT COUNT(*) FROM full_brackets fb "
                "JOIN alive_outcomes_south   s ON fb.south_outcomes   = s.outcome_value "
                "JOIN alive_outcomes_east    e ON fb.east_outcomes    = e.outcome_value "
                "JOIN alive_outcomes_west    w ON fb.west_outcomes    = w.outcome_value "
                "JOIN alive_outcomes_midwest m ON fb.midwest_outcomes = m.outcome_value "
                "JOIN alive_outcomes_f4      f ON fb.f4_outcomes      = f.outcome_value "
                "WHERE fb.tournament_year = :year"
            ),
            {"year": year},
        ).scalar()

        # Champion odds via weighted JOIN
        champ_rows = conn.execute(
            text(
                "SELECT t.name, SUM(fb.weight) as tw "
                "FROM full_brackets fb "
                "JOIN alive_outcomes_south   s ON fb.south_outcomes   = s.outcome_value "
                "JOIN alive_outcomes_east    e ON fb.east_outcomes    = e.outcome_value "
                "JOIN alive_outcomes_west    w ON fb.west_outcomes    = w.outcome_value "
                "JOIN alive_outcomes_midwest m ON fb.midwest_outcomes = m.outcome_value "
                "JOIN alive_outcomes_f4      f ON fb.f4_outcomes      = f.outcome_value "
                "JOIN teams t ON t.seed = fb.champion_seed "
                "  AND t.region = fb.champion_region "
                "  AND t.tournament_year = :year "
                "WHERE fb.tournament_year = :year "
                "GROUP BY t.name ORDER BY tw DESC"
            ),
            {"year": year},
        ).fetchall()
        total_weight = sum(float(r[1]) for r in champ_rows) if champ_rows else 1.0
        champion_odds = json.dumps([
            {"name": r[0], "probability": float(r[1]) / total_weight}
            for r in champ_rows
        ])

        # Upset distribution
        upset_rows = conn.execute(
            text(
                "SELECT fb.total_upsets, COUNT(*) "
                "FROM full_brackets fb "
                "JOIN alive_outcomes_south   s ON fb.south_outcomes   = s.outcome_value "
                "JOIN alive_outcomes_east    e ON fb.east_outcomes    = e.outcome_value "
                "JOIN alive_outcomes_west    w ON fb.west_outcomes    = w.outcome_value "
                "JOIN alive_outcomes_midwest m ON fb.midwest_outcomes = m.outcome_value "
                "JOIN alive_outcomes_f4      f ON fb.f4_outcomes      = f.outcome_value "
                "WHERE fb.tournament_year = :year "
                "GROUP BY fb.total_upsets ORDER BY fb.total_upsets"
            ),
            {"year": year},
        ).fetchall()
        upset_dist = json.dumps([
            {"upsets": int(r[0]), "count": int(r[1])}
            for r in upset_rows
        ])

    elapsed_ms = int((time.time() - t) * 1000)

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM stats_cache WHERE tournament_year = :year"),
            {"year": year},
        )
        conn.execute(
            text(
                "INSERT INTO stats_cache "
                "(tournament_year, total_brackets, alive_brackets, champion_odds, upset_distribution) "
                "VALUES (:year, :total, :alive, CAST(:champ AS jsonb), CAST(:upset AS jsonb))"
            ),
            {"year": year, "total": total, "alive": alive,
             "champ": champion_odds, "upset": upset_dist},
        )

    print(f"  Stats cache refreshed in {elapsed_ms}ms — {alive:,} alive")
