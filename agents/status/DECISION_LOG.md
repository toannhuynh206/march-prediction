# Decision Log

## D001 — Simulation Algorithm
**Date:** 2026-03-06  **Status:** LOCKED
**Decision:** Stratified Importance Sampling, 3M brackets per region (12M total)
**Proposed by:** Math Agent | **Approved by:** User
**Details:**
- 3M samples per region with world-stratified allocation (not 10M naive MC)
- 30 canonical "worlds" defined by (k_R1 upset count, k_R2 upset count, champion seed)
- Budget allocated proportional to √P(world) — Neyman allocation
- Guaranteed minimum 50K brackets per possible champion seed
- `weight FLOAT` and `stratum_id INT` columns added to brackets table
- Bayesian soft-likelihood weight update after each real round (SMC-style)
- Binary is_alive pruning retained for user-facing display; weights used for internal stats
- Storage: 12M × ~6 bytes = ~72MB total (vs 80MB naive MC, with far better rare coverage)

## D002 — Power Index Formula
**Date:** 2026-03-06  **Status:** LOCKED
**Decision:** Revised 9-factor formula (see below)
**Proposed by:** Stats Agent | **Approved by:** User
| Factor | Weight | Notes |
|--------|--------|-------|
| AdjEM (KenPom) | 40% | Single most predictive stat. Subsumes O+D. |
| Defensive Efficiency Premium | 10% | D > O in single-elim. Bonus for top-20 AdjD in tier. |
| Non-Conference SOS | 10% | Tests quality vs. external competition (not redundant with AdjEM) |
| Experience Score (Bart Torvik) | 10% | Validated independent predictor |
| Luck Adjustment (Pythagorean gap) | 8% | Negative luck teams overseeded; invert KenPom Luck |
| Free Throw Rate Index | 7% | Close-game discriminator (FTA/FGA + FT%) |
| Coaching Tournament Score | 7% | 15+ appearances: bonus; first-timer: penalty |
| Key Injuries | 5% | Applied as hard point adjustment: -2 role, -8 starter, -15 star |
| 3-Point Variance Flag | 3% | Widens probability distribution; does NOT shift mean |
**REMOVED:** Standalone AdjO/AdjD (double-counted), Seed (collinear), Recent Form (noise)

## D003 — Market Signal Integration
**Date:** 2026-03-06  **Status:** LOCKED (amended v2)
**Decision:** 4-component log-odds blend with CTO-approved weights
**Proposed by:** Sports Betting Agent + Math Agent | **Approved by:** User + CTO
**Formula:** `P_final = sigmoid(w_m×logit(P_market) + w_s×logit(P_stats) + w_x×logit(P_matchup) + w_f×logit(P_factors))`

| Context | w_m | w_s | w_x | w_f |
|---------|-----|-----|-----|-----|
| Game-specific lines (baseline) | 0.55 | 0.25 | 0.12 | 0.08 |
| Futures only (pre-bracket) | 0.40 | 0.35 | 0.15 | 0.10 |
| No market data (fallback) | 0.00 | 0.55 | 0.30 | 0.15 |
| Live tournament (R2+) | 0.60 | 0.18 | 0.14 | 0.08 |

- P_market: de-vigged moneylines (multiplicative for games, Shin for futures)
- P_stats: power index logistic function (D002 + D004)
- P_matchup: pace mismatch, size, 3PT variance, FT in close games (max +/- 0.8 pts)
- P_factors: poll residual, sentiment (small weight)
- Market source: The Odds API (the-odds-api.com) — free tier sufficient
- Blue-blood futures deflator: ×0.88-0.92 on Duke/Kansas/Kentucky/UNC championship futures
- Year-adaptive via Futures Concentration Index (FCI): chalk_factor = FCI / 0.40
- Futures consistency check: if simulation champion % deviates >15% from market, recalibrate power index

## D004 — Logistic Function Calibration
**Date:** 2026-03-06  **Status:** LOCKED
**Decision:** Calibrate divisor k against historical data; target Brier Score ≤ 0.205
**Current formula:** `P(A wins) = 1 / (1 + 10^((power_B - power_A) / k))`
- k is NOT assumed to be 15; it will be fit to historical tournament data
- Grid search: k ∈ [10, 12, 14, 16, 18, 20], minimize Brier Score on 2010-2019 tournament games
- Validation set: 2021-2024 tournament games (held out)
- Benchmark: Brier Score must beat seed-only model (0.225); target ≤ KenPom baseline (0.205)

## D005 — Tournament Data Strategy
**Date:** 2026-03-06  **Status:** LOCKED
**Decision:** Use 2025 bracket data (pre-tournament state) as test harness now; swap to 2026 on Selection Sunday March 15
- Research agents will collect 2025 team stats AS OF the pre-tournament date (March 2025)
- All DB schemas include `tournament_year INT NOT NULL` column
- Swapping years = updating `tournament_year` in config only; no code changes
- First Four: simulate probabilistically (4 separate games before main bracket)

## D006 — Infrastructure
**Date:** 2026-03-06  **Status:** LOCKED
**Decision:** Docker Compose for local PostgreSQL + pgAdmin
- `docker-compose.yml` in project root
- PostgreSQL 16, pgAdmin 4
- All credentials in `.env` file (not committed)
- Table partitioning by region on brackets table
- PostgreSQL COPY (not INSERT) for 12M bracket bulk load
