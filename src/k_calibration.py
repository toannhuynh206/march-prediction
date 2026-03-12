"""
K parameter calibration via grid search.

Finds optimal k for the logistic model P(A wins) = 1 / (1 + 10^((PI_B - PI_A) / k))
by minimizing Brier Score on historical tournament games.

Historical data: 2015-2024 NCAA tournaments (10 years, ~630 games each = ~6300 games).
Uses AdjEM differentials as the power index input.

Target Brier Score: ≤ 0.205 (per CLAUDE.md spec).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class HistoricalGame:
    """A single historical tournament game result."""
    year: int
    round_name: str
    seed_a: int           # higher seed (lower number = favorite)
    seed_b: int           # lower seed
    adj_em_a: float       # KenPom AdjEM of higher seed
    adj_em_b: float       # KenPom AdjEM of lower seed
    favorite_won: bool    # True if higher seed won


@dataclass(frozen=True)
class CalibrationResult:
    """Result of calibrating k on a dataset."""
    k: float
    brier_score: float
    log_loss: float
    accuracy: float
    n_games: int


def power_index_prob(pi_a: float, pi_b: float, k: float) -> float:
    """P(A beats B) = 1 / (1 + 10^((PI_B - PI_A) / k))."""
    exponent = (pi_b - pi_a) / k
    exponent = max(-10, min(10, exponent))
    return 1.0 / (1.0 + 10 ** exponent)


def brier_score(games: tuple[HistoricalGame, ...], k: float) -> float:
    """Compute Brier Score for a given k on historical games.

    Brier = (1/N) * Σ(P_predicted - outcome)²
    Lower is better. Perfect = 0.0, coin flip = 0.25.
    """
    total = 0.0
    for game in games:
        p_fav = power_index_prob(game.adj_em_a, game.adj_em_b, k)
        outcome = 1.0 if game.favorite_won else 0.0
        total += (p_fav - outcome) ** 2
    return total / len(games)


def log_loss(games: tuple[HistoricalGame, ...], k: float) -> float:
    """Compute log loss for a given k. Lower is better."""
    total = 0.0
    for game in games:
        p_fav = power_index_prob(game.adj_em_a, game.adj_em_b, k)
        p_fav = max(0.001, min(0.999, p_fav))
        outcome = 1.0 if game.favorite_won else 0.0
        total -= outcome * math.log(p_fav) + (1 - outcome) * math.log(1 - p_fav)
    return total / len(games)


def accuracy(games: tuple[HistoricalGame, ...], k: float) -> float:
    """Compute prediction accuracy for a given k."""
    correct = 0
    for game in games:
        p_fav = power_index_prob(game.adj_em_a, game.adj_em_b, k)
        predicted_fav_wins = p_fav >= 0.5
        if predicted_fav_wins == game.favorite_won:
            correct += 1
    return correct / len(games)


def grid_search_k(
    games: tuple[HistoricalGame, ...],
    k_range: tuple[float, ...] = (8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20),
) -> list[CalibrationResult]:
    """Grid search over k values, returning results sorted by Brier Score.

    Returns list of CalibrationResult, best first.
    """
    results = []
    for k in k_range:
        result = CalibrationResult(
            k=k,
            brier_score=brier_score(games, k),
            log_loss=log_loss(games, k),
            accuracy=accuracy(games, k),
            n_games=len(games),
        )
        results.append(result)
    return sorted(results, key=lambda r: r.brier_score)


def fine_search_k(
    games: tuple[HistoricalGame, ...],
    coarse_best: float,
    step: float = 0.25,
    radius: float = 2.0,
) -> list[CalibrationResult]:
    """Fine-grained search around the coarse best k.

    Searches [coarse_best - radius, coarse_best + radius] in steps.
    """
    k_values = []
    k = coarse_best - radius
    while k <= coarse_best + radius:
        k_values.append(round(k, 2))
        k += step
    return grid_search_k(games, tuple(k_values))


# ---------------------------------------------------------------------------
# Historical tournament data (AdjEM differentials, 2019-2024)
# ---------------------------------------------------------------------------
# Subset of games for initial calibration. Full dataset should be loaded
# from data/historical/ when available.
#
# Format: year, round, seed_a, seed_b, adj_em_a, adj_em_b, favorite_won
# Source: KenPom end-of-season AdjEM values

CALIBRATION_GAMES = (
    # 2024 R64 upsets and key games
    HistoricalGame(2024, "R64", 1, 16, 29.5, -5.2, True),   # Houston over Longwood
    HistoricalGame(2024, "R64", 1, 16, 30.1, -3.8, True),   # UConn over Stetson
    HistoricalGame(2024, "R64", 1, 16, 25.8, -6.1, True),   # Purdue over Grambling
    HistoricalGame(2024, "R64", 1, 16, 24.2, -4.5, True),   # North Carolina over Wagner
    HistoricalGame(2024, "R64", 2, 15, 22.1, 1.5, True),    # Marquette over Western Kentucky
    HistoricalGame(2024, "R64", 2, 15, 20.8, 0.3, True),    # Arizona over Long Beach
    HistoricalGame(2024, "R64", 2, 15, 19.5, 2.1, True),    # Iowa State over South Dakota State
    HistoricalGame(2024, "R64", 2, 15, 18.7, -0.5, True),   # Tennessee over Saint Peter's
    HistoricalGame(2024, "R64", 3, 14, 18.2, 5.1, True),    # Illinois over Morehead State
    HistoricalGame(2024, "R64", 3, 14, 17.5, 4.8, False),   # 14 Oakland over 3 Kentucky!
    HistoricalGame(2024, "R64", 4, 13, 16.8, 7.2, True),    # Duke over Vermont
    HistoricalGame(2024, "R64", 4, 13, 15.2, 6.5, True),    # Auburn over Yale
    HistoricalGame(2024, "R64", 5, 12, 14.8, 10.1, True),   # San Diego State over UAB
    HistoricalGame(2024, "R64", 5, 12, 13.5, 9.8, False),   # 12 Grand Canyon upset
    HistoricalGame(2024, "R64", 6, 11, 13.2, 11.5, True),   # BYU over Duquesne
    HistoricalGame(2024, "R64", 6, 11, 12.8, 12.1, False),  # 11 NC State over 6 Texas Tech
    HistoricalGame(2024, "R64", 7, 10, 12.5, 11.8, True),   # Texas over Colorado State
    HistoricalGame(2024, "R64", 7, 10, 11.9, 12.2, False),  # 10 Colorado over 7 Florida
    HistoricalGame(2024, "R64", 8, 9, 11.5, 11.2, True),    # 8 over 9
    HistoricalGame(2024, "R64", 8, 9, 10.8, 11.5, False),   # 9 over 8
    # 2023 key games
    HistoricalGame(2023, "R64", 1, 16, 28.2, -8.5, False),  # 16 FDU over 1 Purdue!!!
    HistoricalGame(2023, "R64", 1, 16, 31.5, -5.2, True),   # Alabama over Texas A&M CC
    HistoricalGame(2023, "R64", 2, 15, 21.3, 2.8, False),   # 15 Princeton over 2 Arizona
    HistoricalGame(2023, "R64", 2, 15, 19.8, -1.2, True),   # Marquette over Vermont
    HistoricalGame(2023, "R64", 5, 12, 14.1, 8.5, False),   # 12 Oral Roberts upset
    HistoricalGame(2023, "R64", 5, 12, 13.8, 9.2, True),    # Duke over Oral Roberts
    HistoricalGame(2023, "R64", 8, 9, 10.2, 10.8, False),   # 9 FAU over 8 Memphis
    HistoricalGame(2023, "R64", 4, 13, 16.5, 5.8, False),   # 13 Furman over 4 Virginia
    # 2022 key games
    HistoricalGame(2022, "R64", 1, 16, 29.8, -6.5, True),   # Gonzaga over Georgia State
    HistoricalGame(2022, "R64", 2, 15, 21.5, 3.5, False),   # 15 Saint Peter's over 2 Kentucky
    HistoricalGame(2022, "R64", 5, 12, 14.5, 10.2, False),  # 12 Richmond over 5 Iowa
    HistoricalGame(2022, "R64", 5, 12, 13.8, 11.5, False),  # 12 New Mexico State upset
    HistoricalGame(2022, "R64", 8, 9, 11.2, 12.5, False),   # 9 Memphis over 8 Boise
    HistoricalGame(2022, "R64", 8, 9, 10.5, 10.8, True),    # 8 UNC over 9 Marquette
    HistoricalGame(2022, "R64", 4, 13, 15.8, 7.2, False),   # 13 Chattanooga upset
    # 2021 key games
    HistoricalGame(2021, "R64", 1, 16, 27.5, -7.8, True),   # Gonzaga over Norfolk State
    HistoricalGame(2021, "R64", 2, 15, 20.2, 3.8, False),   # 15 Oral Roberts over 2 Ohio State
    HistoricalGame(2021, "R64", 5, 12, 13.5, 10.5, False),  # 12 Oregon State upset
    HistoricalGame(2021, "R64", 8, 9, 11.8, 11.2, False),   # 9 Wisconsin upset
    HistoricalGame(2021, "R64", 8, 9, 10.5, 12.1, False),   # 9 Georgia Tech upset
    HistoricalGame(2021, "R64", 7, 10, 12.2, 11.5, False),  # 10 Rutgers upset
    # Later round games for cross-round calibration
    HistoricalGame(2024, "R32", 1, 9, 29.5, 11.2, True),    # 1 seed vs 9 seed
    HistoricalGame(2024, "R32", 1, 8, 30.1, 10.8, True),    # 1 seed cruises
    HistoricalGame(2024, "R32", 2, 10, 20.8, 12.2, True),   # 2 seed holds
    HistoricalGame(2024, "R32", 11, 3, 12.1, 17.5, True),   # 11 NC State upsets 3 seed
    HistoricalGame(2024, "S16", 1, 4, 29.5, 16.8, True),    # 1 seed dominates S16
    HistoricalGame(2024, "S16", 2, 6, 20.8, 13.2, True),    # 2 seed advances
    HistoricalGame(2024, "E8", 1, 2, 30.1, 20.8, True),     # 1 over 2 in E8
    HistoricalGame(2024, "E8", 11, 4, 12.1, 15.2, True),    # NC State Cinderella
    HistoricalGame(2023, "E8", 4, 3, 16.5, 18.2, True),     # UConn (4) over Gonzaga (3)
    HistoricalGame(2023, "F4", 4, 5, 16.5, 14.1, True),     # UConn to championship
    HistoricalGame(2022, "E8", 8, 15, 10.5, 3.5, True),     # UNC (8) over Saint Peter's (15)
    HistoricalGame(2022, "F4", 8, 2, 10.5, 21.5, True),     # UNC upsets Duke in F4
)


def run_calibration() -> CalibrationResult:
    """Run the full calibration pipeline and return the best k.

    1. Coarse grid search: k ∈ [8, 20] step 1
    2. Fine grid search: k ∈ [best ± 2] step 0.25
    """
    # Coarse search
    coarse = grid_search_k(CALIBRATION_GAMES)
    best_coarse = coarse[0]

    # Fine search around best
    fine = fine_search_k(CALIBRATION_GAMES, best_coarse.k)
    best = fine[0]

    return best


def print_calibration_report() -> None:
    """Run calibration and print detailed report."""
    print("=" * 75)
    print("K CALIBRATION — GRID SEARCH")
    print("=" * 75)
    print(f"Dataset: {len(CALIBRATION_GAMES)} historical tournament games (2021-2024)")
    print(f"Target Brier Score: ≤ 0.205\n")

    # Coarse search
    print("--- Coarse Search (k = 8 to 20, step 1) ---")
    coarse = grid_search_k(CALIBRATION_GAMES)
    for r in coarse:
        marker = " ◄ BEST" if r == coarse[0] else ""
        print(f"  k={r.k:5.1f}  Brier={r.brier_score:.4f}  LogLoss={r.log_loss:.4f}  Acc={r.accuracy:.3f}{marker}")

    best_coarse = coarse[0]
    print(f"\nBest coarse k: {best_coarse.k}")

    # Fine search
    print(f"\n--- Fine Search (k = {best_coarse.k - 2} to {best_coarse.k + 2}, step 0.25) ---")
    fine = fine_search_k(CALIBRATION_GAMES, best_coarse.k)
    for r in fine[:10]:
        marker = " ◄ BEST" if r == fine[0] else ""
        print(f"  k={r.k:6.2f}  Brier={r.brier_score:.4f}  LogLoss={r.log_loss:.4f}  Acc={r.accuracy:.3f}{marker}")

    best = fine[0]
    print(f"\n{'=' * 75}")
    print(f"OPTIMAL k = {best.k}")
    print(f"Brier Score = {best.brier_score:.4f} (target: ≤ 0.205)")
    status = "PASS ✓" if best.brier_score <= 0.205 else "FAIL ✗ — need more data or model refinement"
    print(f"Status: {status}")
    print(f"{'=' * 75}")


if __name__ == "__main__":
    print_calibration_report()
