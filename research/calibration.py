"""
Calibrate the logistic k parameter via grid search against historical data.

Uses seed-averaged power indices from the current year's field and
historical seed-vs-seed win rates (1985-2025) to find the k that
minimizes Brier Score.

Usage:
    python -m research.calibration --year 2026
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.constants import LOGISTIC_K_RANGE, TARGET_BRIER_SCORE
from db.connection import session_scope
from sqlalchemy import text


# =========================================================================
# Logistic function (duplicate-free import would be circular, so inline)
# =========================================================================

def _logistic_prob(pi_a: float, pi_b: float, k: float) -> float:
    """P(A wins) = 1 / (1 + 10^((pi_B - pi_A) / k))"""
    exponent = (pi_b - pi_a) / k
    return 1.0 / (1.0 + 10.0 ** exponent)


# =========================================================================
# Seed-averaged power indices
# =========================================================================

def _load_seed_avg_power(year: int) -> dict[int, float]:
    """Compute average power index per seed from current year's data.

    Returns {seed: avg_power_index} for seeds 1-16.
    """
    with session_scope() as session:
        rows = session.execute(text("""
            SELECT t.seed, AVG(ts.power_index) as avg_pi
            FROM teams t
            JOIN team_stats ts ON t.id = ts.team_id
            WHERE t.tournament_year = :year
              AND ts.tournament_year = :year
              AND ts.power_index IS NOT NULL
            GROUP BY t.seed
            ORDER BY t.seed
        """), {"year": year}).fetchall()

    return {int(row[0]): float(row[1]) for row in rows}


# =========================================================================
# Historical matchup extraction
# =========================================================================

def _extract_calibration_games(
    historical: dict[str, Any],
) -> list[tuple[int, int, int, int]]:
    """Extract (seed_higher, seed_lower, wins_higher, wins_lower) tuples.

    Uses R64 seed-vs-seed data (cleanest — fixed matchups every year)
    plus R32 specific matchup data for additional signal.
    """
    games: list[tuple[int, int, int, int]] = []

    # R64: clean seed-vs-seed matchups (1v16, 2v15, ..., 8v9)
    for key, data in historical.get("r64", {}).items():
        seeds = key.split("v")
        if len(seeds) != 2:
            continue
        seed_h, seed_l = int(seeds[0]), int(seeds[1])
        games.append((
            seed_h, seed_l,
            data["higher_seed_wins"], data["lower_seed_wins"],
        ))

    # R32: specific matchup records (e.g., 1v8, 1v9, 2v7, 2v10, ...)
    for key, data in historical.get("r32", {}).items():
        if key.startswith("_"):
            continue
        seeds = key.split("v")
        if len(seeds) != 2:
            continue
        seed_h, seed_l = int(seeds[0]), int(seeds[1])
        # Keys vary: "seed_1_wins" / "seed_2_wins" / etc. or "seed_X_wins"
        wins_key = f"seed_{seed_h}_wins"
        if wins_key not in data:
            continue
        wins_h = data[wins_key]
        wins_l = data["opponent_wins"]
        games.append((seed_h, seed_l, wins_h, wins_l))

    # S16: specific matchup records
    for key, data in historical.get("s16", {}).items():
        if key.startswith("_"):
            continue
        seeds = key.split("v")
        if len(seeds) != 2:
            continue
        seed_h, seed_l = int(seeds[0]), int(seeds[1])
        wins_key = f"seed_{seed_h}_wins"
        if wins_key not in data:
            continue
        wins_h = data[wins_key]
        wins_l = data["opponent_wins"]
        games.append((seed_h, seed_l, wins_h, wins_l))

    # E8: specific matchup records
    for key, data in historical.get("e8", {}).items():
        if key.startswith("_"):
            continue
        seeds = key.split("v")
        if len(seeds) != 2:
            continue
        seed_h, seed_l = int(seeds[0]), int(seeds[1])
        wins_key = f"seed_{seed_h}_wins"
        if wins_key not in data:
            continue
        wins_h = data[wins_key]
        wins_l = data["opponent_wins"]
        games.append((seed_h, seed_l, wins_h, wins_l))

    return games


# =========================================================================
# Brier score computation
# =========================================================================

def _compute_brier_score(
    k: float,
    seed_power: dict[int, float],
    games: list[tuple[int, int, int, int]],
) -> float:
    """Compute Brier Score for a candidate k value.

    For each historical matchup, expands into individual game outcomes:
    - Each win by higher seed = observation with outcome 1
    - Each win by lower seed = observation with outcome 0
    - Predicted probability = logistic(pi_higher, pi_lower, k)

    Brier Score = (1/N) * sum((predicted - outcome)^2)
    """
    total_sq_error = 0.0
    total_games = 0

    for seed_h, seed_l, wins_h, wins_l in games:
        pi_h = seed_power.get(seed_h)
        pi_l = seed_power.get(seed_l)
        if pi_h is None or pi_l is None:
            continue

        p_higher_wins = _logistic_prob(pi_h, pi_l, k)

        # Higher seed wins: outcome = 1, error = (p - 1)^2
        total_sq_error += wins_h * (p_higher_wins - 1.0) ** 2
        # Lower seed wins: outcome = 0, error = (p - 0)^2
        total_sq_error += wins_l * p_higher_wins ** 2

        total_games += wins_h + wins_l

    if total_games == 0:
        return 1.0

    return total_sq_error / total_games


# =========================================================================
# Grid search
# =========================================================================

def calibrate_k(
    year: int,
    k_min: float | None = None,
    k_max: float | None = None,
    step: float = 0.25,
) -> dict[str, Any]:
    """Run grid search over k values and return optimal k + diagnostics.

    Returns dict with: optimal_k, brier_score, all_results, diagnostics.
    """
    k_lo = k_min or LOGISTIC_K_RANGE[0]
    k_hi = k_max or LOGISTIC_K_RANGE[1]

    # Load seed-averaged power indices
    seed_power = _load_seed_avg_power(year)
    if len(seed_power) < 8:
        print(f"Only {len(seed_power)} seeds have power indices — need at least 8")
        return {"optimal_k": 15.0, "brier_score": 1.0, "error": "insufficient data"}

    # Load historical data
    historical_path = PROJECT_ROOT / "data" / "historical" / "seed_win_rates.json"
    if not historical_path.exists():
        print("Missing seed_win_rates.json")
        return {"optimal_k": 15.0, "brier_score": 1.0, "error": "missing historical data"}

    with open(historical_path) as f:
        historical = json.load(f)

    games = _extract_calibration_games(historical)
    total_observations = sum(w_h + w_l for _, _, w_h, w_l in games)

    print(f"\nCalibration data: {len(games)} matchup types, "
          f"{total_observations} total game observations")
    print(f"Seed power indices ({year}):")
    for seed in sorted(seed_power.keys()):
        print(f"  Seed {seed:2d}: PI = {seed_power[seed]:.2f}")

    # Grid search
    k_values = np.arange(k_lo, k_hi + step / 2, step)
    results: list[dict[str, float]] = []

    for k in k_values:
        brier = _compute_brier_score(float(k), seed_power, games)
        results.append({"k": float(k), "brier_score": brier})

    # Find optimal
    best = min(results, key=lambda r: r["brier_score"])
    optimal_k = best["k"]
    best_brier = best["brier_score"]

    # Fine-grained search around optimal (±2.0, step 0.05)
    fine_lo = max(k_lo, optimal_k - 2.0)
    fine_hi = min(k_hi, optimal_k + 2.0)
    fine_k_values = np.arange(fine_lo, fine_hi + 0.025, 0.05)

    for k in fine_k_values:
        brier = _compute_brier_score(float(k), seed_power, games)
        results.append({"k": float(k), "brier_score": brier})

    # Re-find optimal after fine search
    best = min(results, key=lambda r: r["brier_score"])
    optimal_k = best["k"]
    best_brier = best["brier_score"]

    # Print results
    print(f"\n{'='*70}")
    print(f" k Calibration Results (grid search)")
    print(f"{'='*70}")
    print(f" {'k':>8s}  {'Brier Score':>12s}  {'vs Target':>10s}")
    print(f" {'-'*8}  {'-'*12}  {'-'*10}")

    # Show coarse grid results
    coarse = [r for r in results if r["k"] % step < 0.01 or abs(r["k"] % step - step) < 0.01]
    coarse_sorted = sorted(set((r["k"], r["brier_score"]) for r in coarse))
    for k_val, brier in coarse_sorted:
        marker = " <-- BEST" if abs(k_val - optimal_k) < 0.01 else ""
        delta = brier - TARGET_BRIER_SCORE
        sign = "+" if delta > 0 else ""
        print(f" {k_val:8.2f}  {brier:12.6f}  {sign}{delta:10.6f}{marker}")

    print(f"\n Fine-tuned optimal: k = {optimal_k:.2f}, Brier = {best_brier:.6f}")
    meets_target = best_brier <= TARGET_BRIER_SCORE
    print(f" Target Brier ≤ {TARGET_BRIER_SCORE}: {'PASS' if meets_target else 'FAIL'}")

    # Diagnostic: show predicted vs actual for each R64 matchup
    print(f"\n{'='*70}")
    print(f" R64 Matchup Diagnostics (k = {optimal_k:.2f})")
    print(f"{'='*70}")
    print(f" {'Matchup':>8s}  {'Predicted':>10s}  {'Actual':>10s}  {'Error':>8s}  {'Games':>6s}")
    print(f" {'-'*8}  {'-'*10}  {'-'*10}  {'-'*8}  {'-'*6}")

    r64_games = [(s_h, s_l, w_h, w_l) for s_h, s_l, w_h, w_l in games
                 if (s_h + s_l) == 17]  # R64 matchups sum to 17
    for seed_h, seed_l, wins_h, wins_l in sorted(r64_games, key=lambda x: x[0]):
        pi_h = seed_power.get(seed_h, 50.0)
        pi_l = seed_power.get(seed_l, 50.0)
        predicted = _logistic_prob(pi_h, pi_l, optimal_k)
        total = wins_h + wins_l
        actual = wins_h / total if total > 0 else 0.5
        error = predicted - actual
        print(f" {seed_h:>2d}v{seed_l:<2d}    {predicted:10.4f}  {actual:10.4f}  "
              f"{error:+8.4f}  {total:6d}")

    return {
        "optimal_k": optimal_k,
        "brier_score": best_brier,
        "meets_target": meets_target,
        "total_observations": total_observations,
        "seed_power": seed_power,
        "all_results": sorted(results, key=lambda r: r["k"]),
    }


# =========================================================================
# Update constants
# =========================================================================

def update_k_in_constants(k: float) -> None:
    """Update LOGISTIC_K_INITIAL in config/constants.py with calibrated value."""
    constants_path = PROJECT_ROOT / "config" / "constants.py"
    content = constants_path.read_text()

    import re
    new_content = re.sub(
        r"LOGISTIC_K_INITIAL\s*=\s*[\d.]+",
        f"LOGISTIC_K_INITIAL = {k:.2f}",
        content,
    )

    if new_content != content:
        constants_path.write_text(new_content)
        print(f"\nUpdated LOGISTIC_K_INITIAL = {k:.2f} in config/constants.py")
    else:
        print(f"\nLOGISTIC_K_INITIAL already set to {k:.2f}")


# =========================================================================
# Main
# =========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate logistic k parameter")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--apply", action="store_true",
                        help="Update constants.py with optimal k")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass

    result = calibrate_k(args.year)

    if args.apply and "error" not in result:
        update_k_in_constants(result["optimal_k"])


if __name__ == "__main__":
    main()
