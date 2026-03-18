"""
Full sanity check on 206M generated brackets in full_brackets table.
Run with: .venv/bin/python scripts/sanity_check.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.connection import get_engine
from sqlalchemy import text

engine = get_engine()

YEAR = 2026
VALID_REGIONS = {"East", "South", "West", "Midwest"}

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def query(sql: str, params: dict | None = None):
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        return result.fetchall()

def query_one(sql: str, params: dict | None = None):
    rows = query(sql, params)
    return rows[0] if rows else None

def status(label: str, result: str, note: str = ""):
    tag = f"[{result}]"
    print(f"  {tag:<8} {label}")
    if note:
        print(f"           {note}")

def section(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

# ──────────────────────────────────────────────────────────────────────────────
# 1. Basic Counts
# ──────────────────────────────────────────────────────────────────────────────
section("1. BASIC COUNTS")

t0 = time.time()
row = query_one("""
    SELECT
        COUNT(*) AS total,
        SUM(CASE WHEN is_alive THEN 1 ELSE 0 END) AS alive,
        SUM(CASE WHEN NOT is_alive THEN 1 ELSE 0 END) AS dead
    FROM full_brackets
    WHERE tournament_year = :yr
""", {"yr": YEAR})
total, alive, dead = int(row[0]), int(row[1]), int(row[2])
elapsed = time.time() - t0

print(f"\n  Total brackets : {total:>15,}")
print(f"  is_alive=TRUE  : {alive:>15,}")
print(f"  is_alive=FALSE : {dead:>15,}")
print(f"  Query time     : {elapsed:.1f}s")

if total == 206_000_000:
    status("Total = 206,000,000", "PASS")
elif total > 0:
    status(f"Total = {total:,} (expected 206,000,000)", "WARN")
else:
    status("No rows found", "FAIL")

if dead == 0:
    status("All brackets is_alive=TRUE (no pruning yet)", "PASS")
else:
    status(f"{dead:,} brackets already dead", "WARN", f"{dead/total*100:.4f}% dead")

# Strategy profile counts
strat_rows = query("""
    SELECT strategy, COUNT(*) as cnt
    FROM full_brackets
    WHERE tournament_year = :yr
    GROUP BY strategy
    ORDER BY cnt DESC
""", {"yr": YEAR})
print(f"\n  Strategy profile breakdown:")
for r in strat_rows:
    strat = r[0] or "NULL"
    cnt = int(r[1])
    pct = cnt / total * 100 if total > 0 else 0
    print(f"    {strat:<15} : {cnt:>15,}  ({pct:.2f}%)")

expected_strategies = {"chalk", "standard", "cinderella", "chaos"}
found_strategies = {r[0] for r in strat_rows if r[0] is not None}
if expected_strategies <= found_strategies:
    status("All 4 strategy profiles present", "PASS")
else:
    missing = expected_strategies - found_strategies
    status(f"Missing strategies: {missing}", "FAIL")

# ──────────────────────────────────────────────────────────────────────────────
# 2. Champion Distribution
# ──────────────────────────────────────────────────────────────────────────────
section("2. CHAMPION DISTRIBUTION")

seed_rows = query("""
    SELECT champion_seed, COUNT(*) as cnt
    FROM full_brackets
    WHERE tournament_year = :yr
    GROUP BY champion_seed
    ORDER BY champion_seed
""", {"yr": YEAR})

print(f"\n  Champion seed distribution:")
seed_map = {}
for r in seed_rows:
    seed = int(r[0])
    cnt = int(r[1])
    pct = cnt / total * 100 if total > 0 else 0
    seed_map[seed] = (cnt, pct)
    bar = "█" * int(pct / 2)
    print(f"    Seed {seed:>2} : {cnt:>12,}  ({pct:>5.2f}%)  {bar}")

# 1-seeds should win >= 40% of REGION simulations
# In full bracket context, 1-seeds win ~50-55% combined
one_seed_pct = seed_map.get(1, (0, 0))[1]
if one_seed_pct >= 40:
    status(f"1-seed champion rate {one_seed_pct:.1f}% >= 40%", "PASS")
elif one_seed_pct >= 30:
    status(f"1-seed champion rate {one_seed_pct:.1f}% (expected >= 40%)", "WARN")
else:
    status(f"1-seed champion rate {one_seed_pct:.1f}% too low", "FAIL")

# Minimum 50K per possible champion seed check
low_seeds = [s for s, (cnt, _) in seed_map.items() if cnt < 50_000]
if not low_seeds:
    status("All champion seeds have >= 50K brackets", "PASS")
else:
    status(f"Seeds below 50K minimum: {low_seeds}", "WARN")

# Top 10 champion teams (need teams table join)
try:
    team_rows = query("""
        SELECT t.name, t.seed, t.region, COUNT(*) as cnt
        FROM full_brackets fb
        JOIN teams t ON t.region = fb.champion_region
                     AND t.seed = fb.champion_seed
                     AND t.tournament_year = fb.tournament_year
        WHERE fb.tournament_year = :yr
        GROUP BY t.name, t.seed, t.region
        ORDER BY cnt DESC
        LIMIT 10
    """, {"yr": YEAR})
    print(f"\n  Top 10 champion teams:")
    for i, r in enumerate(team_rows, 1):
        name, seed, region, cnt = r[0], r[1], r[2], int(r[3])
        pct = cnt / total * 100 if total > 0 else 0
        print(f"    {i:>2}. {name:<25} (#{seed} {region:<10}) : {cnt:>12,}  ({pct:.2f}%)")
    status("Top 10 champion teams retrieved", "PASS")
except Exception as e:
    status(f"Champion team JOIN failed: {e}", "WARN")

# ──────────────────────────────────────────────────────────────────────────────
# 3. Weight Distribution
# ──────────────────────────────────────────────────────────────────────────────
section("3. WEIGHT DISTRIBUTION")

w_row = query_one("""
    SELECT
        SUM(weight)::double precision AS total_weight,
        MIN(weight) AS min_w,
        MAX(weight) AS max_w,
        AVG(weight) AS mean_w,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY weight) AS median_w,
        STDDEV(weight) AS std_w
    FROM full_brackets
    WHERE tournament_year = :yr
""", {"yr": YEAR})

total_weight = float(w_row[0])
min_w, max_w, mean_w, median_w, std_w = (float(w_row[i]) for i in range(1, 6))
print(f"\n  Sum of all weights : {total_weight:>20.4f}")
print(f"  Min weight         : {min_w:>20.8f}")
print(f"  Max weight         : {max_w:>20.8f}")
print(f"  Mean weight        : {mean_w:>20.8f}")
print(f"  Median weight      : {median_w:>20.8f}")
print(f"  Std dev weight     : {std_w:>20.8f}")

# Check if normalized (sum ≈ 1.0) or sum ≈ N
if abs(total_weight - 1.0) < 0.01:
    status("Weights normalized (sum ≈ 1.0)", "PASS")
elif abs(total_weight - total) < total * 0.01:
    status(f"Weights = N (sum ≈ {total:,})", "PASS",
           "Weights are uniform (unscaled) — normalize before Bayesian update")
else:
    status(f"Weight sum = {total_weight:.4f} (unusual)", "WARN")

# Top 1% weight concentration
top1pct_threshold = int(total * 0.01)
top1_row = query_one("""
    SELECT SUM(weight)::double precision
    FROM (
        SELECT weight FROM full_brackets
        WHERE tournament_year = :yr
        ORDER BY weight DESC
        LIMIT :lim
    ) sub
""", {"yr": YEAR, "lim": top1pct_threshold})
top1_weight = float(top1_row[0])
concentration = top1_weight / total_weight * 100 if total_weight > 0 else 0
print(f"\n  Top 1% brackets hold {concentration:.2f}% of total weight")
if concentration < 50:
    status(f"Weight concentration healthy ({concentration:.1f}% in top 1%)", "PASS")
elif concentration < 80:
    status(f"Weight moderately concentrated ({concentration:.1f}% in top 1%)", "WARN")
else:
    status(f"Weight highly concentrated ({concentration:.1f}% in top 1%)", "FAIL")

# ──────────────────────────────────────────────────────────────────────────────
# 4. Regional Outcome Diversity
# ──────────────────────────────────────────────────────────────────────────────
section("4. REGIONAL OUTCOME DIVERSITY")

MAX_POSSIBLE = 32768  # 2^15 regional outcomes
for col in ("south_outcomes", "east_outcomes", "west_outcomes", "midwest_outcomes"):
    row = query_one(f"""
        SELECT COUNT(DISTINCT {col}) as distinct_vals
        FROM full_brackets
        WHERE tournament_year = :yr
    """, {"yr": YEAR})
    distinct = int(row[0])
    pct_of_max = distinct / MAX_POSSIBLE * 100
    label = f"{col}: {distinct:,} distinct / {MAX_POSSIBLE:,} possible ({pct_of_max:.1f}%)"
    print(f"\n  {label}")
    if distinct >= int(MAX_POSSIBLE * 0.9):
        status(f"{col} diversity", "PASS", f"{pct_of_max:.1f}% of possible outcomes covered")
    elif distinct >= int(MAX_POSSIBLE * 0.5):
        status(f"{col} diversity moderate", "WARN", f"Only {pct_of_max:.1f}% covered")
    else:
        status(f"{col} suspiciously LOW diversity", "FAIL", f"Only {distinct:,} distinct values")

# ──────────────────────────────────────────────────────────────────────────────
# 5. Upset Distribution
# ──────────────────────────────────────────────────────────────────────────────
section("5. UPSET DISTRIBUTION")

upset_row = query_one("""
    SELECT
        AVG(total_upsets) AS mean_u,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_upsets) AS median_u,
        STDDEV(total_upsets) AS std_u,
        MIN(total_upsets) AS min_u,
        MAX(total_upsets) AS max_u,
        COUNT(CASE WHEN total_upsets IS NULL THEN 1 END) AS nulls
    FROM full_brackets
    WHERE tournament_year = :yr
""", {"yr": YEAR})
mean_u, median_u, std_u, min_u, max_u, nulls_u = (
    float(upset_row[0]) if upset_row[0] is not None else 0,
    float(upset_row[1]) if upset_row[1] is not None else 0,
    float(upset_row[2]) if upset_row[2] is not None else 0,
    int(upset_row[3]) if upset_row[3] is not None else 0,
    int(upset_row[4]) if upset_row[4] is not None else 0,
    int(upset_row[5]),
)
print(f"\n  Mean upsets   : {mean_u:.2f}")
print(f"  Median upsets : {median_u:.2f}")
print(f"  Std dev       : {std_u:.2f}")
print(f"  Min           : {min_u}")
print(f"  Max           : {max_u}")
print(f"  NULL count    : {nulls_u:,}")

# Histogram (10 buckets)
hist_rows = query("""
    SELECT
        bucket,
        COUNT(*) as cnt
    FROM (
        SELECT width_bucket(total_upsets, 0, 40, 10) AS bucket
        FROM full_brackets
        WHERE tournament_year = :yr
          AND total_upsets IS NOT NULL
    ) sub
    GROUP BY bucket
    ORDER BY bucket
""", {"yr": YEAR})
print(f"\n  Histogram (10 buckets, 0-40 upsets):")
for r in hist_rows:
    b, cnt = int(r[0]), int(r[1])
    lo = (b - 1) * 4
    hi = b * 4
    bar = "█" * int(cnt / (total / 10) * 20)
    print(f"    [{lo:>2}-{hi:>2}] : {cnt:>12,}  {bar}")

if nulls_u == 0 and 3 <= mean_u <= 15:
    status(f"Upset distribution looks healthy (mean={mean_u:.2f})", "PASS")
elif nulls_u > 0:
    status(f"{nulls_u:,} NULL total_upsets values", "WARN")
else:
    status(f"Unusual mean upsets: {mean_u:.2f}", "WARN")

# ──────────────────────────────────────────────────────────────────────────────
# 6. Strategy Profile Validation
# ──────────────────────────────────────────────────────────────────────────────
section("6. STRATEGY PROFILE VALIDATION")

strat_detail = query("""
    SELECT
        strategy,
        COUNT(*) as cnt,
        AVG(total_upsets) as mean_upsets,
        AVG(probability) as mean_prob,
        MODE() WITHIN GROUP (ORDER BY champion_seed) as mode_champ_seed
    FROM full_brackets
    WHERE tournament_year = :yr
      AND strategy IS NOT NULL
    GROUP BY strategy
    ORDER BY AVG(total_upsets)
""", {"yr": YEAR})

print(f"\n  {'Strategy':<15} {'Count':>12} {'Mean Upsets':>12} {'Mean Prob':>14} {'Mode Champ Seed':>16}")
print(f"  {'-'*15} {'-'*12} {'-'*12} {'-'*14} {'-'*16}")
mean_upsets_by_strat = {}
for r in strat_detail:
    strat = r[0] or "NULL"
    cnt = int(r[1])
    mu = float(r[2]) if r[2] is not None else 0.0
    mp = float(r[3]) if r[3] is not None else 0.0
    ms = int(r[4]) if r[4] is not None else -1
    mean_upsets_by_strat[strat] = mu
    print(f"  {strat:<15} {cnt:>12,} {mu:>12.2f} {mp:>14.8f} {ms:>16}")

# Chalk should have fewer upsets than chaos
chalk_u = mean_upsets_by_strat.get("chalk", None)
chaos_u = mean_upsets_by_strat.get("chaos", None)
if chalk_u is not None and chaos_u is not None:
    if chalk_u < chaos_u:
        status(f"Chalk ({chalk_u:.2f}) < Chaos ({chaos_u:.2f}) upsets", "PASS")
    else:
        status(f"Chalk has MORE upsets than chaos — ordering wrong", "FAIL")

# ──────────────────────────────────────────────────────────────────────────────
# 7. Probability Sanity
# ──────────────────────────────────────────────────────────────────────────────
section("7. PROBABILITY SANITY")

prob_row = query_one("""
    SELECT
        SUM(probability)::double precision AS total_prob,
        MIN(probability) AS min_p,
        MAX(probability) AS max_p,
        AVG(probability) AS mean_p,
        COUNT(CASE WHEN probability <= 0 THEN 1 END) AS zero_or_neg,
        COUNT(CASE WHEN probability IS NULL THEN 1 END) AS null_count
    FROM full_brackets
    WHERE tournament_year = :yr
""", {"yr": YEAR})
total_prob = float(prob_row[0])
min_p, max_p, mean_p = float(prob_row[1]), float(prob_row[2]), float(prob_row[3])
zero_neg = int(prob_row[4])
null_p = int(prob_row[5])

print(f"\n  Sum of probabilities : {total_prob:>20.6f}")
print(f"  Min probability      : {min_p:>20.10f}")
print(f"  Max probability      : {max_p:>20.10f}")
print(f"  Mean probability     : {mean_p:>20.10f}")
print(f"  Zero/negative count  : {zero_neg:>20,}")
print(f"  NULL count           : {null_p:>20,}")

if abs(total_prob - 1.0) < 0.01:
    status("Probabilities normalized (sum ≈ 1.0)", "PASS")
else:
    expected_sum = total * mean_p
    status(f"Probability sum = {total_prob:.6f} (not normalized to 1.0)", "WARN",
           f"This is OK if individual bracket probs are not required to sum to 1")

if zero_neg == 0:
    status("No zero/negative probabilities", "PASS")
else:
    status(f"{zero_neg:,} brackets have probability <= 0", "FAIL")

if null_p == 0:
    status("No NULL probabilities", "PASS")
else:
    status(f"{null_p:,} NULL probabilities", "FAIL")

# ──────────────────────────────────────────────────────────────────────────────
# 8. F4 Outcomes
# ──────────────────────────────────────────────────────────────────────────────
section("8. F4 OUTCOMES")

f4_rows = query("""
    SELECT f4_outcomes, COUNT(*) as cnt
    FROM full_brackets
    WHERE tournament_year = :yr
    GROUP BY f4_outcomes
    ORDER BY f4_outcomes
""", {"yr": YEAR})

distinct_f4 = len(f4_rows)
print(f"\n  Distinct f4_outcomes values: {distinct_f4} (max possible: 8)")
print(f"\n  f4_outcomes distribution:")
for r in f4_rows:
    f4val = int(r[0])
    cnt = int(r[1])
    pct = cnt / total * 100 if total > 0 else 0
    # Decode: 3 bits = [South>East, West>Midwest, bit2(champion)]
    binary = f"{f4val:03b}"
    print(f"    {f4val:>3} ({binary}) : {cnt:>12,}  ({pct:.2f}%)")

if distinct_f4 == 8:
    status("All 8 F4 outcome combinations present", "PASS")
elif distinct_f4 >= 4:
    status(f"Only {distinct_f4}/8 F4 combinations present", "WARN")
else:
    status(f"Only {distinct_f4}/8 F4 combinations — very low diversity", "FAIL")

# ──────────────────────────────────────────────────────────────────────────────
# 9. Cross-Region Independence
# ──────────────────────────────────────────────────────────────────────────────
section("9. CROSS-REGION INDEPENDENCE (sample of 10,000)")

# Sample 10,000 random brackets and compute correlation
corr_row = query_one("""
    SELECT CORR(south_outcomes::float, east_outcomes::float) AS corr_se,
           CORR(south_outcomes::float, west_outcomes::float) AS corr_sw,
           CORR(east_outcomes::float, midwest_outcomes::float) AS corr_em
    FROM (
        SELECT south_outcomes, east_outcomes, west_outcomes, midwest_outcomes
        FROM full_brackets
        WHERE tournament_year = :yr
        TABLESAMPLE SYSTEM(0.005)
    ) sample
""", {"yr": YEAR})

corr_se = float(corr_row[0]) if corr_row[0] is not None else 0
corr_sw = float(corr_row[1]) if corr_row[1] is not None else 0
corr_em = float(corr_row[2]) if corr_row[2] is not None else 0

print(f"\n  Correlation(South, East)     = {corr_se:.6f}")
print(f"  Correlation(South, West)     = {corr_sw:.6f}")
print(f"  Correlation(East, Midwest)   = {corr_em:.6f}")

max_corr = max(abs(corr_se), abs(corr_sw), abs(corr_em))
if max_corr < 0.05:
    status(f"Regions are independent (max |corr| = {max_corr:.4f})", "PASS")
elif max_corr < 0.15:
    status(f"Mild cross-region correlation detected (max |corr| = {max_corr:.4f})", "WARN")
else:
    status(f"High cross-region correlation — regions NOT independent (max |corr| = {max_corr:.4f})", "FAIL")

# ──────────────────────────────────────────────────────────────────────────────
# 10. Data Integrity
# ──────────────────────────────────────────────────────────────────────────────
section("10. DATA INTEGRITY")

# NULL checks
null_row = query_one("""
    SELECT
        COUNT(CASE WHEN south_outcomes IS NULL THEN 1 END) AS null_south,
        COUNT(CASE WHEN east_outcomes IS NULL THEN 1 END) AS null_east,
        COUNT(CASE WHEN west_outcomes IS NULL THEN 1 END) AS null_west,
        COUNT(CASE WHEN midwest_outcomes IS NULL THEN 1 END) AS null_midwest,
        COUNT(CASE WHEN f4_outcomes IS NULL THEN 1 END) AS null_f4,
        COUNT(CASE WHEN probability IS NULL THEN 1 END) AS null_prob,
        COUNT(CASE WHEN weight IS NULL THEN 1 END) AS null_weight,
        COUNT(CASE WHEN champion_seed IS NULL THEN 1 END) AS null_champ_seed,
        COUNT(CASE WHEN champion_region IS NULL THEN 1 END) AS null_champ_region,
        COUNT(CASE WHEN is_alive IS NULL THEN 1 END) AS null_is_alive
    FROM full_brackets
    WHERE tournament_year = :yr
""", {"yr": YEAR})

null_cols = [
    "south_outcomes", "east_outcomes", "west_outcomes", "midwest_outcomes",
    "f4_outcomes", "probability", "weight", "champion_seed", "champion_region", "is_alive"
]
print(f"\n  NULL value check:")
any_nulls = False
for i, col in enumerate(null_cols):
    cnt = int(null_row[i])
    if cnt > 0:
        print(f"    {col:<25} : {cnt:>12,} NULLs  <-- PROBLEM")
        any_nulls = True
    else:
        print(f"    {col:<25} : {cnt:>12,} NULLs  OK")

if not any_nulls:
    status("No NULLs in critical columns", "PASS")
else:
    status("Found NULLs in critical columns", "FAIL")

# Duplicate ID check
dup_row = query_one("""
    SELECT COUNT(*) - COUNT(DISTINCT id) AS duplicate_ids
    FROM full_brackets
    WHERE tournament_year = :yr
""", {"yr": YEAR})
dup_ids = int(dup_row[0])
if dup_ids == 0:
    status("No duplicate IDs", "PASS")
else:
    status(f"{dup_ids:,} duplicate IDs found", "FAIL")

# Invalid champion_region check
invalid_region_row = query_one("""
    SELECT COUNT(*) AS invalid_count
    FROM full_brackets
    WHERE tournament_year = :yr
      AND champion_region NOT IN ('East', 'South', 'West', 'Midwest')
""", {"yr": YEAR})
invalid_regions = int(invalid_region_row[0])
if invalid_regions == 0:
    status("All champion_region values are valid", "PASS")
else:
    # Show what the invalid values are
    bad_regions = query("""
        SELECT DISTINCT champion_region, COUNT(*)
        FROM full_brackets
        WHERE tournament_year = :yr
          AND champion_region NOT IN ('East', 'South', 'West', 'Midwest')
        GROUP BY champion_region
    """, {"yr": YEAR})
    status(f"{invalid_regions:,} invalid champion_region values", "FAIL",
           f"Values: {[(r[0], r[1]) for r in bad_regions]}")

# F4 range check (should be 0-7)
f4_range_row = query_one("""
    SELECT COUNT(*) AS out_of_range
    FROM full_brackets
    WHERE tournament_year = :yr
      AND (f4_outcomes < 0 OR f4_outcomes > 7)
""", {"yr": YEAR})
f4_bad = int(f4_range_row[0])
if f4_bad == 0:
    status("All f4_outcomes in valid range [0, 7]", "PASS")
else:
    status(f"{f4_bad:,} f4_outcomes out of range", "FAIL")

# Regional outcomes range check (should be 0-32767 for SMALLINT, but also valid as unsigned)
for col in ("south_outcomes", "east_outcomes", "west_outcomes", "midwest_outcomes"):
    range_row = query_one(f"""
        SELECT MIN({col}), MAX({col})
        FROM full_brackets
        WHERE tournament_year = :yr
    """, {"yr": YEAR})
    mn, mx = int(range_row[0]), int(range_row[1])
    print(f"\n  {col} range: [{mn}, {mx}]")
    if mn >= -32768 and mx <= 32767:
        status(f"{col} within SMALLINT range", "PASS")
    else:
        status(f"{col} out of SMALLINT range: [{mn}, {mx}]", "FAIL")

# ──────────────────────────────────────────────────────────────────────────────
# Vegas Odds Comparison (bonus check)
# ──────────────────────────────────────────────────────────────────────────────
section("BONUS: VEGAS ODDS COMPARISON")

try:
    odds_rows = query("""
        SELECT t.name, t.seed, t.region, o.fair_prob, o.implied_prob
        FROM odds o
        JOIN teams t ON t.id = o.team_id
        WHERE o.tournament_year = :yr
          AND o.market ILIKE '%championship%'
          AND o.line_type = 'futures'
        ORDER BY o.fair_prob DESC NULLS LAST
        LIMIT 10
    """, {"yr": YEAR})

    if odds_rows:
        print(f"\n  Vegas championship futures (top 10):")
        print(f"  {'Team':<25} {'Seed':>4} {'Region':<10} {'Fair Prob':>10} {'Implied':>10}")
        print(f"  {'-'*25} {'-'*4} {'-'*10} {'-'*10} {'-'*10}")
        for r in odds_rows:
            name, seed, region = r[0], r[1], r[2]
            fair = float(r[3]) if r[3] is not None else 0
            imp = float(r[4]) if r[4] is not None else 0
            print(f"  {name:<25} {seed:>4} {region:<10} {fair:>10.4f} {imp:>10.4f}")
        status("Vegas odds data available for comparison", "PASS")
    else:
        # Try a different query
        odds_rows2 = query("""
            SELECT t.name, t.seed, t.region, o.fair_prob, o.market, o.line_type
            FROM odds o
            JOIN teams t ON t.id = o.team_id AND t.tournament_year = o.tournament_year
            WHERE o.tournament_year = :yr
            ORDER BY o.fair_prob DESC NULLS LAST
            LIMIT 10
        """, {"yr": YEAR})
        if odds_rows2:
            print(f"\n  Odds data (top 10 by fair_prob):")
            for r in odds_rows2:
                print(f"    {r[0]:<25} seed={r[1]} region={r[2]} fair_prob={r[3]} market={r[4]} type={r[5]}")
        else:
            status("No odds data found in odds table", "WARN", "Skipping Vegas comparison")
except Exception as e:
    status(f"Odds comparison failed: {e}", "WARN")

# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────
section("SUMMARY")
print("""
  All checks complete. Review PASS/WARN/FAIL labels above.

  Key thresholds:
    PASS  = matches spec / healthy
    WARN  = worth investigating but not necessarily broken
    FAIL  = definite problem that should be fixed
""")
