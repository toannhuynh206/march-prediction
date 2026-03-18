"""
Win probability engine for March Madness bracket simulation.

Computes P_final for every matchup by blending:
- P_market (from Vegas spreads/moneylines)
- P_stats (from team AdjEM via power index model)
- P_matchup (tempo/size differentials)
- P_factors (sentiment, field strength gap)

Uses spread-adaptive blending (weights vary by spread magnitude):
  P_final = sigmoid(w_m*logit(P_market) + w_s*logit(P_stats) + w_x*logit(P_matchup) + w_f*logit(P_factors))
"""

import sqlite3
import json
import os
import math

from math_primitives import (
    spread_to_prob,
    power_index_prob,
    log_odds_blend,
    get_spread_adaptive_tier,
    SIGMA_SPREAD,
    K_DEFAULT,
)
from database import get_connection, DB_PATH

# Historical seed upset rates (base rates from 1985-2024)
SEED_UPSET_RATES = {
    (1, 16): 0.013,
    (2, 15): 0.065,
    (3, 14): 0.150,
    (4, 13): 0.210,
    (5, 12): 0.356,
    (6, 11): 0.370,
    (7, 10): 0.390,
    (8, 9): 0.519,   # 9-seed actually wins slightly more
}

# 2025 R1 consensus opening spreads (verified: Yahoo, CBS, FOX, FanDuel)
# Positive = higher seed favored by that many points
# Negative = lower seed favored (upset line)
#
# NOTE: This module is in src/ (legacy/prototype path). The production
# pipeline (simulation/) reads spreads from the PostgreSQL matchups table,
# populated by research/market.py from The Odds API.
# For 2026, update the DB via: python -m research.agent --year 2026 --phase matchups
R1_SPREADS_2025 = {
    # South
    ("Auburn", "Alabama State"): 32.5,
    ("Michigan State", "Bryant"): 18.5,
    ("Iowa State", "Lipscomb"): 13.5,
    ("Texas A&M", "Yale"): 7.5,
    ("Michigan", "UC San Diego"): 3.5,
    ("Ole Miss", "UNC"): -1.5,           # 11-seed UNC favored
    ("Marquette", "New Mexico"): 3.5,
    ("Louisville", "Creighton"): 1.5,
    # East
    ("Duke", "Mount St. Mary's"): 32.5,
    ("Alabama", "Robert Morris"): 22.5,
    ("Wisconsin", "Montana"): 17.5,
    ("Arizona", "Akron"): 15.5,
    ("Oregon", "Liberty"): 4.5,
    ("BYU", "VCU"): 3.5,
    ("St. Mary's", "Vanderbilt"): 5.5,
    ("Mississippi State", "Baylor"): -1.5, # 9-seed Baylor favored
    # Midwest
    ("Houston", "SIU Edwardsville"): 27.5,
    ("Tennessee", "Wofford"): 19.5,
    ("Kentucky", "Troy"): 10.5,
    ("Purdue", "High Point"): 10.5,
    ("Clemson", "McNeese"): 7.5,
    ("Illinois", "Xavier"): 4.0,
    ("UCLA", "Utah State"): 5.5,
    ("Gonzaga", "Georgia"): 4.5,
    # West
    ("Florida", "Norfolk State"): 28.5,
    ("St. John's", "Omaha"): 17.5,
    ("Texas Tech", "UNC Wilmington"): 15.5,
    ("Maryland", "Grand Canyon"): 11.5,
    ("Memphis", "Colorado State"): -3.5,   # 12-seed Colorado State favored!
    ("Missouri", "Drake"): 6.5,
    ("Kansas", "Arkansas"): 5.5,
    ("UConn", "Oklahoma"): 4.5,
}

# 2025 FCI = 61.1% → chalk_factor = 1.528
FCI_2025 = 0.611
CHALK_FACTOR = FCI_2025 / 0.40  # 1.528


def compute_p_market(spread: float) -> float:
    """Convert spread to P(higher seed wins) using Phi(spread/sigma)."""
    return spread_to_prob(-spread, sigma=SIGMA_SPREAD)


def compute_p_stats(adj_em_a: float, adj_em_b: float) -> float:
    """Compute P(A wins) from adjusted efficiency margins.

    Uses the power index logistic model. AdjEM difference maps to
    win probability via P = 1 / (1 + 10^((EM_B - EM_A) / k)).
    k is calibrated via grid search (K_DEFAULT=47.75, Brier=0.1823 on 271 games).
    """
    return power_index_prob(adj_em_a, adj_em_b, k=K_DEFAULT)


def compute_p_matchup(team_a_stats: dict, team_b_stats: dict) -> float:
    """Compute matchup adjustment probability.

    Small nudges based on tempo differential, height differential.
    Capped at +/- 0.8 points (per research: matchups have minimal predictive value).
    Returns probability centered at 0.5 (no advantage).
    """
    adjustment = 0.0

    # Tempo differential: extreme mismatch slightly favors slower team (variance compression)
    tempo_a = team_a_stats.get("tempo", 68)
    tempo_b = team_b_stats.get("tempo", 68)
    tempo_diff = abs(tempo_a - tempo_b)
    if tempo_diff > 8:  # Extreme tempo mismatch
        # Slower team gets small edge (fewer possessions = less variance = upset boost)
        if tempo_a < tempo_b:
            adjustment += 0.3  # slight edge to A
        else:
            adjustment -= 0.3

    # Height differential
    height_a = team_a_stats.get("height_avg_inches", 78)
    height_b = team_b_stats.get("height_avg_inches", 78)
    height_diff = height_a - height_b
    if abs(height_diff) > 2.0:
        adjustment += height_diff * 0.1  # taller team gets small edge

    # Cap at +/- 0.8 points
    adjustment = max(-0.8, min(0.8, adjustment))

    # Convert point adjustment to probability shift
    # 0.8 points ≈ 0.07 logit units ≈ ~1.7% probability shift
    return spread_to_prob(-adjustment, sigma=SIGMA_SPREAD)


def compute_p_factors(seed_a: int, seed_b: int) -> float:
    """Compute factors probability (sentiment + field strength gap).

    For 2025: chalk-heavy year (FCI=61.1%), top seeds get a boost.
    ESPN pick % and YouTube sentiment would go here once we have the data.
    For now, uses the FCI-adjusted base rates.
    """
    matchup_key = (min(seed_a, seed_b), max(seed_a, seed_b))
    base_upset_rate = SEED_UPSET_RATES.get(matchup_key, 0.5)

    # Apply chalk factor for top seeds in 2025
    if min(seed_a, seed_b) <= 2:
        adjusted_upset_rate = base_upset_rate / CHALK_FACTOR
    elif min(seed_a, seed_b) <= 4:
        adjusted_upset_rate = base_upset_rate / math.sqrt(CHALK_FACTOR)
    else:
        adjusted_upset_rate = base_upset_rate  # no adjustment for 5-8 seeds

    # Return P(higher seed wins) as the factors signal
    p_higher_seed = 1.0 - adjusted_upset_rate
    return p_higher_seed


def compute_all_r1_probabilities(db_path: str = DB_PATH):
    """Compute P_final for all 32 R1 matchups and store in the database."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    matchups = cursor.execute("""
        SELECT m.id, m.region, m.seed_a, m.seed_b,
               ta.name as team_a, tb.name as team_b,
               sa.adj_em as em_a, sa.adj_o as ao_a, sa.adj_d as ad_a, sa.tempo as tempo_a, sa.height_avg_inches as height_a,
               sb.adj_em as em_b, sb.adj_o as ao_b, sb.adj_d as ad_b, sb.tempo as tempo_b, sb.height_avg_inches as height_b
        FROM matchups m
        JOIN teams ta ON m.team_a_id = ta.id
        JOIN teams tb ON m.team_b_id = tb.id
        LEFT JOIN team_stats sa ON ta.id = sa.team_id
        LEFT JOIN team_stats sb ON tb.id = sb.team_id
        WHERE m.round = 'R64'
        ORDER BY m.region, m.seed_a
    """).fetchall()

    results = []

    for m in matchups:
        team_a = m["team_a"]
        team_b = m["team_b"]
        seed_a = m["seed_a"]
        seed_b = m["seed_b"]

        # P_market from spreads
        spread_key = (team_a, team_b)
        spread = R1_SPREADS_2025.get(spread_key, 0)
        p_market = compute_p_market(spread)

        # P_stats from AdjEM
        em_a = m["em_a"] or 0
        em_b = m["em_b"] or 0
        p_stats = compute_p_stats(em_a, em_b)

        # P_matchup from style differentials
        stats_a = {"tempo": m["tempo_a"] or 68, "height_avg_inches": m["height_a"] or 78}
        stats_b = {"tempo": m["tempo_b"] or 68, "height_avg_inches": m["height_b"] or 78}
        p_matchup = compute_p_matchup(stats_a, stats_b)

        # P_factors from FCI + base rates
        p_factors = compute_p_factors(seed_a, seed_b)

        # Spread-adaptive tier: coin-flip games amplify non-market signals
        tier = get_spread_adaptive_tier(spread)
        p_final = log_odds_blend(p_market, p_stats, p_matchup, p_factors, tier=tier)

        # Update matchup in database
        cursor.execute("""
            UPDATE matchups
            SET p_market = ?, p_stats = ?, p_matchup = ?, p_factors = ?, p_final = ?
            WHERE id = ?
        """, (p_market, p_stats, p_matchup, p_factors, p_final, m["id"]))

        results.append({
            "region": m["region"],
            "matchup": f"({seed_a}) {team_a} vs ({seed_b}) {team_b}",
            "spread": spread,
            "tier": tier,
            "p_market": round(p_market, 3),
            "p_stats": round(p_stats, 3),
            "p_matchup": round(p_matchup, 3),
            "p_factors": round(p_factors, 3),
            "p_final": round(p_final, 3),
        })

    conn.commit()
    conn.close()
    return results


if __name__ == "__main__":
    results = compute_all_r1_probabilities()

    print("=" * 105)
    print(f"{'MATCHUP':<45} {'SPREAD':>7} {'TIER':>10} {'P_MKT':>7} {'P_STAT':>7} {'P_MTCH':>7} {'P_FAC':>7} {'P_FINAL':>8}")
    print("=" * 105)

    current_region = None
    for r in results:
        if r["region"] != current_region:
            current_region = r["region"]
            print(f"\n--- {current_region} ---")

        print(f"{r['matchup']:<45} {r['spread']:>+7.1f} {r['tier']:>10} {r['p_market']:>7.3f} {r['p_stats']:>7.3f} {r['p_matchup']:>7.3f} {r['p_factors']:>7.3f} {r['p_final']:>8.3f}")

    print("\n" + "=" * 105)
    print("Spread-adaptive blending: locks (|s|>15), lean (5-15), coin_flip (<5)")
    print("Coin-flip games amplify matchup + factors signals over Vegas")
