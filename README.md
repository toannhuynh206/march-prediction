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

The SHA-256 hash is computed from the champion distribution + strategy breakdown of all 206M brackets.
This commit timestamp on GitHub serves as cryptographic proof that these brackets existed before tournament results were known.

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
