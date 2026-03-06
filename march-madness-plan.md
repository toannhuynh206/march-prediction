# March Madness Bracket Simulation Engine — Claude Code Spec

## Project Overview

Build an end-to-end March Madness bracket prediction system that:
1. Researches and power-ranks all 68 tournament teams
2. Simulates 10 million brackets per region (40M total) using Monte Carlo methods
3. Serves a React website that tracks bracket survival day-by-day as real results come in

**Test case:** 2025 NCAA Tournament bracket (designed to be reusable for 2026+).

---

## Architecture Summary

```
┌──────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│  PHASE 1          │     │  PHASE 2              │     │  PHASE 3             │
│  Research Agent    │────▶│  Bracket Simulator     │────▶│  Tracker Website     │
│                    │     │                        │     │                      │
│  - Web search      │     │  - Monte Carlo engine  │     │  - React frontend    │
│  - Power index     │     │  - 10M per region      │     │  - Day-by-day pruning│
│  - Matchup cache   │     │  - Bottom-up rounds    │     │  - Manual result input│
│  - PostgreSQL      │     │  - PostgreSQL storage   │     │  - Bracket counts    │
└──────────────────┘     └──────────────────────┘     └─────────────────────┘
```

**Tech stack:** Python (backend/simulation) + PostgreSQL (storage) + React (frontend)

---

## PHASE 1: Research Agent

### Goal
Produce a **power index** (0–100 scale) for each of the 68 tournament teams, plus cached head-to-head/matchup research for all possible pairings within each region.

### Step 1.1 — Team Power Index

**Input:** The 68-team tournament field (user provides team names + seeds + region assignments).

**Process — for each team, research and score these factors:**

| Factor | Weight (suggested) | Source |
|--------|-------------------|--------|
| Adjusted Efficiency Margin (KenPom-style) | 25% | Web search |
| Strength of Schedule | 15% | Web search |
| Recent form (last 10 games) | 15% | Web search |
| Tournament seed (historical seed performance) | 15% | Hardcoded lookup table |
| Key player injuries / availability | 10% | Web search |
| Offensive efficiency | 10% | Web search |
| Defensive efficiency | 10% | Web search |

**Output per team:**
```json
{
  "team": "Duke",
  "seed": 1,
  "region": "South",
  "power_index": 92.4,
  "factors": {
    "efficiency_margin": 23.5,
    "sos_rank": 8,
    "last_10": "8-2",
    "offensive_efficiency": 118.2,
    "defensive_efficiency": 94.7,
    "injuries": "none significant",
    "notes": "Strong perimeter defense, vulnerable inside..."
  },
  "research_summary": "..."
}
```

**Implementation:**
- Create a Python script `research_agent.py`
- Use Claude Code's web search (via subprocess or tool use) to gather data for each team
- Parse and normalize results into the power index formula
- Store results in PostgreSQL table `teams`

### Step 1.2 — Matchup Research Cache

**Why:** Before simulating each round, we need head-to-head context for every possible pairing. Since a 16-team region has at most C(16,2) = 120 unique pairs, we pre-compute ALL of them.

**Process — for each pair (Team A vs Team B):**
- Have they played each other this season or recently?
- What is their stylistic matchup? (e.g., pace mismatch, size advantage)
- What do analysts/models say about this matchup?
- Compute a **matchup adjustment** (-10 to +10 modifier to base win probability)

**Output per matchup:**
```json
{
  "team_a": "Duke",
  "team_b": "Vermont",
  "base_win_prob_a": 0.95,
  "matchup_adjustment": 0.0,
  "adjusted_win_prob_a": 0.95,
  "head_to_head": "No recent meetings",
  "matchup_notes": "Massive size and talent advantage for Duke...",
  "researched_at": "2025-03-15T10:00:00Z"
}
```

**Implementation:**
- Create `matchup_researcher.py`
- Loop through all 120 pairs per region (480 total)
- Use web search to gather matchup-specific intel
- Compute base win probability from power index differential using a logistic function:
  ```
  P(A wins) = 1 / (1 + 10^((power_B - power_A) / 15))
  ```
- Apply matchup adjustment from research
- Store in PostgreSQL table `matchup_cache`
- **Cache is keyed by (team_a, team_b) — never re-research the same pair**

### Step 1.3 — Database Schema (Phase 1 tables)

```sql
CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    seed INT NOT NULL,
    region VARCHAR(20) NOT NULL,  -- 'South', 'East', 'West', 'Midwest'
    power_index FLOAT NOT NULL,
    factors JSONB,
    research_summary TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE matchup_cache (
    id SERIAL PRIMARY KEY,
    team_a_id INT REFERENCES teams(id),
    team_b_id INT REFERENCES teams(id),
    base_win_prob_a FLOAT NOT NULL,
    matchup_adjustment FLOAT DEFAULT 0,
    adjusted_win_prob_a FLOAT NOT NULL,
    head_to_head TEXT,
    matchup_notes TEXT,
    researched_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(team_a_id, team_b_id)
);
```

---

## PHASE 2: Bracket Simulation

### Goal
Generate 10 million bracket outcomes per region using bottom-up Monte Carlo simulation. Each bracket is a sequence of game results from Round of 64 through the Regional Final.

### Step 2.1 — Simulation Engine Architecture

**Key design: bottom-up, round-by-round simulation.**

A single region has 4 rounds:
- Round of 64: 8 games (16 teams → 8 winners)
- Round of 32: 4 games (8 → 4)
- Sweet 16: 2 games (4 → 2)
- Elite 8: 1 game (2 → 1 regional champion)

Total: 15 games per regional bracket.

**Algorithm for one region (e.g., South):**

```
For each of 10,000,000 simulations:
    current_teams = [seed_1, seed_16, seed_8, seed_9, seed_5, seed_12, seed_4, seed_13,
                     seed_6, seed_11, seed_3, seed_14, seed_7, seed_10, seed_2, seed_15]

    bracket_result = []

    For each round in [R64, R32, S16, E8]:
        next_round_teams = []
        For each game (pair of adjacent teams in current_teams):
            team_a, team_b = pair
            prob_a = lookup_matchup_cache(team_a, team_b)
            random_val = random()
            winner = team_a if random_val < prob_a else team_b
            bracket_result.append(winner)
            next_round_teams.append(winner)
        current_teams = next_round_teams

    store bracket_result
```

### Step 2.2 — Performance Requirements

10M simulations × 4 regions = 40M total simulations. Each simulation is 15 coin flips with probability lookups.

**Performance strategy:**
- Use **NumPy vectorized operations** — do NOT loop in Python
- Pre-build a probability lookup matrix (16×16) per region from the matchup cache
- Generate all random numbers upfront: `np.random.random((10_000_000, 15))`
- Simulate all 10M brackets for round 1 simultaneously, then round 2, etc.
- This should complete in seconds, not hours

**Pseudocode (vectorized):**
```python
import numpy as np

def simulate_region(prob_matrix, n_sims=10_000_000):
    """
    prob_matrix: dict mapping (team_a_idx, team_b_idx) -> P(team_a wins)
    Returns: array of shape (n_sims, 15) containing winner indices for each game
    """
    # Initial bracket order (indices 0-15 for the 16 teams)
    # Standard NCAA bracket order: 1v16, 8v9, 5v12, 4v13, 6v11, 3v14, 7v10, 2v15
    seeds = np.array([0,15, 7,8, 4,11, 3,12, 5,10, 2,13, 6,9, 1,14])

    results = np.zeros((n_sims, 15), dtype=np.int16)
    game_idx = 0

    current = np.tile(seeds, (n_sims, 1))  # (n_sims, 16)

    for round_size in [8, 4, 2, 1]:  # games per round
        next_round = []
        for g in range(round_size):
            team_a = current[:, 2*g]      # (n_sims,)
            team_b = current[:, 2*g + 1]  # (n_sims,)

            # Vectorized probability lookup
            probs = np.array([prob_matrix[(a, b)] for a, b in zip(team_a, team_b)])
            # NOTE: This inner loop is slow — optimize with precomputed matrix below

            rand = np.random.random(n_sims)
            winners = np.where(rand < probs, team_a, team_b)

            results[:, game_idx] = winners
            next_round.append(winners)
            game_idx += 1

        current = np.column_stack(next_round)

    return results
```

**CRITICAL optimization — precompute full probability matrix:**
```python
# Build 16x16 probability matrix per region
prob_matrix = np.zeros((16, 16))
for i in range(16):
    for j in range(16):
        if i != j:
            prob_matrix[i][j] = lookup_from_cache(team_i, team_j)

# Then in simulation, lookup is just: prob_matrix[team_a, team_b]
# This makes the vectorized lookup O(1) per element
```

### Step 2.3 — Storage Format

Each bracket is 15 game results (winner of each game). Store compactly.

**Option A — Bitpacked (recommended for 10M brackets):**
Each game result is 1 bit (team A won = 0, team B won = 1). 15 games = 15 bits = fits in a 2-byte integer. 10M brackets × 2 bytes = 20MB per region. Total: 80MB.

**Option B — Full storage in PostgreSQL:**
```sql
CREATE TABLE brackets (
    id SERIAL PRIMARY KEY,
    region VARCHAR(20) NOT NULL,
    results SMALLINT NOT NULL,  -- 15-bit packed results
    is_alive BOOLEAN DEFAULT TRUE,
    eliminated_round INT DEFAULT NULL,
    eliminated_day DATE DEFAULT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_brackets_region_alive ON brackets(region, is_alive);
CREATE INDEX idx_brackets_region ON brackets(region);
```

**Encoding/decoding:**
```python
def encode_bracket(game_results: list[int]) -> int:
    """game_results: list of 15 values, each 0 or 1 (0=higher seed won, 1=lower seed won)"""
    result = 0
    for i, r in enumerate(game_results):
        result |= (r << i)
    return result

def decode_bracket(packed: int) -> list[int]:
    return [(packed >> i) & 1 for i in range(15)]
```

### Step 2.4 — Simulation Script Structure

```
simulation/
├── simulate.py          # Main entry point
├── engine.py            # Vectorized simulation engine
├── probability.py       # Probability matrix builder (reads from matchup_cache)
├── storage.py           # PostgreSQL bracket storage (batch insert)
├── config.py            # Constants, DB config
└── bracket_structure.py # NCAA bracket ordering, seed mappings
```

**Batch insert for performance:**
```python
# Insert 10M rows in batches of 100K
BATCH_SIZE = 100_000
for i in range(0, n_sims, BATCH_SIZE):
    batch = results[i:i+BATCH_SIZE]
    execute_batch(cursor, "INSERT INTO brackets (region, results) VALUES (%s, %s)", 
                  [(region, int(r)) for r in packed_batch])
```

### Step 2.5 — Later: Final Four Simulation

After all 4 regions are simulated:
- Each bracket has a regional champion
- To build full brackets: combine one outcome from each region
- Final Four matchups require additional matchup research (4 new pairs max)
- Simulate Final Four + Championship as additional 3 games
- This is a FUTURE step — skip for now, focus on regional simulation

---

## PHASE 3: Tracker Website

### Goal
A React + Python API website that shows how many brackets survive each day as real tournament results are entered manually.

### Step 3.1 — Backend API (Python/FastAPI)

```
api/
├── main.py              # FastAPI app
├── routes/
│   ├── results.py       # POST real game results
│   ├── brackets.py      # GET bracket stats
│   └── regions.py       # GET region-specific data
├── services/
│   ├── pruner.py        # Mark dead brackets
│   └── stats.py         # Compute survival stats
└── models.py            # Pydantic models
```

**Key endpoints:**

```
POST /api/results
Body: { "region": "South", "round": 1, "game": 1, "winner": "Duke" }
→ Triggers pruning of brackets where that game result doesn't match

GET /api/stats
→ Returns: { 
    "day": 3,
    "total_alive": 2_847_392,
    "by_region": {
      "South": { "alive": 1_203_847, "total": 10_000_000 },
      "East": { "alive": 892_341, "total": 10_000_000 },
      ...
    },
    "history": [
      { "day": 0, "alive": 40_000_000 },
      { "day": 1, "alive": 12_384_729 },
      ...
    ]
  }

GET /api/regions/:region
→ Returns detailed bracket survival for that region
```

**Pruning logic:**
When a real result is entered, we need to eliminate all brackets that got that game wrong.

```python
def prune_brackets(region: str, game_index: int, actual_result: int, day: date):
    """
    game_index: 0-14 (which of the 15 games)
    actual_result: 0 or 1 (which team won)
    """
    # Bitwise check: bracket is wrong if bit at game_index doesn't match
    if actual_result == 1:
        # Eliminate brackets where bit is 0
        UPDATE brackets 
        SET is_alive = FALSE, eliminated_round = ..., eliminated_day = ...
        WHERE region = region 
          AND is_alive = TRUE 
          AND (results & (1 << game_index)) = 0
    else:
        # Eliminate brackets where bit is 1
        UPDATE brackets
        SET is_alive = FALSE, eliminated_round = ..., eliminated_day = ...
        WHERE region = region 
          AND is_alive = TRUE 
          AND (results & (1 << game_index)) != 0
```

This is a **single SQL query per game result** — extremely fast even on 10M rows thanks to the bitwise operation and the index on (region, is_alive).

### Step 3.2 — Additional DB Tables

```sql
CREATE TABLE game_results (
    id SERIAL PRIMARY KEY,
    region VARCHAR(20) NOT NULL,
    round INT NOT NULL,        -- 1=R64, 2=R32, 3=S16, 4=E8
    game_number INT NOT NULL,  -- game within the round (1-indexed)
    game_index INT NOT NULL,   -- 0-14 position in the 15-game bracket
    team_a VARCHAR(100),
    team_b VARCHAR(100),
    winner VARCHAR(100) NOT NULL,
    result_bit INT NOT NULL,   -- 0 or 1 (matches bracket encoding)
    entered_at TIMESTAMP DEFAULT NOW(),
    day INT NOT NULL            -- tournament day (0 = before start, 1 = first day, ...)
);

CREATE TABLE daily_stats (
    id SERIAL PRIMARY KEY,
    day INT NOT NULL,
    region VARCHAR(20),        -- NULL for overall stats
    alive_count BIGINT NOT NULL,
    total_count BIGINT NOT NULL,
    snapshot_at TIMESTAMP DEFAULT NOW()
);
```

### Step 3.3 — React Frontend

```
frontend/
├── src/
│   ├── App.jsx
│   ├── components/
│   │   ├── Dashboard.jsx       # Main overview — total alive, chart
│   │   ├── RegionCard.jsx      # Per-region alive count + percentage
│   │   ├── SurvivalChart.jsx   # Line chart of brackets alive over days
│   │   ├── ResultEntry.jsx     # Admin panel to input game results
│   │   └── BracketViewer.jsx   # (future) View a sample surviving bracket
│   └── api/
│       └── client.js           # Axios/fetch wrapper for API calls
```

**Dashboard layout:**
```
┌─────────────────────────────────────────────────┐
│  MARCH MADNESS BRACKET TRACKER                  │
│  Day 3  |  2,847,392 / 40,000,000 alive (7.1%) │
├─────────────────────────────────────────────────┤
│  [====== Survival Chart Over Time =========]    │
│                                                  │
├────────────┬────────────┬───────────┬───────────┤
│  SOUTH     │  EAST      │  WEST     │  MIDWEST  │
│  1.2M/10M  │  892K/10M  │  423K/10M │  332K/10M │
│  12.0%     │  8.9%      │  4.2%     │  3.3%     │
└────────────┴────────────┴───────────┴───────────┘
```

**Result entry (simple admin form):**
- Dropdown: select region
- Dropdown: select game (auto-populated from bracket structure)
- Dropdown: select winner (shows the two teams in that game)
- Submit → POST /api/results → triggers pruning → refreshes stats

---

## Execution Order for Claude Code

### Sprint 1: Foundation
```
Task 1.1: Set up project structure (folders, requirements.txt, package.json)
Task 1.2: Set up PostgreSQL database + create all tables from schema above
Task 1.3: Create config.py with DB connection, constants
Task 1.4: Create bracket_structure.py — NCAA bracket ordering for all 4 regions
          Input: User provides 2025 bracket (68 teams, seeds, regions)
```

### Sprint 2: Research Agent
```
Task 2.1: Build research_agent.py — web search for each team, compute power index
Task 2.2: Build matchup_researcher.py — research all 120 pairs per region
Task 2.3: Build probability.py — convert power index + matchup data into win probabilities
Task 2.4: Run research for all 68 teams, store in DB
Task 2.5: Run matchup research for all 480 pairs, store in DB
```

### Sprint 3: Simulation Engine
```
Task 3.1: Build engine.py — vectorized NumPy simulation for one region
Task 3.2: Build storage.py — batch insert brackets into PostgreSQL
Task 3.3: Run simulation for South region (10M) as test
Task 3.4: Verify results — check distribution of champions matches seed expectations
Task 3.5: Run all 4 regions (40M total)
```

### Sprint 4: Tracker Website
```
Task 4.1: Build FastAPI backend with /api/results, /api/stats, /api/regions endpoints
Task 4.2: Build pruner.py — bitwise elimination logic
Task 4.3: Build React frontend — Dashboard, RegionCards, SurvivalChart
Task 4.4: Build ResultEntry admin form
Task 4.5: End-to-end test — enter a few results, verify pruning + UI updates
```

### Sprint 5: Polish + Final Four (Future)
```
Task 5.1: Final Four simulation (combine regional winners)
Task 5.2: Championship game simulation
Task 5.3: Full 63-game bracket tracking
Task 5.4: Add "most common surviving bracket" analysis
Task 5.5: Add export functionality
```

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Duplicates | Allowed | Simplifies simulation, can diverge in future rounds |
| Storage format | Bitpacked SMALLINT (15 bits) | 20MB per 10M brackets vs 150MB+ for JSON |
| Simulation method | Vectorized NumPy | 10M sims in seconds vs hours with Python loops |
| Matchup cache | Pre-compute all 120 pairs per region | Only 480 total research calls needed |
| Pruning | Bitwise SQL query | Single query eliminates millions of brackets instantly |
| Win probability | Logistic function from power index differential | Industry-standard approach, easy to calibrate |
| Research | Claude Code web search | No API keys needed, flexible data gathering |

---

## Inputs Needed From User Before Starting

1. **2025 bracket:** All 68 teams with seed + region assignment (or link to bracket)
2. **PostgreSQL credentials:** Host, port, database name, user, password
3. **Any custom weighting preferences** for the power index formula
4. **Confirmation of region names** for 2025 (South, East, West, Midwest — these change yearly)
