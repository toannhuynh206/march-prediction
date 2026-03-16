"""
Win probability computation using 4-layer spread-adaptive blend.

Combines:
  P_market  — de-vigged moneyline / spread from Vegas
  P_stats   — logistic function from power index differential
  P_matchup — tempo/size differential adjustments
  P_factors — qualitative (coaching, sentiment, FCI-adjusted base rates)

Usage:
    python -m research.probability --year 2026
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

from config.constants import BLEND_TIERS, LOGISTIC_K_INITIAL
from data.injuries_2026 import INJURY_IMPACTS_2026
from data.rivalries_2026 import RIVALRY_MATCHUPS_2026
from data.team_locations import travel_distance_miles
from db.connection import session_scope
from sqlalchemy import text


# =========================================================================
# Logistic function
# =========================================================================

def logistic_win_prob(
    power_a: float,
    power_b: float,
    k: float = LOGISTIC_K_INITIAL,
) -> float:
    """P(A wins) = 1 / (1 + 10^((power_B - power_A) / k))"""
    exponent = (power_b - power_a) / k
    return 1.0 / (1.0 + 10.0 ** exponent)


# =========================================================================
# Logit / inverse-logit helpers (for log-odds blending)
# =========================================================================

def _logit(p: float) -> float:
    """Convert probability to log-odds. Clamp to avoid ±inf."""
    p = max(0.001, min(0.999, p))
    return np.log(p / (1.0 - p))


def _inv_logit(x: float) -> float:
    """Convert log-odds back to probability."""
    return 1.0 / (1.0 + np.exp(-x))


# =========================================================================
# Matchup adjustment (P_matchup)
# =========================================================================

def _compute_p_matchup(
    team_a: dict[str, Any],
    team_b: dict[str, Any],
    venue_city: str | None = None,
    year: int = 2026,
) -> float:
    """Compute matchup-specific probability adjustment.

    Five sub-factors centered at 0.5:
      1. Tempo/defense control — slow + defensive teams impose their style
      2. Size/rebounding — taller teams dominate the glass
      3. Travel distance — closer team has logistical + crowd advantage
      4. Injury differential — healthier team gets edge
      5. Rivalry/familiarity — underdogs get boost in revenge/rivalry games
    """
    name_a = team_a.get("name", "")
    name_b = team_b.get("name", "")

    # --- Sub-factor 1: Tempo control advantage ---
    tempo_a = team_a.get("tempo") or 68.0
    tempo_b = team_b.get("tempo") or 68.0
    adj_d_a = team_a.get("adj_d") or 95.0
    adj_d_b = team_b.get("adj_d") or 95.0

    tempo_diff = tempo_b - tempo_a  # positive if A plays slower
    defense_edge = adj_d_b - adj_d_a  # positive if A has better (lower) defense
    tempo_factor = 0.0
    if tempo_diff > 3 and defense_edge > 2:
        tempo_factor = 0.02
    elif tempo_diff < -3 and defense_edge < -2:
        tempo_factor = -0.02

    # --- Sub-factor 2: Size/rebounding ---
    height_a = team_a.get("height_avg_inches") or 78.0
    height_b = team_b.get("height_avg_inches") or 78.0
    orb_a = team_a.get("orb_pct") or 30.0
    orb_b = team_b.get("orb_pct") or 30.0

    height_diff = height_a - height_b
    orb_diff = orb_a - orb_b
    size_factor = np.clip(height_diff * 0.005 + orb_diff * 0.002, -0.03, 0.03)

    # --- Sub-factor 3: Travel distance ---
    travel_factor = 0.0
    if venue_city and name_a and name_b:
        try:
            dist_a = travel_distance_miles(name_a, venue_city)
            dist_b = travel_distance_miles(name_b, venue_city)
            # 0.5% per 100 miles advantage, capped at ±4%
            diff_hundreds = (dist_b - dist_a) / 100.0
            travel_factor = np.clip(diff_hundreds * 0.005, -0.04, 0.04)
        except KeyError:
            pass  # Unknown team/venue — no adjustment

    # --- Sub-factor 4: Injury differential ---
    injury_factor = 0.0
    if year == 2026 and name_a and name_b:
        inj_a = INJURY_IMPACTS_2026.get(name_a, 0.0)
        inj_b = INJURY_IMPACTS_2026.get(name_b, 0.0)
        # Injury impacts are negative. Team A advantage = B is more injured.
        # inj_b more negative → B is worse off → advantage to A
        injury_factor = np.clip((inj_b - inj_a) * 0.5, -0.03, 0.03)

    # --- Sub-factor 5: Rivalry/familiarity ---
    rivalry_factor = 0.0
    if year == 2026 and name_a and name_b:
        # Check both orderings
        rivalry = RIVALRY_MATCHUPS_2026.get((name_a, name_b))
        if rivalry is None:
            rivalry = RIVALRY_MATCHUPS_2026.get((name_b, name_a))
            if rivalry:
                # Boost goes to underdog — since key order is (higher, lower),
                # and team_a is typically the higher seed, flip the sign
                rivalry_factor = -rivalry["underdog_boost"]
        else:
            # team_a is listed first in the rivalry dict
            # underdog_boost favors team_b (the underdog)
            rivalry_factor = -rivalry["underdog_boost"]

    # Combine all sub-factors
    adjustment = tempo_factor + size_factor + travel_factor + injury_factor + rivalry_factor
    return 0.5 + np.clip(adjustment, -0.15, 0.15)


# =========================================================================
# Factors adjustment (P_factors)
# =========================================================================

def _compute_p_factors(
    team_a: dict[str, Any],
    team_b: dict[str, Any],
    seed_a: int | None,
    seed_b: int | None,
    historical_rates: dict[str, Any] | None,
) -> float:
    """Compute qualitative factor probability from coaching, base rates, etc.

    Uses FCI-adjusted historical seed win rates as the base, then adjusts
    for coaching experience differential.
    """
    # Historical base rate by seed matchup
    base_prob = 0.5
    if seed_a is not None and seed_b is not None and historical_rates:
        higher_seed = min(seed_a, seed_b)
        lower_seed = max(seed_a, seed_b)
        matchup_key = f"{higher_seed}v{lower_seed}"

        r64_data = historical_rates.get("r64", {})
        if matchup_key in r64_data:
            higher_pct = r64_data[matchup_key].get("higher_seed_pct", 0.5)
            # Assign to team A based on which seed they are
            if seed_a == higher_seed:
                base_prob = higher_pct
            else:
                base_prob = 1.0 - higher_pct

    # Coaching experience differential
    coach_a = team_a.get("coaching_tourney_apps") or 0
    coach_b = team_b.get("coaching_tourney_apps") or 0
    coach_diff = coach_a - coach_b
    # Each tournament appearance = tiny edge (capped)
    coach_adj = np.clip(coach_diff * 0.003, -0.05, 0.05)

    return max(0.01, min(0.99, base_prob + coach_adj))


# =========================================================================
# Spread-adaptive blend
# =========================================================================

def _get_blend_weights(spread: float | None) -> dict[str, float]:
    """Get blend weights for the appropriate spread tier."""
    if spread is None:
        spread = 5.0  # default to lean tier

    abs_spread = abs(spread)
    for tier_name, tier in BLEND_TIERS.items():
        if tier["condition"](abs_spread):
            return {
                "w_market": tier["w_market"],
                "w_stats": tier["w_stats"],
                "w_matchup": tier["w_matchup"],
                "w_factors": tier["w_factors"],
            }

    # Fallback (should never reach here)
    return BLEND_TIERS["lean"]


def blend_probabilities(
    p_market: float | None,
    p_stats: float,
    p_matchup: float,
    p_factors: float,
    spread: float | None,
) -> float:
    """Compute blended win probability using log-odds weighted average.

    logit(P_final) = w_m*logit(P_market) + w_s*logit(P_stats)
                   + w_x*logit(P_matchup) + w_f*logit(P_factors)
    """
    weights = _get_blend_weights(spread)

    # If no market data, redistribute market weight to stats
    if p_market is None:
        w_stats = weights["w_stats"] + weights["w_market"]
        w_market = 0.0
    else:
        w_stats = weights["w_stats"]
        w_market = weights["w_market"]

    logit_sum = 0.0
    if w_market > 0 and p_market is not None:
        logit_sum += w_market * _logit(p_market)
    logit_sum += w_stats * _logit(p_stats)
    logit_sum += weights["w_matchup"] * _logit(p_matchup)
    logit_sum += weights["w_factors"] * _logit(p_factors)

    return _inv_logit(logit_sum)


# =========================================================================
# Compute all matchup probabilities
# =========================================================================

def _load_venue_lookup(year: int) -> dict[tuple[str, int, int], str]:
    """Load venue city for each R64 matchup from bracket JSON.

    Returns {(region, higher_seed, lower_seed): venue_city}.
    """
    bracket_path = PROJECT_ROOT / "data" / "brackets" / f"{year}_bracket.json"
    if not bracket_path.exists():
        return {}

    with open(bracket_path) as f:
        bracket = json.load(f)

    venue_lookup: dict[tuple[str, int, int], str] = {}
    for region_name, region_data in bracket.get("regions", {}).items():
        for matchup in region_data.get("first_round_matchups", []):
            key = (region_name, matchup["higher_seed"], matchup["lower_seed"])
            venue_lookup[key] = matchup["location"]

    return venue_lookup


def compute_matchup_probabilities(year: int) -> list[dict[str, Any]]:
    """Compute blended win probabilities for all R64 matchups.

    Reads power indices, team stats, market probabilities, and historical
    seed rates. Updates matchups table with p_stats, p_matchup, p_factors,
    and p_final.
    """
    # Load historical seed win rates
    historical_path = PROJECT_ROOT / "data" / "historical" / "seed_win_rates.json"
    historical_rates = None
    if historical_path.exists():
        with open(historical_path) as f:
            historical_rates = json.load(f)

    # Load venue locations for travel distance
    venue_lookup = _load_venue_lookup(year)

    # Load team data + power indices + matchup data from DB
    with session_scope() as session:
        teams_raw = session.execute(text("""
            SELECT t.id, t.name, t.seed,
                   ts.power_index, ts.adj_d, ts.tempo,
                   ts.height_avg_inches, ts.orb_pct,
                   ts.coaching_tourney_apps
            FROM teams t
            JOIN team_stats ts ON t.id = ts.team_id
            WHERE t.tournament_year = :year AND ts.tournament_year = :year
        """), {"year": year}).fetchall()

        matchups_raw = session.execute(text("""
            SELECT id, team_a_id, team_b_id, seed_a, seed_b,
                   p_market, region
            FROM matchups
            WHERE tournament_year = :year AND round = 'R64'
        """), {"year": year}).fetchall()

    # Build team lookup
    teams: dict[int, dict[str, Any]] = {}
    for r in teams_raw:
        teams[r[0]] = {
            "id": r[0], "name": r[1], "seed": r[2],
            "power_index": r[3], "adj_d": r[4], "tempo": r[5],
            "height_avg_inches": r[6], "orb_pct": r[7],
            "coaching_tourney_apps": r[8],
        }

    # Compute probabilities for each matchup
    results = []
    for m in matchups_raw:
        m_id, a_id, b_id, seed_a, seed_b, p_market, region = m

        team_a = teams.get(a_id, {})
        team_b = teams.get(b_id, {})

        pi_a = team_a.get("power_index") or 50.0
        pi_b = team_b.get("power_index") or 50.0

        # P_stats from logistic function
        p_stats = logistic_win_prob(pi_a, pi_b)

        # Look up venue for this matchup
        higher_seed = min(seed_a or 99, seed_b or 99)
        lower_seed = max(seed_a or 0, seed_b or 0)
        venue_city = venue_lookup.get((region, higher_seed, lower_seed))

        # P_matchup from tempo/size/travel/injury/rivalry
        p_matchup = _compute_p_matchup(
            team_a, team_b,
            venue_city=venue_city,
            year=year,
        )

        # P_factors from coaching + historical base rates
        p_factors = _compute_p_factors(
            team_a, team_b, seed_a, seed_b, historical_rates
        )

        # Get spread for blend tier selection
        spread = None
        if p_market is not None:
            # Approximate spread from market prob: spread ≈ (p - 0.5) * 30
            spread = (p_market - 0.5) * 30.0

        # Blended final probability
        p_final = blend_probabilities(p_market, p_stats, p_matchup, p_factors, spread)

        results.append({
            "matchup_id": m_id,
            "region": region,
            "team_a": team_a.get("name", "?"),
            "team_b": team_b.get("name", "?"),
            "seed_a": seed_a,
            "seed_b": seed_b,
            "p_market": float(p_market) if p_market is not None else None,
            "p_stats": float(p_stats),
            "p_matchup": float(p_matchup),
            "p_factors": float(p_factors),
            "p_final": float(p_final),
            "spread": spread,
            "venue": venue_city,
        })

    # Write back to DB
    with session_scope() as session:
        for r in results:
            session.execute(text("""
                UPDATE matchups
                SET p_stats = :p_stats,
                    p_matchup = :p_matchup,
                    p_factors = :p_factors,
                    p_final = :p_final
                WHERE id = :mid
            """), {
                "p_stats": r["p_stats"],
                "p_matchup": r["p_matchup"],
                "p_factors": r["p_factors"],
                "p_final": r["p_final"],
                "mid": r["matchup_id"],
            })

    # Print results
    print(f"\n{'='*105}")
    print(f" R64 Win Probabilities — {year} Tournament (P = P(team_a wins))")
    print(f" Enhanced: travel distance + injuries + rivalries")
    print(f"{'='*105}")
    print(f" {'Region':10s} {'Matchup':35s} {'P_mkt':>6s} {'P_stat':>6s} "
          f"{'P_mup':>6s} {'P_fac':>6s} {'P_fin':>6s} {'Tier':>9s} {'Venue':>20s}")
    print(f" {'-'*10} {'-'*35} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*9} {'-'*20}")

    for r in sorted(results, key=lambda x: (x["region"], x["seed_a"] or 99)):
        pm = f"{r['p_market']:.3f}" if r["p_market"] else "  N/A"
        spread = r["spread"]
        tier = "locks" if spread and abs(spread) > 15 else \
               "lean" if spread and abs(spread) >= 5 else "coin_flip"
        venue = r.get("venue") or "N/A"
        matchup_str = (f"#{r['seed_a']} {r['team_a']:15s} vs "
                       f"#{r['seed_b']} {r['team_b']:15s}")
        print(f" {r['region']:10s} {matchup_str:35s} {pm:>6s} "
              f"{r['p_stats']:.3f} {r['p_matchup']:.3f} "
              f"{r['p_factors']:.3f} {r['p_final']:.3f} {tier:>9s} {venue:>20s}")

    return results


# =========================================================================
# Main
# =========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Compute R64 win probabilities")
    parser.add_argument("--year", type=int, default=2026)
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass

    compute_matchup_probabilities(args.year)


if __name__ == "__main__":
    main()
