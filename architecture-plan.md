Good. I now have a complete picture of the project. The directory is a clean slate with only the spec and Claude settings. Let me produce the full architecture plan.

---

# March Madness Bracket Simulation Engine — Deep Architecture Plan

## Table of Contents
1. Architecture Gaps and Risks
2. Refined File/Folder Structure
3. Agent Strategy for Phase 1
4. Database Design Review
5. Simulation Performance Plan
6. React Frontend Plan
7. Refined Sprint Breakdown
8. CLAUDE.md Recommendations

---

## 1. Architecture Gaps and Risks

### Gap 1: The 2025 Tournament Has Already Concluded

Today is March 6, 2026. The 2025 NCAA tournament ended in April 2025. The spec says "Test case: 2025 NCAA Tournament bracket (designed to be reusable for 2026+)." The 2026 tournament bracket will be announced in mid-March 2026 — approximately one week from now. This is actually ideal timing: build the system now against the 2025 bracket as a test harness, then swap in the 2026 bracket on Selection Sunday (March 15, 2026). The system must be parameterized so swapping the bracket is a single config change, not a code change.

**Risk:** If you target 2025 data with web searches, sources may return stale/inconsistent stats. Build research prompts to explicitly request the metric as-of a specific date (e.g., "KenPom efficiency margin for Duke as of March 15, 2025").

### Gap 2: Play-In Games (First Four)

The bracket has 68 teams, but the First Four reduces it to 64 before the main bracket begins. The spec treats this as a flat 68-team lookup but the simulation operates on 16-team regions. The First Four involves 4 games (2 games among the lowest-seeded at-large bids, 2 games among the 16-seeds). This is unspecified entirely.

**Decision needed:** Do you simulate the First Four games as part of the bracket, or do you hard-code the First Four winners and operate on 64 teams? The simpler and recommended approach is to pre-simulate the First Four separately (4 one-off matchup lookups), pick the winners probabilistically or deterministically, and feed those into the 64-team bracket. This means the `bracket_structure.py` file needs a `first_four` section.

### Gap 3: The Probability Matrix Inner Loop is Still Slow

The spec's pseudocode contains this warning inline:

```
probs = np.array([prob_matrix[(a, b)] for a, b in zip(team_a, team_b)])
# NOTE: This inner loop is slow — optimize with precomputed matrix below
```

But the "fix" (building a 16×16 NumPy matrix) is described for pre-computation, yet the simulation loop still iterates over `round_size` games one at a time. In Round 1 there are 8 games, and for each game, `team_a` and `team_b` are constant across all 10M simulations in Round 1 — because the Round 1 matchups are deterministic (1v16, 8v9, etc.). The teams only become variable in Round 2+. This means the inner probability lookup in Round 1 is just a scalar lookup, and the slow list comprehension only becomes a problem in Rounds 2-4 where team identities vary across simulations. The fix is to use NumPy advanced indexing: `probs = prob_matrix[team_a_indices, team_b_indices]` which is O(1) vectorized.

### Gap 4: Memory Budget for 40M Rows in RAM During Simulation

10M simulations × 15 games × 2 bytes (int16) = 300MB per region during the simulation phase. All 4 regions simultaneously would be 1.2GB. This is fine for a modern machine but must be accounted for. The spec suggests generating all random numbers upfront: `np.random.random((10_000_000, 15))` — that's 10M × 15 × 8 bytes (float64) = 1.2GB just for random numbers, per region. Use `np.float32` instead (600MB) or generate round-by-round.

**Recommended fix:** Generate random numbers one round at a time, not all 15 games upfront. This reduces peak memory from ~1.2GB to ~80MB per round.

### Gap 5: Matchup Cache Symmetry and Canonical Ordering

The spec says matchup_cache is keyed by `(team_a_id, team_b_id)` with a UNIQUE constraint, but doesn't specify canonical ordering. If you insert (Duke, Vermont) and later look up (Vermont, Duke), you'll get a cache miss. You need a canonical rule: always store with the lower `team_id` as `team_a`. The lookup function must enforce this by checking both orderings and flipping the probability: `P(B wins A) = 1 - P(A wins B)`. This is not implemented in the spec.

### Gap 6: The Bitwise Pruning SQL Has an Off-by-One Risk

The game_index in the bitpacked format must be consistent between the encoder (Python simulation), the database, and the pruner (API). The spec defines `game_index: 0-14`, but the game_results table also has `round` and `game_number` fields. There must be a single source of truth for the mapping `(round, game_number) -> game_index`. This mapping must live in `bracket_structure.py` and be used by all three systems. If any one of them uses a different mapping, pruning will silently eliminate the wrong brackets.

### Gap 7: No Authentication on Admin Endpoints

`POST /api/results` is the endpoint that triggers mass elimination of brackets. It has no authentication. Anyone who discovers the API can corrupt the tournament data. At minimum, a static API key passed in a header is needed. The spec mentions an "admin panel" in the UI but doesn't protect the API.

### Gap 8: No Idempotency on Result Entry

If a result is entered twice (e.g., user submits the same game result twice), the pruning query will run twice. The second run will find no alive brackets with the wrong bit (they were already eliminated) and do nothing harmful, but the `game_results` table will have a duplicate entry, and `daily_stats` will double-count. The `game_results` table needs a UNIQUE constraint on `(region, round, game_number)`.

### Gap 9: No Recovery Strategy for Partial Research Failures

The spec mentions 480 matchup lookups but doesn't specify what happens when a web search fails, returns garbage, or times out. With 480 individual research calls, some will fail. There's no retry table, no partial-completion tracking, no mechanism to re-run only the failed ones. Without this, a failure at matchup #350 means re-running the entire research phase.

### Gap 10: PostgreSQL COPY vs INSERT for 40M Rows

Batch INSERT at 100K rows per batch = 400 round trips for 40M rows. PostgreSQL COPY FROM is 10-50x faster for bulk loads. The spec mentions batch insert but doesn't mention COPY. At 40M rows this is the difference between a 2-minute load and a 30-minute load.

### Gap 11: No Tournament Year Parameterization

The spec is written for 2025 but designed to be reusable. However, the database schema has no `tournament_year` column anywhere. If you run this for 2026, the 2025 data is overwritten. Add `tournament_year INT NOT NULL DEFAULT 2025` to teams, matchup_cache, brackets, game_results, and daily_stats.

### Gap 12: React Build and Deployment Not Specified

The spec describes a React app but doesn't say how the frontend talks to the backend in development (proxy? CORS?), how it's built for production, or whether it's served by FastAPI as static files or a separate server. This needs a decision before Sprint 1.

### Gap 13: The "Matchup Adjustment" is Vague

The spec says matchup adjustment is "-10 to +10 modifier to base win probability." But win probability is between 0 and 1, and the adjustment is described as a point modifier on the power index scale (since the logistic function takes power index differentials). Is the adjustment applied to the power index differential before the logistic function, or is it a direct probability delta? These are very different: a +10 power index shift on a close matchup changes probability by ~15 points; a +10 probability delta on a 0.80 favorite pushes them to 0.90. The spec needs to define this precisely.

**Recommended:** The adjustment should be applied to the power index differential (before the logistic function), not to the probability directly. This keeps the probability bounded between 0 and 1 naturally.

---

## 2. Refined File/Folder Structure

```
march-prediction/
├── CLAUDE.md                          # Project conventions for Claude Code
├── README.md                          # Human-readable overview
├── .env.example                       # Environment variable template
├── .gitignore
├── docker-compose.yml                 # PostgreSQL + pgAdmin local dev
│
├── config/
│   ├── __init__.py
│   ├── settings.py                    # Pydantic BaseSettings — reads from .env
│   └── constants.py                   # Tournament year, region names, seed weightings
│
├── data/
│   ├── brackets/
│   │   ├── 2025_bracket.json          # 68 teams: name, seed, region, first_four flag
│   │   └── 2026_bracket.json          # Populated on Selection Sunday
│   └── seed_performance/
│       └── historical_seed_wins.json  # Historical seed win rates R64 through Final Four
│
├── db/
│   ├── __init__.py
│   ├── connection.py                  # SQLAlchemy engine + session factory
│   ├── migrations/
│   │   ├── 001_initial_schema.sql     # All CREATE TABLE statements
│   │   └── 002_add_indexes.sql        # All CREATE INDEX statements
│   └── models.py                      # SQLAlchemy ORM models
│
├── research/
│   ├── __init__.py
│   ├── agent.py                       # Orchestrates all research tasks
│   ├── team_researcher.py             # Per-team power index research
│   ├── matchup_researcher.py          # Per-pair matchup adjustment research
│   ├── probability.py                 # Logistic function, power index -> win prob
│   ├── prompts/
│   │   ├── team_research_prompt.txt   # Template for team power index web search
│   │   └── matchup_research_prompt.txt # Template for matchup analysis web search
│   ├── cache/
│   │   └── research_progress.json    # Tracks which teams/matchups are done (restart safety)
│   └── validators.py                  # Sanity checks on research output
│
├── simulation/
│   ├── __init__.py
│   ├── run_simulation.py              # Main entry point: python -m simulation.run_simulation
│   ├── engine.py                      # Vectorized NumPy simulation core
│   ├── probability_matrix.py          # Builds 16x16 matrix from matchup_cache
│   ├── storage.py                     # COPY-based bulk insert to PostgreSQL
│   ├── bracket_structure.py           # Canonical game ordering, (round,game)->game_index map
│   ├── encoder.py                     # encode_bracket / decode_bracket functions
│   └── validator.py                   # Verify champion distributions post-simulation
│
├── api/
│   ├── __init__.py
│   ├── main.py                        # FastAPI app factory, CORS, middleware
│   ├── dependencies.py                # DB session injection, auth token check
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── results.py                 # POST /api/results — enter game result
│   │   ├── brackets.py                # GET /api/stats, GET /api/brackets/sample
│   │   └── regions.py                 # GET /api/regions/:region
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pruner.py                  # Bitwise SQL elimination logic
│   │   └── stats.py                   # Alive counts, survival percentages
│   ├── schemas.py                     # Pydantic request/response models
│   └── auth.py                        # Static API key validation
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js                 # Vite build tool (faster than CRA)
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── api/
│       │   └── client.js              # Axios instance with base URL + auth header
│       ├── components/
│       │   ├── Dashboard.jsx
│       │   ├── RegionCard.jsx
│       │   ├── SurvivalChart.jsx      # Recharts line chart
│       │   ├── ResultEntry.jsx        # Admin form — protected by API key in localStorage
│       │   ├── BracketViewer.jsx      # Sample surviving bracket display (Sprint 5)
│       │   └── LoadingSpinner.jsx
│       ├── hooks/
│       │   ├── useStats.js            # Polling hook for /api/stats every 30s
│       │   └── useRegion.js           # Per-region data fetch
│       ├── store/
│       │   └── tournamentStore.js     # Zustand store for global state
│       └── styles/
│           └── index.css              # Tailwind CSS imports
│
├── scripts/
│   ├── run_research.sh                # Shell wrapper: python -m research.agent
│   ├── run_simulation.sh              # Shell wrapper: python -m simulation.run_simulation
│   ├── reset_db.sh                    # Drop + recreate all tables (dev only)
│   └── verify_simulation.py          # Champion distribution analysis
│
├── tests/
│   ├── __init__.py
│   ├── test_encoder.py               # encode/decode round-trip
│   ├── test_probability.py           # Logistic function edge cases
│   ├── test_pruner.py                # Pruning logic correctness
│   ├── test_simulation_small.py      # 1000-bracket smoke test
│   └── fixtures/
│       └── sample_matchup_cache.json
│
└── requirements.txt                   # Python dependencies
```

**Key additions over the spec:**
- `config/` separates settings from constants
- `data/brackets/` makes the bracket JSON the single source of truth
- `research/cache/research_progress.json` enables resumable research
- `research/prompts/` externalizes prompt templates for iteration
- `db/migrations/` makes schema changes trackable
- `simulation/encoder.py` isolates the bit-packing as a standalone testable unit
- `frontend/hooks/` and `frontend/store/` replace implicit state management
- `tests/` with specific unit tests for the three most dangerous modules

---

## 3. Agent Strategy for Phase 1

### The Research Volume Problem

The research phase requires:
- 68 team power index lookups
- 480 matchup pair analyses
- Total: 548 web search tasks

Doing these serially at ~30 seconds each = 4.5 hours. With parallelism this is a 15-20 minute job.

### Recommended Strategy: Tiered Parallel Subagents

**Tier 1: Team Research (68 tasks)**

Launch 4 parallel Claude Code subagents, each responsible for one region (17 teams each, including First Four teams). Each subagent:
1. Receives a JSON list of its 17 teams with seeds
2. Researches each team one at a time (web search per team)
3. Writes results to a region-specific staging file: `research/cache/south_teams.json`
4. Reports done

All 4 subagents run simultaneously. After all complete, the orchestrator reads the 4 staging files, validates them, normalizes power indices to a consistent scale, and bulk-inserts into PostgreSQL.

Why per-region rather than interleaved? It keeps each subagent's context window focused. A subagent handling 68 teams serially will exhaust its context before finishing. 17 teams per subagent is manageable.

**Tier 2: Matchup Research (480 tasks)**

After Tier 1 completes (power indices are in the DB), launch 4 parallel subagents — one per region — each handling 120 matchup pairs. Each subagent:
1. Reads its region's team list from the DB (or staging files)
2. Iterates through all C(16,2)=120 pairs in a fixed order
3. For each pair: web search, compute adjustment, write to `research/cache/south_matchups.json`
4. Checks `research_progress.json` before each pair to skip already-completed ones (idempotent restart)

**Batching within each subagent:** Do not research all 120 pairs in one shot. Process in batches of 20-30. After each batch, flush results to the staging file. This makes the subagent restartable mid-way.

**Rate limit handling:**
- Between each web search call, add a 1-2 second delay (`time.sleep(1)`)
- If a web search returns an error or timeout, log the failure to `research/cache/failed_lookups.json` and continue
- After all pairs are done, a recovery subagent re-runs only the entries in `failed_lookups.json`

**Validation pass:**
After all research completes, run `research/validators.py`:
- Every team has a power_index in [0, 100]
- Every matchup pair exists in the cache (check for 480 rows)
- No win probability is exactly 0 or 1 (would break simulation)
- Power index rankings roughly correlate with seeds (1-seeds should be top-4 in their region)

**Prompt templates** (stored in `research/prompts/`):

For team research, the prompt must request specific structured output:
```
Search for current {team_name} NCAA basketball statistics for the {year} tournament.
Return ONLY a JSON object with these exact fields:
- efficiency_margin: float (KenPom adjusted efficiency margin, typical range -10 to +35)
- sos_rank: int (strength of schedule rank among all D1 teams, 1=hardest)
- last_10_wins: int (wins in last 10 games)
- last_10_losses: int (losses in last 10 games)
- offensive_efficiency: float (adjusted offensive efficiency, typical range 95-125)
- defensive_efficiency: float (adjusted defensive efficiency, lower is better, typical range 85-110)
- injuries: str (description of any key injuries, or "none significant")
- notes: str (1-2 sentence analyst summary)
Do not include any text before or after the JSON.
```

Structured output with explicit type hints and valid ranges dramatically reduces the need for post-processing.

### The Normalization Problem

Different web sources will report KenPom efficiency margin in different units and scales. The power index formula must normalize each factor independently before combining. Define expected ranges for each factor in `config/constants.py` and apply min-max normalization:

```
normalized = (raw - min_expected) / (max_expected - min_expected) * 100
```

These ranges should be set conservatively (e.g., efficiency_margin from -15 to +35) so outliers get clamped to 0 or 100 rather than causing the power index to go negative or above 100.

---

## 4. Database Design Review

### Schema Improvements

**Add tournament_year everywhere:**
```sql
-- On every table:
tournament_year INT NOT NULL DEFAULT 2026,
```
This allows re-use across years without dropping data.

**Canonical matchup ordering:**
```sql
CREATE TABLE matchup_cache (
    id SERIAL PRIMARY KEY,
    tournament_year INT NOT NULL DEFAULT 2026,
    team_a_id INT REFERENCES teams(id),  -- always the team with lower id
    team_b_id INT REFERENCES teams(id),  -- always the team with higher id
    ...
    UNIQUE(tournament_year, team_a_id, team_b_id),
    CHECK (team_a_id < team_b_id)         -- enforce canonical ordering
);
```

The CHECK constraint prevents accidentally inserting (Vermont, Duke) when (Duke, Vermont) exists. The application layer must sort before inserting.

**Brackets table — partitioning:**

40M rows in a single table is manageable in PostgreSQL (it regularly handles billions), but query performance for "UPDATE WHERE region='South' AND is_alive=TRUE" benefits from partitioning by region. Use declarative partitioning:

```sql
CREATE TABLE brackets (
    id BIGSERIAL,
    tournament_year INT NOT NULL DEFAULT 2026,
    region VARCHAR(20) NOT NULL,
    results SMALLINT NOT NULL,
    is_alive BOOLEAN DEFAULT TRUE,
    eliminated_round INT DEFAULT NULL,
    eliminated_day INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (id, region)
) PARTITION BY LIST (region);

CREATE TABLE brackets_south    PARTITION OF brackets FOR VALUES IN ('South');
CREATE TABLE brackets_east     PARTITION OF brackets FOR VALUES IN ('East');
CREATE TABLE brackets_west     PARTITION OF brackets FOR VALUES IN ('West');
CREATE TABLE brackets_midwest  PARTITION OF brackets FOR VALUES IN ('Midwest');
```

Each partition is 10M rows (~50-80MB on disk). Pruning queries hit exactly one partition. Index sizes drop by 4x per partition.

**Indexes:**

```sql
-- Partition-local indexes (created on each partition automatically in PG14+)
CREATE INDEX idx_brackets_alive ON brackets(is_alive) WHERE is_alive = TRUE;
-- Partial index — only indexes alive brackets, shrinks dramatically as tournament progresses

CREATE INDEX idx_brackets_results ON brackets(results);
-- Enables fast bitwise filtering if PostgreSQL decides a full scan is needed

CREATE INDEX idx_game_results_unique ON game_results(tournament_year, region, round, game_number) UNIQUE;

CREATE INDEX idx_teams_region_year ON teams(tournament_year, region, seed);

CREATE INDEX idx_daily_stats_day ON daily_stats(tournament_year, day, region);
```

**SMALLINT sufficiency check:**

15 bits fits in a SMALLINT (16-bit signed, range -32768 to 32767). But bit 15 (0-indexed) of a signed SMALLINT is the sign bit. Since we only use bits 0-14, we never touch bit 15 and never go negative. This is safe, but the application must treat the SMALLINT as unsigned in all bitwise operations. In Python, always cast to `int` (arbitrary precision) before bit manipulation. PostgreSQL's bitwise operators on SMALLINT use signed arithmetic — `(results & (1 << 14))` will work correctly since bit 14 = 16384, well within SMALLINT range.

**game_results — add constraint:**

```sql
CREATE TABLE game_results (
    id SERIAL PRIMARY KEY,
    tournament_year INT NOT NULL DEFAULT 2026,
    region VARCHAR(20) NOT NULL,
    round INT NOT NULL CHECK (round BETWEEN 1 AND 4),
    game_number INT NOT NULL CHECK (game_number BETWEEN 1 AND 8),
    game_index INT NOT NULL CHECK (game_index BETWEEN 0 AND 14),
    team_a_id INT REFERENCES teams(id),
    team_b_id INT REFERENCES teams(id),
    winner_id INT REFERENCES teams(id),
    winner VARCHAR(100) NOT NULL,
    result_bit INT NOT NULL CHECK (result_bit IN (0, 1)),
    entered_at TIMESTAMP DEFAULT NOW(),
    day INT NOT NULL CHECK (day >= 0),
    UNIQUE(tournament_year, region, round, game_number)  -- no duplicate results
);
```

**daily_stats — denormalized for read performance:**

The `daily_stats` table is queried on every page load. Pre-compute and cache it:
```sql
CREATE TABLE daily_stats (
    id SERIAL PRIMARY KEY,
    tournament_year INT NOT NULL DEFAULT 2026,
    day INT NOT NULL,
    region VARCHAR(20),  -- NULL for aggregate across all regions
    alive_count BIGINT NOT NULL,
    total_count BIGINT NOT NULL,
    snapshot_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tournament_year, day, region)
);
```

After each pruning operation, immediately INSERT or UPDATE daily_stats for the current day. This means `/api/stats` is a single fast SELECT with no aggregation.

---

## 5. Simulation Performance Plan

### Do NOT Store 40M Individual Brackets in PostgreSQL

This is the most important architectural recommendation departing from the spec.

Storing 40M rows is feasible technically, but the ongoing maintenance cost is high:
- Loading 40M rows via COPY takes 3-8 minutes
- The is_alive update index must be maintained across 40M rows
- Database backup/restore of 80MB of bracket data adds complexity
- The only operation on this table is UPDATE (pruning) and COUNT — no per-row reads

**Alternative: Store Aggregated Histograms**

Instead of storing each bracket individually, store the count of brackets for each unique bitpacked result. There are at most 2^15 = 32,768 unique bracket patterns per region. The number of distinct patterns that actually appear across 10M simulations will be far fewer (many patterns are impossible given bracket structure constraints), but in the worst case:

```sql
CREATE TABLE bracket_histogram (
    id SERIAL PRIMARY KEY,
    tournament_year INT NOT NULL DEFAULT 2026,
    region VARCHAR(20) NOT NULL,
    results SMALLINT NOT NULL,          -- the 15-bit pattern
    count INT NOT NULL,                 -- how many of the 10M brackets have this pattern
    is_alive BOOLEAN DEFAULT TRUE,
    UNIQUE(tournament_year, region, results)
);
```

This table has at most 4 × 32,768 = 131,072 rows — negligible size. Pruning becomes:

```sql
UPDATE bracket_histogram
SET is_alive = FALSE
WHERE tournament_year = 2026
  AND region = 'South'
  AND is_alive = TRUE
  AND (results & (1 << :game_index)) != :expected_bit_value;
```

Survival count becomes:
```sql
SELECT SUM(count) FROM bracket_histogram
WHERE tournament_year = 2026 AND region = 'South' AND is_alive = TRUE;
```

This query runs in milliseconds on 131K rows vs. seconds on 10M rows.

**Simulation generates the histogram directly:**

```python
# After generating all 10M results as a NumPy array
packed = encode_all_brackets(results_array)  # shape: (10_000_000,)
unique_patterns, counts = np.unique(packed, return_counts=True)
# unique_patterns is at most 32768 elements
# Insert these into bracket_histogram instead of 10M individual rows
```

This is dramatically simpler, faster, and more maintainable. The only thing you lose is the ability to display "a sample surviving bracket" — but you can reconstruct a sample by randomly selecting from alive patterns weighted by their counts.

**If you insist on individual bracket storage** (for "show me a random surviving bracket" features), use the hybrid approach: store the histogram for pruning and counting, and separately store a random sample of 100K brackets for display purposes.

### Simulation Execution Plan

**Memory-efficient round-by-round approach:**

```
Per region:
  1. Load 16x16 probability matrix into memory (trivial size)
  2. Generate 10M initial bracket states (seed ordering array) - 10M x 16 x 2 bytes = 320MB
  3. Round 1 (8 games):
     a. For each of 8 games, team_a and team_b are constant across all 10M sims
     b. Generate 10M random numbers per game: np.random.random(10_000_000)
     c. Apply single probability: winners = np.where(rand < prob_scalar, team_a_idx, team_b_idx)
     d. Record results bits: results[:, game_index] = (winners != expected_winner)
  4. Round 2 (4 games): team identities now vary — use prob_matrix[team_a, team_b] with vectorized indexing
  5. Rounds 3-4: same as Round 2
  6. Aggregate into histogram: np.unique(packed_results, return_counts=True)
  7. Discard the large results array, keep only the histogram (< 1MB)
```

Peak memory per region: ~500MB (manageable). Process one region at a time. Total wall time: under 5 minutes for all 40M simulations.

### COPY vs INSERT

Use PostgreSQL COPY for bulk loading. In Python with psycopg2:

```python
import io
buf = io.StringIO()
for pattern, count in zip(unique_patterns, counts):
    buf.write(f"{year}\t{region}\t{int(pattern)}\t{int(count)}\n")
buf.seek(0)
cursor.copy_from(buf, 'bracket_histogram', 
                 columns=('tournament_year', 'region', 'results', 'count'))
```

For the histogram approach, this is at most 131K rows per region — essentially instantaneous.

---

## 6. React Frontend Plan

### Technology Choices

**Build tool: Vite** (not Create React App)
CRA is deprecated and slow. Vite starts in < 1 second, has native ESM, and produces smaller bundles. Use `npm create vite@latest frontend -- --template react`.

**Styling: Tailwind CSS**
Zero-config utility classes. No CSS files to maintain. Works well with Vite. Alternatively, shadcn/ui components on top of Tailwind for pre-built accessible components.

**Charting: Recharts**
Purpose-built for React, small bundle (~110KB), composable. The SurvivalChart is a LineChart with a custom tooltip. Alternative: Nivo (heavier but more polished).

**State management: Zustand**
The spec has one shared state concern: the stats data (alive counts by region and day). Zustand is 1KB, zero boilerplate, no Provider needed. This is appropriate for a small dashboard. Do NOT use Redux — it's excessive here.

**API communication: Axios with React Query**
React Query (TanStack Query) handles polling, caching, loading states, and error states automatically. Replace the manual `useStats.js` polling hook with:

```js
const { data: stats, isLoading } = useQuery({
  queryKey: ['stats', year],
  queryFn: () => api.getStats(year),
  refetchInterval: 30_000,  // poll every 30 seconds
  staleTime: 25_000,
});
```

This eliminates the need to write polling logic manually and gives automatic background refresh.

**Admin authentication:**
Store the API key in `localStorage` under key `mm_admin_key`. The ResultEntry component reads it and includes it as a header. Add a simple login form that prompts for the key on first access. Do NOT hard-code the key in source.

### State Architecture

Global Zustand store (`tournamentStore.js`):
```
{
  year: 2026,
  stats: { day, total_alive, by_region, history },
  selectedRegion: null,
  adminKey: null,
  setAdminKey: fn,
  setSelectedRegion: fn,
}
```

React Query handles all fetching. The Zustand store holds UI state only (selected region, admin key). Stats data lives in the React Query cache.

### Real-Time Update Flow

1. Admin submits game result via ResultEntry form
2. `POST /api/results` fires → server runs pruning SQL → updates daily_stats
3. Response includes updated alive counts
4. React Query `invalidateQueries(['stats'])` is called → triggers immediate refetch
5. All components subscribed to stats re-render with new counts
6. SurvivalChart gains a new data point

No WebSockets needed. The admin is the only person entering results, and they're at the same keyboard. Simple POST-then-invalidate is sufficient.

### Component Breakdown

**Dashboard.jsx** — Page layout only. Renders header, SurvivalChart, 4x RegionCard, ResultEntry.

**RegionCard.jsx** — Props: `{ region, alive, total }`. Displays percentage bar and counts. Color changes: green > 10%, yellow 1-10%, red < 1%.

**SurvivalChart.jsx** — Props: `{ history: [{day, alive}] }`. Recharts LineChart. X-axis: tournament days (labeled "Day 1", "Day 2", etc.). Y-axis: bracket count with K/M formatting. Tooltip shows exact count and percentage.

**ResultEntry.jsx** — Controlled form with 4 fields:
1. Year (default: current year, can be changed)
2. Region (dropdown: South, East, West, Midwest)
3. Round (dropdown: 1-4, labels "Round of 64" etc.)
4. Game (dropdown: populated based on region+round from bracket_structure)
5. Winner (radio or dropdown: shows the two teams for that game)

On submit: POST to API, show success/error toast, invalidate queries.

**BracketViewer.jsx** — Sprint 5. Fetches a random alive bracket from `/api/brackets/sample?region=South`, renders the 15 games in a visual tree.

### CORS Configuration

FastAPI must allow the React dev server origin during development. In `main.py`:
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["X-Admin-Key", "Content-Type"],
)
```

In production, FastAPI serves the built React app as static files from `frontend/dist/`. No CORS needed in production.

---

## 7. Refined Sprint Breakdown

### Pre-Sprint: Gather Inputs (Day 0 — Do This First)

These block everything else. Do not write a line of code until these are resolved.

| Task | Input | Output | Blocker? |
|------|-------|--------|----------|
| Confirm tournament year | Calendar (today is March 6, 2026) | Year = 2026, bracket available March 15 | Yes — blocks all research |
| Confirm PostgreSQL credentials | User provides | `.env` file | Yes — blocks all DB work |
| Confirm 68-team bracket | Wait for Selection Sunday (March 15) OR use 2025 data | `data/brackets/2026_bracket.json` | Yes — blocks research |
| Confirm power index weights | User confirms or modifies | `config/constants.py` weights | Soft — defaults are fine |

---

### Sprint 1: Foundation (2-3 days)

All tasks can start in parallel after Pre-Sprint.

**Task 1.1: Project scaffold**
- Input: Spec
- Output: Full directory tree created, `requirements.txt`, `package.json`, `.env.example`, `.gitignore`, `docker-compose.yml`
- Dependencies: None
- Parallel: Yes

**Task 1.2: Database setup**
- Input: PostgreSQL credentials
- Output: All tables created via `db/migrations/001_initial_schema.sql`, connection tested
- Dependencies: PostgreSQL credentials
- Parallel: Yes (with 1.1)

**Task 1.3: Config and constants**
- Input: Confirmed weights, region names, tournament year
- Output: `config/settings.py`, `config/constants.py` with all weights, region list, seed ordering
- Dependencies: None
- Parallel: Yes (with 1.1, 1.2)

**Task 1.4: bracket_structure.py**
- Input: 68-team bracket JSON, NCAA bracket seeding rules
- Output: `simulation/bracket_structure.py` with seed ordering per region, First Four designation, `(round, game_number) -> game_index` mapping (this is the canonical map used by everyone)
- Dependencies: Task 1.3 (uses constants)
- Parallel: Can start before 1.2 completes

**Task 1.5: encoder.py + tests**
- Input: bracket_structure.py
- Output: `simulation/encoder.py` with encode/decode, `tests/test_encoder.py` with round-trip tests
- Dependencies: Task 1.4
- Parallel: No dependency on 1.2

**Sprint 1 exit criteria:** `pytest tests/test_encoder.py` passes. `python -c "from db.connection import engine; print('DB OK')"` works.

---

### Sprint 2: Research Agent (3-5 days)

**Task 2.1: Research infrastructure**
- Input: `requirements.txt` (add `tenacity` for retries)
- Output: `research/agent.py` orchestrator, `research_progress.json` schema, `research/validators.py`
- Dependencies: Sprint 1 complete, bracket JSON ready
- Parallel: With 2.2

**Task 2.2: Team researcher**
- Input: `research/prompts/team_research_prompt.txt`, team list from bracket JSON
- Output: `research/team_researcher.py` — web search, JSON parse, power index calculation, DB insert
- Dependencies: Task 1.2 (DB tables), Task 1.3 (weights)
- Parallel: With 2.1

**Task 2.3: Matchup researcher**
- Input: `research/prompts/matchup_research_prompt.txt`
- Output: `research/matchup_researcher.py` — pair enumeration, web search, matchup adjustment, canonical ordering, DB insert
- Dependencies: Task 2.2 must define canonical pair ordering
- Parallel: Can start writing while 2.2 runs (depends on schema, not on data)

**Task 2.4: Probability module**
- Input: Logistic formula from spec, matchup adjustment definition (gap #13 resolved)
- Output: `research/probability.py` with logistic function, test cases for edge cases (equal teams, huge favorites)
- Dependencies: Task 2.1
- Parallel: Can run entirely in parallel with 2.2 and 2.3

**Task 2.5: Execute team research (68 teams)**
- Input: 4 parallel subagents, one per region
- Output: 68 rows in `teams` table, staging JSON files per region
- Dependencies: Tasks 2.1, 2.2, 1.4
- Sequential after 2.2 is built

**Task 2.6: Validate team research**
- Input: Teams table
- Output: Validation report — power indices in range, seed-rank correlation check
- Dependencies: Task 2.5
- Must run before 2.7

**Task 2.7: Execute matchup research (480 pairs)**
- Input: 4 parallel subagents, teams table populated
- Output: 480 rows in `matchup_cache`
- Dependencies: Task 2.6 (validated teams), Task 2.3 (matchup researcher built)
- Sequential after validation

**Task 2.8: Validate matchup research**
- Input: matchup_cache table
- Output: Confirm 480 rows, no probability at 0 or 1, symmetric pair coverage
- Dependencies: Task 2.7

**Sprint 2 exit criteria:** `SELECT COUNT(*) FROM teams` = 68. `SELECT COUNT(*) FROM matchup_cache` = 480. All probabilities in [0.01, 0.99].

---

### Sprint 3: Simulation Engine (2-3 days)

**Task 3.1: Probability matrix builder**
- Input: matchup_cache table
- Output: `simulation/probability_matrix.py` — reads from DB, builds 16x16 NumPy array per region
- Dependencies: Sprint 2 complete
- Parallel: With 3.2

**Task 3.2: Simulation engine**
- Input: bracket_structure.py, probability_matrix.py
- Output: `simulation/engine.py` — vectorized NumPy engine, histogram output (not individual bracket array)
- Dependencies: Task 1.5 (encoder), Task 3.1 (probability matrix)
- This is the most critical implementation task — allocate the most time here

**Task 3.3: Storage layer**
- Input: histogram output from engine
- Output: `simulation/storage.py` — COPY-based insert into `bracket_histogram` table
- Dependencies: Task 3.2 (defines output format)
- Parallel: Can design while 3.2 is written

**Task 3.4: Smoke test — South region, 100K simulations**
- Input: Tasks 3.1-3.3 complete
- Output: `bracket_histogram` populated for South with 100K sims, champion distribution checked
- Dependencies: All of 3.1-3.3
- This is the integration test before running full 40M

**Task 3.5: Distribution validator**
- Input: `scripts/verify_simulation.py`
- Output: Report showing % of South brackets where seed 1 wins > seed 2 wins > ... > seed 16 wins (should hold statistically)
- Dependencies: Task 3.4
- Must pass before 3.6

**Task 3.6: Full simulation — all 4 regions × 10M**
- Input: All prior tasks validated
- Output: `bracket_histogram` fully populated (4 regions × up to 32,768 unique patterns × count)
- Dependencies: Task 3.5
- Estimated runtime: 3-10 minutes

**Sprint 3 exit criteria:** 4 entries in `SELECT COUNT(DISTINCT region) FROM bracket_histogram`. `SELECT SUM(count) FROM bracket_histogram WHERE region='South'` = exactly 10,000,000. Seed 1 teams have > 30% championship probability.

---

### Sprint 4: Tracker Website (4-5 days)

**Task 4.1: FastAPI skeleton**
- Input: `api/` structure
- Output: `api/main.py` with CORS, `api/dependencies.py` with DB session and auth
- Dependencies: Sprint 1 (config, DB)
- Parallel: With 4.5

**Task 4.2: Stats service**
- Input: daily_stats table, bracket_histogram table
- Output: `api/services/stats.py` — alive counts, history, by-region breakdown
- Dependencies: Task 4.1
- Parallel: With 4.3

**Task 4.3: Pruner service**
- Input: bracket_histogram table, game_results table, bracket_structure.py (for game_index lookup)
- Output: `api/services/pruner.py` — bitwise UPDATE on bracket_histogram, insert into game_results, update daily_stats. `tests/test_pruner.py`
- Dependencies: Task 4.1, Task 1.4 (game_index mapping)
- This is high-risk — write tests first

**Task 4.4: API routes**
- Input: Tasks 4.2, 4.3, `api/schemas.py`
- Output: `api/routes/results.py`, `api/routes/brackets.py`, `api/routes/regions.py`
- Dependencies: Tasks 4.2, 4.3
- Parallel: With 4.5

**Task 4.5: React scaffold**
- Input: Vite template
- Output: Vite project initialized, Tailwind configured, React Query configured, Axios client configured, Zustand store created
- Dependencies: None (can start Day 1 of Sprint 4)
- Parallel: With 4.1-4.4

**Task 4.6: Dashboard and RegionCards**
- Input: Task 4.5 scaffold, Task 4.4 API (or mock data)
- Output: Dashboard.jsx, RegionCard.jsx rendering with mock data
- Dependencies: Task 4.5
- Parallel: Can use mock data before API is ready

**Task 4.7: SurvivalChart**
- Input: Recharts, daily_stats shape from API
- Output: SurvivalChart.jsx with working line chart, day labels, percentage tooltip
- Dependencies: Task 4.5
- Parallel: With 4.6

**Task 4.8: ResultEntry admin form**
- Input: bracket_structure.py game list, API schemas, auth flow
- Output: ResultEntry.jsx — full form, localStorage API key, POST on submit, invalidate queries
- Dependencies: Tasks 4.4, 4.6
- Test: manually enter a result, verify pruning fires

**Task 4.9: End-to-end integration test**
- Sequence: Enter 8 results for Day 1 of South region. Verify alive count drops correctly. Verify SurvivalChart adds a data point. Verify eliminated brackets match expected count mathematically.
- Dependencies: All of 4.1-4.8

**Sprint 4 exit criteria:** Can enter real game results via the UI and see the alive bracket count drop. The SurvivalChart updates in the same browser session.

---

### Sprint 5: Polish + Final Four (Future)

**Task 5.1: Final Four matchup research**
- 4 new team pairings (regional champions, which are probabilistic — use top-2 most likely champions from each region as the 4 "expected" matchups to research, then handle actuals during tournament)

**Task 5.2: Final Four + Championship simulation**
- Extend bracket_structure.py with 3 additional game slots (game_index 15-17)
- Extend bracket_histogram with 3 additional bits
- SMALLINT is now too small (18 bits) — use INT (4 bytes) instead. Plan for this now.

**Task 5.3: Full 63-game bracket tracking**
- Merges regional simulations into full-bracket simulations
- Requires cross-region matchup research for Final Four pairs

**Task 5.4: Most common surviving bracket analysis**
- Query: `SELECT results, count FROM bracket_histogram WHERE is_alive=TRUE ORDER BY count DESC LIMIT 10`
- Decode each result and display as a human-readable bracket path

**Task 5.5: Export functionality**
- CSV export of all alive bracket patterns with counts
- PDF bracket visualization of the most likely surviving bracket

---

## 8. CLAUDE.md Recommendations

The following content should go in `/Users/toanhuynh/Desktop/toan code/march prediction/CLAUDE.md`. This is what Claude Code reads at the start of every session.

---

### Section 1: Project Identity

```
# March Madness Bracket Simulation Engine

## What this project does
Simulates 10 million NCAA tournament bracket outcomes per region (40M total) using
Monte Carlo methods, then tracks which simulated brackets survive as real tournament
results come in.

## Current status
[Update this at the start of each sprint]
- Sprint 1: COMPLETE
- Sprint 2: IN PROGRESS — matchup research 240/480 pairs done
- Sprint 3: NOT STARTED
- Sprint 4: NOT STARTED

## Tournament year
2026. Selection Sunday is March 15, 2026. Bracket JSON: data/brackets/2026_bracket.json
```

### Section 2: Architecture Decisions

```
## Critical architectural decisions

### Storage: histogram, not individual brackets
We store bracket_histogram (unique bit patterns + counts), NOT 40M individual bracket rows.
Max 32,768 unique patterns per region. Pruning and counting are instant on this table.
NEVER suggest switching to individual row storage.

### Canonical matchup ordering
matchup_cache always stores (team_a_id, team_b_id) with team_a_id < team_b_id.
P(team_b wins) = 1 - adjusted_win_prob_a. Enforced by CHECK constraint.
The research code must sort before insert. The lookup code must handle both orderings.

### Game index mapping
The ONLY authoritative source for (round, game_number) -> game_index is:
simulation/bracket_structure.py: GAME_INDEX_MAP
Never hardcode game indices anywhere else. Always import from this module.

### Matchup adjustment
The matchup_adjustment is applied to the POWER INDEX DIFFERENTIAL before the logistic
function, not to the probability directly.
Formula: P(A wins) = 1 / (1 + 10^((power_B - power_A + adjustment) / 15))
Adjustment range: -10 to +10 (positive means A is favored more than raw power suggests).

### First Four
The First Four involves 4 games among 8 teams that produce 4 bracket entrants.
These are handled as pre-bracket coin flips using matchup_cache.
After First Four simulation, the bracket operates on exactly 64 teams (16 per region).
```

### Section 3: Python Conventions

```
## Python conventions

### Package management
Use requirements.txt (not pyproject.toml). Pin all versions.
Key packages: numpy, psycopg2-binary, fastapi, uvicorn, pydantic-settings, tenacity

### Environment variables
All config comes from .env via config/settings.py (Pydantic BaseSettings).
NEVER hardcode credentials, URLs, or the tournament year.
The .env file is gitignored. Copy .env.example and fill in values.

### Database access
Always use the session factory from db/connection.py.
Never create raw psycopg2 connections outside of db/connection.py and simulation/storage.py.
Use COPY (via cursor.copy_from) for bulk inserts, never executemany for large batches.

### NumPy simulation rules
- Generate random numbers per-round, not per-bracket
- Use np.float32 for random arrays (not float64) to halve memory usage
- Use vectorized indexing: prob_matrix[team_a_arr, team_b_arr] — never zip/list-comprehension
- Output from engine.py must be a histogram dict {pattern: count}, not a raw bracket array

### Error handling in research
Use tenacity @retry with exponential backoff for all web search calls.
Log failures to research/cache/failed_lookups.json (append mode).
Never crash the entire research run on a single lookup failure.
```

### Section 4: React Conventions

```
## React/Frontend conventions

### Stack
- Vite (not CRA), React 18, Tailwind CSS, Recharts, React Query (TanStack Query), Zustand, Axios

### State rules
- Server state (stats, region data): React Query cache only
- UI state (selected region): Zustand store
- Never store fetched data in useState — use React Query

### API calls
All API calls go through frontend/src/api/client.js (Axios instance).
The admin API key is stored in localStorage key 'mm_admin_key' and injected by the client.
Never use fetch() directly — always use the client module.

### Component rules
- Each component file exports one named export (not default export)
- Props must be destructured in the function signature
- No inline styles — Tailwind classes only

### Build and serve
Dev: npm run dev (port 5173)
Production: npm run build → FastAPI serves frontend/dist/ as static files
```

### Section 5: Database Rules

```
## Database rules

### Never modify these tables during tournament play
- teams
- matchup_cache
- bracket_histogram (only is_alive can change — via pruner only)

### Table ownership
- research/ writes to: teams, matchup_cache
- simulation/ writes to: bracket_histogram
- api/ writes to: game_results, daily_stats
- api/ updates: bracket_histogram.is_alive (pruner only)
No code should write to tables owned by another phase.

### Migration rules
Schema changes go in db/migrations/ as numbered SQL files.
Never ALTER TABLE in application code. Always write a migration file.

### tournament_year
Every table has tournament_year. Always include it in WHERE clauses.
The current year is in config/constants.py: TOURNAMENT_YEAR.
```

### Section 6: Testing

```
## Testing

### Run tests
pytest tests/ -v

### Required tests to pass before each sprint exit
Sprint 1: tests/test_encoder.py
Sprint 2: tests/test_probability.py
Sprint 3: tests/test_simulation_small.py (1000-bracket smoke test)
Sprint 4: tests/test_pruner.py

### Test data
Use fixtures/sample_matchup_cache.json for offline testing.
Never hit the real DB in unit tests — use pytest fixtures with in-memory SQLite where possible.
```

### Section 7: Common Commands

```
## Common commands

# Start PostgreSQL (local dev)
docker-compose up -d

# Run research (all 68 teams)
bash scripts/run_research.sh

# Run simulation (all 4 regions)
bash scripts/run_simulation.sh

# Verify simulation results
python scripts/verify_simulation.py

# Start API server
uvicorn api.main:app --reload --port 8000

# Start frontend dev server
cd frontend && npm run dev

# Reset database (CAUTION: destroys all data)
bash scripts/reset_db.sh
```

### Section 8: Known Risks and Gotchas

```
## Known risks and gotchas

1. SMALLINT bit limit: bits 0-14 are safe. If Sprint 5 adds Final Four (3 more games),
   switch results column to INT before inserting any Final Four data.

2. Research subagents share a database: use INSERT ... ON CONFLICT DO NOTHING for all
   research inserts so parallel subagents don't collision.

3. Pruning idempotency: running pruner twice for the same game result is safe
   (second run affects 0 rows) but game_results has a UNIQUE constraint that will
   raise an error on duplicate result entry. Handle this at the API layer.

4. Power index normalization: each research subagent normalizes independently.
   The final normalization pass (scaling to 0-100) must happen AFTER all 68 teams
   are researched, not during per-team research. Per-team, store raw factor values.

5. The simulator assumes tournament bracket structure never changes.
   If a region has fewer than 16 teams due to First Four, pad the bracket with byes.
```

---

## Summary: The Three Biggest Bets

1. **Histogram storage over row storage.** The switch from 40M individual rows to a 32K-row histogram is the highest-impact decision in the plan. It makes the simulation 10x simpler, the DB 1000x smaller, and pruning queries 100x faster. The only downside is you lose the ability to query individual brackets by ID — but that use case doesn't exist in the spec.

2. **Parallel research subagents with resumability.** The 548-task research phase is the most failure-prone part of the system. The `research_progress.json` checkpoint file is essential. Without it, any failure during the 4-hour research phase means starting over.

3. **Single canonical game index map.** The `(round, game_number) -> game_index` mapping is used in three places: the encoder (simulation), the pruner (API), and the ResultEntry form (frontend). If any one of them diverges, bracket data is silently corrupted. Making `bracket_structure.py` the single source of truth and importing it everywhere (or serializing it for the frontend) prevents this class of bug entirely.

---

### Critical Files for Implementation

- `/Users/toanhuynh/Desktop/toan code/march prediction/march-madness-plan.md` - Original spec: read this for all domain details, especially the logistic formula, bit encoding scheme, and pruning SQL logic — these are load-bearing and must be implemented exactly as specified (with the matchup adjustment correction noted above)
- `/Users/toanhuynh/Desktop/toan code/march prediction/simulation/bracket_structure.py` - (to be created) The canonical `GAME_INDEX_MAP` dictionary lives here and is the single source of truth used by encoder, pruner, and frontend form — this is the highest-risk integration point in the entire system
- `/Users/toanhuynh/Desktop/toan code/march prediction/simulation/engine.py` - (to be created) The vectorized NumPy simulation core — performance-critical, must use `np.float32` arrays, per-round random generation, and `np.unique` for histogram output rather than storing individual brackets
- `/Users/toanhuynh/Desktop/toan code/march prediction/api/services/pruner.py` - (to be created) The bitwise SQL pruner — correctness-critical, must import game_index from bracket_structure.py, must be wrapped in a database transaction with the game_results insert, and must update daily_stats atomically
- `/Users/toanhuynh/Desktop/toan code/march prediction/db/migrations/001_initial_schema.sql` - (to be created) Foundation for everything — must include tournament_year on every table, the CHECK constraint on matchup_cache for canonical ordering, list partitioning on brackets (or bracket_histogram), and the UNIQUE constraint on game_results to prevent duplicate result entry

agentId: a658028e038e63047 (for resuming to continue this agent's work if needed)
<usage>total_tokens: 32592
tool_uses: 6
duration_ms: 302077</usage>