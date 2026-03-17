-- Migration 005: Remove mild_chaos strategy, split its brackets between chalk and standard.
-- mild_chaos brackets (IDs 6000001–7500000) → first half to chalk, second half to standard.

-- First half → chalk
UPDATE full_brackets
SET strategy = 'chalk'
WHERE strategy = 'mild_chaos'
  AND id <= 6750000;

-- Second half → standard
UPDATE full_brackets
SET strategy = 'standard'
WHERE strategy = 'mild_chaos'
  AND id > 6750000;
