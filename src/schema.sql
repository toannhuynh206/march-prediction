-- March Madness Bracket Simulation Engine - SQLite Schema
-- Sprint 1: Core tables for teams, odds, brackets, and results
-- Matches math-model-spec.md v3

-- ---------------------------------------------------------------------------
-- Teams & Tournament Structure
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS teams (
    team_id     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    seed        INTEGER NOT NULL CHECK (seed BETWEEN 1 AND 16),
    region      TEXT NOT NULL CHECK (region IN ('South', 'East', 'West', 'Midwest')),
    conference  TEXT,
    -- Power Index factors (9-factor model, Section 5.1)
    adj_efficiency_margin   REAL,
    bart_torvik_rating      REAL,
    strength_of_schedule    REAL,
    recent_form             REAL,
    offensive_efficiency    REAL,
    defensive_efficiency    REAL,
    free_throw_rate_index   REAL,
    coaching_tournament_score REAL,
    key_injuries            REAL,
    three_point_variance    REAL,
    -- Computed
    power_index             REAL,
    -- Style vector for matchup analysis (display/minimal use per CTO)
    pace                    REAL,
    three_pt_rate           REAL,
    ft_rate                 REAL,
    off_reb_rate            REAL,
    turnover_rate           REAL,
    assist_rate             REAL,
    avg_height              REAL,
    UNIQUE(seed, region)
);

-- First-round matchups (bracket structure)
CREATE TABLE IF NOT EXISTS matchups (
    game_id     INTEGER PRIMARY KEY,
    round       TEXT NOT NULL CHECK (round IN ('R64','R32','S16','E8','F4','Championship')),
    region      TEXT CHECK (region IN ('South','East','West','Midwest')),
    game_index  INTEGER NOT NULL,  -- 0-14 within region, 60-62 for F4
    team_a_id   INTEGER REFERENCES teams(team_id),
    team_b_id   INTEGER REFERENCES teams(team_id),
    -- Probabilities (pre-tournament)
    p_market    REAL,
    p_stats     REAL,
    p_matchup   REAL DEFAULT 0.5,
    p_factors   REAL DEFAULT 0.5,
    p_final     REAL,
    weight_tier TEXT DEFAULT 'game_lines',
    -- Actual result (filled during tournament)
    winner_id   INTEGER REFERENCES teams(team_id),
    margin      INTEGER,
    completed   INTEGER DEFAULT 0
);

-- ---------------------------------------------------------------------------
-- Odds Data
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS odds (
    odds_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id     INTEGER REFERENCES matchups(game_id),
    team_id     INTEGER REFERENCES teams(team_id),
    sportsbook  TEXT NOT NULL,
    odds_type   TEXT NOT NULL CHECK (odds_type IN ('moneyline', 'spread', 'futures')),
    odds_value  REAL NOT NULL,  -- American odds for ML, point spread, or futures odds
    spread      REAL,           -- point spread (if applicable)
    implied_prob REAL,          -- raw implied probability (before de-vig)
    fair_prob   REAL,           -- after de-vig
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    is_opening  INTEGER DEFAULT 0,
    is_closing  INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_odds_game ON odds(game_id);
CREATE INDEX IF NOT EXISTS idx_odds_team ON odds(team_id);

-- Futures Concentration Index (FCI) for year-adaptive modeling
CREATE TABLE IF NOT EXISTS futures_concentration (
    year            INTEGER PRIMARY KEY,
    top4_share      REAL NOT NULL,  -- sum of top 4 teams' championship probabilities
    historical_avg  REAL NOT NULL,  -- historical average top4 share
    fci             REAL NOT NULL   -- top4_share / historical_avg
);

-- ---------------------------------------------------------------------------
-- Matchup Probability Matrix (64x64, Section 12.2)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS probability_matrix (
    team_a_id   INTEGER NOT NULL REFERENCES teams(team_id),
    team_b_id   INTEGER NOT NULL REFERENCES teams(team_id),
    p_final     REAL NOT NULL,
    weight_tier TEXT DEFAULT 'game_lines',
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (team_a_id, team_b_id)
);

-- ---------------------------------------------------------------------------
-- Regional Brackets (32,768 per region, Section 9)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS regional_brackets (
    region          TEXT NOT NULL CHECK (region IN ('South','East','West','Midwest')),
    bracket_int     INTEGER NOT NULL,  -- 15-bit encoding
    probability     REAL NOT NULL,
    expected_score  REAL,
    champion_seed   INTEGER,
    champion_team_id INTEGER REFERENCES teams(team_id),
    rank_in_region  INTEGER,
    PRIMARY KEY (region, bracket_int)
);

CREATE INDEX IF NOT EXISTS idx_rb_region_prob ON regional_brackets(region, probability DESC);
CREATE INDEX IF NOT EXISTS idx_rb_champion ON regional_brackets(region, champion_team_id);

-- ---------------------------------------------------------------------------
-- Full Brackets (10M target, Section 10)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS full_brackets (
    bracket_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    bracket_int     INTEGER NOT NULL UNIQUE,  -- 63-bit encoding
    south_int       INTEGER NOT NULL,
    east_int        INTEGER NOT NULL,
    west_int        INTEGER NOT NULL,
    midwest_int     INTEGER NOT NULL,
    f4_bits         INTEGER NOT NULL,  -- 3-bit: semi1, semi2, championship
    probability     REAL NOT NULL,
    expected_score  REAL,
    scenario_id     INTEGER,  -- Final Four scenario index
    alive           INTEGER DEFAULT 1,
    actual_score    INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_fb_alive ON full_brackets(alive) WHERE alive = 1;
CREATE INDEX IF NOT EXISTS idx_fb_scenario ON full_brackets(scenario_id);
CREATE INDEX IF NOT EXISTS idx_fb_prob ON full_brackets(probability DESC);

-- ---------------------------------------------------------------------------
-- Final Four Scenarios (Section 10.3)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS f4_scenarios (
    scenario_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    south_champ_id  INTEGER REFERENCES teams(team_id),
    east_champ_id   INTEGER REFERENCES teams(team_id),
    west_champ_id   INTEGER REFERENCES teams(team_id),
    midwest_champ_id INTEGER REFERENCES teams(team_id),
    probability     REAL NOT NULL,
    bracket_budget  INTEGER,  -- N_s allocated brackets
    UNIQUE(south_champ_id, east_champ_id, west_champ_id, midwest_champ_id)
);

-- ---------------------------------------------------------------------------
-- Live Tournament Tracking (Section 11)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS game_results (
    result_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         INTEGER NOT NULL REFERENCES matchups(game_id),
    winner_id       INTEGER NOT NULL REFERENCES teams(team_id),
    loser_id        INTEGER NOT NULL REFERENCES teams(team_id),
    winner_score    INTEGER,
    loser_score     INTEGER,
    margin          INTEGER,
    -- PI updates applied after this game
    winner_pi_delta REAL,
    loser_pi_delta  REAL,
    timestamp       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bracket_survival (
    round           TEXT NOT NULL,
    total_brackets  INTEGER NOT NULL,
    alive_brackets  INTEGER NOT NULL,
    survival_rate   REAL NOT NULL,
    timestamp       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- Views for common queries
-- ---------------------------------------------------------------------------

-- Teams ranked by power index
CREATE VIEW IF NOT EXISTS v_team_rankings AS
SELECT team_id, name, seed, region, power_index,
       RANK() OVER (ORDER BY power_index DESC) as overall_rank,
       RANK() OVER (PARTITION BY region ORDER BY power_index DESC) as region_rank
FROM teams
WHERE power_index IS NOT NULL
ORDER BY power_index DESC;

-- Regional champion probabilities
CREATE VIEW IF NOT EXISTS v_regional_champ_probs AS
SELECT region, champion_team_id, t.name, t.seed,
       SUM(probability) as win_region_prob
FROM regional_brackets rb
JOIN teams t ON rb.champion_team_id = t.team_id
GROUP BY region, champion_team_id
ORDER BY region, win_region_prob DESC;

-- Top surviving brackets
CREATE VIEW IF NOT EXISTS v_top_brackets AS
SELECT bracket_id, bracket_int, probability, expected_score, actual_score
FROM full_brackets
WHERE alive = 1
ORDER BY expected_score DESC
LIMIT 100;

-- Bracket survival summary
CREATE VIEW IF NOT EXISTS v_survival_summary AS
SELECT round, alive_brackets, survival_rate,
       ROUND(100.0 * alive_brackets / total_brackets, 2) as pct_alive
FROM bracket_survival
ORDER BY timestamp;
