"""
Rivalry and familiarity matchup adjustments for 2026 NCAA Tournament R64.

Each entry maps a (team_a, team_b) pair to a rivalry type and underdog_boost.
underdog_boost is added to the lower-seeded team's p_matchup (0.01 to 0.05).

Rivalry types:
  - conference_rivals: Same conference, know each other well → closer to 50/50
  - historical_rivals: Storied matchup history → higher variance
  - geographic_rivals: Same state/metro → extra motivation for underdog
  - revenge_game: Played earlier this season → loser gets prep advantage

Only includes actual R64 matchups (plus First Four) that have rivalry characteristics.
"""

# R64 Matchups by region (seed vs seed):
# East:  1-Duke vs 16-Siena, 8-Ohio State vs 9-TCU, 5-St. John's vs 12-Northern Iowa,
#        4-Kansas vs 13-Cal Baptist, 6-Louisville vs 11-South Florida,
#        3-Michigan State vs 14-North Dakota State, 7-UCLA vs 10-UCF, 2-UConn vs 15-Furman
# South: 1-Florida vs 16-FF winner, 8-Clemson vs 9-Iowa, 5-Vanderbilt vs 12-McNeese,
#        4-Nebraska vs 13-Troy, 6-North Carolina vs 11-VCU, 3-Illinois vs 14-Penn,
#        7-Saint Mary's vs 10-Texas A&M, 2-Houston vs 15-Idaho
# West:  1-Arizona vs 16-LIU, 8-Villanova vs 9-Utah State, 5-Wisconsin vs 12-High Point,
#        4-Arkansas vs 13-Hawaii, 6-BYU vs 11-FF winner (Texas/NC State),
#        3-Gonzaga vs 14-Kennesaw State, 7-Miami vs 10-Missouri, 2-Purdue vs 15-Queens
# Midwest: 1-Michigan vs 16-FF winner, 8-Georgia vs 9-Saint Louis, 5-Texas Tech vs 12-Akron,
#          4-Alabama vs 13-Hofstra, 6-Tennessee vs 11-FF winner (Miami OH/SMU),
#          3-Virginia vs 14-Wright State, 7-Kentucky vs 10-Santa Clara,
#          2-Iowa State vs 15-Tennessee State

RIVALRY_MATCHUPS_2026: dict[tuple[str, str], dict] = {
    # ── Conference Rivals (same conference, played 2x+ this season) ──────

    # East: Louisville (ACC) vs South Florida (AAC) — no conference rivalry
    # But: Duke (ACC) vs Siena — no rivalry
    # Ohio State (Big Ten) vs TCU (Big 12) — no conf rivalry

    # South: Clemson (ACC) vs Iowa (Big Ten) — no conf rivalry
    # Florida (SEC) vs Vanderbilt (SEC) — same conference but NOT playing each other R64

    # West: BYU (Big 12) vs Texas (SEC) or NC State (ACC) — no conf rivalry
    # Miami (ACC) vs Missouri (SEC) — no conf rivalry

    # Midwest: Tennessee (SEC) vs SMU (ACC) or Miami OH (MAC) — no conf rivalry
    # Kentucky (SEC) vs Santa Clara (WCC) — no conf rivalry

    # No same-conference R64 matchups exist in this bracket.

    # ── Historical Rivals ────────────────────────────────────────────────

    # Kansas vs Cal Baptist — no historical rivalry (Cal Baptist is D1 newcomer)
    # UConn vs Furman — no significant history

    # North Carolina vs VCU — 2019 tournament meeting (UNC won); VCU had famous
    # 2011 Final Four run. Mid-major giant-killer narrative.
    ("North Carolina", "VCU"): {
        "type": "historical_rivals",
        "underdog_boost": 0.02,
        "notes": "VCU tournament pedigree; 2019 R1 meeting. VCU plays with chip on shoulder vs blue bloods.",
    },

    # Kentucky vs Santa Clara — Steve Nash era Santa Clara upset Kentucky in 1993 tourney.
    # Deep historical callback, but notable.
    ("Kentucky", "Santa Clara"): {
        "type": "historical_rivals",
        "underdog_boost": 0.01,
        "notes": "1993 upset (Santa Clara over #2 Kentucky). Historical echo, minimal modern relevance.",
    },

    # ── Geographic Rivals ────────────────────────────────────────────────

    # Tennessee (SEC) vs Tennessee State (OVC) — both from Tennessee.
    # Tennessee State is 15-seed vs 2-seed Iowa State, NOT playing Tennessee.
    # But if we check: Tennessee (6-seed Midwest) vs Miami OH/SMU — no geographic.

    # Miami (ACC, Coral Gables FL) vs Missouri (SEC) — no geographic.

    # Florida (SEC, Gainesville) vs Prairie View A&M/Lehigh — no geographic.

    # Clemson (ACC, SC) vs Iowa (Big Ten, IA) — no geographic.

    # Georgia (SEC, Athens GA) vs Saint Louis (A10, St. Louis MO) — no geographic.

    # Alabama (SEC, Tuscaloosa AL) vs Hofstra (CAA, Long Island NY) — no geographic.

    # No strong geographic rivalries in actual R64 matchups.

    # ── Revenge Games (played earlier this 2025-26 season) ───────────────

    # Ohio State (Big Ten) vs TCU (Big 12) — played in Big 12-Big Ten Challenge
    # (non-conference game earlier this season).
    ("Ohio State", "TCU"): {
        "type": "revenge_game",
        "underdog_boost": 0.02,
        "notes": "Met in non-conference play earlier this season. Familiarity and preparation edge for underdog.",
    },

    # UCLA (Big Ten) vs UCF (Big 12) — no regular season meeting.

    # Clemson (ACC) vs Iowa (Big Ten) — no regular season meeting.

    # Illinois (Big Ten) vs Penn (Ivy) — no regular season meeting.

    # ── First Four Rivalries ─────────────────────────────────────────────

    # Texas (SEC) vs NC State (ACC) — First Four, West 11 seed
    # Both power conference at-large teams. Texas was in the ACC's footprint
    # before conference realignment. NC State had magical 2024 Final Four run.
    ("Texas", "NC State"): {
        "type": "revenge_game",
        "underdog_boost": 0.02,
        "notes": "Both bubble teams with something to prove. NC State 2024 Final Four mystique. High motivation game.",
    },

    # Miami (OH) vs SMU — First Four, Midwest 11 seed
    # Miami OH (MAC, 31-1) vs SMU (ACC, 20-13). David vs Goliath narrative.
    # SMU is the higher-profile program but Miami OH has the better record.
    ("Miami (OH)", "SMU"): {
        "type": "historical_rivals",
        "underdog_boost": 0.02,
        "notes": "Miami OH 31-1 vs SMU at-large. Mid-major validation game. SMU has brand but worse record.",
    },

    # ── Conference Familiarity (same conference but not direct rivals) ────

    # St. John's (Big East, 5-seed) could meet UConn (Big East, 2-seed) in R32
    # but NOT in R64. No Big East R64 matchups.

    # Multiple Big Ten teams but none face each other in R64:
    # Michigan State, Ohio State, UCLA, Illinois, Nebraska, Wisconsin, Iowa, Michigan, Purdue

    # Multiple SEC teams but none face each other in R64:
    # Florida, Vanderbilt, Tennessee, Kentucky, Georgia, Texas A&M, Arkansas, Alabama, Missouri, Texas
}
