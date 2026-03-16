"""
Compute the 9-factor power index for all tournament teams.

Reads team_stats from the database plus injury data from research JSON.
Normalizes each factor to [0, 100], applies CLAUDE.md weights, and writes
the resulting power_index back to team_stats.

Usage:
    python -m research.power_index --year 2026
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

from config.constants import POWER_INDEX_WEIGHTS
from db.connection import session_scope
from sqlalchemy import text


# =========================================================================
# Injury impact scoring
# =========================================================================

# (status, impact_rating) -> penalty on 0-100 injury health scale
_INJURY_PENALTIES: dict[tuple[str, str], float] = {
    ("OUT", "CRITICAL"):        25.0,
    ("OUT", "HIGH"):            15.0,
    ("OUT", "MODERATE"):         8.0,
    ("OUT", "LOW"):              3.0,
    ("QUESTIONABLE", "CRITICAL"): 15.0,
    ("QUESTIONABLE", "HIGH"):     8.0,
    ("QUESTIONABLE", "MODERATE"):  4.0,
    ("QUESTIONABLE", "LOW"):      2.0,
    ("PROBABLE", "CRITICAL"):     5.0,
    ("PROBABLE", "HIGH"):         2.0,
    ("PROBABLE", "MODERATE"):     1.0,
    ("PROBABLE", "LOW"):          0.0,
    ("AVAILABLE", "CRITICAL"):    0.0,
    ("AVAILABLE", "HIGH"):        0.0,
    ("AVAILABLE", "MODERATE"):    0.0,
    ("AVAILABLE", "LOW"):         0.0,
    ("CLEARED", "CRITICAL"):     0.0,
    ("CLEARED", "HIGH"):         0.0,
    ("CLEARED", "MODERATE"):     0.0,
    ("CLEARED", "LOW"):          0.0,
}


def _load_injury_scores(year: int) -> dict[str, float]:
    """Compute per-team injury health scores (0-100, 100 = fully healthy).

    Reads the most recent injuries JSON and sums penalties per team.
    """
    research_dir = PROJECT_ROOT / "data" / "research"
    injury_files = sorted(research_dir.glob(f"injuries_{year}*.json"), reverse=True)
    if not injury_files:
        return {}

    with open(injury_files[0]) as f:
        data = json.load(f)

    # Sum penalties per team
    team_penalties: dict[str, float] = {}
    for injury in data.get("injuries", []):
        team = injury["team"]
        status = injury.get("status", "").upper()
        impact = injury.get("impact_rating", "").upper()
        penalty = _INJURY_PENALTIES.get((status, impact), 0.0)
        team_penalties[team] = team_penalties.get(team, 0.0) + penalty

    # Convert to health score: 100 - total_penalty, clamped to [0, 100]
    return {
        team: max(0.0, min(100.0, 100.0 - penalty))
        for team, penalty in team_penalties.items()
    }


# =========================================================================
# Normalization helpers
# =========================================================================

def _fill_nan_with_median(values: np.ndarray) -> np.ndarray:
    """Replace NaN values with the field median."""
    median = np.nanmedian(values)
    filled = values.copy()
    filled[np.isnan(filled)] = median
    return filled


def _min_max_normalize(values: np.ndarray) -> np.ndarray:
    """Normalize array to [0, 100] using min-max scaling. NaN filled with median."""
    filled = _fill_nan_with_median(values)
    v_min = np.min(filled)
    v_max = np.max(filled)
    if v_max - v_min < 1e-9:
        return np.full_like(filled, 50.0)
    return (filled - v_min) / (v_max - v_min) * 100.0


def _invert_normalize(values: np.ndarray) -> np.ndarray:
    """Normalize where LOWER raw values are BETTER. NaN filled with median."""
    filled = _fill_nan_with_median(values)
    v_min = np.min(filled)
    v_max = np.max(filled)
    if v_max - v_min < 1e-9:
        return np.full_like(filled, 50.0)
    return (v_max - filled) / (v_max - v_min) * 100.0


# =========================================================================
# Power index computation
# =========================================================================

def compute_power_indices(year: int) -> dict[str, float]:
    """Compute 9-factor power index for all teams in a tournament year.

    Returns dict of team_name -> power_index.
    """
    # 1. Load team data from DB
    with session_scope() as session:
        rows = session.execute(text("""
            SELECT t.id, t.name,
                   ts.adj_em, ts.adj_d, ts.nonconf_sos, ts.experience,
                   ts.luck, ts.ft_rate, ts.coaching_tourney_apps,
                   ts.three_pt_defense, ts.three_pt_pct
            FROM teams t
            JOIN team_stats ts ON t.id = ts.team_id
            WHERE t.tournament_year = :year AND ts.tournament_year = :year
            ORDER BY t.id
        """), {"year": year}).fetchall()

    if not rows:
        print(f"No team stats found for {year}")
        return {}

    n = len(rows)
    team_ids = [r[0] for r in rows]
    team_names = [r[1] for r in rows]

    # Extract raw arrays (handle None -> NaN)
    def _col(idx: int) -> np.ndarray:
        return np.array([r[idx] if r[idx] is not None else np.nan for r in rows],
                        dtype=np.float64)

    raw_adj_em = _col(2)
    raw_adj_d = _col(3)
    raw_nonconf_sos = _col(4)
    raw_experience = _col(5)
    raw_luck = _col(6)
    raw_ft_rate = _col(7)
    raw_coaching = _col(8)
    raw_three_pt_def = _col(9)
    raw_three_pt_pct = _col(10)

    # 2. Load injury health scores
    injury_scores = _load_injury_scores(year)
    raw_injury = np.array(
        [injury_scores.get(name, 100.0) for name in team_names],
        dtype=np.float64,
    )

    # 3. Normalize each factor to [0, 100]
    # AdjEM: higher = better
    f_adj_em = _min_max_normalize(raw_adj_em)

    # Defensive efficiency: LOWER adj_d = better defense
    f_def_eff = _invert_normalize(raw_adj_d)

    # Non-conference SOS: LOWER rank = tougher schedule = better
    f_nonconf_sos = _invert_normalize(raw_nonconf_sos)

    # Experience: higher = more experienced
    f_experience = _min_max_normalize(raw_experience)

    # Luck: higher luck = overperformance = regression risk = PENALIZE
    f_luck = _invert_normalize(raw_luck)

    # Free throw rate: higher = better (gets to line more)
    f_ft_rate = _min_max_normalize(raw_ft_rate)

    # Coaching tournament apps: more = better
    f_coaching = _min_max_normalize(raw_coaching)

    # Injury health score: already on [0, 100]
    f_injury = raw_injury

    # 3-point variance: teams with bad 3PT defense AND mediocre own 3PT
    # shooting are high-variance (risky). Reward low variance.
    # Score = good 3PT defense (low opp %) + good own 3PT accuracy
    f_three_pt_stability = (
        _invert_normalize(raw_three_pt_def) * 0.6  # good defense matters more
        + _min_max_normalize(raw_three_pt_pct) * 0.4  # consistent shooting
    )

    # 4. Weighted sum
    weights = POWER_INDEX_WEIGHTS
    power_index = (
        weights["adj_em"]         * f_adj_em
        + weights["def_efficiency"] * f_def_eff
        + weights["nonconf_sos"]    * f_nonconf_sos
        + weights["experience"]     * f_experience
        + weights["luck"]           * f_luck
        + weights["ft_rate"]        * f_ft_rate
        + weights["coaching"]       * f_coaching
        + weights["injuries"]       * f_injury
        + weights["three_pt_var"]   * f_three_pt_stability
    )

    # 5. Write power_index back to team_stats
    with session_scope() as session:
        for i, tid in enumerate(team_ids):
            session.execute(
                text("""
                    UPDATE team_stats
                    SET power_index = :pi, data_verified = TRUE
                    WHERE team_id = :tid AND tournament_year = :year
                """),
                {"pi": float(power_index[i]), "tid": tid, "year": year},
            )

    # Build result dict
    result = {name: float(power_index[i]) for i, name in enumerate(team_names)}

    # Print summary
    sorted_teams = sorted(result.items(), key=lambda x: x[1], reverse=True)
    print(f"\n{'='*60}")
    print(f" Power Index Rankings — {year} Tournament")
    print(f"{'='*60}")
    for rank, (name, pi) in enumerate(sorted_teams, 1):
        print(f"  {rank:3d}. {name:25s} {pi:6.2f}")
    print(f"{'='*60}")
    print(f" Field: min={min(result.values()):.2f}  "
          f"max={max(result.values()):.2f}  "
          f"mean={np.mean(list(result.values())):.2f}")

    # Print factor breakdown for top 5
    print(f"\n{'='*60}")
    print(f" Factor Breakdown (Top 5)")
    print(f"{'='*60}")
    print(f"  {'Team':25s} {'AdjEM':>6s} {'DefEf':>6s} {'SOS':>6s} "
          f"{'Exp':>6s} {'Luck':>6s} {'FT':>6s} {'Coach':>6s} "
          f"{'Injry':>6s} {'3PT':>6s} {'TOTAL':>7s}")
    for rank, (name, pi) in enumerate(sorted_teams[:5], 1):
        idx = team_names.index(name)
        print(f"  {name:25s} {f_adj_em[idx]:6.1f} {f_def_eff[idx]:6.1f} "
              f"{f_nonconf_sos[idx]:6.1f} {f_experience[idx]:6.1f} "
              f"{f_luck[idx]:6.1f} {f_ft_rate[idx]:6.1f} "
              f"{f_coaching[idx]:6.1f} {f_injury[idx]:6.1f} "
              f"{f_three_pt_stability[idx]:6.1f} {pi:7.2f}")

    return result


# =========================================================================
# Main
# =========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Compute power index for tournament teams")
    parser.add_argument("--year", type=int, default=2026)
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass

    compute_power_indices(args.year)


if __name__ == "__main__":
    main()
