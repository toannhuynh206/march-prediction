"""Import tournament state from tournament_state.json into the database."""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.connection import get_engine
from sqlalchemy import text

with open(PROJECT_ROOT / "scripts" / "tournament_state.json") as f:
    data = json.load(f)

e = get_engine()

print(f"Importing {len(data['brackets'])} brackets + {len(data['games'])} game results...")

with e.begin() as c:
    c.execute(text("TRUNCATE full_brackets"))
    c.execute(text("DELETE FROM game_results WHERE tournament_year = 2026"))

    for b in data["brackets"]:
        c.execute(text("""
            INSERT INTO full_brackets
                (id, east_outcomes, south_outcomes, west_outcomes, midwest_outcomes,
                 f4_outcomes, probability, weight, champion_seed, champion_region,
                 total_upsets, strategy, tournament_year, is_alive)
            VALUES (:id, :east, :south, :west, :midwest, :f4, :prob, :weight,
                    :cs, :cr, :upsets, :strat, 2026, true)
        """), {"id": b["id"], "east": b["east"], "south": b["south"], "west": b["west"],
               "midwest": b["midwest"], "f4": b["f4"], "prob": b["prob"], "weight": b["weight"],
               "cs": b["cs"], "cr": b["cr"], "upsets": b["upsets"], "strat": b["strat"]})

    for g in data["games"]:
        c.execute(text("""
            INSERT INTO game_results
                (tournament_year, region, round, game_number, winner_seed, loser_seed, winner_name, loser_name)
            VALUES (2026, :region, :round, :gn, :ws, :ls, :wn, :ln)
            ON CONFLICT (tournament_year, region, round, game_number) DO UPDATE SET
                winner_seed = EXCLUDED.winner_seed, loser_seed = EXCLUDED.loser_seed,
                winner_name = EXCLUDED.winner_name, loser_name = EXCLUDED.loser_name
        """), {"region": g["region"], "round": g["round"], "gn": g["gn"],
               "ws": g["ws"], "ls": g["ls"], "wn": g["wn"], "ln": g["ln"]})

# Reset alive tables
with e.begin() as c:
    for r in ["south", "east", "west", "midwest"]:
        c.execute(text(f"DELETE FROM alive_outcomes_{r}"))
        c.execute(text(f"INSERT INTO alive_outcomes_{r} (outcome_value) SELECT generate_series(0, 32767)"))
    c.execute(text("DELETE FROM alive_outcomes_f4"))
    c.execute(text("INSERT INTO alive_outcomes_f4 (outcome_value) SELECT generate_series(0, 7)"))

# Rebuild alive_bracket_ids from the 2 brackets
with e.begin() as c:
    c.execute(text("DROP TABLE IF EXISTS alive_bracket_ids"))
    c.execute(text("""
        CREATE TABLE alive_bracket_ids AS
        SELECT id, probability, weight, champion_seed, champion_region, total_upsets
        FROM full_brackets WHERE tournament_year = 2026
    """))
    c.execute(text("CREATE INDEX idx_alive_ids ON alive_bracket_ids (id)"))
    c.execute(text("CREATE INDEX idx_alive_prob ON alive_bracket_ids (probability DESC, id ASC)"))

# Stats cache
with e.begin() as c:
    c.execute(text("DELETE FROM stats_cache WHERE tournament_year = 2026"))
    c.execute(text("""
        INSERT INTO stats_cache (tournament_year, total_brackets, alive_brackets)
        VALUES (2026, 206000000, 2)
    """))

print("Done! 2 brackets + 47 game results imported. Stats cache set to 206M/2.")
