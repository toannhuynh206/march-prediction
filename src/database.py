"""
SQLite database setup and operations for March Madness bracket simulation.

Tables: teams, team_stats, odds, matchups, brackets
"""

import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "march_madness.db")


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Get a connection to the SQLite database."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Create all tables if they don't exist."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            seed INTEGER NOT NULL,
            region TEXT NOT NULL,
            conference TEXT,
            record TEXT,
            tournament_year INTEGER NOT NULL DEFAULT 2025
        );

        CREATE TABLE IF NOT EXISTS team_stats (
            team_id INTEGER PRIMARY KEY REFERENCES teams(id),
            adj_em REAL,
            adj_o REAL,
            adj_d REAL,
            tempo REAL,
            experience REAL,
            nonconf_sos INTEGER,
            luck REAL,
            ft_rate REAL,
            ft_pct REAL,
            efg_pct REAL,
            to_pct REAL,
            orb_pct REAL,
            three_pt_rate REAL,
            three_pt_pct REAL,
            three_pt_defense REAL,
            three_pt_variance REAL,
            block_pct REAL,
            steal_pct REAL,
            coaching_tourney_apps INTEGER,
            height_avg_inches REAL,
            conf_tourney_games INTEGER,
            espn_pick_pct_r32 REAL,
            espn_pick_pct_s16 REAL,
            espn_pick_pct_f4 REAL,
            data_verified BOOLEAN DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER REFERENCES teams(id),
            opponent_id INTEGER REFERENCES teams(id),
            market TEXT,
            line_type TEXT,
            odds_value REAL,
            spread REAL,
            implied_prob REAL,
            fair_prob REAL,
            timestamp TEXT
        );

        CREATE TABLE IF NOT EXISTS matchups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round TEXT NOT NULL,
            region TEXT,
            game_index INTEGER,
            team_a_id INTEGER REFERENCES teams(id),
            team_b_id INTEGER REFERENCES teams(id),
            seed_a INTEGER,
            seed_b INTEGER,
            p_market REAL,
            p_stats REAL,
            p_matchup REAL,
            p_factors REAL,
            p_final REAL,
            actual_winner_id INTEGER REFERENCES teams(id)
        );

        CREATE TABLE IF NOT EXISTS brackets (
            id INTEGER PRIMARY KEY,
            outcomes BLOB NOT NULL,
            probability REAL,
            expected_score REAL,
            pool_value REAL,
            scenario_id INTEGER,
            south_score REAL,
            east_score REAL,
            west_score REAL,
            midwest_score REAL,
            is_alive BOOLEAN DEFAULT 1
        );

        CREATE INDEX IF NOT EXISTS idx_teams_region ON teams(region);
        CREATE INDEX IF NOT EXISTS idx_teams_seed ON teams(seed);
        CREATE INDEX IF NOT EXISTS idx_brackets_alive ON brackets(is_alive) WHERE is_alive = 1;
        CREATE INDEX IF NOT EXISTS idx_brackets_score ON brackets(expected_score DESC);
        CREATE INDEX IF NOT EXISTS idx_brackets_scenario ON brackets(scenario_id);
        CREATE INDEX IF NOT EXISTS idx_odds_team ON odds(team_id);
        CREATE INDEX IF NOT EXISTS idx_matchups_round ON matchups(round);
    """)

    conn.commit()
    conn.close()


def import_bracket_json(json_path: str, db_path: str = DB_PATH) -> int:
    """Import teams from the 2025-bracket.json file.

    Returns the number of teams imported.
    """
    with open(json_path) as f:
        data = json.load(f)

    conn = get_connection(db_path)
    cursor = conn.cursor()
    count = 0

    for region_name, region_data in data["regions"].items():
        for seed_str, team_data in region_data["seeds"].items():
            cursor.execute(
                """INSERT OR IGNORE INTO teams (name, seed, region, conference, record, tournament_year)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    team_data["team"],
                    int(seed_str),
                    region_name,
                    team_data.get("conference"),
                    team_data.get("record"),
                    data.get("tournament_year", 2025),
                ),
            )
            count += 1

    conn.commit()
    conn.close()
    return count


def import_team_stats_json(json_path: str, db_path: str = DB_PATH) -> int:
    """Import team stats from the 2025-team-stats.json file.

    Returns the number of stat rows imported.
    """
    with open(json_path) as f:
        data = json.load(f)

    conn = get_connection(db_path)
    cursor = conn.cursor()
    count = 0

    for team in data["teams"]:
        # Look up team_id by name
        row = cursor.execute(
            "SELECT id FROM teams WHERE name = ?", (team["team"],)
        ).fetchone()
        if not row:
            continue

        team_id = row["id"]
        cursor.execute(
            """INSERT OR REPLACE INTO team_stats
               (team_id, adj_em, adj_o, adj_d, tempo, experience, nonconf_sos,
                luck, ft_rate, ft_pct, efg_pct, to_pct, orb_pct,
                three_pt_rate, three_pt_pct, three_pt_defense, three_pt_variance,
                block_pct, steal_pct, coaching_tourney_apps, height_avg_inches,
                conf_tourney_games, espn_pick_pct_r32, espn_pick_pct_s16, espn_pick_pct_f4)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                team_id,
                team.get("adjEM"),
                team.get("adjO"),
                team.get("adjD"),
                team.get("tempo"),
                team.get("experience"),
                team.get("nonconf_sos"),
                team.get("luck"),
                team.get("ft_rate"),
                team.get("ft_pct"),
                team.get("efg_pct"),
                team.get("to_pct"),
                team.get("orb_pct"),
                team.get("three_pt_rate"),
                team.get("three_pt_pct"),
                team.get("three_pt_defense"),
                team.get("three_pt_variance"),
                team.get("block_pct"),
                team.get("steal_pct"),
                team.get("coaching_tourney_apps"),
                team.get("height_avg_inches"),
                team.get("conf_tourney_games"),
                team.get("espn_pick_pct_r32"),
                team.get("espn_pick_pct_s16"),
                team.get("espn_pick_pct_f4"),
            ),
        )
        count += 1

    conn.commit()
    conn.close()
    return count


def import_matchups_json(json_path: str, db_path: str = DB_PATH) -> int:
    """Import first-round matchups from 2025-first-round-matchups.json.

    Returns the number of matchups imported.
    """
    with open(json_path) as f:
        data = json.load(f)

    conn = get_connection(db_path)
    cursor = conn.cursor()
    count = 0

    for matchup in data.get("matchups", []):
        higher = matchup["higher_seed"]
        lower = matchup["lower_seed"]

        row_a = cursor.execute(
            "SELECT id FROM teams WHERE name = ?", (higher["team"],)
        ).fetchone()
        row_b = cursor.execute(
            "SELECT id FROM teams WHERE name = ?", (lower["team"],)
        ).fetchone()

        if not row_a or not row_b:
            continue

        cursor.execute(
            """INSERT OR IGNORE INTO matchups
               (round, region, game_index, team_a_id, team_b_id, seed_a, seed_b)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                "R64",
                matchup.get("region"),
                matchup.get("game"),
                row_a["id"],
                row_b["id"],
                higher["seed"],
                lower["seed"],
            ),
        )
        count += 1

    conn.commit()
    conn.close()
    return count


def get_team(name: str, db_path: str = DB_PATH):
    """Fetch a team and its stats by name."""
    conn = get_connection(db_path)
    row = conn.execute(
        """SELECT t.*, ts.adj_em, ts.adj_o, ts.adj_d, ts.tempo
           FROM teams t
           LEFT JOIN team_stats ts ON t.id = ts.team_id
           WHERE t.name = ?""",
        (name,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_region_teams(region: str, db_path: str = DB_PATH) -> list[dict]:
    """Fetch all teams in a region, ordered by seed."""
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT t.*, ts.adj_em, ts.adj_o, ts.adj_d, ts.tempo
           FROM teams t
           LEFT JOIN team_stats ts ON t.id = ts.team_id
           WHERE t.region = ?
           ORDER BY t.seed""",
        (region,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    print("Initializing database...")
    init_db()

    reports_dir = os.path.join(os.path.dirname(__file__), "..", "agents", "reports")

    bracket_path = os.path.join(reports_dir, "2025-bracket.json")
    if os.path.exists(bracket_path):
        n = import_bracket_json(bracket_path)
        print(f"Imported {n} teams from bracket JSON")

    stats_path = os.path.join(reports_dir, "2025-team-stats.json")
    if os.path.exists(stats_path):
        n = import_team_stats_json(stats_path)
        print(f"Imported {n} team stat rows")

    matchups_path = os.path.join(reports_dir, "2025-first-round-matchups.json")
    if os.path.exists(matchups_path):
        n = import_matchups_json(matchups_path)
        print(f"Imported {n} first-round matchups")

    # Quick verification
    conn = get_connection()
    team_count = conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    stat_count = conn.execute("SELECT COUNT(*) FROM team_stats").fetchone()[0]
    print(f"\nDatabase ready: {team_count} teams, {stat_count} stat rows")
    print(f"DB location: {os.path.abspath(DB_PATH)}")
    conn.close()
