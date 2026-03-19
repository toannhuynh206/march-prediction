-- Alive outcome tables for validity bitmap pruning.
-- Each table holds all possible packed values. Pruning = DELETE rows.
-- A bracket is alive if ALL 5 of its outcome values exist in the alive tables.

CREATE TABLE IF NOT EXISTS alive_outcomes_south (
    outcome_value SMALLINT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS alive_outcomes_east (
    outcome_value SMALLINT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS alive_outcomes_west (
    outcome_value SMALLINT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS alive_outcomes_midwest (
    outcome_value SMALLINT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS alive_outcomes_f4 (
    outcome_value SMALLINT PRIMARY KEY
);

-- Stats cache: pre-computed counts refreshed after each prune
CREATE TABLE IF NOT EXISTS stats_cache (
    tournament_year INT PRIMARY KEY,
    total_brackets BIGINT NOT NULL DEFAULT 0,
    alive_brackets BIGINT NOT NULL DEFAULT 0,
    champion_odds JSONB,
    upset_distribution JSONB
);

-- Prune audit log
CREATE TABLE IF NOT EXISTS prune_log (
    id SERIAL PRIMARY KEY,
    tournament_year INT NOT NULL,
    pruned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    games_submitted INT,
    game_details JSONB,
    brackets_before BIGINT,
    brackets_deleted BIGINT,
    brackets_remaining BIGINT,
    prune_duration_ms INT
);

-- Generation proof for audit trail
CREATE TABLE IF NOT EXISTS generation_proof (
    id SERIAL PRIMARY KEY,
    tournament_year INT NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_brackets BIGINT NOT NULL,
    sha256_hash TEXT,
    strategy_breakdown JSONB,
    champion_distribution JSONB
);

-- Required indexes on full_brackets for 5-way JOIN pruning
CREATE INDEX IF NOT EXISTS idx_fb_south_outcomes ON full_brackets (south_outcomes);
CREATE INDEX IF NOT EXISTS idx_fb_east_outcomes ON full_brackets (east_outcomes);
CREATE INDEX IF NOT EXISTS idx_fb_west_outcomes ON full_brackets (west_outcomes);
CREATE INDEX IF NOT EXISTS idx_fb_midwest_outcomes ON full_brackets (midwest_outcomes);
CREATE INDEX IF NOT EXISTS idx_fb_f4_outcomes ON full_brackets (f4_outcomes);

-- Probability index for sorted browsing
CREATE INDEX IF NOT EXISTS idx_fb_prob ON full_brackets (probability DESC);

-- Champion filtering
CREATE INDEX IF NOT EXISTS idx_fb_champion ON full_brackets (champion_region, champion_seed);
