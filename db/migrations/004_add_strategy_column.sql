-- 004_add_strategy_column.sql
-- Adds strategy column to full_brackets to track which portfolio strategy
-- (chalk, standard, mild_chaos, cinderella, chaos) generated each bracket.

BEGIN;

ALTER TABLE full_brackets ADD COLUMN IF NOT EXISTS strategy TEXT;

-- Index for portfolio-level queries
CREATE INDEX IF NOT EXISTS idx_full_brackets_strategy
    ON full_brackets (strategy)
    WHERE is_alive = TRUE;

-- Composite index for portfolio champion analysis
CREATE INDEX IF NOT EXISTS idx_full_brackets_strategy_champion
    ON full_brackets (strategy, champion_seed, champion_region)
    WHERE is_alive = TRUE;

-- Retroactively assign strategies based on known insertion order.
-- 10M brackets allocated: chalk 25%, standard 35%, mild_chaos 15%, cinderella 15%, chaos 10%.
-- Brackets are inserted sequentially by profile in sample_stratified_brackets.
UPDATE full_brackets SET strategy = 'chalk'      WHERE id BETWEEN 1       AND 2500000;
UPDATE full_brackets SET strategy = 'standard'   WHERE id BETWEEN 2500001 AND 6000000;
UPDATE full_brackets SET strategy = 'mild_chaos' WHERE id BETWEEN 6000001 AND 7500000;
UPDATE full_brackets SET strategy = 'cinderella' WHERE id BETWEEN 7500001 AND 9000000;
UPDATE full_brackets SET strategy = 'chaos'      WHERE id BETWEEN 9000001 AND 10000000;

COMMIT;
