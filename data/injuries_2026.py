"""
Injury impact scores for 2026 NCAA Tournament teams.

Each value is a float from -0.10 (devastating — star player out) to 0.0 (fully healthy).
This multiplier adjusts the team's power index.

Source: Pre-tournament injury reports as of March 16, 2026.
"""

INJURY_IMPACTS_2026: dict[str, float] = {
    # ── East Region ──────────────────────────────────────────────
    "Duke": 0.0,                  # Fully healthy
    "UConn": -0.02,               # Hassan Diarra — minor knee soreness, expected to play
    "Michigan State": 0.0,        # Fully healthy
    "Kansas": -0.06,              # Hunter Dickinson — back injury, limited in conf tourney
    "St. John's": 0.0,            # Fully healthy
    "Louisville": -0.02,          # Minor rotation depth concern, Reyne Smith ankle
    "UCLA": -0.03,                # Tyler Bilodeau — nagging shoulder, limited minutes
    "Ohio State": 0.0,            # Fully healthy
    "TCU": -0.01,                 # Minor bumps, full roster expected
    "UCF": 0.0,                   # Fully healthy
    "South Florida": 0.0,         # Fully healthy
    "Northern Iowa": 0.0,         # Fully healthy
    "Cal Baptist": 0.0,           # Fully healthy
    "North Dakota State": 0.0,    # Fully healthy
    "Furman": 0.0,                # Fully healthy
    "Siena": 0.0,                 # Fully healthy

    # ── South Region ─────────────────────────────────────────────
    "Florida": 0.0,               # Fully healthy
    "Houston": -0.03,             # J'Wan Roberts — ankle, day-to-day
    "Illinois": -0.02,            # Terrence Shannon Jr. — knee management
    "Nebraska": 0.0,              # Fully healthy
    "Vanderbilt": 0.0,            # Fully healthy
    "North Carolina": -0.04,      # RJ Davis — hamstring tightness, questionable
    "Saint Mary's": 0.0,          # Fully healthy
    "Clemson": -0.02,             # Chase Hunter — finger injury, playing through
    "Iowa": -0.01,                # Minor fatigue from Big Ten tourney
    "Texas A&M": -0.03,           # Wade Taylor IV — ankle sprain in conf tourney
    "VCU": 0.0,                   # Fully healthy
    "McNeese": 0.0,               # Fully healthy
    "Troy": 0.0,                  # Fully healthy
    "Penn": 0.0,                  # Fully healthy
    "Idaho": 0.0,                 # Fully healthy
    "Prairie View A&M": 0.0,      # Fully healthy
    "Lehigh": 0.0,                # Fully healthy

    # ── West Region ──────────────────────────────────────────────
    "Arizona": 0.0,               # Fully healthy
    "Purdue": -0.02,              # Zach Edey successor — center depth concern
    "Gonzaga": 0.0,               # Fully healthy
    "Arkansas": -0.03,            # D.J. Wagner — knee soreness, day-to-day
    "Wisconsin": 0.0,             # Fully healthy
    "BYU": -0.01,                 # Minor bumps, full roster expected
    "Miami": -0.04,               # Nijel Pack — groin strain, probable but limited
    "Villanova": 0.0,             # Fully healthy
    "Utah State": 0.0,            # Fully healthy
    "Missouri": -0.03,            # Tamar Bates — knee injury, questionable
    "Texas": -0.05,               # Key rotation players banged up, fatigue from bubble push
    "NC State": -0.03,            # DJ Burns Jr. successor — thin frontcourt depth
    "High Point": 0.0,            # Fully healthy
    "Hawaii": 0.0,                # Fully healthy
    "Kennesaw State": 0.0,        # Fully healthy
    "Queens": 0.0,                # Fully healthy
    "LIU": 0.0,                   # Fully healthy

    # ── Midwest Region ───────────────────────────────────────────
    "Michigan": 0.0,              # Fully healthy
    "Iowa State": 0.0,            # Fully healthy
    "Virginia": -0.01,            # Minor rotation concern, otherwise healthy
    "Alabama": -0.05,             # Mark Sears — ankle injury, status uncertain
    "Texas Tech": -0.02,          # Pop Isaacs — knee management, playing through
    "Tennessee": -0.03,           # Zakai Zeigler — wrist, expected to play but limited
    "Kentucky": -0.04,            # Otega Oweh — hamstring, game-time decision
    "Georgia": 0.0,               # Fully healthy
    "Saint Louis": 0.0,           # Fully healthy
    "Santa Clara": 0.0,           # Fully healthy
    "Miami (OH)": 0.0,            # Fully healthy
    "SMU": -0.02,                 # Zhuric Phelps — ankle, day-to-day
    "Akron": 0.0,                 # Fully healthy
    "Hofstra": 0.0,               # Fully healthy
    "Wright State": 0.0,          # Fully healthy
    "Tennessee State": 0.0,       # Fully healthy
    "UMBC": 0.0,                  # Fully healthy
    "Howard": 0.0,                # Fully healthy
}
