Run a full research refresh for the March Madness bracket simulation engine.

## What This Does

Kicks off the agent research team to gather fresh data, then loads it all into the model. This is the one command to run before simulation.

## Step 1: Research (Agents gather fresh data)

Spawn 4 research agents in parallel to update all data sources. Each agent must output a **dated JSON file** to `data/research/` following the schemas in `agents/RESEARCH_OUTPUT_GUIDE.md`.

### Agent 1: Stats Agent (KenPom/Torvik)
Research latest KenPom ratings, Bart Torvik metrics, and ESPN BPI for all 64 tournament teams. Output: `data/research/kenpom_YYYYMMDD.json` with fields: team, adj_em, adj_o, adj_d, tempo, luck, nonconf_sos, experience, three_pt_pct, three_pt_defense, three_pt_rate, ft_rate, ft_pct, efg_pct, orb_pct, to_pct, block_pct, steal_pct, height_avg_inches.

### Agent 2: Betting Agent (Vegas Odds)
Research latest championship futures, Final Four odds, and R64 spreads/moneylines from DraftKings, FanDuel, BetMGM, Caesars, ESPN Bet. Output: `data/research/vegas_odds_YYYYMMDD.json` with sections: championship_futures, final_four_odds, r64_lines, first_four_lines.

### Agent 3: Injury Agent
Research latest injury reports from ESPN, CBS Sports, Yahoo Sports, RotoWire, team beat writers for all 64 teams. Output: `data/research/injuries_YYYYMMDD.json` with fields per injury: team, player, injury_type, status (OUT/DOUBTFUL/QUESTIONABLE/PROBABLE/AVAILABLE), impact_rating (CRITICAL/HIGH/MODERATE/LOW/MINIMAL), date_updated, notes.

### Agent 4: Coaching Agent
Research coaching tournament experience for all 64 team head coaches. Output: `data/research/coaching_tourney_YYYYMMDD.json` with fields: team, coaching_tourney_apps.

## Step 2: Load Data Into Model

After all research JSONs are saved, run the full refresh pipeline:

```bash
cd "/Users/toanhuynh/Desktop/toan code/march prediction"
.venv/bin/python -m data.loader --year 2026 --full-refresh
```

This runs 6 steps automatically:
1. Load teams from bracket JSON
2. Load Vegas odds (picks most recent `vegas_odds_*.json`)
3. Load KenPom stats (picks most recent `kenpom_*.json`)
4. Load R64 matchups with p_market from odds
5. Recompute 9-factor power index (reads injuries + coaching + stats from DB)
6. Recompute matchup probabilities (p_stats, p_matchup, p_factors, p_final)

## Step 3: Verify

After the refresh, verify the data looks right:

```bash
.venv/bin/python -c "
from db.connection import get_engine
from sqlalchemy import text
engine = get_engine()
with engine.connect() as conn:
    teams = conn.execute(text('SELECT COUNT(*) FROM teams WHERE tournament_year = 2026')).scalar()
    stats = conn.execute(text('SELECT COUNT(*) FROM team_stats WHERE tournament_year = 2026 AND power_index IS NOT NULL')).scalar()
    matchups = conn.execute(text('SELECT COUNT(*) FROM matchups WHERE tournament_year = 2026')).scalar()
    null_market = conn.execute(text('SELECT COUNT(*) FROM matchups WHERE tournament_year = 2026 AND p_market IS NULL')).scalar()
    pi_top = conn.execute(text('SELECT t.name, ts.power_index FROM teams t JOIN team_stats ts ON t.id = ts.team_id WHERE t.tournament_year = 2026 ORDER BY ts.power_index DESC LIMIT 5')).fetchall()
    print(f'Teams: {teams}/64')
    print(f'Stats with PI: {stats}/64')
    print(f'Matchups: {matchups} ({null_market} missing p_market)')
    print(f'Top 5 PI: {[(r[0], round(r[1],1)) for r in pi_top]}')
"
```

Check that:
- 64 teams, 64 stats with power_index
- 32 matchups (4 may have NULL p_market for First Four games — that's OK)
- Top power index teams match expectations

## Important Notes

- The loader **automatically picks the most recent dated file** for each data source
- Agent reports in `agents/reports/` are for human reasoning — they do NOT feed the model
- Only structured JSON in `data/research/` feeds the pipeline
- See `agents/RESEARCH_OUTPUT_GUIDE.md` for exact JSON schemas
