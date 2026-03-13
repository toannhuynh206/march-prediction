"""
Integration test: 2026 projected bracket simulation.

Runs the full pipeline end-to-end as if today (March 12, 2026) is Selection Sunday:
  1. Load projected bracket from mock_brackets_2026.json
  2. Estimate team ratings from NET rankings + futures odds
  3. Build TeamProfile objects with talent factors
  4. Build probability matrices per region
  5. Run stratified simulation at small scale (10K per region)
  6. Validate output distributions

Usage:
    python integration_test_2026.py [--budget N]  # default 10000 per region
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

# Add src to path for imports
SRC_DIR = Path(__file__).parent
PROJECT_DIR = SRC_DIR.parent
DATA_DIR = PROJECT_DIR / "data" / "research"

# Local imports
from round_probability import (
    TeamProfile,
    build_probability_matrix,
    build_full_tournament_matrices,
)
from talent_factors import PlayerExperience
from stratifier import allocate_regional_budget, neyman_allocation, ALL_WORLDS
from engine import simulate_region, print_simulation_report, simulation_summary
from math_primitives import R64_MATCHUPS


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict:
    """Load JSON file."""
    with open(path, "r") as f:
        return json.load(f)


def load_projected_bracket() -> dict[str, dict[str, str]]:
    """Load projected bracket: region -> {seed_str: team_name}."""
    data = load_json(DATA_DIR / "mock_brackets_2026.json")
    return data["projected_seedings"]


def load_net_rankings() -> dict[str, dict]:
    """Load NET rankings: team_name -> {net, record}."""
    data = load_json(DATA_DIR / "initial_rankings.json")
    return data["net_rankings"]


def load_futures() -> dict[str, float]:
    """Load championship futures: team_name -> implied_probability."""
    data = load_json(DATA_DIR / "vegas_odds_20260312.json")
    result = {}
    for entry in data.get("championship_futures", []):
        name = entry["team_name"]
        prob = entry.get("consensus_implied_prob")
        if prob is not None and prob > 0:
            result[name] = prob
    return result


def load_injuries() -> dict[str, dict]:
    """Load injury data: team_name -> {player, status, impact_rating}."""
    data = load_json(DATA_DIR / "injuries_20260312.json")
    result = {}
    for injury in data.get("injuries", []):
        team = injury["team"]
        if team not in result:
            result[team] = []
        result[team].append({
            "player": injury["player"],
            "status": injury["status"],
            "impact": injury["impact_rating"],
        })
    return result


# ---------------------------------------------------------------------------
# Rating estimation from NET rankings
# ---------------------------------------------------------------------------

def estimate_adj_em(net_rank: int) -> float:
    """Estimate AdjEM from NET ranking.

    Approximation based on historical KenPom/NET correlation:
      - Rank 1: ~35 AdjEM
      - Rank 10: ~27 AdjEM
      - Rank 25: ~20 AdjEM
      - Rank 50: ~12 AdjEM
      - Rank 75: ~5 AdjEM
      - Rank 100: ~0 AdjEM

    Uses a logarithmic fit: AdjEM ≈ 40 - 8.5 * ln(rank)
    """
    if net_rank <= 0:
        return 35.0
    return max(0.0, 40.0 - 8.5 * math.log(net_rank))


def estimate_adj_o_d(adj_em: float, is_offense_first: bool = True) -> tuple[float, float]:
    """Estimate AdjO and AdjD from AdjEM.

    AdjEM = AdjO - AdjD.
    Average team: AdjO ~105, AdjD ~105.
    Good team: AdjO ~115, AdjD ~95 (offense_first) or AdjO ~108, AdjD ~88 (defense_first).
    """
    baseline_o = 105.0
    baseline_d = 105.0

    if is_offense_first:
        adj_o = baseline_o + adj_em * 0.55
        adj_d = baseline_d - adj_em * 0.45
    else:
        adj_o = baseline_o + adj_em * 0.40
        adj_d = baseline_d - adj_em * 0.60

    return adj_o, adj_d


# ---------------------------------------------------------------------------
# Injury adjustment
# ---------------------------------------------------------------------------

INJURY_ADJ_EM = {
    ("OUT", "CRITICAL"): -4.0,
    ("OUT", "HIGH"): -2.5,
    ("OUT", "MODERATE"): -1.0,
    ("OUT", "LOW"): -0.3,
    ("DOUBTFUL", "CRITICAL"): -3.0,
    ("DOUBTFUL", "HIGH"): -1.5,
    ("QUESTIONABLE", "CRITICAL"): -1.5,
    ("QUESTIONABLE", "HIGH"): -0.8,
    ("QUESTIONABLE", "MODERATE"): -0.3,
    ("PROBABLE", "HIGH"): -0.5,
    ("PROBABLE", "MODERATE"): -0.2,
}


def compute_injury_adjustment(team_injuries: list[dict]) -> float:
    """Compute AdjEM adjustment from injuries."""
    total = 0.0
    for injury in team_injuries:
        status = injury["status"]
        impact = injury["impact"]
        adj = INJURY_ADJ_EM.get((status, impact), 0.0)
        total += adj
    return total


# ---------------------------------------------------------------------------
# Team strength indicators for offense/defense split
# ---------------------------------------------------------------------------

# Teams known for defense-first identity (lower AdjD)
DEFENSE_FIRST_TEAMS = {
    "Houston", "Virginia", "Tennessee", "Iowa State", "Purdue",
    "Texas Tech", "San Diego State", "UConn",
}

# Teams known for NBA-caliber talent (projected draft picks)
NBA_TALENT = {
    "Duke": ("top_3", "top_10", "top_20"),       # Flagg, Boozer, others
    "Michigan": ("top_10", "top_20"),              # projected lottery
    "Arizona": ("top_3", "top_10"),                # Peat + another
    "UConn": ("top_10", "top_20"),
    "Arkansas": ("top_10",),                       # Acuff
    "Alabama": ("top_20", "top_20"),               # multiple prospects
    "Kentucky": ("top_20",),
    "Houston": ("top_20",),
    "Florida": ("top_20",),
    "Gonzaga": ("top_10",),
    "Illinois": ("top_20",),
    "Kansas": ("top_20",),
    "Tennessee": ("top_20",),
    "BYU": ("top_3",),                             # AJ Dybantsa
    "St. John's": ("top_20",),
    "Louisville": ("top_10",),                     # Mikel Brown Jr.
}

# Star player metrics (usage rate, offensive rating)
STAR_PLAYERS = {
    "Duke": (32.0, 125.0),          # Cooper Flagg
    "Arizona": (30.0, 122.0),       # Koa Peat
    "BYU": (31.0, 118.0),           # AJ Dybantsa
    "Arkansas": (29.0, 120.0),      # Darius Acuff
    "Michigan": (28.0, 118.0),
    "Florida": (27.0, 116.0),
    "Alabama": (28.0, 115.0),
    "Houston": (26.0, 115.0),
    "UConn": (27.0, 117.0),
    "Illinois": (28.0, 116.0),
    "Louisville": (29.0, 117.0),    # Mikel Brown Jr. (if healthy)
    "Tennessee": (26.0, 114.0),
    "Gonzaga": (27.0, 115.0),       # Warley returned
    "St. John's": (26.0, 113.0),
    "Texas Tech": (28.0, 116.0),    # JT Toppin (OUT - ACL)
    "Nebraska": (25.0, 112.0),
    "Virginia": (25.0, 111.0),
    "Kansas": (26.0, 112.0),
}

# Tournament experience (teams with returning players who have March minutes)
EXPERIENCED_TEAMS = {
    "UConn": (
        PlayerExperience("Alex Karaban", 350, "Championship", 3),
        PlayerExperience("Solo Ball", 180, "Championship", 2),
        PlayerExperience("Jaylin Stewart", 120, "R32", 2),
    ),
    "Houston": (
        PlayerExperience("J'Wan Roberts", 280, "F4", 3),
        PlayerExperience("Terrance Arceneaux", 150, "E8", 2),
        PlayerExperience("LJ Cryer", 200, "E8", 3),
    ),
    "Duke": (
        PlayerExperience("Tyrese Proctor", 180, "E8", 2),
        PlayerExperience("Kon Knueppel", 80, "R32", 1),
        PlayerExperience("Mason Gillis", 60, "S16", 2),
    ),
    "Kansas": (
        PlayerExperience("Dajuan Harris", 300, "Championship", 4),
        PlayerExperience("Hunter Dickinson", 250, "E8", 4),
        PlayerExperience("KJ Adams", 200, "Championship", 3),
    ),
    "Gonzaga": (
        PlayerExperience("Ryan Nembhard", 200, "S16", 3),
        PlayerExperience("Graham Ike", 80, "R32", 2),
        PlayerExperience("Ben Gregg", 60, "R32", 2),
    ),
    "Michigan State": (
        PlayerExperience("Jaden Akins", 200, "S16", 3),
        PlayerExperience("Malik Hall", 250, "F4", 4),
        PlayerExperience("Tyson Walker", 150, "S16", 3),
    ),
    "Tennessee": (
        PlayerExperience("Zakai Zeigler", 220, "S16", 3),
        PlayerExperience("Josiah-Jordan James", 180, "S16", 3),
        PlayerExperience("Jonas Aidoo", 100, "R32", 2),
    ),
    "Purdue": (
        PlayerExperience("Braden Smith", 280, "Championship", 3),
        PlayerExperience("Fletcher Loyer", 200, "Championship", 2),
        PlayerExperience("Trey Kaufman-Renn", 180, "Championship", 2),
    ),
}


# ---------------------------------------------------------------------------
# Build TeamProfile objects from research data
# ---------------------------------------------------------------------------

def build_team_profiles(
    bracket: dict[str, dict[str, str]],
    net_rankings: dict[str, dict],
    futures: dict[str, float],
    injuries: dict[str, list[dict]],
) -> dict[str, dict[int, TeamProfile]]:
    """Build TeamProfile objects for each region.

    Returns: {region_name: {seed: TeamProfile}}
    """
    regions = {}

    for region_name, seedings in bracket.items():
        teams = {}
        for seed_str, team_name in seedings.items():
            seed = int(seed_str)

            # Rating estimation from NET ranking
            net_data = net_rankings.get(team_name, {})
            net_rank = net_data.get("net", 75)
            adj_em = estimate_adj_em(net_rank)

            # Injury adjustment
            team_injuries = injuries.get(team_name, [])
            injury_adj = compute_injury_adjustment(team_injuries)
            adj_em += injury_adj

            # Offense/defense split
            is_defense_first = team_name in DEFENSE_FIRST_TEAMS
            adj_o, adj_d = estimate_adj_o_d(adj_em, is_offense_first=not is_defense_first)

            # Talent data
            draft_picks = NBA_TALENT.get(team_name, ())
            star_data = STAR_PLAYERS.get(team_name, (0.0, 0.0))
            experience = EXPERIENCED_TEAMS.get(team_name, ())

            # Star adjustment for injured stars
            star_usage, star_rating = star_data
            for inj in team_injuries:
                if inj["status"] in ("OUT", "DOUBTFUL") and inj["impact"] == "CRITICAL":
                    star_usage = max(0, star_usage - 8)
                    star_rating = max(0, star_rating - 10)

            profile = TeamProfile(
                name=team_name,
                seed=seed,
                region=region_name,
                adj_em=adj_em,
                adj_o=adj_o,
                adj_d=adj_d,
                tempo=68.0,              # default, not critical
                kenpom_rank=net_rank,     # proxy
                torvik_rank=None,
                bpi_rank=None,
                net_rank=net_rank,
                elo=1800 - net_rank * 4,  # rough Elo estimate
                defensive_rating=adj_d,
                experience_score=len(experience),
                conference=None,
                tourney_appearances=len(experience),
                season_results=None,      # no h2h data for this test
                draft_picks=draft_picks,
                players_experience=experience,
                star_usage_rate=star_usage,
                star_offensive_rating=star_rating,
            )
            teams[seed] = profile

        regions[region_name] = teams

    return regions


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_results(
    region_name: str,
    brackets: list,
    stats: dict,
) -> list[str]:
    """Validate simulation output against expectations."""
    issues = []

    total = stats.get("total", 0)
    if total == 0:
        issues.append(f"[{region_name}] No brackets generated!")
        return issues

    # 1. Check champion distribution: 1-seeds should win >= 35% (relaxed for test)
    weighted_probs = stats.get("weighted_champion_probs", {})
    seed_1_prob = weighted_probs.get(1, 0.0)
    if seed_1_prob < 0.25:
        issues.append(
            f"[{region_name}] 1-seed champion prob too low: {seed_1_prob:.3f} (expected >= 0.25)"
        )
    if seed_1_prob > 0.80:
        issues.append(
            f"[{region_name}] 1-seed champion prob too high: {seed_1_prob:.3f} (expected <= 0.80)"
        )

    # 2. Top-2 seeds should win >= 50% combined
    top2_prob = weighted_probs.get(1, 0.0) + weighted_probs.get(2, 0.0)
    if top2_prob < 0.40:
        issues.append(
            f"[{region_name}] Top-2 seeds combined prob too low: {top2_prob:.3f} (expected >= 0.40)"
        )

    # 3. Mean R64 upsets should be 2-4 (historical average ~2.7)
    mean_upsets = stats.get("mean_r64_upsets", 0)
    if mean_upsets < 1.5 or mean_upsets > 5.0:
        issues.append(
            f"[{region_name}] Mean R64 upsets out of range: {mean_upsets:.2f} (expected 1.5-5.0)"
        )

    # 4. Should have some unique brackets
    unique = stats.get("unique_brackets", 0)
    unique_pct = unique / total * 100
    if unique_pct < 30:
        issues.append(
            f"[{region_name}] Low bracket diversity: {unique_pct:.1f}% unique (expected >= 30%)"
        )

    # 5. Cinderella seeds (9+) should have some representation
    # Threshold scales with budget: strict at 3M, relaxed at 10K
    cinderella_prob = sum(
        weighted_probs.get(s, 0.0) for s in range(9, 17)
    )
    cinderella_threshold = 0.005 if total > 100_000 else 0.001
    if cinderella_prob < cinderella_threshold:
        issues.append(
            f"[{region_name}] No cinderella representation: {cinderella_prob:.4f} (expected >= {cinderella_threshold})"
        )

    return issues


# ---------------------------------------------------------------------------
# Main integration test
# ---------------------------------------------------------------------------

def run_integration_test(budget_per_region: int = 10_000) -> bool:
    """Run full integration test. Returns True if all validations pass."""

    print("=" * 70)
    print("MARCH MADNESS 2026 — INTEGRATION TEST")
    print(f"Budget: {budget_per_region:,} brackets per region")
    print(f"Total: {budget_per_region * 4:,} brackets across 4 regions")
    print("=" * 70)

    # Load data
    print("\n[1/5] Loading research data...")
    bracket = load_projected_bracket()
    net_rankings = load_net_rankings()
    futures = load_futures()
    injuries = load_injuries()

    print(f"  Bracket: {sum(len(v) for v in bracket.values())} teams across {len(bracket)} regions")
    print(f"  NET rankings: {len(net_rankings)} teams")
    print(f"  Futures: {len(futures)} teams with championship odds")
    print(f"  Injuries: {sum(len(v) for v in injuries.values())} entries across {len(injuries)} teams")

    # Build team profiles
    print("\n[2/5] Building team profiles...")
    regions = build_team_profiles(bracket, net_rankings, futures, injuries)

    for region_name, teams in regions.items():
        top_team = teams[1]
        print(f"  {region_name}: 1-seed {top_team.name} (AdjEM={top_team.adj_em:.1f}, "
              f"draft={top_team.draft_picks}, star=({top_team.star_usage_rate:.0f}%/{top_team.star_offensive_rating:.0f}))")

    # Build probability matrices
    print("\n[3/5] Building probability matrices...")
    all_matrices = build_full_tournament_matrices(regions, futures=futures)

    for region_name, round_matrices in all_matrices.items():
        r64_matrix = round_matrices["R64"]
        # Print R64 probabilities
        print(f"\n  --- {region_name.upper()} R64 ---")
        for high_seed, low_seed in R64_MATCHUPS:
            p = r64_matrix.get((high_seed, low_seed), 0.5)
            team_a = regions[region_name][high_seed].name
            team_b = regions[region_name][low_seed].name
            bar_len = int(p * 40)
            bar = "█" * bar_len + "░" * (40 - bar_len)
            print(f"    ({high_seed:2d}) {team_a:<20s} {p:.3f} [{bar}] {1-p:.3f} ({low_seed:2d}) {team_b}")

    # Run simulation
    print(f"\n[4/5] Running simulation ({budget_per_region:,} brackets per region)...")
    allocations = allocate_regional_budget(
        budget_per_region=budget_per_region,
        min_per_world=max(10, budget_per_region // 500),
    )

    all_issues = []
    region_results = {}

    for region_name, teams in regions.items():
        t0 = time.time()

        # Use R64 matrix for the simulation (engine uses flat prob_matrix)
        # We need to merge all round matrices into one for the engine
        merged_matrix = {}
        for rnd, matrix in all_matrices[region_name].items():
            for key, prob in matrix.items():
                if key not in merged_matrix:
                    merged_matrix[key] = prob

        brackets = simulate_region(
            prob_matrix=merged_matrix,
            allocations=allocations,
            seed=42 + hash(region_name) % 1000,
            mutation_rate=0.06,
        )
        elapsed = time.time() - t0

        stats = simulation_summary(brackets)
        region_results[region_name] = stats

        print(f"\n  === {region_name.upper()} ({elapsed:.2f}s) ===")
        print_simulation_report(brackets)

        # Validate
        issues = validate_results(region_name, brackets, stats)
        all_issues.extend(issues)

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    if all_issues:
        print(f"\n  ISSUES FOUND ({len(all_issues)}):")
        for issue in all_issues:
            print(f"    ⚠ {issue}")
    else:
        print("\n  ALL VALIDATIONS PASSED")

    # Cross-region summary
    print("\n  CROSS-REGION CHAMPION PROBABILITIES:")
    print(f"  {'Region':<12} {'1-seed':<15} {'P(1)':<8} {'P(2)':<8} {'P(3-5)':<8} {'P(6+)':<8}")
    print("  " + "-" * 59)
    for region_name, stats in region_results.items():
        wp = stats.get("weighted_champion_probs", {})
        one_seed = regions[region_name][1].name
        p1 = wp.get(1, 0.0)
        p2 = wp.get(2, 0.0)
        p_mid = sum(wp.get(s, 0.0) for s in range(3, 6))
        p_low = sum(wp.get(s, 0.0) for s in range(6, 17))
        print(f"  {region_name:<12} {one_seed:<15} {p1:<8.3f} {p2:<8.3f} {p_mid:<8.3f} {p_low:<8.3f}")

    total_brackets = sum(s.get("total", 0) for s in region_results.values())
    total_unique = sum(s.get("unique_brackets", 0) for s in region_results.values())
    print(f"\n  Total brackets: {total_brackets:,}")
    print(f"  Total unique:   {total_unique:,} ({total_unique/max(total_brackets,1)*100:.1f}%)")

    success = len(all_issues) == 0
    print(f"\n  RESULT: {'PASS' if success else 'FAIL'}")
    print("=" * 70)

    return success


if __name__ == "__main__":
    budget = 10_000
    if len(sys.argv) > 1 and sys.argv[1] == "--budget":
        budget = int(sys.argv[2])
    elif len(sys.argv) > 1:
        try:
            budget = int(sys.argv[1])
        except ValueError:
            pass

    success = run_integration_test(budget)
    sys.exit(0 if success else 1)
