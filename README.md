# March Madness Bracket Prediction Engine

## Generation Proof — 2026 NCAA Tournament

**206,000,000 brackets generated BEFORE the first game.**

| Field | Value |
|-------|-------|
| Generated | **March 19, 2026 at 3:54 PM UTC** |
| Total brackets | 206,000,000 |
| SHA-256 | `6d9f395424b988a383e63720cd87482fa88c588f5ffa880db82b3fb2c6a68f84` |
| Unique brackets | 201,370,623 (97.8%) |
| 1-seed champion rate | 65.4% |

### How to verify the hash

The SHA-256 is computed from this exact string (champion counts per seed/region + strategy counts):

```
year=2026|total=206000000|1-East:44211012|1-Midwest:28222682|1-South:26135494|1-West:36095611|2-East:4402912|2-Midwest:13611079|2-South:25858110|2-West:10662572|3-East:2695204|3-Midwest:551685|3-South:3089718|3-West:2683138|4-East:1170209|4-Midwest:856123|4-South:562775|4-West:883747|5-East:772958|5-Midwest:458421|5-South:468211|5-West:454797|6-East:110881|6-Midwest:1109541|6-South:135521|6-West:153329|7-East:87681|7-Midwest:65778|7-South:89670|7-West:43449|8-East:36012|8-Midwest:29892|8-South:42234|8-West:27996|9-East:14983|9-Midwest:11387|9-South:32616|9-West:12102|10-East:17080|10-Midwest:18236|10-South:14256|10-West:13881|11-East:17884|11-Midwest:6120|11-South:13356|11-West:23549|12-East:6094|12-Midwest:4776|12-South:4255|12-West:3495|13-East:1279|13-Midwest:1374|13-South:994|13-West:1484|14-East:827|14-Midwest:504|14-South:541|14-West:485|chalk:61800000|chaos:20600000|cinderella:30900000|smart_upset:20600000|standard:72100000
```

Verify it yourself:
```bash
echo -n 'year=2026|total=206000000|1-East:44211012|1-Midwest:28222682|1-South:26135494|1-West:36095611|2-East:4402912|2-Midwest:13611079|2-South:25858110|2-West:10662572|3-East:2695204|3-Midwest:551685|3-South:3089718|3-West:2683138|4-East:1170209|4-Midwest:856123|4-South:562775|4-West:883747|5-East:772958|5-Midwest:458421|5-South:468211|5-West:454797|6-East:110881|6-Midwest:1109541|6-South:135521|6-West:153329|7-East:87681|7-Midwest:65778|7-South:89670|7-West:43449|8-East:36012|8-Midwest:29892|8-South:42234|8-West:27996|9-East:14983|9-Midwest:11387|9-South:32616|9-West:12102|10-East:17080|10-Midwest:18236|10-South:14256|10-West:13881|11-East:17884|11-Midwest:6120|11-South:13356|11-West:23549|12-East:6094|12-Midwest:4776|12-South:4255|12-West:3495|13-East:1279|13-Midwest:1374|13-South:994|13-West:1484|14-East:827|14-Midwest:504|14-South:541|14-West:485|chalk:61800000|chaos:20600000|cinderella:30900000|smart_upset:20600000|standard:72100000' | shasum -a 256
```

Should output: `6d9f395424b988a383e63720cd87482fa88c588f5ffa880db82b3fb2c6a68f84`

This proves: the exact number of brackets picking each seed in each region as champion was locked before the tournament started. If any bracket was added, removed, or modified after the fact, the hash would not match.

The `full_brackets` table is **immutable** — no rows are ever modified or deleted after generation. Pruning works via separate `alive_outcomes_*` tables.

---

## How It Works

An agentic AI system that generates 206 million stratified importance-sampled March Madness brackets using a multi-signal probability model.

### 4-Layer Probability Blend

```
P_final = sigmoid(w_m × logit(P_market) + w_s × logit(P_stats) + w_x × logit(P_matchup) + w_f × logit(P_factors))
```

Weights adapt based on spread magnitude:

| Tier | Condition | Market | Stats | Matchup | Factors |
|------|-----------|--------|-------|---------|---------|
| locks | \|spread\| > 15 | 0.60 | 0.20 | 0.10 | 0.10 |
| lean | \|spread\| 5–15 | 0.45 | 0.25 | 0.15 | 0.15 |
| coin_flip | \|spread\| < 5 | 0.40 | 0.25 | 0.20 | 0.15 |

### 9-Factor Power Index

| Factor | Weight |
|--------|--------|
| AdjEM (KenPom) | 53% |
| Defensive Efficiency | 8% |
| Non-Conference SOS | 8% |
| Experience (Bart Torvik) | 8% |
| Luck Adjustment | 6% |
| Free Throw Rate | 6% |
| Coaching Tournament Score | 3% |
| Key Injuries | 5% |
| 3-Point Variance | 3% |

### 5 Strategy Profiles

| Strategy | Allocation | Temperature | Description |
|----------|-----------|-------------|-------------|
| chalk | 30% | T=0.5 | Conservative — all regions favor top seeds |
| standard | 35% | T=1.0 | True probability — unmodified model |
| smart_upset | 10% | T=0.7/2.0 | Targeted coin-flip upsets |
| cinderella | 15% | T=1.0/2.5 | ~1 region gets chaos |
| chaos | 10% | T=1.8/3.0 | Multiple upset regions |

### Validity Bitmap Pruning

The 206M bracket table is **immutable**. Pruning uses 5 tiny alive-outcome tables (32,768 rows each). A bracket is alive if all 5 of its packed outcome values exist in the alive tables. Prune speed: < 50ms per game.

## Tech Stack

- **Python 3.12** + NumPy — Simulation engine
- **PostgreSQL 16** — 206M bracket storage (35 GB)
- **FastAPI** — REST API
- **React + Vite** — Live tournament tracker
- **Claude Code Agent Teams** — Multi-agent research pipeline

## Live Site

[marchmadnesschallenge.store](https://marchmadnesschallenge.store)
