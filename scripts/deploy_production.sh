#!/bin/bash
# Deploy and generate brackets on Digital Ocean
# Usage: ./scripts/deploy_production.sh
#
# Run this ON the droplet inside /opt/march-prediction (or ~/apps/march-prediction)
# Generates 1M brackets for the public demo site.

set -e

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
echo "=== MARCH MADNESS PRODUCTION DEPLOY ==="
echo "Dir: $APP_DIR"
echo "Time: $(date)"
echo ""

# Step 1: Pull latest code
echo "[1/9] Pulling latest code..."
git pull

# Step 2: Rebuild API container with latest code
echo "[2/9] Rebuilding API container..."
docker compose -f docker-compose.prod.yml build --quiet api
docker compose -f docker-compose.prod.yml up -d
sleep 5

# Step 3+4: Create tables + clear everything (combined to avoid race conditions)
echo "[3/9] Migrations + clearing database..."
docker compose -f docker-compose.prod.yml exec -T api python3 << 'PYEOF'
from db.connection import get_engine
from sqlalchemy import text

e = get_engine()

# Create all tables first
with e.begin() as c:
    c.execute(text("CREATE TABLE IF NOT EXISTS alive_outcomes_south (outcome_value SMALLINT PRIMARY KEY)"))
    c.execute(text("CREATE TABLE IF NOT EXISTS alive_outcomes_east (outcome_value SMALLINT PRIMARY KEY)"))
    c.execute(text("CREATE TABLE IF NOT EXISTS alive_outcomes_west (outcome_value SMALLINT PRIMARY KEY)"))
    c.execute(text("CREATE TABLE IF NOT EXISTS alive_outcomes_midwest (outcome_value SMALLINT PRIMARY KEY)"))
    c.execute(text("CREATE TABLE IF NOT EXISTS alive_outcomes_f4 (outcome_value SMALLINT PRIMARY KEY)"))
    c.execute(text("CREATE TABLE IF NOT EXISTS stats_cache (tournament_year INT PRIMARY KEY, total_brackets BIGINT NOT NULL DEFAULT 0, alive_brackets BIGINT NOT NULL DEFAULT 0, champion_odds JSONB, upset_distribution JSONB)"))
    c.execute(text("CREATE TABLE IF NOT EXISTS prune_log (id SERIAL PRIMARY KEY, tournament_year INT NOT NULL, pruned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), games_submitted INT, game_details JSONB, brackets_before BIGINT, brackets_deleted BIGINT, brackets_remaining BIGINT, prune_duration_ms INT)"))
    c.execute(text("CREATE TABLE IF NOT EXISTS generation_proof (id SERIAL PRIMARY KEY, tournament_year INT NOT NULL, generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), total_brackets BIGINT NOT NULL, sha256_hash TEXT, strategy_breakdown JSONB, champion_distribution JSONB)"))
print("Tables created")

# Now clear everything
with e.begin() as c:
    c.execute(text("TRUNCATE full_brackets"))
    c.execute(text("DELETE FROM game_results WHERE tournament_year = 2026"))
    c.execute(text("DELETE FROM prune_log WHERE tournament_year = 2026"))
    c.execute(text("DELETE FROM stats_cache WHERE tournament_year = 2026"))
    for idx in ["idx_fb_south_outcomes", "idx_fb_east_outcomes", "idx_fb_west_outcomes",
                "idx_fb_midwest_outcomes", "idx_fb_f4_outcomes", "idx_fb_prob", "idx_fb_champion"]:
        c.execute(text(f"DROP INDEX IF EXISTS {idx}"))
print("Database cleared, indexes dropped")
PYEOF

# Step 5: Load teams + First Four resolution
echo "[5/9] Loading teams and fixing First Four..."
docker compose -f docker-compose.prod.yml exec -T api python3 -c "
from data.loader import load_teams, _get_team_id_map, load_odds, load_stats, load_matchups
from db.connection import session_scope
from sqlalchemy import text

# Load all 68 teams
name_to_id = load_teams(2026)

# Remove actual First Four losers
losers = ['UMBC', 'NC State', 'Lehigh', 'SMU']
with session_scope() as s:
    for l in losers:
        if l not in name_to_id:
            continue
        tid = name_to_id[l]
        s.execute(text('DELETE FROM team_stats WHERE team_id = :t'), {'t': tid})
        s.execute(text('DELETE FROM odds WHERE team_id = :t OR opponent_id = :t'), {'t': tid})
        s.execute(text('DELETE FROM matchups WHERE team_a_id = :t OR team_b_id = :t'), {'t': tid})
        s.execute(text('DELETE FROM teams WHERE id = :t'), {'t': tid})
        print(f'  Removed {l}')

# Reload data for 64 teams
name_to_id = _get_team_id_map(2026)
load_odds(2026, name_to_id)
load_stats(2026, name_to_id)
load_matchups(2026, name_to_id)
print(f'Loaded {len(name_to_id)} teams')
"

# Step 6: Compute power index + matchup probabilities
echo "[6/9] Computing power index and matchup probabilities..."
docker compose -f docker-compose.prod.yml exec -T api python3 -c "
from research.power_index import compute_power_indices
from research.probability import compute_matchup_probabilities

pi = compute_power_indices(2026)
top3 = sorted(pi.items(), key=lambda x: x[1], reverse=True)[:3]
print(f'Power index: {len(pi)} teams. Top 3: {top3[0][0]}, {top3[1][0]}, {top3[2][0]}')

results = compute_matchup_probabilities(2026)
print(f'Matchup probabilities: {len(results)} matchups computed')
"

# Step 7: Generate brackets (default 1K for low-RAM droplets, override with BRACKET_COUNT env var)
BRACKET_COUNT="${BRACKET_COUNT:-1000}"
echo "[7/9] Generating $BRACKET_COUNT brackets..."
docker compose -f docker-compose.prod.yml exec -T api python3 -m simulation.simulate --full-tournament --count "$BRACKET_COUNT" --year 2026

# Step 8: Rebuild indexes
echo "[8/9] Rebuilding indexes..."
docker compose -f docker-compose.prod.yml exec -T api python3 -c "
import time
from db.connection import get_engine
from sqlalchemy import text
e = get_engine()
indexes = [
    ('idx_fb_south_outcomes', 'full_brackets (south_outcomes)'),
    ('idx_fb_east_outcomes', 'full_brackets (east_outcomes)'),
    ('idx_fb_west_outcomes', 'full_brackets (west_outcomes)'),
    ('idx_fb_midwest_outcomes', 'full_brackets (midwest_outcomes)'),
    ('idx_fb_f4_outcomes', 'full_brackets (f4_outcomes)'),
    ('idx_fb_prob', 'full_brackets (probability DESC)'),
    ('idx_fb_champion', 'full_brackets (champion_region, champion_seed)'),
]
with e.connect() as c:
    for name, defn in indexes:
        t = time.time()
        c.execute(text(f'CREATE INDEX IF NOT EXISTS {name} ON {defn}'))
        c.commit()
        print(f'  {name}: {time.time()-t:.1f}s')
print('All indexes rebuilt')
"

# Step 9: Sanity check
echo "[9/9] Running sanity checks..."
docker compose -f docker-compose.prod.yml exec -T api python3 -c "
from db.connection import get_engine
from sqlalchemy import text
e = get_engine()
with e.connect() as c:
    total = c.execute(text('SELECT COUNT(*) FROM full_brackets WHERE tournament_year = 2026')).scalar()
    unique = c.execute(text('''
        SELECT COUNT(DISTINCT (east_outcomes, south_outcomes, west_outcomes, midwest_outcomes, f4_outcomes))
        FROM full_brackets WHERE tournament_year = 2026
    ''')).scalar()
    sc = c.execute(text('SELECT total_brackets, alive_brackets FROM stats_cache WHERE tournament_year = 2026')).fetchone()
    size = c.execute(text(\"SELECT pg_size_pretty(pg_database_size(current_database()))\")).scalar()

    seeds = c.execute(text('''
        SELECT champion_seed, COUNT(*) FROM full_brackets
        WHERE tournament_year = 2026 GROUP BY champion_seed ORDER BY champion_seed
    ''')).fetchall()

    print(f'Total brackets:  {total:,}')
    print(f'Unique brackets: {unique:,} ({unique/total*100:.1f}%)')
    print(f'Stats cache:     {sc[0]:,} total / {sc[1]:,} alive')
    print(f'DB size:         {size}')
    print()
    print('Champion seed distribution:')
    for s in seeds:
        pct = s[1]/total*100
        if pct > 0.01:
            print(f'  Seed {s[0]:>2d}: {s[1]:>10,} ({pct:.2f}%)')
"

echo ""
echo "=== PRODUCTION DEPLOY COMPLETE ==="
echo "Site: https://marchmadnesschallenge.store"
echo "Time: $(date)"
