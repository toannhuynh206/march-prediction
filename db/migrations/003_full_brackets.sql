-- 003_full_brackets.sql
-- Full tournament brackets: 4 regional outcomes + 3 Final Four games.
-- 206M rows. No partitioning (no natural partition key across all regions).

BEGIN;

CREATE TABLE IF NOT EXISTS full_brackets (
    id                  BIGINT PRIMARY KEY,
    east_outcomes       SMALLINT NOT NULL,     -- 15-bit packed East region
    south_outcomes      SMALLINT NOT NULL,     -- 15-bit packed South region
    west_outcomes       SMALLINT NOT NULL,     -- 15-bit packed West region
    midwest_outcomes    SMALLINT NOT NULL,     -- 15-bit packed Midwest region
    f4_outcomes         SMALLINT NOT NULL,     -- 3 bits: semi1, semi2, championship
    probability         DOUBLE PRECISION NOT NULL,
    weight              REAL NOT NULL DEFAULT 1.0,
    champion_seed       SMALLINT NOT NULL,
    champion_region     TEXT NOT NULL,
    total_upsets        SMALLINT,
    is_alive            BOOLEAN NOT NULL DEFAULT TRUE,
    tournament_year     INT NOT NULL DEFAULT 2026,

    -- F4 encoding: only bits 0-2 used (values 0-7)
    CHECK (f4_outcomes BETWEEN 0 AND 7)
);

-- Pruning: filter alive brackets
CREATE INDEX IF NOT EXISTS idx_full_brackets_alive
    ON full_brackets (is_alive)
    WHERE is_alive = TRUE;

-- Champion analysis
CREATE INDEX IF NOT EXISTS idx_full_brackets_champion
    ON full_brackets (champion_seed, champion_region)
    WHERE is_alive = TRUE;

-- Year filtering
CREATE INDEX IF NOT EXISTS idx_full_brackets_year
    ON full_brackets (tournament_year);

-- Weight-based ranking
CREATE INDEX IF NOT EXISTS idx_full_brackets_weight
    ON full_brackets (weight DESC)
    WHERE is_alive = TRUE;

COMMIT;
