# Agent Research Output Guide

## How Research Feeds The Model

```
You research → JSON files in data/research/ → python -m data.loader --year 2026 --full-refresh → DB → Simulation
```

**The model only reads structured JSON files.** Narrative reports (markdown) are for human understanding but do NOT feed the simulation. Every piece of research that should affect bracket probabilities must end up in a dated JSON file.

---

## Required Output Files

When doing a fresh research cycle, agents must produce these files. Use today's date in the filename (YYYYMMDD format). The loader automatically picks the most recent file.

### 1. KenPom Stats — `data/research/kenpom_YYYYMMDD.json`

**Sources:** KenPom.com, Bart Torvik, ESPN BPI, Sports Reference

```json
{
  "date": "2026-03-18",
  "source": "KenPom / Bart Torvik",
  "notes": "Description of what changed since last snapshot",
  "teams": [
    {
      "team": "Duke",
      "adj_em": 39.68,
      "adj_o": 127.9,
      "adj_d": 88.6,
      "tempo": 71.8,
      "luck": 0.018,
      "nonconf_sos": 12,
      "experience": 0.72,
      "three_pt_pct": 37.8,
      "three_pt_defense": 28.5,
      "three_pt_rate": null,
      "ft_rate": 38.2,
      "ft_pct": 76.8,
      "efg_pct": 56.9,
      "orb_pct": 32.5,
      "to_pct": 15.8,
      "block_pct": 12.4,
      "steal_pct": 10.8,
      "height_avg_inches": 78.2
    }
  ]
}
```

**All 64 tournament teams must be included.** Fields map directly to `team_stats` table columns.

| Field | Source | Used In | Weight |
|-------|--------|---------|--------|
| adj_em | KenPom | Power Index (40%), P_stats logistic | Primary signal |
| adj_o | KenPom | Historical patterns, advancement boost | Secondary |
| adj_d | KenPom | Power Index (10%), tempo matchup factor | Secondary |
| tempo | KenPom | P_matchup (tempo control adjustment) | Tertiary |
| luck | KenPom | Power Index (8%) — Pythagorean gap | Regression signal |
| nonconf_sos | KenPom | Power Index (10%) | Schedule strength |
| experience | Bart Torvik | Power Index (10%) | Upperclassmen correlation |
| three_pt_pct | KenPom/NCAA | P_matchup (3PT shooting factor) | Style matchup |
| three_pt_defense | KenPom/NCAA | P_matchup (3PT defense factor) | Style matchup |
| ft_rate | KenPom | Power Index (7%), P_matchup (FT exploitation) | Close-game factor |
| ft_pct | KenPom | P_matchup (FT exploitation) | Close-game factor |
| efg_pct | KenPom | P_matchup (shooting efficiency) | Style matchup |
| orb_pct | KenPom | P_matchup (rebounding advantage) | Style matchup |
| to_pct | KenPom | P_matchup (turnover battle) | Style matchup |
| block_pct | KenPom | P_matchup (interior defense) | Style matchup |
| steal_pct | KenPom | P_matchup (steal factor) | Style matchup |
| height_avg_inches | KenPom/roster | P_matchup (interior defense) | Style matchup |

---

### 2. Vegas Odds — `data/research/vegas_odds_YYYYMMDD.json`

**Sources:** DraftKings, FanDuel, BetMGM, Caesars, ESPN Bet

```json
{
  "date": "2026-03-18",
  "source": "DraftKings / FanDuel / BetMGM / Caesars / ESPN Bet",
  "last_updated": "2026-03-18T18:00:00-04:00",
  "notes": "Description of line movements",

  "championship_futures": [
    {
      "team": "Duke", "seed": 1, "region": "East",
      "odds": "+300", "implied_prob": 0.250, "fair_prob": 0.264,
      "dk": "+330", "fd": "+325", "mgm": "+325",
      "caesars": "+315", "espn_bet": "+300",
      "movement": "shortened from +330 opening"
    }
  ],

  "final_four_odds": {
    "East": [
      {"team": "Duke", "odds": "-150"},
      {"team": "UConn", "odds": "+400"}
    ],
    "South": [],
    "West": [],
    "Midwest": []
  },

  "r64_lines": [
    {
      "matchup": "1 Duke vs 16 Siena",
      "region": "East",
      "spread": 28.5,
      "moneyline_fav": -10000,
      "moneyline_dog": 3000,
      "favorite": "Duke",
      "over_under": 148.5
    }
  ],

  "first_four_lines": [
    {
      "matchup": "11 SMU vs 11 Miami OH",
      "region": "Midwest",
      "spread": 6.5,
      "moneyline_fav": -280,
      "moneyline_dog": 220,
      "favorite": "SMU"
    }
  ]
}
```

**Key:** The `r64_lines` array feeds `matchups.p_market` via de-vigging. Games without spreads (First Four pending) will have NULL p_market and fall back to stats-only blend.

---

### 3. Injuries — `data/research/injuries_YYYYMMDD.json`

**Sources:** ESPN, CBS Sports, Yahoo Sports, team beat writers, RotoWire

```json
{
  "date": "2026-03-18",
  "last_updated": "2026-03-18T18:00:00Z",
  "notes": "Summary of changes since last update",
  "changes_since_last": [
    "Description of each change"
  ],
  "injuries": [
    {
      "team": "Alabama",
      "player": "Aden Holloway",
      "injury_type": "Suspended / arrested",
      "status": "OUT",
      "impact_rating": "CRITICAL",
      "date_updated": "2026-03-16",
      "notes": "Context about the injury and its impact on the team"
    }
  ]
}
```

**Status values:** `OUT`, `DOUBTFUL`, `QUESTIONABLE`, `PROBABLE`, `AVAILABLE`
**Impact rating values:** `CRITICAL`, `HIGH`, `MODERATE`, `LOW`, `MINIMAL`

The power index computation uses these to apply a penalty (5% weight):
- (OUT, CRITICAL): -5.0 points
- (OUT, HIGH): -3.0 points
- (QUESTIONABLE, CRITICAL): -1.5 points
- (PROBABLE, MODERATE): -0.2 points

---

### 4. Coaching — `data/research/coaching_tourney_YYYYMMDD.json`

**Sources:** Sports Reference, KenPom, school athletics pages

```json
{
  "date": "2026-03-15",
  "teams": [
    {
      "team": "Duke",
      "coaching_tourney_apps": 4
    }
  ]
}
```

This feeds the 7% coaching weight in the power index (15+ appearances = max score).

---

## Optional Output Files (Not Auto-Loaded)

These don't feed the model automatically but inform qualitative analysis:

| File | What Goes In It |
|------|----------------|
| `youtube_analysis_YYYYMMDD.json` | Sentiment, narrative momentum per team |
| `conf_tournaments_YYYYMMDD.json` | Conference tournament results, hot/cold streaks |
| `reddit_sentiment.json` | r/CollegeBasketball sentiment analysis |

---

## After Research: Run The Pipeline

```bash
# One command refreshes everything from the latest JSONs
python -m data.loader --year 2026 --full-refresh
```

This runs 6 steps:
1. Load teams from bracket JSON
2. Load Vegas odds (picks most recent `vegas_odds_*.json`)
3. Load KenPom stats (picks most recent `kenpom_*.json`)
4. Load R64 matchups with p_market
5. Recompute 9-factor power index (reads injuries + coaching + stats)
6. Recompute matchup probabilities (p_stats, p_matchup, p_factors, p_final)

---

## Checklist Before Simulation

After `--full-refresh`, verify:
- [ ] 64 teams loaded
- [ ] 64 team_stats with non-null power_index
- [ ] 32 R64 matchups with p_final (4 may have NULL p_market for First Four — OK)
- [ ] p_final range looks reasonable (0.48–0.97 for R64)
- [ ] Top power index teams match your priors (Duke, Houston, Florida, Arizona near top)
- [ ] Injury adjustments visible (Alabama's PI should drop after Holloway suspension)
