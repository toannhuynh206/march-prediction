#!/bin/bash
# Sync local tournament state to Digital Ocean
# Exports the 2 alive brackets + 47 game results from local DB,
# then imports them on the droplet.
#
# Usage: ./scripts/sync_to_do.sh

set -e

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"

DROPLET="root@138.197.125.220"
REMOTE_DIR="/root/apps/march-prediction"

echo "=== Syncing local tournament state to DO ==="

# Step 1: Export from local DB
echo "[1/5] Exporting local data..."
source .venv/bin/activate
python3 << 'PYEOF'
import json
from db.connection import get_engine
from sqlalchemy import text

e = get_engine()
with e.connect() as c:
    # Export alive brackets
    alive = c.execute(text("""
        SELECT fb.id, fb.east_outcomes, fb.south_outcomes, fb.west_outcomes,
               fb.midwest_outcomes, fb.f4_outcomes, fb.probability, fb.weight,
               fb.champion_seed, fb.champion_region, fb.total_upsets, fb.strategy
        FROM full_brackets fb
        JOIN alive_bracket_ids abi ON fb.id = abi.id
    """)).fetchall()

    brackets = [{"id":r[0],"east":r[1],"south":r[2],"west":r[3],"midwest":r[4],
                 "f4":r[5],"prob":float(r[6]),"weight":float(r[7]),
                 "champ_seed":r[8],"champ_region":r[9],"upsets":r[10],"strategy":r[11]}
                for r in alive]

    # Export game results
    games = c.execute(text("""
        SELECT region, round, game_number, winner_seed, loser_seed, winner_name, loser_name
        FROM game_results WHERE tournament_year = 2026
        ORDER BY round, region, game_number
    """)).fetchall()

    results = [{"region":r[0],"round":r[1],"game_number":r[2],
                "winner_seed":r[3],"loser_seed":r[4],"winner_name":r[5],"loser_name":r[6]}
               for r in games]

    export = {"brackets": brackets, "game_results": results}
    with open("scripts/tournament_state.json", "w") as f:
        json.dump(export, f, indent=2)

    print(f"Exported {len(brackets)} brackets + {len(results)} game results")
PYEOF

# Step 2: Push latest code + export file
echo "[2/5] Pushing to GitHub..."
git add scripts/tournament_state.json scripts/sync_to_do.sh
git commit -m "data: export tournament state for DO sync" 2>/dev/null || true
git push 2>/dev/null || true

# Step 3: Pull on droplet
echo "[3/5] Pulling on droplet..."
ssh $DROPLET "cd $REMOTE_DIR && git pull"

# Step 4: Rebuild frontend on droplet
echo "[4/5] Rebuilding frontend..."
ssh $DROPLET "cd $REMOTE_DIR && docker build -t mm-frontend frontend/app && docker run --rm -v /var/www/marchmadness/dist:/output mm-frontend sh -c 'cp -r /dist/* /output/'"

# Step 5: Import tournament state
echo "[5/5] Importing tournament state..."
ssh $DROPLET "cd $REMOTE_DIR && docker compose -f docker-compose.prod.yml exec -T api python3" << 'PYEOF'
import json
from db.connection import get_engine
from sqlalchemy import text

with open("scripts/tournament_state.json") as f:
    data = json.load(f)

e = get_engine()

with e.begin() as c:
    # Clear DO brackets and game results
    c.execute(text("TRUNCATE full_brackets"))
    c.execute(text("DELETE FROM game_results WHERE tournament_year = 2026"))

    # Insert the 2 alive brackets
    for b in data["brackets"]:
        c.execute(text("""
            INSERT INTO full_brackets
                (id, east_outcomes, south_outcomes, west_outcomes, midwest_outcomes,
                 f4_outcomes, probability, weight, champion_seed, champion_region,
                 total_upsets, strategy, tournament_year, is_alive)
            VALUES (:id, :east, :south, :west, :midwest, :f4, :prob, :weight,
                    :cs, :cr, :upsets, :strat, 2026, true)
        """), {"id":b["id"],"east":b["east"],"south":b["south"],"west":b["west"],
               "midwest":b["midwest"],"f4":b["f4"],"prob":b["prob"],"weight":b["weight"],
               "cs":b["champ_seed"],"cr":b["champ_region"],"upsets":b["upsets"],"strat":b["strategy"]})

    # Insert game results
    for g in data["game_results"]:
        c.execute(text("""
            INSERT INTO game_results
                (tournament_year, region, round, game_number, winner_seed, loser_seed, winner_name, loser_name)
            VALUES (2026, :region, :round, :gn, :ws, :ls, :wn, :ln)
            ON CONFLICT (tournament_year, region, round, game_number) DO UPDATE SET
                winner_seed = EXCLUDED.winner_seed, loser_seed = EXCLUDED.loser_seed,
                winner_name = EXCLUDED.winner_name, loser_name = EXCLUDED.loser_name
        """), {"region":g["region"],"round":g["round"],"gn":g["game_number"],
               "ws":g["winner_seed"],"ls":g["loser_seed"],"wn":g["winner_name"],"ln":g["loser_name"]})

# Reset alive tables and stats
with e.begin() as c:
    for r in ["south","east","west","midwest"]:
        c.execute(text(f"DELETE FROM alive_outcomes_{r}"))
        c.execute(text(f"INSERT INTO alive_outcomes_{r} (outcome_value) SELECT generate_series(0, 32767)"))
    c.execute(text("DELETE FROM alive_outcomes_f4"))
    c.execute(text("INSERT INTO alive_outcomes_f4 (outcome_value) SELECT generate_series(0, 7)"))

# Rebuild alive_bracket_ids
with e.begin() as c:
    c.execute(text("DROP TABLE IF EXISTS alive_bracket_ids"))
    c.execute(text("""
        CREATE TABLE alive_bracket_ids AS
        SELECT fb.id, fb.probability, fb.weight, fb.champion_seed, fb.champion_region, fb.total_upsets
        FROM full_brackets fb WHERE fb.tournament_year = 2026
    """))
    c.execute(text("CREATE INDEX idx_alive_ids ON alive_bracket_ids (id)"))

# Update stats cache
with e.begin() as c:
    c.execute(text("DELETE FROM stats_cache WHERE tournament_year = 2026"))
    c.execute(text("""
        INSERT INTO stats_cache (tournament_year, total_brackets, alive_brackets, champion_odds, upset_distribution)
        VALUES (2026, 206000000, 2, '[]'::jsonb, '[]'::jsonb)
    """))

print(f"Imported {len(data['brackets'])} brackets + {len(data['game_results'])} game results")
print("DO is synced!")
PYEOF

echo ""
echo "=== Sync complete ==="
echo "Site: https://marchmadnesschallenge.store"
