-- 002_indexes.sql
-- Performance indexes for 206M bracket simulation engine.
-- Designed for partition-pruned queries on brackets table.

BEGIN;

-- =========================================================================
-- Teams
-- =========================================================================

CREATE INDEX IF NOT EXISTS idx_teams_region
    ON teams (region);

CREATE INDEX IF NOT EXISTS idx_teams_seed
    ON teams (seed);

CREATE INDEX IF NOT EXISTS idx_teams_year_region
    ON teams (tournament_year, region);

-- =========================================================================
-- Team stats
-- =========================================================================

CREATE INDEX IF NOT EXISTS idx_team_stats_team_year
    ON team_stats (team_id, tournament_year);

-- =========================================================================
-- Odds
-- =========================================================================

CREATE INDEX IF NOT EXISTS idx_odds_team
    ON odds (team_id);

CREATE INDEX IF NOT EXISTS idx_odds_captured
    ON odds (captured_at DESC);

-- =========================================================================
-- Matchups
-- =========================================================================

CREATE INDEX IF NOT EXISTS idx_matchups_round
    ON matchups (round);

CREATE INDEX IF NOT EXISTS idx_matchups_pair
    ON matchups (team_a_id, team_b_id);

CREATE INDEX IF NOT EXISTS idx_matchups_region_round
    ON matchups (region, round);

-- =========================================================================
-- Brackets (partition-local indexes)
-- Each index is created on every partition automatically by PostgreSQL.
-- =========================================================================

-- Critical: pruning queries filter on is_alive = TRUE
CREATE INDEX IF NOT EXISTS idx_brackets_alive
    ON brackets (is_alive)
    WHERE is_alive = TRUE;

-- For survival statistics queries
CREATE INDEX IF NOT EXISTS idx_brackets_stratum
    ON brackets (stratum_id)
    WHERE is_alive = TRUE;

-- For cluster-level analysis
CREATE INDEX IF NOT EXISTS idx_brackets_cluster_alive
    ON brackets (cluster)
    WHERE is_alive = TRUE;

-- For expected score ranking
CREATE INDEX IF NOT EXISTS idx_brackets_score
    ON brackets (expected_score DESC NULLS LAST)
    WHERE is_alive = TRUE;

-- =========================================================================
-- Game results
-- =========================================================================

CREATE INDEX IF NOT EXISTS idx_game_results_lookup
    ON game_results (tournament_year, region, round);

-- =========================================================================
-- Strata
-- =========================================================================

CREATE INDEX IF NOT EXISTS idx_strata_region
    ON strata (tournament_year, region);

COMMIT;
