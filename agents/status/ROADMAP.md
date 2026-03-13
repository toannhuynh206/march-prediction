# DAILY ROADMAP — March Madness Bracket Engine

**Last updated:** 2026-03-12
**Selection Sunday:** March 15 (3 days away)
**Tournament starts:** March 19 (7 days away)
**Deploy target:** March 16-17 (Sunday/Monday)

---

## DAILY CHECKLIST (Run Every Session)

- [ ] Research refresh: KenPom, odds, injuries, conference tourneys
- [ ] Review research agent outputs for accuracy
- [ ] Update blog/frontend with latest insights
- [ ] Check for new conference tournament results
- [ ] Run test simulation if code changed
- [ ] Update this roadmap with progress

---

## TIMELINE: March 12 → Tournament

### TODAY — March 12 (Wednesday)
**Priority: Research + Roadmap + Code Integration**
- [x] Wire talent_factors.py into probability engine
- [x] Launch daily research refresh (5 agents)
- [x] Create this roadmap
- [ ] Review research agent outputs when they return
- [ ] Test run: simulate 2025 bracket end-to-end
- [ ] Blog update with latest research insights

### March 13 (Thursday)
**Priority: Simulation Pipeline + Test Run**
- [ ] End-to-end simulation test on 2025 data
- [ ] Verify bracket encoding round-trip
- [ ] Daily research refresh
- [ ] Fix any simulation bugs found
- [ ] Blog update

### March 14 (Friday)
**Priority: Infrastructure + Deployment Prep**
- [ ] Docker Compose + PostgreSQL setup
- [ ] Database schema deployment
- [ ] SQLite → PostgreSQL migration path
- [ ] Deploy.sh testing
- [ ] Daily research refresh
- [ ] Pre-Selection Sunday blog post

### March 15 (Saturday) — SELECTION SUNDAY
**Priority: BRACKET DROPS — All Hands**
- [ ] Watch Selection Sunday show
- [ ] Create data/brackets/2026_bracket.json with actual bracket
- [ ] Populate all 64 teams with seeds, regions
- [ ] Get R64 Vegas lines (released within hours of bracket)
- [ ] Final KenPom/rankings snapshot
- [ ] Daily research: injury updates, expert bracket picks
- [ ] Update blog with bracket reaction + our picks

### March 16 (Sunday) — DEPLOY DAY
**Priority: Deploy + Generate Brackets**
- [ ] Deploy frontend + API to production
- [ ] Run full 12M bracket simulation (3M × 4 regions)
- [ ] Load brackets into PostgreSQL
- [ ] Verify pruner works with test results
- [ ] API endpoint testing (GET /stats, POST /results)
- [ ] Blog: publish our bracket + methodology
- [ ] Share with friends/pool members

### March 17 (Monday) — DEPLOY BUFFER
**Priority: Polish + Final Testing**
- [ ] Stress test API under load
- [ ] Fix any deployment bugs
- [ ] Final odds update before tip-off
- [ ] Blog: final predictions post

### March 18 (Tuesday)
**Priority: Final Pre-Game Check**
- [ ] Last injury updates
- [ ] Last odds movements
- [ ] Ensure live tracking is ready
- [ ] Blog: game day preview

### March 19 (Wednesday) — TOURNAMENT STARTS
**Priority: LIVE TRACKING**
- [ ] Enter R64 results as games finish
- [ ] Monitor bracket pruning
- [ ] Track survival rates
- [ ] Blog: Day 1 recap + updated odds
- [ ] Verify weight re-normalization after pruning

### March 20-22 — R64 + R32
- [ ] Continue entering results
- [ ] Daily survival updates
- [ ] Blog: daily recaps

### March 27-28 — Sweet 16 / Elite 8
- [ ] Enter S16/E8 results
- [ ] Blog: regional analysis

### April 5-7 — Final Four + Championship
- [ ] Enter F4 results
- [ ] Championship prediction
- [ ] Blog: final analysis + post-mortem

---

## WORK STREAMS (Priority Order)

### 1. RESEARCH (Daily — Never Stops)
**Owner:** Research agents (automated)
**Status:** Running now (March 12 refresh in progress)

| Data Source | Last Updated | Frequency | Status |
|------------|-------------|-----------|--------|
| KenPom rankings | March 10 | Daily | REFRESHING NOW |
| Vegas odds/futures | March 10 | Daily | REFRESHING NOW |
| Injury reports | March 10 | Daily | REFRESHING NOW |
| Conference tourneys | March 10 | Daily | REFRESHING NOW |
| YouTube analysis | Never | Weekly | REFRESHING NOW |
| Reddit sentiment | March 10 | Every 2-3 days | Current |
| NBA mock drafts | March 10 | Weekly | Current |
| Expert brackets | Not started | After bracket drop | Waiting |

### 2. SIMULATION ENGINE (Code Complete — Needs Integration Test)
**Status:** Core math done, needs end-to-end test

| Component | File | Status |
|-----------|------|--------|
| Math primitives | src/math_primitives.py | DONE |
| K calibration | src/k_calibration.py | DONE (k=22, Brier=0.189) |
| Talent factors | src/talent_factors.py | DONE |
| Round probability | src/round_probability.py | DONE (talent wired in) |
| Seed composition | src/seed_composition.py | DONE |
| Calibration targets | src/calibration_targets.py | DONE |
| Strategy profiles | src/strategy_profiles.py | DONE |
| Sharpening rules | src/sharpening_rules.py | DONE |
| Portfolio strategy | src/portfolio_strategy.py | DONE |
| Simulation engine | src/engine.py | DONE |
| Stratifier | src/stratifier.py | DONE |
| Probability engine | src/probability_engine.py | DONE |
| Research aggregator | src/research_aggregator.py | DONE |
| Round calibration | src/round_calibration.py | DONE |
| Tournament config | src/tournament_config.py | DONE |
| Database layer | src/database.py | DONE |
| **Integration test** | — | NOT DONE |

### 3. FRONTEND + API (Built — Needs Deployment)
**Status:** React app + FastAPI complete, not deployed

| Component | Status |
|-----------|--------|
| App.jsx + routing | DONE |
| BracketView.jsx | DONE |
| StatsPage.jsx | DONE |
| ExplorerPage.jsx | DONE |
| BlogPage.jsx | DONE |
| AdminPage.jsx | DONE |
| API routes (stats, results, brackets, events) | DONE |
| Pruner service | DONE |
| Decoder service | DONE |
| Zustand store | DONE |
| API client + polling | DONE |
| **Deployment** | NOT DONE |

### 4. INFRASTRUCTURE (Not Started)
**Status:** Needs setup before Selection Sunday

| Task | Status | Blocker |
|------|--------|---------|
| Docker Compose (PostgreSQL) | NOT DONE | None |
| Database schema deployment | NOT DONE | Docker |
| .env setup | NOT DONE | None |
| Production deployment | NOT DONE | All above |
| Domain/hosting | NOT DONE | Decision needed |

### 5. BLOG CONTENT (Ongoing)
**Status:** BlogPage.jsx exists, needs content updates

| Post | Status | Target Date |
|------|--------|------------|
| Methodology explainer | DRAFT (in BlogPage) | March 13 |
| Pre-Selection Sunday preview | NOT STARTED | March 14 |
| Bracket reaction | NOT STARTED | March 15 |
| Our picks + strategy | NOT STARTED | March 16 |
| Daily tournament recaps | NOT STARTED | March 19+ |

---

## CRITICAL PATH (Must-Do Before Tournament)

```
March 12-14: Integration test on 2025 data
March 14-15: Infrastructure (Docker, DB, deploy prep)
March 15:    Bracket drops → populate 2026_bracket.json + get lines
March 16-17: Deploy + generate 12M brackets + verify pruner
March 19:    GO LIVE — start tracking
```

**If we only have time for ONE thing each day:**
- Mar 12: Integration test ← proves the engine works
- Mar 13: Fix bugs from test
- Mar 14: Docker + DB setup
- Mar 15: Populate real bracket data
- Mar 16: Deploy + simulate
- Mar 17: Buffer day
- Mar 18: Final check
- Mar 19: Track games

---

## RISKS

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Bracket data entry errors | Medium | HIGH | Double-check against ESPN bracket |
| Simulation takes too long | Low | HIGH | Test on 100K first, then scale to 12M |
| PostgreSQL not ready | Medium | HIGH | Fallback: SQLite for test, PG for prod |
| Vegas lines not available in time | Low | MEDIUM | Use futures-only tier weights |
| Deployment issues | Medium | MEDIUM | Deploy Sunday, Monday buffer |
| Stale research data | HIGH | HIGH | Daily automated refresh (fixed today) |

---

## DECISIONS NEEDED

1. **Hosting platform** — Where to deploy? (Fly.io, Railway, DigitalOcean, AWS?)
2. **Domain name** — Do we want a custom domain?
3. **Genetic algorithm** — Layer on top of stratified IS or defer to 2027?
4. **Division-first optimization** — Change objective function or defer?

---

## DONE (Completed Work)

- [x] Architecture finalized + 6 decisions locked
- [x] 9-factor power index formula
- [x] Win probability blend (3-layer logit)
- [x] K calibration grid search (k=22, Brier=0.189)
- [x] 17 Python source files (6,153 lines)
- [x] API layer (10 files, 1,019 lines)
- [x] Frontend (9 files, 3,824 lines)
- [x] All agent reports complete (Math, Stats, Betting, Biology)
- [x] GA feasibility review complete
- [x] Historical Final Four data verified (1985-2025)
- [x] Talent factors module (NBA draft, experience, star player)
- [x] Talent factors wired into probability engine
- [x] 2025 test data collected
- [x] 2026 research data collected (needs daily refresh)
- [x] Database schema written
- [x] Test suite for math primitives
