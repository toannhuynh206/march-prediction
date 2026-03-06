# Project Status — March Madness Bracket Simulation Engine
**Last updated:** 2026-03-06
**Current Phase:** Sprint 1 — READY TO START
**Program Manager:** Active

---

## All Pre-Sprint Decisions: LOCKED ✓

| Decision | Choice |
|----------|--------|
| Infrastructure | Docker Compose (PostgreSQL 16 + pgAdmin) |
| First Four | Simulate probabilistically (4 games) |
| Tournament data | 2025 pre-tournament state as test; swap 2026 on March 15 |
| Simulation method | 3M Stratified Importance Sampling per region (12M total) |
| Win probability | Blend: 40% stats + 45% market + 15% factors (log-odds) |

---

## Sprint Status

| Sprint | Name | Status | Gate |
|--------|------|--------|------|
| Pre-Sprint | Architecture + Decisions | ✅ COMPLETE | All decisions locked |
| Sprint 1 | Foundation | 🟡 READY TO START | — |
| Sprint 2 | Research Agent | ⬜ NOT STARTED | Sprint 1 complete |
| Sprint 3 | Simulation Engine | ⬜ NOT STARTED | Sprint 2 complete + data in DB |
| Sprint 4 | Tracker Website | ⬜ NOT STARTED | Sprint 3 complete + 12M brackets in DB |
| Sprint 5 | Polish + Final Four | ⬜ FUTURE | — |

---

## Sprint 1 Tasks (Start Here)

| Task | Description | Dependencies | Parallel? |
|------|-------------|--------------|-----------|
| 1.1 | Project scaffold (folders, requirements.txt, package.json, .gitignore) | None | Yes |
| 1.2 | docker-compose.yml + .env.example | None | Yes |
| 1.3 | DB migrations: 001_initial_schema.sql (all tables with tournament_year, partitioning) | None | Yes |
| 1.4 | DB migrations: 002_indexes.sql (all indexes including partial index on is_alive) | 1.3 | No |
| 1.5 | config/settings.py + config/constants.py (weights, k placeholder, regions) | 1.1 | Yes |
| 1.6 | simulation/bracket_structure.py (seed ordering, game_index mapping) | 1.5 | Yes |
| 1.7 | simulation/encoder.py + tests/test_encoder.py | 1.6 | No |
| 1.8 | data/brackets/2025_bracket.json (all 68 teams, seeds, regions) | None | Yes |
| 1.9 | data/historical/seed_win_rates.json (1985-2024 upset rates) | None | Yes |

**Sprint 1 Exit Gate:**
- [ ] `docker compose up -d` works, PostgreSQL accessible
- [ ] All tables created with correct schema
- [ ] `pytest tests/test_encoder.py` passes (round-trip encode/decode)
- [ ] 2025 bracket JSON populated with all 68 teams

---

## Agent Outputs

| Agent | Report | Status |
|-------|--------|--------|
| Math Agent | agents/reports/math-agent-report.md | ✅ COMPLETE |
| Stats Agent | agents/reports/stats-agent-report.md | ✅ COMPLETE |
| Sports Betting Agent | agents/reports/betting-agent-report.md | ✅ COMPLETE |
| Architecture Agent | architecture-plan.md | ✅ COMPLETE |

## Agent Team (All Defined)

| Agent | File | Status |
|-------|------|--------|
| Program Manager | agents/program-manager-agent.md | ✅ Active |
| Lead Software Engineer | agents/lead-swe-agent.md | ✅ Ready |
| Design Agent | agents/design-agent.md | ✅ Ready |
| Elite Research Agent | agents/elite-research-agent.md | ✅ Ready — deploy in Sprint 2 |

---

## Next Immediate Actions
1. Begin Sprint 1 tasks 1.1, 1.2, 1.3, 1.5, 1.8, 1.9 in parallel
2. Deploy Elite Research Agent in Sprint 2 to collect 2025 team data
3. Obtain The Odds API key before Sprint 2 (free tier at the-odds-api.com)
