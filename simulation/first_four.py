"""
First Four play-in game resolution.

Detects duplicate seeds (play-in teams) in each region and resolves
them probabilistically using power index logistic function.
After resolution, creates any missing R64 matchup records.

Per CLAUDE.md: "First Four: Simulate before loading main bracket.
4 games. Winners replace placeholder."
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.constants import LOGISTIC_K_INITIAL, TOURNAMENT_YEAR
from db.connection import session_scope
from simulation.bracket_structure import R64_SEED_MATCHUPS
from sqlalchemy import text


def find_first_four_pairs(
    year: int = TOURNAMENT_YEAR,
) -> list[dict]:
    """Find all First Four play-in pairs (duplicate seeds within a region).

    Returns list of dicts with keys:
        region, seed, team_a (name, id, pi), team_b (name, id, pi)
    """
    pairs: list[dict] = []

    with session_scope() as session:
        rows = session.execute(text("""
            SELECT t.id, t.name, t.seed, t.region,
                   COALESCE(ts.power_index, 50.0) as power_index
            FROM teams t
            LEFT JOIN team_stats ts ON t.id = ts.team_id
              AND ts.tournament_year = :year
            WHERE t.tournament_year = :year
            ORDER BY t.region, t.seed, t.name
        """), {"year": year}).fetchall()

    # Group by (region, seed) and find duplicates
    from collections import defaultdict
    grouped: dict[tuple[str, int], list] = defaultdict(list)
    for row in rows:
        key = (row[3], row[2])  # (region, seed)
        grouped[key].append({
            "id": row[0],
            "name": row[1],
            "seed": row[2],
            "region": row[3],
            "power_index": float(row[4]),
        })

    for (region, seed), teams in grouped.items():
        if len(teams) == 2:
            pairs.append({
                "region": region,
                "seed": seed,
                "team_a": teams[0],
                "team_b": teams[1],
            })

    return pairs


def resolve_first_four(
    year: int = TOURNAMENT_YEAR,
    k: float = LOGISTIC_K_INITIAL,
    rng_seed: int = 42,
) -> list[dict]:
    """Simulate First Four games and remove losers from the database.

    Uses logistic function on power indices to determine win probability,
    then probabilistically selects winners.

    Returns list of resolution results with winner/loser info.
    """
    pairs = find_first_four_pairs(year)
    if not pairs:
        print("  No First Four games to resolve.")
        return []

    rng = np.random.default_rng(seed=rng_seed)
    results: list[dict] = []

    print(f"\n  First Four Resolution ({len(pairs)} games):")
    print(f"  {'Region':>8s} {'Seed':>4s} {'Team A':>20s} {'PI_A':>6s} "
          f"{'Team B':>20s} {'PI_B':>6s} {'P(A)':>6s} {'Winner':>20s}")
    print(f"  {'-'*8} {'-'*4} {'-'*20} {'-'*6} {'-'*20} {'-'*6} {'-'*6} {'-'*20}")

    for pair in pairs:
        ta = pair["team_a"]
        tb = pair["team_b"]

        # Logistic win probability
        exponent = (tb["power_index"] - ta["power_index"]) / k
        p_a_wins = 1.0 / (1.0 + 10.0 ** exponent)

        # Probabilistic selection
        a_wins = rng.random() < p_a_wins
        winner = ta if a_wins else tb
        loser = tb if a_wins else ta

        print(f"  {pair['region']:>8s} {pair['seed']:>4d} "
              f"{ta['name']:>20s} {ta['power_index']:>6.1f} "
              f"{tb['name']:>20s} {tb['power_index']:>6.1f} "
              f"{p_a_wins:>6.3f} {winner['name']:>20s}")

        results.append({
            "region": pair["region"],
            "seed": pair["seed"],
            "winner": winner,
            "loser": loser,
            "p_winner": p_a_wins if a_wins else 1.0 - p_a_wins,
        })

    # Remove losers from DB
    with session_scope() as session:
        for res in results:
            loser_id = res["loser"]["id"]
            session.execute(text("""
                DELETE FROM team_stats
                WHERE team_id = :tid AND tournament_year = :year
            """), {"tid": loser_id, "year": year})
            session.execute(text("""
                DELETE FROM teams WHERE id = :tid
            """), {"tid": loser_id})
            print(f"  Removed: {res['loser']['name']} "
                  f"(id={loser_id}) from {res['region']}")

    return results


def create_missing_matchups(
    year: int = TOURNAMENT_YEAR,
    k: float = LOGISTIC_K_INITIAL,
) -> int:
    """Create R64 matchup records for any missing seed pairs.

    After First Four resolution, some R64 matchups may not exist in the
    matchups table (e.g., 1v16 in a region that had a 16-seed play-in).
    Creates them using the logistic function from power indices.

    Returns count of matchups created.
    """
    created = 0

    with session_scope() as session:
        # Get existing R64 matchups per region
        existing = session.execute(text("""
            SELECT region, seed_a, seed_b
            FROM matchups
            WHERE tournament_year = :year AND round = 'R64'
        """), {"year": year}).fetchall()

        existing_set = {(r[0], r[1], r[2]) for r in existing}

        # Get all regions
        regions = session.execute(text("""
            SELECT DISTINCT region FROM teams WHERE tournament_year = :year
        """), {"year": year}).fetchall()

        for (region,) in regions:
            # Load teams for this region
            teams = session.execute(text("""
                SELECT t.seed, COALESCE(ts.power_index, 50.0) as power_index,
                       t.id, t.name
                FROM teams t
                LEFT JOIN team_stats ts ON t.id = ts.team_id
                  AND ts.tournament_year = :year
                WHERE t.tournament_year = :year AND t.region = :region
                ORDER BY t.seed
            """), {"year": year, "region": region}).fetchall()

            seed_to_pi = {int(t[0]): float(t[1]) for t in teams}
            seed_to_id = {int(t[0]): t[2] for t in teams}
            seed_to_name = {int(t[0]): t[3] for t in teams}

            # Check each R64 matchup
            for seed_h, seed_l in R64_SEED_MATCHUPS:
                if (region, seed_h, seed_l) in existing_set:
                    continue

                pi_h = seed_to_pi.get(seed_h, 50.0)
                pi_l = seed_to_pi.get(seed_l, 50.0)
                id_h = seed_to_id.get(seed_h)
                id_l = seed_to_id.get(seed_l)

                if id_h is None or id_l is None:
                    print(f"  WARNING: Can't create matchup {region} "
                          f"#{seed_h}v#{seed_l} — missing team")
                    continue

                # Logistic probability
                exponent = (pi_l - pi_h) / k
                p_final = 1.0 / (1.0 + 10.0 ** exponent)

                session.execute(text("""
                    INSERT INTO matchups
                        (tournament_year, region, round, seed_a, seed_b,
                         team_a_id, team_b_id, p_stats, p_final)
                    VALUES (:year, :region, 'R64', :seed_a, :seed_b,
                            :team_a_id, :team_b_id, :p_stats, :p_final)
                """), {
                    "year": year,
                    "region": region,
                    "seed_a": seed_h,
                    "seed_b": seed_l,
                    "team_a_id": id_h,
                    "team_b_id": id_l,
                    "p_stats": p_final,
                    "p_final": p_final,
                })

                name_h = seed_to_name.get(seed_h, f"#{seed_h}")
                name_l = seed_to_name.get(seed_l, f"#{seed_l}")
                print(f"  Created: {region} #{seed_h} ({name_h}) vs "
                      f"#{seed_l} ({name_l}): P={p_final:.4f}")
                created += 1

    return created


def resolve_and_prepare(
    year: int = TOURNAMENT_YEAR,
    k: float = LOGISTIC_K_INITIAL,
) -> None:
    """Full First Four resolution pipeline.

    1. Detect and resolve play-in games
    2. Create missing R64 matchups
    3. Verify all regions have exactly 16 teams and 8 R64 matchups
    """
    print("\n[0/5] Resolving First Four play-in games...")

    # Check if already resolved (no duplicate seeds)
    pairs = find_first_four_pairs(year)
    if pairs:
        resolve_first_four(year, k)
    else:
        print("  First Four already resolved.")

    # Create missing matchups
    n_created = create_missing_matchups(year, k)
    if n_created:
        print(f"  Created {n_created} missing R64 matchups.")

    # Verify
    with session_scope() as session:
        counts = session.execute(text("""
            SELECT region, COUNT(*)
            FROM teams
            WHERE tournament_year = :year
            GROUP BY region
            ORDER BY region
        """), {"year": year}).fetchall()

        all_good = True
        for region, count in counts:
            status = "OK" if count == 16 else "PROBLEM"
            if count != 16:
                all_good = False
            print(f"  {region}: {count} teams [{status}]")

        matchup_counts = session.execute(text("""
            SELECT region, COUNT(*)
            FROM matchups
            WHERE tournament_year = :year AND round = 'R64'
            GROUP BY region
            ORDER BY region
        """), {"year": year}).fetchall()

        for region, count in matchup_counts:
            status = "OK" if count == 8 else f"MISSING {8-count}"
            if count != 8:
                all_good = False
            print(f"  {region}: {count}/8 R64 matchups [{status}]")

        if all_good:
            print("  All regions ready for simulation.")
        else:
            print("  WARNING: Some regions have issues!")


if __name__ == "__main__":
    resolve_and_prepare()
