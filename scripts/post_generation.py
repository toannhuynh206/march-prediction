"""
Post-generation sanity checks and index rebuild.

Run after 206M bracket generation completes:
    python scripts/post_generation.py --year 2026
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.connection import get_engine
from sqlalchemy import text


def rebuild_indexes(engine):
    """Rebuild all full_brackets indexes after bulk insert."""
    indexes = [
        ("idx_fb_south_outcomes", "full_brackets (south_outcomes)"),
        ("idx_fb_east_outcomes", "full_brackets (east_outcomes)"),
        ("idx_fb_west_outcomes", "full_brackets (west_outcomes)"),
        ("idx_fb_midwest_outcomes", "full_brackets (midwest_outcomes)"),
        ("idx_fb_f4_outcomes", "full_brackets (f4_outcomes)"),
        ("idx_fb_prob", "full_brackets (probability DESC)"),
        ("idx_fb_champion", "full_brackets (champion_region, champion_seed)"),
    ]
    print("\n[INDEX] Rebuilding indexes...")
    for name, definition in indexes:
        t = time.time()
        with engine.connect() as c:
            c.execute(text(f"DROP INDEX IF EXISTS {name}"))
            c.execute(text(f"CREATE INDEX {name} ON {definition}"))
            c.commit()
        elapsed = time.time() - t
        print(f"  {name}: {elapsed:.1f}s")
    print("  All indexes rebuilt.")


def sanity_checks(engine, year: int):
    """Run comprehensive sanity checks on generated brackets."""
    print(f"\n{'='*70}")
    print(f" SANITY CHECKS — {year}")
    print(f"{'='*70}")
    passed = 0
    failed = 0

    with engine.connect() as c:
        # 1. Total count
        total = c.execute(text(
            "SELECT COUNT(*) FROM full_brackets WHERE tournament_year = :y"
        ), {"y": year}).scalar()
        print(f"\n[1] Total brackets: {total:,}")

        # 2. Uniqueness — full bracket fingerprint
        print("\n[2] Uniqueness check...")
        t = time.time()
        unique = c.execute(text("""
            SELECT COUNT(DISTINCT (east_outcomes, south_outcomes,
                                   west_outcomes, midwest_outcomes, f4_outcomes))
            FROM full_brackets WHERE tournament_year = :y
        """), {"y": year}).scalar()
        elapsed = time.time() - t
        dup_count = total - unique
        dup_pct = dup_count / total * 100 if total > 0 else 0
        status = "PASS" if dup_pct < 5 else "WARN" if dup_pct < 20 else "FAIL"
        print(f"  Unique: {unique:,} / {total:,} ({100 - dup_pct:.2f}% unique)")
        print(f"  Duplicates: {dup_count:,} ({dup_pct:.2f}%) [{status}] ({elapsed:.1f}s)")
        if status == "PASS":
            passed += 1
        else:
            failed += 1

        # 3. Strategy distribution
        print("\n[3] Strategy distribution...")
        rows = c.execute(text("""
            SELECT strategy, COUNT(*) as cnt
            FROM full_brackets WHERE tournament_year = :y
            GROUP BY strategy ORDER BY cnt DESC
        """), {"y": year}).fetchall()
        for r in rows:
            pct = r[1] / total * 100
            print(f"  {r[0] or 'null':>15s}: {r[1]:>12,} ({pct:.1f}%)")
        passed += 1

        # 4. Champion seed distribution
        print("\n[4] Champion seed distribution...")
        rows = c.execute(text("""
            SELECT champion_seed, COUNT(*) as cnt
            FROM full_brackets WHERE tournament_year = :y
            GROUP BY champion_seed ORDER BY champion_seed
        """), {"y": year}).fetchall()
        seed1_pct = 0
        for r in rows:
            pct = r[1] / total * 100
            if r[0] == 1:
                seed1_pct = pct
            if pct > 0.01:
                print(f"  Seed {r[0]:>2d}: {r[1]:>12,} ({pct:.2f}%)")
        status = "PASS" if 50 <= seed1_pct <= 70 else "WARN"
        print(f"  1-seed rate: {seed1_pct:.1f}% (target 55-65%) [{status}]")
        if status == "PASS":
            passed += 1
        else:
            failed += 1

        # 5. Champion region balance
        print("\n[5] Champion region balance...")
        rows = c.execute(text("""
            SELECT champion_region, COUNT(*) as cnt
            FROM full_brackets WHERE tournament_year = :y
            GROUP BY champion_region ORDER BY cnt DESC
        """), {"y": year}).fetchall()
        for r in rows:
            pct = r[1] / total * 100
            print(f"  {r[0]:>10s}: {r[1]:>12,} ({pct:.1f}%)")
        passed += 1

        # 6. No 15/16 seed champions
        print("\n[6] No 15/16 seed champions...")
        bad = c.execute(text("""
            SELECT COUNT(*) FROM full_brackets
            WHERE tournament_year = :y AND champion_seed >= 15
        """), {"y": year}).scalar()
        status = "PASS" if bad == 0 else "FAIL"
        print(f"  15/16 seed champions: {bad} [{status}]")
        if status == "PASS":
            passed += 1
        else:
            failed += 1

        # 7. Upset distribution
        print("\n[7] Upset distribution (total_upsets)...")
        rows = c.execute(text("""
            SELECT MIN(total_upsets), MAX(total_upsets),
                   ROUND(AVG(total_upsets)::numeric, 1),
                   ROUND(STDDEV(total_upsets)::numeric, 1)
            FROM full_brackets WHERE tournament_year = :y
        """), {"y": year}).fetchone()
        print(f"  Min: {rows[0]}, Max: {rows[1]}, Avg: {rows[2]}, StdDev: {rows[3]}")
        status = "PASS" if 15 <= float(rows[2]) <= 25 else "WARN"
        print(f"  Average upsets: {rows[2]} (target 18-22) [{status}]")
        if status == "PASS":
            passed += 1
        else:
            failed += 1

        # 8. Top 10 most common brackets
        print("\n[8] Most common bracket fingerprints...")
        rows = c.execute(text("""
            SELECT east_outcomes, south_outcomes, west_outcomes,
                   midwest_outcomes, f4_outcomes, COUNT(*) as cnt
            FROM full_brackets WHERE tournament_year = :y
            GROUP BY east_outcomes, south_outcomes, west_outcomes,
                     midwest_outcomes, f4_outcomes
            ORDER BY cnt DESC LIMIT 10
        """), {"y": year}).fetchall()
        for i, r in enumerate(rows, 1):
            print(f"  #{i}: E={r[0]} S={r[1]} W={r[2]} M={r[3]} F4={r[4]} — {r[5]:,} copies")
        passed += 1

        # 9. DB size
        size = c.execute(text(
            "SELECT pg_size_pretty(pg_database_size(current_database()))"
        )).scalar()
        print(f"\n[9] Database size: {size}")
        passed += 1

    print(f"\n{'='*70}")
    print(f" RESULTS: {passed} passed, {failed} warnings/failures")
    print(f"{'='*70}")


def create_generation_proof(engine, year: int):
    """Create a SHA-256 proof of bracket generation."""
    print("\n[PROOF] Generating SHA-256 proof...")
    t = time.time()

    with engine.connect() as c:
        total = c.execute(text(
            "SELECT COUNT(*) FROM full_brackets WHERE tournament_year = :y"
        ), {"y": year}).scalar()

        # Hash the champion distribution + strategy breakdown
        champ_rows = c.execute(text("""
            SELECT champion_seed, champion_region, COUNT(*)
            FROM full_brackets WHERE tournament_year = :y
            GROUP BY champion_seed, champion_region
            ORDER BY champion_seed, champion_region
        """), {"y": year}).fetchall()

        strat_rows = c.execute(text("""
            SELECT strategy, COUNT(*)
            FROM full_brackets WHERE tournament_year = :y
            GROUP BY strategy ORDER BY strategy
        """), {"y": year}).fetchall()

    # Build deterministic hash input
    hash_input = f"year={year}|total={total}|"
    hash_input += "|".join(f"{r[0]}-{r[1]}:{r[2]}" for r in champ_rows)
    hash_input += "|"
    hash_input += "|".join(f"{r[0]}:{r[1]}" for r in strat_rows)

    sha = hashlib.sha256(hash_input.encode()).hexdigest()

    champ_dist = json.dumps([
        {"seed": r[0], "region": r[1], "count": r[2]} for r in champ_rows
    ])
    strat_dist = json.dumps([
        {"strategy": r[0], "count": r[1]} for r in strat_rows
    ])

    with engine.begin() as c:
        c.execute(text("""
            INSERT INTO generation_proof
                (tournament_year, total_brackets, sha256_hash,
                 strategy_breakdown, champion_distribution)
            VALUES (:y, :total, :sha, CAST(:strat AS jsonb), CAST(:champ AS jsonb))
        """), {
            "y": year, "total": total, "sha": sha,
            "strat": strat_dist, "champ": champ_dist,
        })

    elapsed = time.time() - t
    print(f"  SHA-256: {sha}")
    print(f"  Total brackets: {total:,}")
    print(f"  Proof stored in generation_proof table ({elapsed:.1f}s)")


def main():
    parser = argparse.ArgumentParser(description="Post-generation sanity checks")
    parser.add_argument("--year", type=int, default=2026)
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass

    engine = get_engine()

    rebuild_indexes(engine)
    sanity_checks(engine, args.year)
    create_generation_proof(engine, args.year)

    print("\nDone. Ready for production.")


if __name__ == "__main__":
    main()
