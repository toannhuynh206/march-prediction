"""
Simulation entry point — regional enumeration + full tournament bracket generation.

Two modes:
  1. Regional enumeration: Compute exact probabilities for all 32,768 brackets per region.
  2. Full tournament: Sample N full brackets (63 games each) by combining
     4 regional brackets + 3 Final Four outcomes.

Usage:
    # Enumerate single region
    python -m simulation.simulate --region South --year 2026

    # Enumerate all regions
    python -m simulation.simulate --all --year 2026

    # Generate full tournament brackets (requires regions enumerated first)
    python -m simulation.simulate --full-tournament --count 1000000 --year 2026
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.constants import FULL_TOURNAMENT_BUDGET, REGIONS, TOURNAMENT_YEAR
from simulation.enumerate import (
    enumerate_region,
    print_enumeration_summary,
)
from simulation.first_four import resolve_and_prepare
from simulation.full_bracket_storage import (
    clear_full_brackets,
    get_full_bracket_count,
    insert_full_brackets_copy,
)
from simulation.probability import load_region_probabilities
from simulation.storage import (
    clear_brackets,
    get_bracket_count,
    insert_enumerated_brackets,
)
from simulation.temperature import DEFAULT_PROFILES, compute_profile_budgets
from simulation.tournament_sampler import sample_stratified_brackets


# =========================================================================
# Region simulation
# =========================================================================

def simulate_region(
    region: str,
    year: int = TOURNAMENT_YEAR,
) -> dict:
    """Enumerate all 32,768 brackets for one region with exact probabilities.

    1. Load probabilities from DB
    2. Enumerate all 2^15 brackets
    3. Store in DB
    4. Print distribution summary

    Returns summary dict.
    """
    print(f"\n{'='*70}")
    print(f" ENUMERATION — {region} Region")
    print(f" 32,768 brackets (exact probabilities)")
    print(f"{'='*70}")

    t_start = time.time()

    # 1. Load probabilities
    print(f"\n[1/3] Loading probability data...")
    region_probs = load_region_probabilities(year, region)
    print(f"  Loaded {len(region_probs.teams)} teams")
    print(f"  R64 probs: {[f'{p:.3f}' for p in region_probs.r64_top_win_probs]}")

    # 2. Enumerate all brackets
    print(f"\n[2/3] Enumerating all 32,768 brackets...")
    t_enum = time.time()
    enum = enumerate_region(region_probs)
    print(f"  Enumerated in {time.time() - t_enum:.2f}s")

    # Verify probabilities sum to ~1.0
    total_prob = float(enum.probabilities.sum())
    print(f"  P(total) = {total_prob:.10f}")
    if abs(total_prob - 1.0) > 0.01:
        print(f"  WARNING: Probabilities sum to {total_prob:.6f}, expected ~1.0")

    # 3. Store in DB
    print(f"\n[3/3] Storing brackets in database...")
    existing = get_bracket_count(region, year)
    if existing > 0:
        print(f"  Clearing {existing:,} existing brackets...")
        clear_brackets(region, year)

    n_inserted = insert_enumerated_brackets(
        enum.packed, enum.probabilities, region, year,
    )
    print(f"  Inserted {n_inserted:,} brackets")

    # Print distribution summary
    print_enumeration_summary(enum)

    t_total = time.time() - t_start
    print(f"\n{'='*70}")
    print(f" COMPLETE — {region}")
    print(f" {n_inserted:,} brackets in {t_total:.1f}s")
    print(f"{'='*70}")

    return {
        "region": region,
        "total_brackets": n_inserted,
        "elapsed_seconds": t_total,
        "total_probability": total_prob,
        "champion_distribution": enum.champion_distribution(),
    }


# =========================================================================
# Full tournament generation
# =========================================================================

def simulate_full_tournament(
    n_brackets: int = FULL_TOURNAMENT_BUDGET,
    year: int = TOURNAMENT_YEAR,
) -> dict:
    """Generate N full tournament brackets by combining regional enumerations.

    Pipeline:
      1. Load probabilities and enumerate all 4 regions (fast, ~4s total)
      2. Sample full brackets in batches (region draws + F4 simulation)
      3. Bulk insert each batch via PostgreSQL COPY

    Args:
        n_brackets: Total full brackets to generate.
        year: Tournament year.

    Returns:
        Summary dict with counts and timing.
    """
    print(f"\n{'='*70}")
    print(f" FULL TOURNAMENT GENERATION")
    print(f" {n_brackets:,} brackets (4 regions × F4)")
    print(f"{'='*70}")

    t_start = time.time()

    # 1. Enumerate all 4 regions
    print(f"\n[1/3] Enumerating all 4 regions...")
    enumerations = {}
    region_teams = {}
    for region in REGIONS:
        region_probs = load_region_probabilities(year, region)
        enum = enumerate_region(region_probs)
        enumerations[region] = enum
        region_teams[region] = region_probs.teams
        total_prob = float(enum.probabilities.sum())
        print(f"  {region}: {enum.n_brackets:,} brackets, "
              f"P(total) = {total_prob:.8f}")

    # 2. Clear existing full brackets
    print(f"\n[2/3] Preparing database...")
    existing = get_full_bracket_count(year)
    if existing > 0:
        print(f"  Clearing {existing:,} existing full brackets...")
        clear_full_brackets(year)

    # 3. Show strategy profile allocation
    budgets = compute_profile_budgets(n_brackets, DEFAULT_PROFILES)
    print(f"\n[3/4] Strategy profile allocation:")
    for profile, budget in budgets:
        upset_exp = 4 * profile.p_upset
        print(f"  {profile.name:>12s}: base_T={profile.base_temperature:.1f}, "
              f"upset_T={profile.upset_temperature:.1f}, "
              f"p_upset={profile.p_upset:.2f} (~{upset_exp:.1f} regions), "
              f"F4_T={profile.f4_temperature:.1f}, "
              f"{budget:>12,} brackets ({profile.fraction*100:.0f}%)")

    # 4. Sample and insert in batches (multi-profile stratified)
    print(f"\n[4/4] Sampling and inserting full brackets...")
    total_inserted = 0
    t_sample = time.time()

    for batch in sample_stratified_brackets(
        enumerations=enumerations,
        region_teams=region_teams,
        n_brackets=n_brackets,
        profiles=DEFAULT_PROFILES,
        rng_seed=year,
    ):
        n_inserted = insert_full_brackets_copy(
            east_outcomes=batch.east_outcomes,
            south_outcomes=batch.south_outcomes,
            west_outcomes=batch.west_outcomes,
            midwest_outcomes=batch.midwest_outcomes,
            f4_outcomes=batch.f4_outcomes,
            probabilities=batch.probabilities,
            weights=batch.weights,
            champion_seeds=batch.champion_seeds,
            champion_region_idx=batch.champion_region_idx,
            total_upsets=batch.total_upsets,
            id_offset=total_inserted,
            strategy=batch.strategy,
            year=year,
        )
        total_inserted += n_inserted

        # Progress update every batch
        elapsed = time.time() - t_sample
        rate = total_inserted / max(elapsed, 0.001)
        pct = total_inserted / n_brackets * 100
        print(f"  {total_inserted:>12,} / {n_brackets:,} "
              f"({pct:5.1f}%) — {rate:,.0f} brackets/s")

    t_total = time.time() - t_start
    print(f"\n{'='*70}")
    print(f" COMPLETE — Full Tournament")
    print(f" {total_inserted:,} brackets in {t_total:.1f}s")
    print(f" ({total_inserted / max(t_total, 0.001):,.0f} brackets/s)")
    print(f"{'='*70}")

    return {
        "total_brackets": total_inserted,
        "elapsed_seconds": t_total,
    }


# =========================================================================
# Main
# =========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="March Madness bracket enumeration engine"
    )
    parser.add_argument("--region", type=str, help="Single region to enumerate")
    parser.add_argument("--all", action="store_true", help="Enumerate all 4 regions")
    parser.add_argument(
        "--full-tournament", action="store_true",
        help="Generate full 63-game tournament brackets (requires regions enumerated)",
    )
    parser.add_argument(
        "--count", type=int, default=FULL_TOURNAMENT_BUDGET,
        help=f"Number of full brackets to generate (default: {FULL_TOURNAMENT_BUDGET:,})",
    )
    parser.add_argument("--year", type=int, default=TOURNAMENT_YEAR)
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass

    if not args.region and not args.all and not args.full_tournament:
        parser.error("Specify --region <name>, --all, or --full-tournament")

    # Resolve First Four play-in games before any simulation
    resolve_and_prepare(year=args.year)

    if args.full_tournament:
        simulate_full_tournament(n_brackets=args.count, year=args.year)

        # Run validation after generation
        from simulation.bracket_validator import validate_portfolio, print_champion_breakdown
        report = validate_portfolio(year=args.year)
        report.print_report()
        print_champion_breakdown(year=args.year)
        return

    regions = list(REGIONS) if args.all else [args.region]

    results = []
    for region in regions:
        result = simulate_region(region=region, year=args.year)
        results.append(result)

    # Final summary
    if len(results) > 1:
        total_brackets = sum(r["total_brackets"] for r in results)
        total_time = sum(r["elapsed_seconds"] for r in results)
        print(f"\n{'='*70}")
        print(f" ALL REGIONS COMPLETE")
        print(f" Total: {total_brackets:,} brackets in {total_time:.1f}s")
        print(f" (131,072 brackets with exact probabilities)")
        print(f"{'='*70}")

        # Cross-region champion distribution
        print(f"\n  Champion Distribution by Region:")
        print(f"  {'Region':>10s} {'1-seed':>8s} {'2-3':>8s} {'4-6':>8s} {'7+':>8s}")
        print(f"  {'-'*10} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
        for r in results:
            dist = r["champion_distribution"]
            s1 = dist.get(1, 0.0) * 100
            s23 = sum(dist.get(s, 0.0) for s in (2, 3)) * 100
            s46 = sum(dist.get(s, 0.0) for s in (4, 5, 6)) * 100
            s7p = sum(dist.get(s, 0.0) for s in range(7, 17)) * 100
            print(f"  {r['region']:>10s} {s1:>7.1f}% {s23:>7.1f}% "
                  f"{s46:>7.1f}% {s7p:>7.1f}%")


if __name__ == "__main__":
    main()
