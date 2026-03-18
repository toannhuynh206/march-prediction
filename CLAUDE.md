# CLAUDE.md — March Madness Bracket Simulation Engine

## What This Project Does
End-to-end March Madness bracket prediction system:
1. **Research Phase** — Power-rank 64 tournament teams using KenPom stats, market odds, and qualitative research
2. **Simulation Phase** — Generate 206M stratified importance-sampled brackets (51.5M per region) using NumPy
3. **Tracker Phase** — React + FastAPI website that prunes brackets live as real results come in

**Test data:** 2025 NCAA Tournament (pre-tournament state, before any games)
**Production target:** 2026 NCAA Tournament (bracket releases March 15, 2026)

---

## Current Status
- Phase: Pre-Sprint — Architecture finalized, awaiting Sprint 1 start
- See `agents/status/PROJECT_STATUS.md` for full status
- See `agents/status/DECISION_LOG.md` for all locked architectural decisions

---

## Tournament Year
```python
TOURNAMENT_YEAR = 2026  # test harness; swap to 2026 on Selection Sunday
```
Every database table has a `tournament_year INT NOT NULL` column. Switching years = one config change.

---

## Critical Architectural Decisions (Non-Negotiable)

### Simulation: Stratified Importance Sampling (NOT naive Monte Carlo)
- 51.5M brackets per region, 206M total
- Worlds defined by (k_R1 upset count, k_R2 upset count, champion seed)
- Budget allocated proportional to √P(world) — Neyman allocation
- Each bracket has `weight FLOAT` column for Bayesian updating
- Minimum 50K brackets per possible champion seed guaranteed
- DO NOT generate all random numbers upfront — generate per-round (memory)

### Power Index Formula (9 factors, specific weights)
| Factor | Weight |
|--------|--------|
| AdjEM (KenPom) | 40% |
| Defensive Efficiency Premium | 10% |
| Non-Conference SOS | 10% |
| Experience Score (Bart Torvik) | 10% |
| Luck Adjustment | 8% |
| Free Throw Rate Index | 7% |
| Coaching Tournament Score | 7% |
| Key Injuries (hard point adj.) | 5% |
| 3-Point Variance Flag | 3% |
**DO NOT** include: raw seed, standalone AdjO/AdjD, recent form (last 10 games)

### Win Probability Blend (4-layer, spread-adaptive)
```
logit(P_final) = w_m×logit(P_market) + w_s×logit(P_stats) + w_x×logit(P_matchup) + w_f×logit(P_factors)
```
Weights adapt based on spread magnitude (spread-adaptive tiers):
| Tier | Condition | w_market | w_stats | w_matchup | w_factors |
|------|-----------|----------|---------|-----------|-----------|
| locks | \|spread\| > 15 | 0.60 | 0.20 | 0.10 | 0.10 |
| lean | \|spread\| 5–15 | 0.45 | 0.25 | 0.15 | 0.15 |
| coin_flip | \|spread\| < 5 | 0.30 | 0.25 | 0.25 | 0.20 |

- P_market: de-vigged moneyline / spread from The Odds API
- P_stats: logistic function from power index differential
- P_matchup: tempo/size differential adjustments
- P_factors: qualitative (coaching, sentiment, FCI-adjusted base rates)

### Logistic Function
```python
P(A wins) = 1 / (1 + 10^((power_B - power_A) / k))
```
k is calibrated from historical data (grid search), NOT hardcoded as 15.
Target Brier Score: ≤ 0.205

---

## Project Structure
```
march-prediction/
├── CLAUDE.md                          # This file
├── README.md
├── .env                               # DB credentials (never commit)
├── .env.example                       # Template
├── .gitignore
├── docker-compose.yml                 # PostgreSQL 16 + pgAdmin
│
├── agents/                            # Agent role definitions and outputs
│   ├── math-agent.md
│   ├── stats-agent.md
│   ├── sports-betting-agent.md
│   ├── elite-research-agent.md
│   ├── program-manager-agent.md
│   ├── lead-swe-agent.md
│   ├── design-agent.md
│   ├── reports/                       # Agent research outputs
│   └── status/                        # PM status docs
│
├── config/
│   ├── settings.py                    # Pydantic BaseSettings (reads .env)
│   └── constants.py                   # Year, regions, weights, k value
│
├── data/
│   ├── brackets/
│   │   ├── 2025_bracket.json          # 64 teams: name, seed, region, first_four flag
│   │   └── 2026_bracket.json          # Populated March 15, 2026
│   └── historical/
│       └── seed_win_rates.json        # Historical upset rates by seed matchup (1985-2024)
│
├── db/
│   ├── connection.py                  # SQLAlchemy engine + connection pool
│   ├── models.py                      # ORM models
│   └── migrations/
│       ├── 001_initial_schema.sql
│       └── 002_indexes.sql
│
├── research/
│   ├── agent.py                       # Orchestrator (parallel subagents)
│   ├── team_researcher.py             # Per-team power index
│   ├── matchup_researcher.py          # Per-pair matchup adjustment
│   ├── probability.py                 # Logistic function + blend formula
│   ├── calibration.py                 # Brier score, k grid search
│   ├── market.py                      # Odds API integration, de-vig formula
│   ├── prompts/                       # Web search prompt templates
│   └── cache/
│       └── research_progress.json     # Checkpoint file — resume on failure
│
├── simulation/
│   ├── simulate.py                    # Entry point
│   ├── engine.py                      # Vectorized NumPy simulation
│   ├── stratifier.py                  # World definition + Neyman allocation
│   ├── probability.py                 # Probability matrix builder
│   ├── storage.py                     # PostgreSQL COPY bulk insert
│   ├── encoder.py                     # 15-bit pack/unpack
│   ├── bracket_structure.py           # NCAA bracket ordering, seed maps
│   └── config.py                      # Simulation constants
│
├── api/
│   ├── main.py                        # FastAPI app
│   ├── routes/
│   │   ├── results.py                 # POST /api/results
│   │   ├── brackets.py                # GET /api/stats
│   │   └── regions.py                 # GET /api/regions/:region
│   ├── services/
│   │   ├── pruner.py                  # Bitwise SQL bracket elimination
│   │   └── stats.py                   # Survival statistics
│   └── models.py                      # Pydantic request/response models
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── RegionCard.jsx
│   │   │   ├── SurvivalChart.jsx
│   │   │   └── ResultEntry.jsx
│   │   ├── store/
│   │   │   └── tournamentStore.js     # Zustand store
│   │   └── api/
│   │       └── client.js
│   └── package.json
│
└── tests/
    ├── test_encoder.py
    ├── test_pruner.py
    ├── test_probability.py
    └── test_stratifier.py
```

---

## Python Conventions

- **Python 3.11+** required
- All data operations use **NumPy vectorized ops** — NEVER Python for-loops over arrays
- Use `psycopg2.extras.execute_values` or **PostgreSQL COPY** for bulk inserts
- Type hints on all public functions
- Use `pathlib.Path`, never `os.path` string joins
- Connection pooling required — never open a bare connection per request
- Use `np.random.default_rng()` not `np.random.random()` (better RNG)
- Use `float32` for probabilities, `int16` for bracket results (memory efficiency)

## Database Rules

- Every table has `tournament_year INT NOT NULL DEFAULT 2026`
- Matchup cache uses canonical ordering: `team_a_id < team_b_id` enforced by CHECK constraint
- UNIQUE constraint on `game_results(tournament_year, region, round, game_number)` — idempotency
- Use PostgreSQL COPY for all bulk inserts (not execute_many)

### Validity Bitmap Pruning (CRITICAL — replaces old UPDATE approach)

**NEVER modify the `full_brackets` table after generation.** It is immutable for audit proof.

Pruning uses 5 tiny "alive outcome" tables instead:
```
alive_outcomes_south    (max 32,768 rows — shrinks with each game)
alive_outcomes_east     (max 32,768 rows)
alive_outcomes_west     (max 32,768 rows)
alive_outcomes_midwest  (max 32,768 rows)
alive_outcomes_f4       (max 8 rows)
```

**How pruning works:**
1. Game result comes in → compute which bit must be 0 or 1
2. DELETE from the tiny alive table: `DELETE FROM alive_outcomes_south WHERE (outcome_value >> bit) & 1 != expected`
3. A bracket is alive if ALL 5 of its outcome values exist in the alive tables (checked via JOIN)
4. Stats cache refreshed via 5-way JOIN (gets faster as tournament progresses)

**Prune speed: < 50ms** (operates on 32K rows, not 206M)

### Required Indexes on full_brackets
- `idx_fb_south_outcomes`, `idx_fb_east_outcomes`, `idx_fb_west_outcomes`, `idx_fb_midwest_outcomes`, `idx_fb_f4_outcomes` — for alive table JOINs
- `idx_fb_prob` — for probability-sorted browsing
- `idx_fb_champion` — for champion name filtering
- `full_brackets_pkey` — for bracket detail lookup

### Proof Tables
- `generation_proof` — SHA-256 hash + timestamp proving pre-tournament generation
- `prune_log` — audit trail of every prune operation
- `stats_cache` — pre-computed counts, champion odds, upset distribution (refreshed after each prune)

### Portfolio Strategy Profiles
```
chalk (30%)        — T=0.5, heavy favorites, ~14 upsets per bracket
standard (35%)     — T=1.0, true model probabilities, ~17 upsets
smart_upset (10%)  — T=0.7/2.0, chalk structure with targeted coin-flip upsets
cinderella (15%)   — T=1.0/2.5, ~1 region goes wild, rest normal
chaos (10%)        — T=1.8/3.0, multiple upset regions, ~20 upsets
```

### Auto-Advance Rules
- 1-seeds and 2-seeds: P=1.0 in R64 (hard lock — zero 16-over-1 or 15-over-2 upsets)
- Enforced in `simulation/historical_patterns.py` calibrate_r64_probabilities()

## React/Frontend Conventions

- **Vite** (not CRA) — `npm create vite@latest frontend -- --template react`
- **Tailwind CSS** for styling
- **Recharts** for SurvivalChart
- **Zustand** for UI state (selected region, admin key)
- **React Query (TanStack)** for all data fetching with 30s polling
- **Framer Motion** for animations (check bundle size impact first)
- Admin API key stored in `localStorage` — never hardcoded
- Bundle size target: < 500KB gzipped
- Design system: deep navy (#1A237E) + basketball orange (#FF6F00) — see agents/design-agent.md

## API Rules

- `POST /api/results` requires `X-Admin-Key` header — static key from `.env`
- All route handlers must be async
- No `SELECT *` queries
- Response time targets: GET /stats < 200ms, POST /results < 2s
- CORS must be configured explicitly (not wildcard in production)

## Research Agent Rules

- Checkpoint file (`research/cache/research_progress.json`) updated after every team/matchup
- Failed lookups written to `research/cache/failed_lookups.json` — never silently dropped
- 1-2 second delay between web searches (rate limit protection)
- Subagents run 4 in parallel (one per region) — never 68 individual top-level agents
- Validation pass required before simulation: all 64 teams have power_index in [0,100], all 480 pairs exist

## Simulation Rules

- 51.5M brackets per region = 206M total
- Use stratified importance sampling (NOT naive Monte Carlo)
- Bracket storage: 15-bit packed SMALLINT + FLOAT weight + INT stratum_id
- Batch insert in chunks of 100K using COPY
- Verify champion distribution after simulation: 1-seeds must win ≥ 40% of region simulations

## Testing

Run before every phase transition:
```bash
pytest tests/                    # all unit tests
python -m simulation.encoder     # round-trip encode/decode test
python -m db.connection          # DB connectivity test
```

## Common Commands

```bash
# Start PostgreSQL
docker compose up -d

# Run research for all teams
python -m research.agent --year 2025 --phase teams

# Run matchup research
python -m research.agent --year 2025 --phase matchups

# Run simulation (one region)
python -m simulation.simulate --region South --year 2025

# Run simulation (all regions)
python -m simulation.simulate --all --year 2025

# Start API server
uvicorn api.main:app --reload --port 8000

# Start frontend
cd frontend && npm run dev
```

## Known Risks and Gotchas

- **Matchup symmetry:** Always look up matchup with `min(id_a, id_b)` as team_a — the DB has a CHECK constraint enforcing this but application code must also enforce it
- **Bit index mapping:** `(round, game_number) → game_index` is defined ONLY in `simulation/bracket_structure.py` — import from there, never re-define
- **Admin endpoint:** `POST /api/results` has no rate limiting — if exposed publicly, add one
- **3M bracket COPY:** PostgreSQL COPY from stdin; use `psycopg2.copy_expert` with a StringIO buffer
- **Weight normalization:** After each Bayesian round update, re-normalize weights so they sum to 1 across alive brackets
- **Blue-blood futures deflator:** Apply before any futures-based calibration check (D/K/UNC/KU get ×0.88-0.92 multiplier)
- **First Four:** Simulate before loading main bracket. 4 games. Winners replace placeholder in `2025_bracket.json`

## Agent Team Reference

| Agent | Role | Key Files |
|-------|------|-----------|
| Program Manager | Status, coordination, quality gates | agents/status/ |
| Lead SWE | Code review, performance, memory | agents/lead-swe-agent.md |
| Design Agent | UI/UX, frontend mockups | agents/design-agent.md |
| Elite Research Agent | ESPN/Reddit/YouTube research | agents/elite-research-agent.md |
| Math Agent | Sampling algorithm, statistics | agents/reports/math-agent-report.md |
| Stats Agent | Power index, historical data | agents/reports/stats-agent-report.md |
| Betting Agent | Market odds, upset factors | agents/reports/betting-agent-report.md |
| Research Validator | Fact-check, cross-reference all research | agents/research-validator-agent.md |
