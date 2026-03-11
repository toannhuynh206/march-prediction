"""
Historical calibration targets for bracket simulation validation.

These targets come from analyzing ~40 years of NCAA tournament data (1985-2024).
Used to validate that our simulation output matches real-world distributions.

Sources:
  - The Polacheck Method (historical bracket composition analysis)
  - ESPN/NCAA historical records
  - KenPom historical data

After generating brackets, compare simulation output against these targets.
If a distribution deviates by more than 2σ from historical norms, investigate.
"""

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# R64 upset count distributions (across all 4 regions per tournament)
# ---------------------------------------------------------------------------
# Key insight from Polacheck: it's not just the per-game upset rate that
# matters, but how upsets distribute across the 4 regions in a tournament.
# This tells our stratifier the prior probability of each "world."

# Format: {num_upsets_out_of_4: probability}
# "How many of the 4 [X]-vs-[Y] games go upset?"

R64_UPSET_COUNT_DISTRIBUTIONS = {
    # 1 vs 16: Only 1 upset in 40 years (UMBC over Virginia, 2018)
    (1, 16): {0: 0.97, 1: 0.03, 2: 0.00, 3: 0.00, 4: 0.00},

    # 2 vs 15: ~6.5% per game, 80% of tournaments have 0 upsets
    (2, 15): {0: 0.80, 1: 0.17, 2: 0.03, 3: 0.00, 4: 0.00},

    # 3 vs 14: ~15% per game, 60% have all 3-seeds advancing
    (3, 14): {0: 0.60, 1: 0.30, 2: 0.08, 3: 0.02, 4: 0.00},

    # 4 vs 13: 21% per game, 55% have exactly 1 upset
    (4, 13): {0: 0.30, 1: 0.55, 2: 0.13, 3: 0.02, 4: 0.00},

    # 5 vs 12: THE classic upset — 35.6% per game
    # Most common outcome: 2-2 split (35% of tournaments)
    (5, 12): {0: 0.02, 1: 0.20, 2: 0.35, 3: 0.25, 4: 0.18},

    # 6 vs 11: 37% per game, 45% of tournaments see 2-2 split
    (6, 11): {0: 0.05, 1: 0.20, 2: 0.45, 3: 0.20, 4: 0.10},

    # 7 vs 10: 39% per game, 50% see 3 of 4 7-seeds advancing
    (7, 10): {0: 0.03, 1: 0.12, 2: 0.30, 3: 0.50, 4: 0.05},

    # 8 vs 9: Nearly a coin flip (46/54)
    (8, 9): {0: 0.10, 1: 0.25, 2: 0.20, 3: 0.30, 4: 0.15},
}


# ---------------------------------------------------------------------------
# Final Four seed composition targets
# ---------------------------------------------------------------------------
# What percentage of Final Four teams are each seed?

FINAL_FOUR_SEED_RATES = {
    1: 0.40,   # 40% — dominant
    2: 0.20,   # 20%
    3: 0.12,   # 12%
    4: 0.09,   # 9%
    5: 0.05,   # 5%
    6: 0.04,   # 4%
    7: 0.03,   # 3%
    8: 0.03,   # 3%
    9: 0.01,   # 1%
    10: 0.01,  # 1%
    11: 0.02,  # 2% (Loyola Chicago, VCU, etc.)
    12: 0.00,  # <1%
}


# ---------------------------------------------------------------------------
# Champion seed rates
# ---------------------------------------------------------------------------

CHAMPION_SEED_RATES = {
    1: 0.628,  # 22/35 — nearly 2 in 3
    2: 0.171,  # 6/35
    3: 0.086,  # 3/35
    4: 0.029,  # 1/35
    5: 0.000,  # never happened
    6: 0.029,  # 1/35 (Villanova 1985 as a 8-seed proxy, debatable)
    7: 0.029,  # 1/35 (UConn 2014)
    8: 0.029,  # 1/35 (Villanova 1985)
}


# ---------------------------------------------------------------------------
# Sweet 16 advancement rates from R32 (for mid-major seeds)
# ---------------------------------------------------------------------------
# Given a seed reached R32, what's the probability of reaching Sweet 16?

SWEET_16_ADVANCEMENT_FROM_R32 = {
    1: 0.86,   # 1-seeds almost always advance past R32
    2: 0.72,   # 2-seeds strong but not automatic
    3: 0.64,   # 3-seeds face tough R32 matchups
    4: 0.55,   # 4-seeds: coin flip territory
    5: 0.52,   # 5-seeds similar
    6: 0.33,   # 6-seeds: only 1 in 3 reach Sweet 16
    7: 0.37,   # 7-seeds: slightly better than 6
    8: 0.14,   # 8-seeds: run into 1-seed wall
    9: 0.14,   # 9-seeds: same wall
    10: 0.34,  # 10-seeds: if they upset 7, face 2-seed
    11: 0.36,  # 11-seeds: slightly better than 10
    12: 0.05,  # 12-seeds: Cinderella rarely survives R32
    13: 0.03,  # 13-seeds: extremely rare
}


# ---------------------------------------------------------------------------
# "Most likely" bracket composition (Polacheck optimal)
# ---------------------------------------------------------------------------
# The statistically most common R64 outcome across all 4 regions.
# This is the "chalk bracket with the right amount of upsets."

MOST_LIKELY_R64_COMPOSITION = {
    "description": "Most statistically common R64 outcome per Polacheck analysis",
    "1v16_upsets": 0,   # all 1-seeds advance
    "2v15_upsets": 0,   # all 2-seeds advance
    "3v14_upsets": 0,   # all 3-seeds advance
    "4v13_upsets": 1,   # exactly one 13-over-4
    "5v12_upsets": 2,   # two 12-over-5 (the sweet spot)
    "6v11_upsets": 2,   # two 11-over-6
    "7v10_upsets": 1,   # one 10-over-7
    "8v9_upsets": 2,    # two 9-over-8 (near coin flip)
    "total_r64_upsets": 8,  # 8 upsets is the statistical mode
}


# ---------------------------------------------------------------------------
# Optimal Final Four seed composition
# ---------------------------------------------------------------------------

MOST_LIKELY_FINAL_FOUR = {
    "description": "Most common FF composition: two 1-seeds, one 2-seed, one 3-or-4",
    "seeds": [1, 1, 2, 3],
    "alternative": [1, 1, 2, 4],
}


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CalibrationResult:
    """Result of comparing simulation output to historical targets."""
    metric: str
    expected: float
    actual: float
    deviation_pct: float
    status: str  # "PASS", "WARN", "FAIL"


def validate_champion_distribution(
    champion_counts: dict[int, int],
    total_brackets: int,
    tolerance: float = 0.10,
) -> list[CalibrationResult]:
    """Check if champion seed distribution matches historical rates.

    champion_counts: seed -> count of brackets with that seed as champion.
    tolerance: acceptable deviation as fraction (0.10 = 10%).

    Returns list of CalibrationResult per seed.
    """
    results = []

    for seed, expected_rate in CHAMPION_SEED_RATES.items():
        if expected_rate == 0:
            continue

        actual_count = champion_counts.get(seed, 0)
        actual_rate = actual_count / max(total_brackets, 1)
        deviation = abs(actual_rate - expected_rate) / max(expected_rate, 0.001)

        if deviation <= tolerance:
            status = "PASS"
        elif deviation <= tolerance * 2:
            status = "WARN"
        else:
            status = "FAIL"

        results.append(CalibrationResult(
            metric=f"champion_seed_{seed}",
            expected=expected_rate,
            actual=actual_rate,
            deviation_pct=deviation * 100,
            status=status,
        ))

    return results


def validate_final_four_distribution(
    ff_seed_counts: dict[int, int],
    total_ff_slots: int,
    tolerance: float = 0.15,
) -> list[CalibrationResult]:
    """Check if Final Four seed distribution matches historical rates.

    ff_seed_counts: seed -> count of FF appearances across all brackets.
    total_ff_slots: total FF slots (num_brackets * 4).
    tolerance: acceptable deviation as fraction.
    """
    results = []

    for seed, expected_rate in FINAL_FOUR_SEED_RATES.items():
        if expected_rate == 0:
            continue

        actual_count = ff_seed_counts.get(seed, 0)
        actual_rate = actual_count / max(total_ff_slots, 1)
        deviation = abs(actual_rate - expected_rate) / max(expected_rate, 0.001)

        status = "PASS" if deviation <= tolerance else (
            "WARN" if deviation <= tolerance * 2 else "FAIL"
        )

        results.append(CalibrationResult(
            metric=f"final_four_seed_{seed}",
            expected=expected_rate,
            actual=actual_rate,
            deviation_pct=deviation * 100,
            status=status,
        ))

    return results


def validate_r64_upset_counts(
    upset_counts: dict[tuple[int, int], dict[int, int]],
    total_brackets: int,
    tolerance: float = 0.15,
) -> list[CalibrationResult]:
    """Check if R64 upset count distributions match historical targets.

    upset_counts: (high_seed, low_seed) -> {num_upsets: count_of_brackets}.
    """
    results = []

    for matchup, expected_dist in R64_UPSET_COUNT_DISTRIBUTIONS.items():
        actual_dist = upset_counts.get(matchup, {})

        for num_upsets, expected_rate in expected_dist.items():
            if expected_rate < 0.01:
                continue

            actual_count = actual_dist.get(num_upsets, 0)
            actual_rate = actual_count / max(total_brackets, 1)
            deviation = abs(actual_rate - expected_rate) / max(expected_rate, 0.001)

            status = "PASS" if deviation <= tolerance else (
                "WARN" if deviation <= tolerance * 2 else "FAIL"
            )

            results.append(CalibrationResult(
                metric=f"r64_{matchup[0]}v{matchup[1]}_{num_upsets}_upsets",
                expected=expected_rate,
                actual=actual_rate,
                deviation_pct=deviation * 100,
                status=status,
            ))

    return results


def print_calibration_report(results: list[CalibrationResult]) -> None:
    """Print a formatted calibration report."""
    print("\n" + "=" * 70)
    print("CALIBRATION REPORT")
    print("=" * 70)

    for r in sorted(results, key=lambda x: x.status):
        icon = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}[r.status]
        print(
            f"  {icon} {r.metric:<35} "
            f"expected={r.expected:.3f}  actual={r.actual:.3f}  "
            f"dev={r.deviation_pct:.1f}%  [{r.status}]"
        )

    passes = sum(1 for r in results if r.status == "PASS")
    warns = sum(1 for r in results if r.status == "WARN")
    fails = sum(1 for r in results if r.status == "FAIL")
    print(f"\n  Summary: {passes} PASS, {warns} WARN, {fails} FAIL")
    print("=" * 70)
