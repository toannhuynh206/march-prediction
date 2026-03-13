# Project Status — March Madness Bracket Simulation Engine

**Last updated:** 2026-03-12
**Current Phase:** Sprint 1 — IN PROGRESS
**Selection Sunday:** March 15 (3 days)
**Tournament starts:** March 19 (7 days)
**Deploy target:** March 16-17
**Daily board:** See ROADMAP.md

---

## All Pre-Sprint Decisions: LOCKED

| Decision | Choice |
|----------|--------|
| Infrastructure | Docker Compose (PostgreSQL 16 + pgAdmin) |
| First Four | Simulate probabilistically (4 games) |
| Tournament data | 2025 pre-tournament state as test; swap 2026 on March 15 |
| Simulation method | 3M Stratified Importance Sampling per region (12M total) |
| Win probability | Blend: 40% stats + 45% market + 15% factors (log-odds) |
| Power index | 9-factor model (AdjEM 40%, see DECISION_LOG.md) |
| K value | k=22 (Brier=0.189 on 79-game balanced dataset) |

---

## Sprint Status

| Sprint | Name | Status | Gate |
|--------|------|--------|------|
| Pre-Sprint | Architecture + Decisions | COMPLETE | All decisions locked |
| Sprint 1 | Foundation + Math | IN PROGRESS | Core engine working |
| Sprint 2 | Research + Data Pipeline | IN PROGRESS (parallel) | All 64 teams populated |
| Sprint 3 | Simulation + Storage | NOT STARTED | 12M brackets generated |
| Sprint 4 | Deploy + Tracker | NOT STARTED | Live tracking works |
| Sprint 5 | Tournament Tracking | NOT STARTED | Games entered, pruning works |

---

## What's DONE

### Source Code (17 files, 6,153 lines)
| File | Lines | Status |
|------|-------|--------|
| math_primitives.py | 524 | DONE — logit, sigmoid, de-vig, encoding, scoring |
| k_calibration.py | 275 | DONE — k=22, Brier=0.189, 79-game dataset |
| talent_factors.py | 263 | DONE — NBA draft, experience, star player boosts |
| round_probability.py | 634 | DONE — 6 signals + talent factors wired in |
| seed_composition.py | 671 | DONE — stratified sampling, FF composition |
| calibration_targets.py | 292 | DONE — historical upset rates, modal configs |
| strategy_profiles.py | 408 | DONE — temperature scaling, upset clustering |
| sharpening_rules.py | 279 | DONE — chalk preference, cinderella filtering |
| portfolio_strategy.py | 309 | DONE — cluster budget, sharpening |
| round_calibration.py | 396 | DONE — round-level calibration targets |
| engine.py | 520 | DONE — vectorized NumPy simulation |
| stratifier.py | 248 | DONE — Neyman allocation |
| probability_engine.py | 250 | DONE — probability matrix builder |
| research_aggregator.py | 391 | DONE — data source aggregation |
| tournament_config.py | 66 | DONE — year, regions, seeds |
| database.py | 326 | DONE — SQLite layer |
| test_math_primitives.py | 301 | DONE — unit tests |

### API (10 files, 1,019 lines) — DONE
### Frontend (9 files, 3,824 lines) — DONE
### Agent Reports (15+ files) — DONE
### Research Data (16 files) — NEEDS DAILY REFRESH

---

## What's LEFT (Critical Path)

| Priority | Task | Target Date | Status |
|----------|------|-------------|--------|
| P0 | Daily research refresh | Every day | Running now (March 12) |
| P0 | Integration test on 2025 data | March 12-13 | NOT STARTED |
| P0 | Docker + PostgreSQL setup | March 14 | NOT STARTED |
| P0 | Populate 2026 bracket | March 15 | Waiting for Selection Sunday |
| P0 | Deploy to production | March 16-17 | NOT STARTED |
| P0 | Generate 12M brackets | March 16 | NOT STARTED |
| P1 | Blog content updates | Ongoing | IN PROGRESS |
| P1 | Verify pruner end-to-end | March 17 | NOT STARTED |
| P2 | Genetic algorithm layer | Deferred | DECIDED: defer to 2027 |
| P2 | Division-first optimization | Deferred | REVIEW NEEDED |

---

## Research Pipeline Status

| Agent/Source | Last Run | Data Date | Next Run |
|-------------|----------|-----------|----------|
| KenPom refresh | March 12 | Updating... | March 13 |
| Vegas odds | March 12 | Updating... | March 13 |
| Injury tracker | March 12 | Updating... | March 13 |
| Conference tourneys | March 12 | Updating... | March 13 |
| YouTube analysis | March 12 | Updating... | March 15 |
| Reddit sentiment | March 10 | March 10 | March 14 |
| Expert brackets | — | — | March 15 (post-bracket) |

---

## Agent Team

| Agent | File | Status |
|-------|------|--------|
| Program Manager | agents/program-manager-agent.md | Active |
| Lead SWE | agents/lead-swe-agent.md | Ready |
| Design Agent | agents/design-agent.md | Ready |
| Math Agent | agents/math-agent.md | Report complete |
| Stats Agent | agents/stats-agent.md | Report complete |
| Betting Agent | agents/sports-betting-agent.md | Report complete |
| Biology Agent | agents/biology-agent.md | Report complete |
| Research Validator | agents/research-validator-agent.md | Ready |
| Elite Research | agents/elite-research-agent.md | Active (daily refresh) |
