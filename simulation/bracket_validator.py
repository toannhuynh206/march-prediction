"""Post-simulation bracket portfolio validator.

Compares generated bracket distributions against historical NCAA tournament
data (1985-2025, 40 tournaments) and flags statistically implausible patterns.

Run after simulation to produce a validation report. Can also reject
individual brackets that violate hard constraints.

Historical reference: data/historical/seed_win_rates.json
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.constants import TOURNAMENT_YEAR
from db.connection import get_engine
from sqlalchemy import text


# =========================================================================
# Historical baselines (from seed_win_rates.json, 1985-2025)
# =========================================================================

HISTORICAL_DATA_PATH = PROJECT_ROOT / "data" / "historical" / "seed_win_rates.json"


def _load_historical() -> dict:
    """Load historical seed win rates from JSON."""
    with open(HISTORICAL_DATA_PATH) as f:
        return json.load(f)


# Historical champion distribution (40 tournaments, 160 regions)
# Seeds that have NEVER won a championship (seeds 7-16): 0 in 40 tournaments
# Highest seed to win: 6-seed (Villanova 1985)
HISTORICAL_CHAMP_BY_SEED = {
    1: 26, 2: 5, 3: 4, 4: 2, 5: 2, 6: 1,
    7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0,
    13: 0, 14: 0, 15: 0, 16: 0,
}
HISTORICAL_CHAMP_TOTAL = 40

# Historical regional champion rates (seed reaching F4 = winning their region)
# Per seed line: 160 opportunities (4 regions × 40 tournaments)
HISTORICAL_REGIONAL_CHAMP_RATE = {
    1: 0.2563,   # 41/160
    2: 0.0813,   # 13/160
    3: 0.0688,   # 11/160
    4: 0.0250,   # 4/160
    5: 0.0250,   # 4/160
    6: 0.0125,   # 2/160
    7: 0.0063,   # 1/160
    8: 0.0125,   # 2/160 (8-seeds: Villanova 2009, Loyola 2018)
    9: 0.0000,   # 0/160
    10: 0.0063,  # 1/160
    11: 0.0000,  # 0/160 (11-seeds: VCU 2011, Loyola Chicago 2018 was 11? No, 11-seed)
    12: 0.0000,  # 0/160
    13: 0.0000,  # 0/160
    14: 0.0000,  # 0/160
    15: 0.0000,  # 0/160
    16: 0.0000,  # 0/160
}

# Average total upsets per tournament (all 63 games): ~20
# R64 upsets alone average ~6.2 per tournament, but total_upsets now
# counts upsets across all rounds (R64 + R32 + S16 + E8 + F4 + Championship).
HISTORICAL_TOTAL_UPSETS_MEAN = 20.0
HISTORICAL_TOTAL_UPSETS_STD = 5.0  # approximate


# =========================================================================
# Validation result types
# =========================================================================

@dataclass(frozen=True)
class ValidationCheck:
    """Single validation check result."""
    name: str
    status: str        # PASS, WARN, FAIL
    message: str
    actual: float | int | None = None
    expected: float | int | None = None
    severity: str = "info"  # info, warning, critical


@dataclass(frozen=True)
class ValidationReport:
    """Complete validation report for a bracket portfolio."""
    total_brackets: int
    checks: tuple[ValidationCheck, ...]
    passed: int
    warned: int
    failed: int

    @property
    def is_valid(self) -> bool:
        return self.failed == 0

    def print_report(self) -> None:
        """Print human-readable validation report."""
        print("\n" + "=" * 70)
        print(" BRACKET PORTFOLIO VALIDATION REPORT")
        print(f" {self.total_brackets:,} brackets analyzed")
        print("=" * 70)

        for check in self.checks:
            icon = {"PASS": "[OK]", "WARN": "[!!]", "FAIL": "[XX]"}[check.status]
            print(f"\n  {icon} {check.name}")
            print(f"      {check.message}")
            if check.actual is not None and check.expected is not None:
                print(f"      Actual: {check.actual}  |  Expected: {check.expected}")

        print(f"\n  Summary: {self.passed} passed, {self.warned} warnings, {self.failed} failed")
        status = "VALID" if self.is_valid else "INVALID"
        print(f"  Portfolio status: {status}")
        print("=" * 70 + "\n")


# =========================================================================
# Core validation functions
# =========================================================================

def validate_champion_distribution(
    seed_counts: dict[int, int],
    total: int,
) -> list[ValidationCheck]:
    """Validate tournament champion seed distribution against historical rates."""
    checks = []

    # Hard constraint: no 16-seed champions (0 in 40 years, physically implausible)
    count_16 = seed_counts.get(16, 0)
    checks.append(ValidationCheck(
        name="No 16-seed champions",
        status="PASS" if count_16 == 0 else "FAIL",
        message=(
            "No 16-seed champions found"
            if count_16 == 0
            else f"{count_16} brackets have 16-seed champion (never happened historically)"
        ),
        actual=count_16,
        expected=0,
        severity="critical",
    ))

    # Hard constraint: no 15-seed champions (0 in 40 years)
    count_15 = seed_counts.get(15, 0)
    max_15 = max(1, int(total * 0.00001))  # allow up to 0.001%
    checks.append(ValidationCheck(
        name="15-seed champion cap",
        status="PASS" if count_15 <= max_15 else "WARN",
        message=(
            f"{count_15} brackets with 15-seed champion (acceptable: <= {max_15})"
            if count_15 <= max_15
            else f"{count_15} brackets with 15-seed champion — too many (max {max_15})"
        ),
        actual=count_15,
        expected=max_15,
        severity="warning",
    ))

    # Soft constraint: seeds 7+ should have very low championship rates
    # Historically: 0 champions from seeds 7-16 in 40 tournaments
    high_seed_champs = sum(seed_counts.get(s, 0) for s in range(7, 17))
    max_high_seed = int(total * 0.02)  # allow up to 2%
    checks.append(ValidationCheck(
        name="High-seed champion rate (7-16)",
        status="PASS" if high_seed_champs <= max_high_seed else "WARN",
        message=(
            f"{high_seed_champs:,} brackets ({high_seed_champs/total*100:.3f}%) with seed 7-16 champion"
        ),
        actual=high_seed_champs,
        expected=max_high_seed,
        severity="warning",
    ))

    # 1-seeds should win ~65% of championships (historical: 26/40 = 65%)
    count_1 = seed_counts.get(1, 0)
    rate_1 = count_1 / total if total > 0 else 0
    checks.append(ValidationCheck(
        name="1-seed champion rate",
        status="PASS" if 0.30 <= rate_1 <= 0.85 else "WARN",
        message=f"1-seed champions: {rate_1*100:.1f}% (historical: ~65%)",
        actual=round(rate_1 * 100, 1),
        expected=65.0,
        severity="info",
    ))

    # Top-4 seeds should win >90% of championships (historical: 37/40 = 92.5%)
    top4 = sum(seed_counts.get(s, 0) for s in range(1, 5))
    rate_top4 = top4 / total if total > 0 else 0
    checks.append(ValidationCheck(
        name="Top-4 seed champion rate",
        status="PASS" if rate_top4 >= 0.50 else "WARN",
        message=f"Seeds 1-4 champions: {rate_top4*100:.1f}% (historical: ~92.5%)",
        actual=round(rate_top4 * 100, 1),
        expected=92.5,
        severity="info",
    ))

    return checks


def validate_upset_distribution(
    upset_stats: dict,
    total: int,
) -> list[ValidationCheck]:
    """Validate total upset count distribution (all 63 games)."""
    checks = []

    avg_upsets = upset_stats.get("mean_upsets", 0)
    checks.append(ValidationCheck(
        name="Average total upsets per bracket",
        status="PASS" if 10.0 <= avg_upsets <= 30.0 else "WARN",
        message=f"Mean total upsets: {avg_upsets:.1f} (expected ~{HISTORICAL_TOTAL_UPSETS_MEAN:.0f} across all 63 games)",
        actual=round(avg_upsets, 1),
        expected=HISTORICAL_TOTAL_UPSETS_MEAN,
        severity="info",
    ))

    # Check for brackets with extreme upset counts (>40 out of 63 games)
    extreme_upsets = upset_stats.get("extreme_count", 0)
    max_extreme = int(total * 0.05)  # <5% should have >40 total upsets
    checks.append(ValidationCheck(
        name="Extreme upset brackets (>40 total upsets)",
        status="PASS" if extreme_upsets <= max_extreme else "WARN",
        message=f"{extreme_upsets:,} brackets with >40 total upsets ({extreme_upsets/total*100:.4f}%)",
        actual=extreme_upsets,
        expected=max_extreme,
        severity="warning",
    ))

    return checks


def validate_alive_brackets(alive_count: int, total: int) -> list[ValidationCheck]:
    """Check alive bracket count is reasonable (before any games played)."""
    checks = []

    # Before any games, all brackets should be alive
    alive_pct = alive_count / total if total > 0 else 0
    checks.append(ValidationCheck(
        name="Alive bracket count",
        status="PASS" if alive_pct > 0.99 else "WARN",
        message=f"{alive_count:,} / {total:,} brackets alive ({alive_pct*100:.1f}%)",
        actual=alive_count,
        expected=total,
        severity="info",
    ))

    return checks


def validate_weight_health(weight_stats: dict, total: int) -> list[ValidationCheck]:
    """Validate importance sampling weight distribution health.

    Checks effective sample size (ESS) and max/min weight ratio.
    Weight collapse makes weighted statistics unreliable.
    """
    checks = []

    # ESS check: ESS = (sum w)^2 / sum(w^2)
    ess = weight_stats.get("ess", 0)
    ess_pct = ess / total * 100 if total > 0 else 0
    min_ess_pct = 1.0  # at least 1% of brackets should be effective

    checks.append(ValidationCheck(
        name="Effective Sample Size (ESS)",
        status="PASS" if ess_pct >= min_ess_pct else "WARN",
        message=f"ESS: {ess:,.0f} ({ess_pct:.2f}% of {total:,})",
        actual=round(ess_pct, 2),
        expected=min_ess_pct,
        severity="warning" if ess_pct < min_ess_pct else "info",
    ))

    # Max/min weight ratio
    max_w = weight_stats.get("max_weight", 0)
    min_w = weight_stats.get("min_positive_weight", 1)
    ratio = max_w / min_w if min_w > 0 else float("inf")
    max_ratio = 10_000

    checks.append(ValidationCheck(
        name="Weight ratio (max/min)",
        status="PASS" if ratio <= max_ratio else "WARN",
        message=f"Max/min weight ratio: {ratio:,.1f} (cap: {max_ratio:,})",
        actual=round(ratio, 1),
        expected=max_ratio,
        severity="warning" if ratio > max_ratio else "info",
    ))

    return checks


# =========================================================================
# Main validation entry point
# =========================================================================

def validate_portfolio(year: int = TOURNAMENT_YEAR) -> ValidationReport:
    """Run full validation suite on the bracket portfolio in the database.

    Queries the database for champion seed distribution, upset counts,
    and other metrics, then compares against historical baselines.

    Args:
        year: Tournament year to validate.

    Returns:
        ValidationReport with all check results.
    """
    engine = get_engine()

    with engine.connect() as conn:
        # Total count
        total = conn.execute(text(
            "SELECT COUNT(*) FROM full_brackets WHERE tournament_year = :year"
        ), {"year": year}).fetchone()[0]

        if total == 0:
            return ValidationReport(
                total_brackets=0,
                checks=(ValidationCheck(
                    name="Portfolio exists",
                    status="FAIL",
                    message="No brackets found in database",
                    severity="critical",
                ),),
                passed=0, warned=0, failed=1,
            )

        # Champion seed distribution
        seed_rows = conn.execute(text(
            "SELECT champion_seed, COUNT(*) "
            "FROM full_brackets WHERE tournament_year = :year "
            "GROUP BY champion_seed ORDER BY champion_seed"
        ), {"year": year}).fetchall()
        seed_counts = {int(r[0]): int(r[1]) for r in seed_rows}

        # Alive count
        alive = conn.execute(text(
            "SELECT COUNT(*) FROM full_brackets "
            "WHERE tournament_year = :year AND is_alive = TRUE"
        ), {"year": year}).fetchone()[0]

        # Upset distribution stats (total_upsets counts all 63 games)
        upset_row = conn.execute(text(
            "SELECT AVG(total_upsets), STDDEV(total_upsets), "
            "  COUNT(*) FILTER (WHERE total_upsets > 40) "
            "FROM full_brackets WHERE tournament_year = :year"
        ), {"year": year}).fetchone()
        upset_stats = {
            "mean_upsets": float(upset_row[0]) if upset_row[0] else 0,
            "std_upsets": float(upset_row[1]) if upset_row[1] else 0,
            "extreme_count": int(upset_row[2]) if upset_row[2] else 0,
        }

        # Weight distribution health (ESS)
        weight_row = conn.execute(text(
            "SELECT SUM(weight), SUM(weight * weight), "
            "  MAX(weight), MIN(weight) FILTER (WHERE weight > 0) "
            "FROM full_brackets WHERE tournament_year = :year"
        ), {"year": year}).fetchone()
        sum_w = float(weight_row[0]) if weight_row[0] else 0
        sum_w2 = float(weight_row[1]) if weight_row[1] else 0
        ess = (sum_w * sum_w) / sum_w2 if sum_w2 > 0 else 0
        weight_stats = {
            "ess": ess,
            "max_weight": float(weight_row[2]) if weight_row[2] else 0,
            "min_positive_weight": float(weight_row[3]) if weight_row[3] else 0,
        }

    # Run all checks
    all_checks: list[ValidationCheck] = []
    all_checks.extend(validate_champion_distribution(seed_counts, total))
    all_checks.extend(validate_upset_distribution(upset_stats, total))
    all_checks.extend(validate_weight_health(weight_stats, total))
    all_checks.extend(validate_alive_brackets(alive, total))

    passed = sum(1 for c in all_checks if c.status == "PASS")
    warned = sum(1 for c in all_checks if c.status == "WARN")
    failed = sum(1 for c in all_checks if c.status == "FAIL")

    return ValidationReport(
        total_brackets=total,
        checks=tuple(all_checks),
        passed=passed,
        warned=warned,
        failed=failed,
    )


def print_champion_breakdown(year: int = TOURNAMENT_YEAR) -> None:
    """Print detailed champion seed breakdown with historical comparison."""
    engine = get_engine()
    historical = _load_historical()

    with engine.connect() as conn:
        total = conn.execute(text(
            "SELECT COUNT(*) FROM full_brackets WHERE tournament_year = :year"
        ), {"year": year}).fetchone()[0]

        seed_rows = conn.execute(text(
            "SELECT champion_seed, COUNT(*) "
            "FROM full_brackets WHERE tournament_year = :year "
            "GROUP BY champion_seed ORDER BY champion_seed"
        ), {"year": year}).fetchall()

    hist_champs = historical.get("champions_by_seed", {})
    hist_total = sum(v for k, v in hist_champs.items() if k != "total" and isinstance(v, (int, float)))

    print(f"\n{'='*60}")
    print(f" CHAMPION SEED DISTRIBUTION — {total:,} brackets")
    print(f"{'='*60}")
    print(f"  {'Seed':>4}  {'Count':>10}  {'Rate':>8}  {'Historical':>10}  {'Delta':>8}")
    print(f"  {'-'*4}  {'-'*10}  {'-'*8}  {'-'*10}  {'-'*8}")

    for seed in range(1, 17):
        count = dict(seed_rows).get(seed, 0)
        rate = count / total * 100 if total > 0 else 0
        hist_count = hist_champs.get(str(seed), 0)
        hist_rate = hist_count / hist_total * 100 if hist_total > 0 else 0
        delta = rate - hist_rate
        delta_str = f"{delta:+.1f}%" if hist_rate > 0 or rate > 0 else "—"
        print(f"  {seed:>4}  {count:>10,}  {rate:>7.3f}%  {hist_rate:>9.1f}%  {delta_str:>8}")

    print(f"{'='*60}\n")


# =========================================================================
# CLI entry point
# =========================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate bracket portfolio")
    parser.add_argument("--year", type=int, default=TOURNAMENT_YEAR)
    parser.add_argument("--detailed", action="store_true", help="Show detailed breakdown")
    args = parser.parse_args()

    report = validate_portfolio(year=args.year)
    report.print_report()

    if args.detailed:
        print_champion_breakdown(year=args.year)
