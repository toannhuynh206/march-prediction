# Session Handoff — March Madness Bracket Simulation Engine
**Date:** 2026-03-06
**From:** Session 1 (Sonnet → Opus)
**To:** Session 2 (Opus 4.6 with Agent Teams enabled)

---

## What Was Accomplished

### Architecture Phase (Complete)
- Read and analyzed the project spec (`march-madness-plan.md`)
- Ran architecture planning agent → `architecture-plan.md` (identified 13 gaps)
- Created 7 agent role definitions in `agents/`
- Ran 3 research agents in parallel (Math, Stats, Betting) → full reports in `agents/reports/`
- Ran strategy review agent → honest critique of the model
- Locked 6 architectural decisions (see `agents/status/DECISION_LOG.md`)
- Created `CLAUDE.md` with full project conventions
- Set up Program Manager status tracking

### Settings Optimized
- Removed `"model": "sonnet"` override from project settings (was silently downgrading Opus)
- Increased `MAX_THINKING_TOKENS` from 10K to 50K
- Enabled `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- Added permissions for docker, npm, pytest, web access

---

## What Needs to Happen Next

### Priority 1: New Ideas from User (Not Yet Integrated)

The user proposed three major strategic shifts at end of session that change the architecture:

#### A) Division-First Optimization
**The idea:** Don't optimize for full 63-game bracket perfection — optimize for regional/round accuracy. Getting a perfect South region bracket is achievable. Getting a perfect Round of 64 is achievable. Getting all 63 games right is near-impossible.

**Impact on architecture:**
- Simulation objective function changes: maximize P(correct region) not P(correct bracket)
- Scoring should weight regional accuracy heavily
- May want separate simulation runs per region with different optimization targets
- Bracket "quality" is measured by: how many regions correct? How many rounds correct?

#### B) Genetic Algorithm / Evolutionary Approach
**The idea:** Model brackets as organisms that evolve. Upsets = mutations. Bracket survival = fitness.

**Key concepts to explore:**
- **Population:** Start with N brackets (the 3M stratified IS samples)
- **Fitness function:** How well does a bracket match emerging real results? How "probable" is it given the model?
- **Selection:** Keep the fittest brackets, discard the weakest
- **Crossover:** Combine two good brackets (e.g., take South region from bracket A, East from bracket B)
- **Mutation:** Random upset flips with a tunable mutation rate. Higher mutation = more exploration. Lower = more exploitation.
- **Temporal correlation:** Day 1 results inform Day 2 mutation rates. If Day 1 had 4 upsets (high chaos), increase mutation rate for Day 2 predictions.

**This is fundamentally different from static Monte Carlo.** MC generates all brackets upfront and prunes. GA evolves brackets in real-time as the tournament progresses. Could layer GA on top of the initial MC population.

#### C) Biology Agent / AlphaFold Inspiration
**The idea:** Research how DeepMind's AlphaFold solved protein folding and see if similar approaches apply.

**AlphaFold analogy:**
- Protein: amino acid sequence → 3D structure (solved by attention + evolutionary data)
- Bracket: team stats → bracket outcome structure
- Both are combinatorial prediction problems with hierarchical dependencies
- AlphaFold uses Multiple Sequence Alignment (evolutionary history) — analogy: historical bracket patterns across 40 years of tournaments

**Create `agents/biology-agent.md`** to research:
- Evolutionary algorithms for combinatorial optimization
- AlphaFold's attention mechanism approach
- Genetic programming applied to bracket pools
- How mutation rates should adapt based on observed results
- Fitness landscape analysis of the bracket space

### Priority 2: Full Team Review
Once Biology Agent is created, run ALL specialist agents through a review of the complete strategy:
- Math Agent: Is genetic algorithm mathematically sound? How does it interact with stratified IS?
- Stats Agent: What historical patterns should inform mutation rates?
- Betting Agent: Can market line movements inform mutation rates in real-time?
- Biology Agent: What's the optimal population size, mutation rate, crossover strategy?
- Lead SWE: Is this computationally feasible? Memory? Speed?

### Priority 3: Begin Sprint 1
After team alignment, start building:
- Task 1.1: Project scaffold
- Task 1.2: docker-compose.yml
- Task 1.3: DB schema
- etc.

---

## Current File Tree
```
march-prediction/
├── CLAUDE.md                          ← Project bible
├── march-madness-plan.md              ← Original spec
├── architecture-plan.md               ← First architecture review
├── .claude/
│   └── settings.local.json            ← Optimized settings (Opus, agent teams, 50K thinking)
├── agents/
│   ├── math-agent.md                  ← Role definition
│   ├── stats-agent.md                 ← Role definition
│   ├── sports-betting-agent.md        ← Role definition
│   ├── elite-research-agent.md        ← Role definition
│   ├── program-manager-agent.md       ← Role definition
│   ├── lead-swe-agent.md             ← Role definition
│   ├── design-agent.md               ← Role definition
│   ├── biology-agent.md              ← NEEDS TO BE CREATED
│   ├── HANDOFF.md                    ← This file
│   ├── reports/
│   │   ├── math-agent-report.md       ← Stratified IS, world simulation, Bayesian updating
│   │   ├── stats-agent-report.md      ← Revised power index, historical seed rates, calibration
│   │   └── betting-agent-report.md    ← Market blend, upset factors, data sources
│   └── status/
│       ├── PROJECT_STATUS.md          ← Sprint tracker (Sprint 1 ready to start)
│       └── DECISION_LOG.md            ← 6 locked decisions
```

---

## User Context
- Technically sophisticated, thinks in biological/evolutionary metaphors
- Wants to deeply understand the math — explain with analogies, not just formulas
- Values agent debate and collaboration
- Primary goal: maximize bracket accuracy at the REGIONAL and ROUND level, not just full bracket
- Now on Opus 4.6 with agent teams — use full capabilities
- Has everything-claude-code plugin with agents, skills, and /commands available
