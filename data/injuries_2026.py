"""
Injury impact scores for 2026 NCAA Tournament teams.

Each value is a float from -0.10 (devastating — star player out) to 0.0 (fully healthy).
This multiplier adjusts the team's power index.

Source: Compiled from injuries_20260316.json research (ESPN, CBS, Yahoo, SI, beat writers).
Last updated: 2026-03-16.
"""

INJURY_IMPACTS_2026: dict[str, float] = {
    # ── East Region ──────────────────────────────────────────────
    "Duke": -0.08,               # Foster OUT (foot fracture, CRITICAL) + Ngongba QUESTIONABLE (trending PROBABLE)
    "UConn": -0.01,              # Demary PROBABLE — X-ray negative, mild sprain, expected available
    "Michigan State": 0.0,       # Fully healthy
    "Kansas": -0.06,             # Dickinson — back injury, limited in conf tourney
    "St. John's": 0.0,           # Fully healthy
    "Louisville": -0.06,         # Mikel Brown Jr. QUESTIONABLE (CRITICAL) — missed 10+ games, back injury, game-time decision
    "UCLA": -0.02,               # Bilodeau PROBABLE (knee cleared) + Dent PROBABLE (calf, expected back)
    "Ohio State": 0.0,           # Fully healthy
    "TCU": -0.01,                # Minor bumps, full roster expected
    "UCF": -0.03,                # Foumena QUESTIONABLE (ankle, missed 6 of 12 games)
    "South Florida": 0.0,        # Fully healthy
    "Northern Iowa": 0.0,        # Fully healthy
    "Cal Baptist": 0.0,          # Fully healthy
    "North Dakota State": 0.0,   # Fully healthy
    "Furman": 0.0,                # Fully healthy
    "Siena": 0.0,                 # Fully healthy

    # ── South Region ─────────────────────────────────────────────
    "Florida": -0.01,            # Haugh PROBABLE (undisclosed, LOW) — rest of roster fully healthy
    "Houston": -0.03,            # Roberts — ankle, day-to-day
    "Illinois": -0.01,           # Stojakovic/Wagler/Boswell all AVAILABLE, minor concerns only
    "Nebraska": 0.0,              # Fully healthy
    "Vanderbilt": 0.0,            # Fully healthy
    "North Carolina": -0.10,     # Wilson OUT (broken thumb, season-ending) — leading scorer 19.8 PPG + rebounder 9.4 RPG
    "Saint Mary's": 0.0,          # Fully healthy
    "Clemson": -0.06,            # Welling OUT (torn ACL, CRITICAL) — 10.2 PPG, 5.4 RPG
    "Iowa": -0.01,               # Minor fatigue from Big Ten tourney
    "Texas A&M": -0.03,          # Taylor — ankle sprain in conf tourney
    "VCU": 0.0,                   # Fully healthy
    "McNeese": 0.0,               # Fully healthy
    "Troy": 0.0,                  # Fully healthy
    "Penn": 0.0,                  # Fully healthy
    "Idaho": 0.0,                 # Fully healthy
    "Prairie View A&M": 0.0,     # Fully healthy
    "Lehigh": 0.0,                # Fully healthy

    # ── West Region ──────────────────────────────────────────────
    "Arizona": -0.03,            # Peat CLEARED but Aristode OUT (undisclosed, 1+ month)
    "Purdue": -0.02,             # Center depth concern
    "Gonzaga": -0.08,            # Huff OUT (dislocated kneecap, CRITICAL) — 17.8 PPG, earliest return Sweet 16
    "Arkansas": -0.01,           # Acuff UPGRADED to AVAILABLE — 37+30 pts in SEC Tourney, ankle manageable
    "Wisconsin": -0.03,          # Winter PROBABLE (ankle, missed 4 games) — Gard says "definitely" available
    "BYU": -0.10,                # Saunders OUT (torn ACL, CRITICAL) + Baker/Pickens/Perry/Kozlowski/Staton all OUT
    "Miami": -0.04,              # Pack — groin strain, probable but limited
    "Villanova": -0.06,          # Hodge OUT (torn ACL, CRITICAL) — 9.2 PPG starting forward
    "Utah State": 0.0,           # Fully healthy
    "Missouri": -0.03,           # Bates — knee injury, questionable
    "Texas": -0.05,              # Key rotation players banged up, fatigue
    "NC State": -0.03,           # Thin frontcourt depth
    "High Point": 0.0,           # Fully healthy
    "Hawaii": 0.0,               # Fully healthy
    "Kennesaw State": 0.0,       # Fully healthy
    "Queens": 0.0,               # Fully healthy
    "LIU": 0.0,                  # Fully healthy

    # ── Midwest Region ───────────────────────────────────────────
    "Michigan": -0.04,           # Cason OUT (torn ACL) + Lendeborg PROBABLE (ankle sprain, expects to play)
    "Iowa State": 0.0,           # Fully healthy
    "Virginia": -0.01,           # Minor rotation concern
    "Alabama": -0.10,            # Holloway OUT (arrested, felony drug charges, removed from team) — 16.8 PPG, best 3PT shooter
    "Texas Tech": -0.10,         # Toppin OUT (torn ACL, CRITICAL) — All-America, 21.8 PPG, 10.8 RPG
    "Tennessee": -0.04,          # Ament PROBABLE (high ankle sprain, HIGH) — struggled in SEC Tourney, 17.4 PPG
    "Kentucky": -0.08,           # Lowe OUT (shoulder surgery) + Quaintance OUT (knee, 16 games missed) + Williams QUESTIONABLE + Moreno PROBABLE
    "Georgia": 0.0,               # Fully healthy
    "Saint Louis": -0.04,        # Avila QUESTIONABLE (chronic plantar fasciitis, HIGH) — A-10 POY, playing through pain
    "Santa Clara": 0.0,           # Fully healthy
    "Miami (OH)": 0.0,           # Fully healthy
    "SMU": -0.04,                # Edwards PROBABLE (ankle, HIGH) + Washington QUESTIONABLE (shoulder)
    "Akron": 0.0,                 # Fully healthy
    "Hofstra": 0.0,               # Fully healthy
    "Wright State": 0.0,         # Fully healthy
    "Tennessee State": 0.0,      # Fully healthy
    "UMBC": 0.0,                  # Fully healthy
    "Howard": 0.0,                # Fully healthy
}
