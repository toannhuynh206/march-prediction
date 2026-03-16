-- 001_initial_schema.sql
-- March Madness Bracket Simulation Engine — PostgreSQL 16
-- Brackets table partitioned by region for 206M total rows (51.5M per region).

BEGIN;

-- =========================================================================
-- Teams
-- =========================================================================

CREATE TABLE IF NOT EXISTS teams (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    seed            SMALLINT NOT NULL CHECK (seed BETWEEN 1 AND 16),
    region          TEXT NOT NULL,
    conference      TEXT,
    record          TEXT,
    tournament_year INT NOT NULL DEFAULT 2026,

    UNIQUE (name, tournament_year)
);

-- =========================================================================
-- Team stats (one row per team per year)
-- =========================================================================

CREATE TABLE IF NOT EXISTS team_stats (
    id                      SERIAL PRIMARY KEY,
    team_id                 INT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    tournament_year         INT NOT NULL DEFAULT 2026,

    -- KenPom core
    adj_em                  REAL,
    adj_o                   REAL,
    adj_d                   REAL,
    tempo                   REAL,

    -- Power index factors
    experience              REAL,
    nonconf_sos             INT,
    luck                    REAL,
    ft_rate                 REAL,
    ft_pct                  REAL,
    efg_pct                 REAL,
    to_pct                  REAL,
    orb_pct                 REAL,
    three_pt_rate           REAL,
    three_pt_pct            REAL,
    three_pt_defense        REAL,
    three_pt_variance       REAL,
    block_pct               REAL,
    steal_pct               REAL,
    coaching_tourney_apps   INT,
    height_avg_inches       REAL,
    conf_tourney_games      INT,

    -- Public pick data
    espn_pick_pct_r32       REAL,
    espn_pick_pct_s16       REAL,
    espn_pick_pct_f4        REAL,

    -- Computed power index (0-100)
    power_index             REAL,

    data_verified           BOOLEAN DEFAULT FALSE,

    UNIQUE (team_id, tournament_year)
);

-- =========================================================================
-- Market odds
-- =========================================================================

CREATE TABLE IF NOT EXISTS odds (
    id              SERIAL PRIMARY KEY,
    team_id         INT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    opponent_id     INT REFERENCES teams(id) ON DELETE CASCADE,
    market          TEXT NOT NULL,
    line_type       TEXT NOT NULL,
    odds_value      REAL,
    spread          REAL,
    implied_prob    REAL,
    fair_prob       REAL,
    tournament_year INT NOT NULL DEFAULT 2026,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =========================================================================
-- Matchups (R64 through Final, all pairwise probabilities)
-- =========================================================================

CREATE TABLE IF NOT EXISTS matchups (
    id              SERIAL PRIMARY KEY,
    round           TEXT NOT NULL,
    region          TEXT,
    game_index      SMALLINT,
    team_a_id       INT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    team_b_id       INT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    seed_a          SMALLINT,
    seed_b          SMALLINT,
    p_market        REAL,
    p_stats         REAL,
    p_matchup       REAL,
    p_factors       REAL,
    p_final         REAL,
    actual_winner_id INT REFERENCES teams(id),
    tournament_year INT NOT NULL DEFAULT 2026,

    -- Canonical ordering: team_a_id < team_b_id prevents duplicate matchups
    CHECK (team_a_id < team_b_id)
);

-- =========================================================================
-- Brackets — partitioned by region
-- 15-bit packed SMALLINT outcomes + weight for importance sampling
-- =========================================================================

CREATE TABLE IF NOT EXISTS brackets (
    id              BIGINT NOT NULL,
    region          TEXT NOT NULL,
    outcomes        SMALLINT NOT NULL,      -- 15-bit packed bracket results
    weight          REAL NOT NULL DEFAULT 1.0,
    stratum_id      INT,                    -- world ID from stratifier
    cluster         TEXT,                   -- 'baseline' or 'gamble'
    probability     REAL,
    expected_score  REAL,
    is_alive        BOOLEAN NOT NULL DEFAULT TRUE,
    tournament_year INT NOT NULL DEFAULT 2026,

    PRIMARY KEY (id, region)
) PARTITION BY LIST (region);

-- Create one partition per region
CREATE TABLE IF NOT EXISTS brackets_south
    PARTITION OF brackets FOR VALUES IN ('South');
CREATE TABLE IF NOT EXISTS brackets_east
    PARTITION OF brackets FOR VALUES IN ('East');
CREATE TABLE IF NOT EXISTS brackets_west
    PARTITION OF brackets FOR VALUES IN ('West');
CREATE TABLE IF NOT EXISTS brackets_midwest
    PARTITION OF brackets FOR VALUES IN ('Midwest');

-- =========================================================================
-- Game results (for live pruning)
-- =========================================================================

CREATE TABLE IF NOT EXISTS game_results (
    id              SERIAL PRIMARY KEY,
    tournament_year INT NOT NULL DEFAULT 2026,
    region          TEXT NOT NULL,
    round           TEXT NOT NULL,
    game_number     SMALLINT NOT NULL,
    winner_seed     SMALLINT NOT NULL,
    loser_seed      SMALLINT NOT NULL,
    winner_name     TEXT,
    loser_name      TEXT,
    winner_score    SMALLINT,
    loser_score     SMALLINT,
    entered_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Idempotency: one result per game slot
    UNIQUE (tournament_year, region, round, game_number)
);

-- =========================================================================
-- Strata / worlds (for tracking simulation budget allocation)
-- =========================================================================

CREATE TABLE IF NOT EXISTS strata (
    id              SERIAL PRIMARY KEY,
    tournament_year INT NOT NULL DEFAULT 2026,
    region          TEXT NOT NULL,
    r64_upsets      SMALLINT NOT NULL,
    champion_tier   TEXT NOT NULL,           -- '1', '2-3', '4-6', '7+'
    prior_prob      REAL NOT NULL,
    target_count    INT NOT NULL,
    actual_count    INT DEFAULT 0,

    UNIQUE (tournament_year, region, r64_upsets, champion_tier)
);

COMMIT;
