# March Madness Bracket Prediction Engine

An agentic AI system that generates 10 million unique, highly probable March Madness bracket scenarios using a multi-signal probability model driven primarily by Vegas betting lines.

## How It Works

The engine uses a **4-component log-odds blend** to compute win probabilities for every possible tournament matchup:

```
P_final = sigmoid(w_m * logit(P_market) + w_s * logit(P_stats) + w_x * logit(P_matchup) + w_f * logit(P_factors))
```

| Component | Weight | Source |
|-----------|--------|--------|
| P_market (Vegas lines) | **0.55** | De-vigged moneylines + spreads from multiple sportsbooks |
| P_stats (Power ratings) | 0.25 | KenPom/Bart Torvik adjusted efficiency margins |
| P_matchup (Style fit) | 0.12 | Tempo, size, pace differentials |
| P_factors (Sentiment) | 0.08 | ESPN pick %, expert consensus, YouTube analyst sentiment |

Vegas lines carry the highest weight because the market aggregates information from thousands of sharp bettors and is the single most accurate predictor of tournament outcomes.

### Weight Tiers

Weights shift based on data availability:
- **Pre-tournament (futures only):** Market 0.40, Stats 0.35, Matchup 0.15, Factors 0.10
- **Game lines available:** Market 0.55, Stats 0.25, Matchup 0.12, Factors 0.08
- **Live tournament:** Market 0.60, Stats 0.18, Matchup 0.14, Factors 0.08

## Architecture

### Bracket Generation (10M unique brackets)

1. **Exhaustive regional enumeration** — 2^15 = 32,768 possible brackets per region. Every single one is scored.
2. **Final Four scenario generation** — Top regional brackets combined into plausible championship scenarios.
3. **Stratified systematic sampling** — 10M full brackets selected proportionally to scenario probability (Neyman allocation).
4. **63-bit encoding** — Each bracket stored as an 8-byte packed integer for efficient storage (~500MB for 10M brackets).

### Live Updating

As the tournament progresses:
- Dead brackets are hard-pruned (weight → 0)
- Surviving brackets reweighted based on margin of victory
- New odds fetched for upcoming rounds
- Market weight increases (lines get sharper as tournament progresses)

### Agentic Research Pipeline

The system uses specialized AI agents to collaboratively research and refine predictions:
- **Sports Analyst** — Team data collection, top 30 factors, YouTube transcript sentiment analysis
- **Betting Agent** — Odds de-vigging, line movement signals, sharp vs public money splits
- **Math Agent** — Probability formulas, bracket encoding, enumeration scoring
- **Biology Agent** — Evolutionary algorithms for bracket population optimization

This is an iterative process: code → run → analyze with agents → adjust → repeat.

## Tech Stack

- **Python 3.12+** — Core engine
- **SQLite** — Team data, stats, odds, 10M bracket storage
- **React** — Frontend for tracking bracket survival day-by-day
- **Claude Code Agent Teams** — Multi-agent research and strategy coordination

## Project Structure

```
march-prediction/
├── src/
│   ├── math_primitives.py    # Core probability functions (de-vig, blend, encode)
│   └── database.py           # SQLite schema, import, queries
├── data/
│   └── march_madness.db      # SQLite database (generated, gitignored)
├── agents/
│   ├── reports/              # Agent research deliverables
│   │   ├── math-model-spec.md
│   │   ├── betting-model-spec.md
│   │   ├── sports-analyst-spec.md
│   │   ├── 2025-bracket.json
│   │   ├── 2025-team-stats.json
│   │   ├── 2025-first-round-matchups.json
│   │   ├── 2025-field-analysis.json
│   │   └── 2025-injuries.json
│   ├── biology-agent.md
│   └── status/
├── CLAUDE.md
└── README.md
```

## Key Research Findings

- **Vegas lines are the best single predictor** — closing moneylines explain ~28% of variance alone
- **H2H history is display-only** — too sparse to be a reliable model input
- **Matchup styles have minimal predictive value** — max +/- 0.8 pts adjustment (research-backed)
- **Temporal adaptation is inverted** — R1 chaos predicts R2 regression to mean, not more chaos
- **2025 is a chalk-heavy year** — FCI ~0.62, all four 1-seeds with AdjEM > +35 (historically dominant)
- **Top 30 factors only** — more factors = more noise, not more signal

## Phased Development

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Teams + data into database | In progress |
| 2 | Win probability engine | Planned |
| 3 | Regional bracket generation (iterative with agents) | Planned |
| 4 | Full bracket assembly + 10M generation | Planned |
| 5 | Live updating + React website | Planned |

## Setup

```bash
# Install Python 3.12+
brew install python@3.12

# Initialize database with 2025 team data
python3 src/database.py

# Database will be created at data/march_madness.db
```

## Data Sources

| Source | Data | Cost |
|--------|------|------|
| Bart Torvik | Team ratings, efficiency, tempo, experience | Free |
| The Odds API | Moneylines, spreads, futures (500 req/mo free) | Free tier |
| ESPN Tournament Challenge | Public bracket pick percentages | Free |
| YouTube Transcripts | Expert analyst sentiment via auto-captions | Free |
| KenPom | Advanced stats (AdjEM, AdjO, AdjD) | $20/year |
