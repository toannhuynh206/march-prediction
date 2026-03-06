# Sports Analyst Factor Specification

**Date:** 2026-03-06
**Author:** Sports Analyst Agent
**Purpose:** Identify, quantify, and classify every non-betting, non-KenPom factor for the P_factors overlay (15% weight per D003)

---

## Part 1: Data Sources for 2025 NCAA Tournament

### 1.1 ESPN BPI (Basketball Power Index)

**What it is:** ESPN's proprietary team strength measure — how many points above/below average a team is. Accounts for opponent strength, pace, site, travel distance, rest, and altitude. Simulates season 10,000 times.

**Where to find it:**
- Main rankings: `espn.com/mens-college-basketball/bpi`
- Tournament view: `espn.com/mens-college-basketball/bpi/_/view/tournament`
- Resume view: `espn.com/mens-college-basketball/bpi/_/view/resume`

**Format:** HTML table, sortable. Columns include BPI rating, offensive BPI, defensive BPI, strength of record, projected wins/losses, tournament probability.

**Accuracy:** BPI favorite wins 75.6% of games since 2007-08. 8 of last 10 NCAA champions were top-4 in BPI on Selection Sunday.

**Independent value:** LOW. BPI is highly correlated with KenPom AdjEM (r > 0.95). Both measure adjusted efficiency. Including both = double-counting. Use KenPom AdjEM as the canonical efficiency metric per D002.

**Recommendation:** Do NOT include BPI in P_factors. It is already captured by P_stats (AdjEM at 40% weight).

---

### 1.2 KenPom Data

**What it is:** The gold standard for tempo-free college basketball analytics. AdjEM = AdjO - AdjD (adjusted points per 100 possessions, offense minus defense).

**Free vs. Paid:**
- FREE: Basic team rankings, AdjEM, AdjO, AdjD, tempo, overall ratings at `kenpom.com`
- PAID ($20/yr): Player stats (usage %, ORB%, DRB%, block%, steal%), matchup comparisons (average height, experience, bench minutes), point distribution breakdowns, Luck metric, experience ranking

**Key free metrics for our model:**
| Metric | Available Free? | Used In D002? |
|--------|----------------|---------------|
| AdjEM | Yes | Yes (40%) |
| AdjO | Yes | Subsumed by AdjEM |
| AdjD | Yes | Yes (10% defensive premium) |
| Tempo | Yes | Not directly |
| Luck | Paid | Yes (8% luck adjustment) |
| Experience | Paid | Yes (10%) |
| Non-Conf SOS | Derived | Yes (10%) |

**Scraping:** KenPom's robots.txt restricts scraping. For 2025 historical data, published articles (247Sports, SI) list all 68 teams' KenPom rankings. The paid subscription matchup page provides height and experience comparisons.

**Recommendation:** Subscribe to KenPom ($20) for Luck and Experience metrics. Alternatively, use Bart Torvik as free proxy.

---

### 1.3 Bart Torvik (T-Rank) — FREE Alternative

**What it is:** Free tempo-free analytics comparable to KenPom. Provides team ratings, player stats, experience metrics, and tournament simulation.

**Where to find it:**
- Main site: `barttorvik.com`
- T-Rank ratings: `barttorvik.com/trank.php`
- Tournament cast: `barttorvik.com/tourneycast.php`
- Coaching tournament records: `barttorvik.com/cgi-bin/ncaat.cgi?type=coach`

**Bulk data access (FREE, no scraping needed):**
- CSV format: `barttorvik.com/YYYY_team_results.csv`
- JSON format: `barttorvik.com/YYYY_team_results.json`
- Example: `barttorvik.com/2025_team_results.csv`

**Available columns:** Barthag (projected win % vs average team on neutral court), AdjOE, AdjDE, tempo, experience, and 40+ player-level variables.

**R Package:** `cbbdata` (replaces `toRvik`) provides programmatic access to all Torvik data. No subscription required.

**Recommendation:** PRIMARY free data source for P_factors overlay. Use for experience metric and as cross-validation against KenPom.

---

### 1.4 Team Height/Roster Data

**Where to find it:**
- KenPom (paid): Minutes-weighted average height per team
- BVM Sports ranked all 68 tournament teams tallest to shortest for 2025
- NCAA stats: `stats.ncaa.org/teams/XXXXX/roster`
- Elite Prospects: `eliteprospects.com/league/ncaa/teams-physical-stats/2024-2025`

**2025 examples:** Duke tallest at 6'7.8" average; Akron shortest at 6'3.1" (minutes-weighted).

**Independent predictive value:** WEAK. Research shows "there may not be much to glean from team height data in terms of useful basketball knowledge." Efficiency metrics already capture what height contributes (rebounding, interior defense). Height alone is not a strong independent predictor after controlling for AdjEM.

**Recommendation:** Do NOT include as a standalone factor. Height's effect is already embedded in efficiency metrics. Could be used as a matchup-specific modifier for specific games (e.g., undersized team vs. elite interior team), but this is qualitative, not systematic.

---

### 1.5 Strength of Schedule

**Where to find it:**
- Warren Nolan: `warrennolan.com/basketball/2025/sos-net` (NET-based SOS, updated daily)
- TeamRankings: `teamrankings.com/ncaa-basketball/ranking/schedule-strength-by-other`
- NCAA official: Published daily on NCAA.com starting in December

**Types of SOS:**
| SOS Type | What It Measures | Independent? |
|----------|-----------------|--------------|
| Overall SOS | Difficulty of full schedule | NO — embedded in AdjEM |
| Non-Conference SOS | Quality of out-of-conference games | YES — tests quality vs external competition |
| NET SOS | Expected win % of tourney-caliber team vs schedule | Partially embedded |

**Recommendation:** Only Non-Conference SOS provides independent signal (already in D002 at 10%). Overall SOS is redundant with AdjEM. Do NOT add any additional SOS factor.

---

### 1.6 Fan/Public Sentiment

**Where to find it:**
- ESPN Tournament Challenge: `fantasy.espn.com/games/tournament-challenge-bracket-2025/` — shows public pick percentages per team per round
- AP Poll: `espn.com/mens-college-basketball/rankings`
- Coaches Poll: Available on same ESPN rankings page
- ESPN analyst picks: Published articles with specific %s (e.g., "77% of analysts picked Duke to win East")

**Independent predictive value:** MIXED.
- AP preseason poll is a surprisingly powerful predictor (wisdom of crowds), but by tournament time, the AP poll is highly correlated with efficiency ratings
- Public pick % reflects casual fan bias, not independent signal. Popular teams (Duke, Kansas, Kentucky, UNC) are systematically over-picked
- This is ALREADY accounted for by D003's blue-blood futures deflator (0.88-0.92 on Duke/Kansas/Kentucky/UNC)

**Recommendation:** Do NOT include as a P_factors input. Public sentiment is either already in odds (sharp market) or is noise (casual bias). The blue-blood deflator in D003 already handles the main systematic bias.

**One exception:** ESPN bracket pick % could be useful as a CONTRARIAN signal — teams picked by <10% of the public that have strong underlying stats may be undervalued. But this is a research insight, not a systematic model input.

---

### 1.7 Historical Seed Upset Rates (1985-2025)

**Where to find it:**
- NCAA.com: `ncaa.com/news/basketball-men/article/2025-04-16/records-every-seed-march-madness-1985-2025`
- Basketball.org: `basketball.org/stats/ncaa-first-round-upsets/`
- MCubed: `mcubed.net/ncaab/seeds.shtml`
- Wikipedia: Comprehensive upset list with all years

**First Round (Round of 64) Win Rates — Lower Seed Upset Rate:**

| Matchup | Upset Rate | Sample (since 1985) | Notes |
|---------|-----------|---------------------|-------|
| 16 vs 1 | 1.25% | 2/160 | UMBC (2018), FDU (2023) |
| 15 vs 2 | 6.88% | 11/160 | ~1 every 1.5 years |
| 14 vs 3 | 14.74% | 23/156 | Significant threat |
| 13 vs 4 | ~20.6% | 33/160 | ~1 in 5 |
| 12 vs 5 | 35.63% | 57/160 | Classic upset pick |
| 11 vs 6 | 39.1% | 61/156 | Near coin flip |
| 10 vs 7 | 38.7% | 60/155 | Near coin flip |
| 9 vs 8 | ~48% | ~77/160 | Essentially 50-50 |

**Annual upset count:** Average ~8 per year. Range: 3 (2007) to 14 (2021, 2022). 2025 was historically low with only 4 upsets.

**Recommendation:** These rates serve as Bayesian priors in the simulation (already planned per D002/D004). They should inform the logistic function calibration, not be a separate factor. The math-agent should use these when fitting k in the logistic function.

---

### 1.8 Coaching Tournament Records

**Where to find it:**
- Bart Torvik: `barttorvik.com/cgi-bin/ncaat.cgi?type=coach` (2000-2025, sortable)
- DBWoerner: `dbwoerner.com/basketball/coaches.html` (comprehensive 2001-2025)
- Sports-Reference: `sports-reference.com/cbb/leaders/men/wins-coach-career.html`
- BetMGM/BoydsStats: Published articles with tournament win totals

**Already in D002:** Coaching Tournament Score at 7% weight. The rule: 15+ appearances = bonus; first-timer = penalty.

**Recommendation:** Data source is confirmed. Use Bart Torvik's coaching records table as the primary source — it's free, sortable, and covers 2000-2025. No additional factor needed beyond D002's 7%.

---

### 1.9 Injury Reports

**Where to find it (reliable pre-tournament sources):**
- RotoWire: `rotowire.com/cbasketball/injury-report.php` — daily updates, best structured format
- 247Sports: Tournament-specific injury roundups
- FOX Sports: `foxsports.com` tournament injury tracker
- Sports Injury Central (SIC): `sicscore.com` — quantifies injury impact on spreads
- Covers.com: `covers.com/sport/basketball/ncaab/injuries` — daily injury report

**Already in D002:** Key Injuries at 5% weight. Applied as hard point adjustment: -2 (role player), -8 (starter), -15 (star).

**2025 examples:**
- Duke's Cooper Flagg (ankle) — played through it, 14 pts R64, 18 pts R32
- Iowa State's Keshon Gilbert — OUT for tournament (13.4 ppg, 4.1 apg)
- Houston's J'wan Roberts — questionable (ankle)

**Recommendation:** RotoWire is the best structured source for programmatic access. Injury adjustments should be applied manually after bracket release (cannot be automated ahead of time). The D002 scale (-2/-8/-15) is reasonable but should also consider backup quality.

---

## Part 2: Factor Independence Analysis

### Factors in D002 Power Index (P_stats) — Already Handled

| Factor | D002 Weight | Independent? | Notes |
|--------|------------|-------------|-------|
| AdjEM (KenPom) | 40% | Baseline | Single most predictive stat |
| Defensive Efficiency Premium | 10% | Yes | D > O in single-elim validated |
| Non-Conference SOS | 10% | Yes | Not redundant with AdjEM |
| Experience Score | 10% | Yes | Validated: 10/11 top experience teams made tourney |
| Luck Adjustment | 8% | Yes | Pythagorean gap identifies over/under-performers |
| Free Throw Rate Index | 7% | Yes | Close-game discriminator |
| Coaching Tournament Score | 7% | Yes | Tournament-specific edge |
| Key Injuries | 5% | Yes | Applied as point adjustment |
| 3-Point Variance Flag | 3% | Yes | Widens distribution, not mean |

### Factors Investigated and REJECTED (Double-Counting Risk)

| Factor | Why Rejected | Already Captured By |
|--------|-------------|-------------------|
| ESPN BPI | r > 0.95 with AdjEM | P_stats: AdjEM (40%) |
| Standalone AdjO/AdjD | Components of AdjEM | P_stats: AdjEM (40%) + D premium (10%) |
| Overall SOS | Embedded in AdjEM calculation | P_stats: AdjEM (40%) |
| Tournament Seed | Collinear with AdjEM | P_stats: AdjEM (40%) + P_market |
| Recent Form (last 10) | Noise per research | Removed in D002 |
| Team Height | Weak independent predictor | P_stats: efficiency metrics capture height's effect |
| AP/Coaches Poll | Correlated with AdjEM by March | P_stats + P_market |
| Fan Bracket Pick % | Casual bias, not signal | D003: blue-blood deflator |

### Factors with MARGINAL Independent Value (Potential P_factors Inputs)

These are factors that have some independent predictive value BEYOND what P_stats and P_market already capture:

| Factor | Marginal Value | Quantification | Data Source |
|--------|---------------|----------------|-------------|
| 3-pt shooting variance | Widens upset probability for high-variance teams | StdDev of game-to-game 3PT% | Bart Torvik game logs |
| Preseason AP rank vs current | Teams that dropped may be undervalued (regression to mean) | Rank difference | ESPN archives |
| Conference tournament fatigue | Extra games in conf tourney = fatigue | Binary: played 4+ conf tourney games | ESPN/NCAA schedules |
| Travel distance to game site | Proximity advantage for nearby teams | Miles from campus to venue | Calculable from locations |
| Blue-blood bias correction | Already in D003 as futures deflator | 0.88-0.92 multiplier on Duke/Kansas/Kentucky/UNC | D003 locked |

---

## Part 3: Double-Counting Prevention Matrix

This is the critical reference for understanding what information flows where in our three-component blend:

```
logit(P_final) = 0.40 * logit(P_stats) + 0.45 * logit(P_market) + 0.15 * logit(P_factors)
```

### What's in P_stats (40% weight):
- AdjEM, defensive premium, non-conf SOS, experience, luck, FT rate, coaching, injuries, 3pt variance
- Source: KenPom + Bart Torvik + manual injury adjustments

### What's in P_market (45% weight):
- Closing moneyline implied probabilities (vig-removed)
- Captures: ALL public information including KenPom, injuries, matchups, public sentiment, coaching
- Source: The Odds API (per D003)

### What's in P_factors (15% weight):
- ONLY factors with marginal independent value not fully in stats or market
- This is intentionally small because the market is efficient
- Primary candidates:
  1. **3-pt variance distribution widening** — markets price means, not distributions
  2. **Conference tournament fatigue** — subtle, not fully priced
  3. **Game-site proximity** — minor but real
  4. **Late-breaking injury updates** — if injury news breaks after closing lines

### Overlap warning:
- P_stats and P_market are ~85% correlated (both reflect team quality)
- The log-odds blend naturally handles this — it's equivalent to a weighted average in probability space
- The 0.40/0.45/0.15 weights mean P_factors only nudges the final probability
- A P_factors input of 55% vs 50% only shifts P_final by ~1-2 percentage points

---

## Part 4: Recommended Data Collection Checklist (Per Team)

For each of the 64/68 tournament teams, collect:

### Must-Have (for P_stats calculation):
| # | Data Point | Source | Format |
|---|-----------|--------|--------|
| 1 | AdjEM | KenPom or Torvik CSV | Float |
| 2 | AdjO | KenPom or Torvik CSV | Float |
| 3 | AdjD | KenPom or Torvik CSV | Float |
| 4 | Non-Conference SOS | Warren Nolan | Float (0-1) |
| 5 | Experience Score | KenPom (paid) or Torvik | Float |
| 6 | Luck (Pythagorean gap) | KenPom (paid) or derive | Float |
| 7 | FT Rate (FTA/FGA) | ESPN team stats or Torvik | Float |
| 8 | FT% | ESPN team stats or Torvik | Float |
| 9 | Coach tournament appearances | Torvik coaching table | Integer |
| 10 | Coach tournament wins | Torvik coaching table | Integer |
| 11 | Injury status | RotoWire | Categorical: OUT/DOUBTFUL/PROBABLE |
| 12 | Injured player role | Manual assessment | Categorical: star/starter/role |
| 13 | 3PT% StdDev (game-to-game) | Torvik game logs | Float |
| 14 | Tournament seed | NCAA bracket | Integer 1-16 |
| 15 | Conference | NCAA | String |
| 16 | Record (W-L) | ESPN | String |

### Nice-to-Have (for P_factors and qualitative):
| # | Data Point | Source | Format |
|---|-----------|--------|--------|
| 17 | Tempo (possessions/game) | Torvik CSV | Float |
| 18 | Minutes-weighted avg height | KenPom (paid) | Float (inches) |
| 19 | Preseason AP rank | ESPN archives | Integer or NR |
| 20 | Current AP rank | ESPN rankings | Integer or NR |
| 21 | ESPN bracket pick % (championship) | ESPN Tournament Challenge | Float |
| 22 | Conf tournament games played | ESPN schedules | Integer |
| 23 | Game venue city/state | NCAA bracket | String |
| 24 | Campus city/state | Reference data | String |

---

## Part 5: Specific Data URLs for 2025 Tournament

### Free, Structured Data (no scraping):
1. **Bart Torvik bulk CSV:** `barttorvik.com/2025_team_results.csv`
2. **Warren Nolan NET SOS:** `warrennolan.com/basketball/2025/sos-net`
3. **ESPN BPI:** `espn.com/mens-college-basketball/bpi`
4. **ESPN team stats:** `espn.com/mens-college-basketball/stats/team`
5. **NCAA official stats:** `ncaa.com/stats/basketball-men/d1`
6. **Torvik coaching records:** `barttorvik.com/cgi-bin/ncaat.cgi?type=coach`
7. **RotoWire injuries:** `rotowire.com/cbasketball/injury-report.php`
8. **Seed records (1985-2025):** `mcubed.net/ncaab/seeds.shtml`

### Paid but Worth It:
1. **KenPom subscription ($20/yr):** `kenpom.com` — Luck, Experience, Height, matchup tools

### Programmatic Access:
1. **R package `cbbdata`:** Wraps all Torvik data, no subscription needed
2. **The Odds API:** `the-odds-api.com` — free tier for betting odds (per D003)
3. **GitHub `toRvik`:** `github.com/andreweatherman/toRvik` — R package for Torvik data

---

## Part 6: Key Findings Summary

### What actually predicts NCAA tournament outcomes (ranked by importance):
1. **Adjusted Efficiency Margin** — single best predictor, ~70% game winner accuracy
2. **Betting market closing lines** — slightly more accurate than any single stat model because they aggregate all information
3. **Defensive efficiency** — premium in single-elimination (D > O)
4. **Team experience** — validated independent predictor
5. **Free throw rate** — close-game discriminator
6. **Coaching tournament experience** — small but real edge

### What does NOT predict well (contrary to popular belief):
1. **Recent form / hot streaks** — noise, not signal
2. **Team height alone** — captured by efficiency metrics
3. **Fan/media sentiment** — follows rankings, adds no independent info
4. **Overall SOS** — embedded in efficiency metrics
5. **Matchup-specific styles** — research says "matchups do not help predictions"

### Critical insight for our model:
Betting markets are MORE accurate than any single statistical model for NCAA tournament games. When the actual point spread differs from both KenPom and Sagarin predictions, the actual spread tends to be closer to the final outcome. This validates D003's decision to give P_market 45% weight (the highest of the three components).

The role of P_factors (15%) should be narrow: only factors where we have genuine information the market hasn't fully priced. The main candidates are variance-related (3-pt shooting distribution widening) and situational (fatigue, travel, late-breaking injuries).

---

## Part 7: Head-to-Head History Data Sources

### 7.1 Where to Find Head-to-Head Results

**Primary source: Sports-Reference.com (College Basketball Reference)**
- URL pattern: `sports-reference.com/cbb/schools/[team-slug]/men/head-to-head.html`
- Example: `sports-reference.com/cbb/schools/duke/men/head-to-head.html`
- Coverage: All games since 1949-50 where both schools were D-I
- Data: Complete W-L record between any two teams, all-time series

**Stathead Matchup Finder (advanced):**
- URL: `sports-reference.com/cbb/play-index/matchup_finder.cgi`
- Allows filtering by date range, venue, margin, etc.
- Can find specific recent matchups between two teams

**Programmatic access:** Sports-Reference does NOT offer a public API. Data must be scraped from HTML tables (check robots.txt/TOS) or manually collected for the ~63 first-round matchups + potential later-round matchups.

### 7.2 Coach vs. Coach Head-to-Head

**Sources:**
- Sports-Reference coach pages: `sports-reference.com/cbb/coaches/[coach-slug].html`
- Bart Torvik coaching records: `barttorvik.com/cgi-bin/ncaat.cgi?type=coach`
- Manual research via game logs for specific coach-vs-coach tournament history

**Practical note:** Coach vs. coach H2H in tournament context is extremely sparse. Most coaches have faced each other 0-2 times in tournament play. This is too small a sample to be statistically meaningful. Use as qualitative color, not a model input.

### 7.3 How to Use Head-to-Head Data

**Research finding:** Academic research (Nearest-Neighbor Matchup Effects, JQAS 2015) found that basic team-level matchup analysis in the four factors does NOT improve predictions beyond what efficiency ratings already capture. The matchup effect is already embedded in the efficiency numbers.

**However:** The nearest-neighbor framework showed that clustering games by similarity (teams with similar profiles playing similar opponents) CAN capture non-transitive matchup effects that pure ratings miss. This is a sophisticated approach that requires:
1. Building a feature vector per team (tempo, 3PT rate, 2PT rate, FT rate, ORB%, TO%, etc.)
2. For each matchup, finding the 10-20 most similar historical matchups
3. Adjusting the predicted spread based on outcomes of those similar matchups

**Recommendation for our model:** Do NOT implement full nearest-neighbor matchup adjustment for v1. The marginal improvement is small (~0.5-1% in prediction accuracy) and the implementation complexity is high. Instead:
- Collect H2H data for informational/display purposes
- Use tempo differential as a simple matchup signal (see 7.4)
- Consider nearest-neighbor as a v2 enhancement

---

## Part 8: Matchup-Specific Style Data

### 8.1 Team Style Profiles — Data Sources

For each team, we need these style metrics to enable matchup adjustments:

| Metric | What It Captures | Source | Format |
|--------|-----------------|--------|--------|
| Adjusted Tempo | Possessions per 40 min (adj for opponent) | Torvik CSV | Float |
| 3PT Rate (3PA/FGA) | Perimeter dependence | Torvik CSV / ESPN | Float |
| 2PT Rate | Interior scoring | Torvik CSV | Float |
| FT Rate (FTA/FGA) | Ability to draw fouls | Torvik CSV / ESPN | Float |
| ORB% | Offensive rebounding | Torvik CSV | Float |
| TO% | Turnover rate | Torvik CSV | Float |
| Block% | Shot-blocking ability | Torvik CSV | Float |
| Steal% | Defensive pressure/steals | Torvik CSV | Float |
| Effective FG% | Shooting efficiency (weights 3s) | ESPN / Torvik | Float |
| Opp 3PT% | How well they defend the 3 | ESPN / Torvik | Float |

**All available in Bart Torvik bulk CSV** — no additional scraping needed.

### 8.2 Style Matchup Adjustments — What the Research Says

**Key finding:** "Based on the four factors, matchups do not help you make better predictions" (thepowerrank.com). This is a well-established result in college basketball analytics.

**Why matchups don't help much:**
1. Adjusted efficiency already accounts for opponent quality
2. Teams that are "bad matchups" for each other still tend to be correctly ranked by efficiency
3. The sample size for specific style-vs-style matchups is too small to be statistically reliable
4. The variance in basketball is high enough that style effects are dwarfed by overall quality differences

**The one exception — Tempo differential:**
- When a fast team (top-50 tempo) plays a slow team (bottom-50 tempo), the game tempo is unpredictable
- If the slow team controls pace, the fast team's advantage shrinks (fewer possessions = fewer chances for talent to dominate)
- This is a real but small effect (~1-2 point swing)

**EvanMiya.com "Relative Ratings":**
- A newer analytics approach that adjusts team ratings based on opponent style
- URL: `evanmiya.com`
- Could be used as a cross-reference but is NOT free for bulk data

### 8.3 Recommended Matchup Adjustment for Our Model

Given the research, implement a MINIMAL matchup adjustment:

```
matchup_adj = 0  (default: no adjustment)

# Tempo mismatch: if |tempo_A - tempo_B| > 8 possessions/game
if abs(tempo_A - tempo_B) > 8:
    # Slight advantage to the slower team (pace control)
    if tempo_A < tempo_B:
        matchup_adj += 0.5  # favor team A
    else:
        matchup_adj -= 0.5  # favor team B

# Size mismatch: if height_diff > 2 inches AND slower team is taller
if height_diff > 2.0 and taller_team == slower_team:
    matchup_adj += 0.3  # additional advantage to tall+slow team
```

This adjustment is intentionally small (max ~0.8 points on power index). The research does not support large matchup adjustments.

### 8.4 Additional Style Data Sources

| Source | URL | What It Provides | Free? |
|--------|-----|-----------------|-------|
| Bart Torvik | `barttorvik.com/trank.php` | Full tempo-free stats, sortable | Yes |
| Warren Nolan | `warrennolan.com/basketball/2025/stats-adv-pace` | Pace rankings for all D-I | Yes |
| TeamRankings | `teamrankings.com/ncaa-basketball/stat/possessions-per-game` | Possessions per game | Yes |
| EvanMiya | `evanmiya.com` | Relative ratings, player-level | Freemium |
| CBB Analytics | `cbbanalytics.com` | Shot charts, player metrics | Yes |
| ESPN Team Stats | `espn.com/mens-college-basketball/stats/team` | Standard stats | Yes |
| KenPom (paid) | `kenpom.com` | Matchup page with style comparison | $20/yr |

### 8.5 Bart Torvik Game Predictor — Built-in Matchup Tool

Torvik already has a game prediction engine that accounts for style:
- **PBP Simulator:** `barttorvik.com/pbpsim.php` — play-by-play simulation
- **TourneyCast:** `barttorvik.com/tourneycast.php` — tournament bracket simulation
- **R function:** `bart_game_prediction(team_A, team_B, location, date)` returns tempo, PPP, points, win%

The Torvik predictor adjusts for:
- Location (home/away/neutral)
- Tempo interaction between teams
- Recency weighting (last 40 days = 100%, degrades 1%/day, floor 60%)
- Blowout discounting (margins >10 in mismatches are discounted)

**Recommendation:** Use Torvik's game prediction as a CROSS-VALIDATION check against our model's predictions. If our P_final disagrees with Torvik by >10%, investigate why.

---

## Part 9: Live Update Data Sources (Round-by-Round)

Per CTO requirement #2, the model must update as the tournament progresses.

### 9.1 What Changes After Each Round

| Data Point | Update Frequency | Source |
|-----------|-----------------|--------|
| Eliminated teams | After each game | NCAA bracket (hard prune) |
| Updated betting odds | Before each game | The Odds API (live) |
| Injury updates | Daily during tourney | RotoWire, 247Sports |
| Game margin/performance | After each game | ESPN box scores |
| Updated AdjEM (if recalculated) | Daily | KenPom/Torvik |
| Public bracket survival % | After each round | ESPN Tournament Challenge |

### 9.2 Performance-Based Updating

After a team wins, HOW they won provides information:
- **Blowout win (15+ pts):** Team may be performing above pre-tournament baseline. Minor upward adjustment.
- **Close win (1-5 pts):** Consistent with pre-tournament rating. No adjustment.
- **Overtime/lucky win:** Team may be overextended. Minor downward adjustment or variance flag.

**Quantification (suggestion for math-agent):**
```
performance_update = (actual_margin - expected_margin) * 0.1
# Caps at +/- 2 points on power index per game
performance_update = max(-2, min(2, performance_update))
```

This is a Bayesian update: small weight (0.1) on new evidence relative to prior (pre-tournament rating).

### 9.3 Live Odds as the Primary Update Signal

The most efficient live update is simply re-pulling betting odds before each game. The market instantly incorporates:
- Injury news from press conferences
- Performance from prior games
- Matchup-specific adjustments for the next opponent
- Travel/rest considerations

**Recommendation:** For live updating, lean heavily on P_market (which updates automatically via The Odds API). The P_stats component should update minimally (only for injuries and hard eliminations). P_factors should update only for late-breaking injury news not yet in the odds.

---

## Part 10: Data Collection Checklist — Matchup-Specific (NEW)

For each potential matchup (63 games in a 64-team bracket), collect:

### Per-Matchup Data Points:
| # | Data Point | Source | Priority |
|---|-----------|--------|----------|
| 25 | Head-to-head all-time record | Sports-Reference | Nice-to-have |
| 26 | Last meeting date and result | Sports-Reference | Nice-to-have |
| 27 | Tempo differential | Torvik CSV (computed) | Must-have |
| 28 | Height differential | KenPom/BVM Sports | Nice-to-have |
| 29 | Style cluster similarity | Computed from style profiles | Nice-to-have |
| 30 | Game venue location | NCAA bracket | Must-have |
| 31 | Travel distance per team | Computed | Nice-to-have |
| 32 | Pre-game betting line | The Odds API | Must-have |

**Note:** Items 25-26 (H2H history) are for display/informational purposes only. Research does not support using them as model inputs — sample sizes are too small and team rosters change yearly.

---

## Part 11: THE TOP 30 FACTORS (Ranked by Predictive Value)

Based on comprehensive research across academic papers, proven prediction models (KenPom, FiveThirtyEight, Torvik), and empirical tournament data, here are the 30 factors that explain the most variance in NCAA tournament outcomes. Everything else is noise.

### Tier 1: Core Predictors (explain ~70% of variance)

| Rank | Factor | Type | Weight Signal | Why It Matters |
|------|--------|------|--------------|----------------|
| 1 | **Closing betting line (vig-removed)** | P_market | Highest | Aggregates ALL public info; most accurate single predictor |
| 2 | **KenPom AdjEM** | P_stats | 40% of stats | Single best statistical predictor; ~70% game accuracy |
| 3 | **Tournament seed** | Embedded | Via AdjEM + market | Best single-number predictor for bracket pools; collinear with AdjEM |
| 4 | **AdjD (Defensive Efficiency)** | P_stats | 10% premium | Defense > Offense in single-elimination; all 4 2025 1-seeds were top-10 AdjD |
| 5 | **AdjO (Offensive Efficiency)** | P_stats | Subsumed by AdjEM | Component of AdjEM; not standalone but critical input |

### Tier 2: Validated Independent Predictors (explain ~15% additional variance)

| Rank | Factor | Type | Weight Signal | Why It Matters |
|------|--------|------|--------------|----------------|
| 6 | **Team experience (D-I minutes-weighted)** | P_stats | 10% | 10/11 top experience teams made 2025 tourney; all 1-seeds top-128 |
| 7 | **Non-conference SOS** | P_stats | 10% | Tests quality outside conf bubble; not redundant with AdjEM |
| 8 | **Luck adjustment (Pythagorean gap)** | P_stats | 8% | Identifies over/under-seeded teams; negative luck = undervalued |
| 9 | **Free throw rate (FTA/FGA)** | P_stats | 7% (part of FT index) | Close-game discriminator; research validates for 1-9 pt margins |
| 10 | **Free throw percentage** | P_stats | 7% (part of FT index) | Making FTs when it counts; combined with FT rate = FT Rate Index |
| 11 | **Coaching tournament experience** | P_stats | 7% | 15+ appearances = bonus; first-timer = penalty |
| 12 | **Effective FG% (eFG%)** | Computed | Via Four Factors | Shooting is the most important of the Four Factors (explains 98% of OE variance) |
| 13 | **Turnover rate (TO%)** | Computed | Via Four Factors | Second-most important Four Factor after shooting |
| 14 | **Offensive rebounding rate (ORB%)** | Computed | Via Four Factors | Extra possessions; similar importance to TO% |

### Tier 3: Situational and Variance Factors (explain ~5% additional variance)

| Rank | Factor | Type | Weight Signal | Why It Matters |
|------|--------|------|--------------|----------------|
| 15 | **Key injuries (star player)** | P_stats | -15 pts | Iowa State lost Gilbert (13.4 ppg) = major impact |
| 16 | **Key injuries (starter)** | P_stats | -8 pts | Starter absence = rotation disruption |
| 17 | **3-point shooting variance (StdDev)** | P_stats | 3% (widens dist) | High-variance teams = more upset potential; does NOT shift mean |
| 18 | **3-point attempt rate (3PA/FGA)** | Computed | Embedded in eFG% | 3-pt dependent teams = higher variance outcomes |
| 19 | **Adjusted tempo** | P_factors | Matchup adj | Tempo mismatch = slight edge to pace-controller |
| 20 | **Field strength gap (year-adaptive)** | P_factors | NEW | How dominant are top seeds vs field THIS year? See Part 12 |
| 21 | **Championship futures concentration** | P_factors | NEW | Proxy for field gap; top-4 teams holding >60% = chalk year |
| 22 | **Opponent 3PT% defense** | Computed | Via matchup | How well team defends the 3; relevant for 3-pt-dependent opponents |
| 23 | **Block%** | Computed | Via style profile | Interior defense; slight edge in matchups vs interior-scoring teams |
| 24 | **Steal%** | Computed | Via style profile | Defensive pressure; forces turnovers |

### Tier 4: Marginal Edge Factors (explain ~2-3% additional variance)

| Rank | Factor | Type | Weight Signal | Why It Matters |
|------|--------|------|--------------|----------------|
| 25 | **Key injuries (role player)** | P_stats | -2 pts | Minor impact but still real |
| 26 | **Conference tournament fatigue** | P_factors | Binary flag | 4+ conf tourney games = slight fatigue risk |
| 27 | **Game-site proximity** | P_factors | Miles to venue | Near-home-court advantage; minor but real |
| 28 | **Public pick % (ESPN Challenge)** | P_factors | Contrarian signal | Free data; when public overweights blue-bloods, fade = +EV. Confirms model when aligned. |
| 29 | **Blue-blood public bias** | P_market adj | 0.88-0.92 deflator | Duke/Kansas/Kentucky/UNC futures systematically overpriced |
| 30 | **Late-breaking injury news** | P_factors | Manual | Injury info after closing line = edge over market |

### EVERYTHING ELSE IS CUT

The following factors were investigated and explicitly excluded:

| Excluded Factor | Reason |
|----------------|--------|
| Team height (standalone) | Captured by efficiency metrics; weak independent predictor |
| Recent form / hot streaks | Noise, not signal per research |
| Fan/media sentiment (raw) | Raw sentiment follows rankings; ESPN pick % reinstated as contrarian signal in Factor #28 |
| Preseason AP rank regression | Replaced by public pick % (Factor #28); AP rank delta too noisy |
| AP/Coaches poll (by March) | Correlated with AdjEM at r > 0.90 |
| Overall SOS | Embedded in AdjEM |
| BPI (standalone) | Redundant with AdjEM (r > 0.95) |
| Head-to-head history | Rosters change yearly; sample too small |
| Coach vs coach H2H | Too sparse; not statistically meaningful |
| Style matchup specifics | Research: "matchups do not help predictions" |
| Conference affiliation | Captured by SOS and AdjEM |
| Margin of victory trend | Noise; regression to mean |
| Home/away record | N/A for neutral-site tournament |
| Bench depth (minutes) | Correlated with experience; not independent |
| Transfer portal additions | Already in current-season efficiency |

---

## Part 12: Year-Adaptive Field Strength Gap Parameter

### The Problem

Not all tournaments are equal. 2025 had four historically dominant 1-seeds (all AdjEM > +35, never before seen in KenPom era). Result: only 4 upsets, all four 1-seeds in Final Four. In contrast, 2021-2022 had 14 upsets each.

The model must recognize this year-to-year variation and adjust upset probabilities accordingly.

### The 2025 Field Strength Profile

| Tier | AdjEM Range | 2025 Context |
|------|------------|--------------|
| 1-seeds | +35 to +40 | HISTORICALLY ELITE — all 4 > +35, unprecedented in KenPom era |
| 2-seeds | +25 to +30 | Strong but 10+ pt gap from 1-seeds (typical gap is 3-5) |
| 3-4 seeds | +18 to +25 | Good, tournament-caliber |
| 5-8 seeds | +10 to +18 | Competitive, capable of runs |
| 9-12 seeds | +5 to +15 | Upset territory; structural chaos |
| 13-16 seeds | -5 to +8 | Long shots |

Duke's AdjEM of +39.62 was the highest ever recorded in KenPom history (since 2002). All four 1-seeds had AdjEM > +35 — no other season has even had TWO such teams.

### Proposed Field Strength Gap Parameter

```
field_gap = mean(AdjEM of 1-seeds) - mean(AdjEM of 5-8 seeds)
```

**Historical calibration:**

| Year | field_gap (approx) | First Round Upsets | Final Four 1-seeds |
|------|-------------------|-------------------|---------------------|
| 2025 | ~25 | 3 | 4 of 4 |
| 2024 | ~15 | ~8 | 1 of 4 |
| 2023 | ~18 | ~9 | 2 of 4 |
| 2022 | ~12 | 14 | 0 of 4 |
| 2021 | ~14 | 14 | 1 of 4 |

### How to Apply the Field Strength Gap

The field_gap modifies upset probability distribution for TOP SEEDS ONLY:

```python
# Compute field gap for the current year
field_gap = mean(adjEM_1seeds) - mean(adjEM_5to8seeds)

# Historical average field gap (~16 based on 2015-2025)
AVG_FIELD_GAP = 16.0

# Gap ratio: >1 means chalk-heavy year, <1 means upset-heavy year
gap_ratio = field_gap / AVG_FIELD_GAP

# Apply to upset probabilities for 1-seeds and 2-seeds ONLY
# When gap_ratio > 1: reduce upset probability (chalk year)
# When gap_ratio < 1: increase upset probability (upset year)
# Does NOT affect 5-12 seed range (structural chaos persists)

for matchup in [1v16, 1v8, 2v15, 2v7]:
    base_upset_prob = logistic_model_probability(underdog)
    # Shrink upset prob toward 0 when field gap is large
    adjusted_upset_prob = base_upset_prob * (1 / gap_ratio)
    # Cap: never reduce below 25% of base probability
    adjusted_upset_prob = max(adjusted_upset_prob, base_upset_prob * 0.25)

# For 5v12, 6v11, 7v10, 8v9: NO adjustment
# These matchups have structural parity regardless of year
```

### Championship Futures Concentration as Proxy

When pre-tournament futures data is available:

```python
# Sum implied championship probability of top-4 favorites
top4_futures_pct = sum(implied_prob for top 4 teams)

# Historical average: ~40-50%
# 2025: ~65-70% (historically concentrated)
# 2022: ~30% (wide-open field)

# Use as secondary confirmation of field_gap
if top4_futures_pct > 0.60:
    year_profile = "chalk_heavy"  # confirms large field_gap
elif top4_futures_pct < 0.35:
    year_profile = "upset_heavy"  # confirms small field_gap
else:
    year_profile = "normal"
```

### Key Insight: Where Chaos Is Structural

Even in the chalkiest years (2025: only 4 upsets), the 5v12 and 6v11 matchups STILL produce upsets. This is because:
1. The efficiency gap between 5-seeds and 12-seeds is small (~5-8 AdjEM points)
2. Single-game variance in basketball is ~11 points (standard deviation)
3. A 5-8 point gap with 11-point variance = ~35-40% upset probability regardless of year

The field strength gap parameter should ONLY dampen upset probabilities for top-seed matchups (1v16, 1v8/9, 2v15, 2v7/10) where the quality gap is abnormally large in strong years.

### Inverse Correlation: First Round Chalk = Second Round Chaos

Research finding: there is an inverse correlation between first-round and second-round upsets. When the first round is chalky (few upsets), the second round tends to have MORE upsets because:
- Higher-seeded second-round opponents are stronger than usual (they were not upset in R1)
- But they face each other, so one must lose
- The surviving "underdogs" from R1 had an easier path and may overperform expectations

The model should account for this: if R1 produces fewer upsets than expected, slightly INCREASE upset probabilities in R2 for the 4v5 and 3v6 type matchups.

---

## Part 13: Public Sentiment as Contrarian Signal (CTO-requested)

### Why Sentiment Was Re-Added

Originally excluded because raw fan/media sentiment correlates with AdjEM rankings and adds no independent predictive info. However, the CTO identified a specific USE CASE: sentiment as a **contrarian indicator** inside P_factors (0.08 weight). When the public overweights blue-bloods or popular teams, fading those picks has positive expected value.

### Data Sources (ranked by priority)

#### 1. ESPN Tournament Challenge Pick % (PRIMARY — FREE)
- **URL:** `fantasy.espn.com/tournament-challenge-bracket/2025/en/whopickedwhom`
- **Data:** % of public brackets picking each team to advance past each round
- **Format:** Table with team, R64%, R32%, S16%, E8%, F4%, Championship%, Winner%
- **Coverage:** 20M+ brackets; largest public sample available
- **How to use:**
  - Compute `public_overweight = ESPN_pick_pct - model_implied_pct`
  - If `public_overweight > 15%`: team is overpicked (blue-blood effect) — slight contrarian fade
  - If `public_overweight < -10%`: team is underpicked — potential value play
  - Adjustment: `sentiment_adj = -0.3 * (public_overweight / 100)` (capped at +/- 0.5 pts on power index)

#### 2. Action Network Public vs Sharp Splits (SECONDARY — if available)
- **URL:** `actionnetwork.com/ncaa-tournament/public-betting`
- **Data:** % of public bets vs % of money on each side
- **Signal:** When >70% of bets are on one side but <40% of money is on that side = sharp money disagrees with public
- **Availability:** Free for basic splits; premium for full detail
- **How to use:** If sharp/public split detected, increase weight on P_market (sharp money is already in the line)

#### 3. Expert Consensus (TERTIARY — manual collection)
- **Sources:** ESPN bracket picks (Lunardi, Bilas, etc.), CBS Sports, The Athletic, YouTube analysts
- **Data:** Count how many experts pick each team to reach F4/Championship
- **Signal:** Expert consensus provides a wisdom-of-crowds check
- **How to use:** Only as qualitative cross-reference. Do NOT automate — too noisy.

#### 4. Reddit/Social Sentiment (OPTIONAL — nice-to-have)
- **Subreddits:** r/CollegeBasketball, r/MarchMadness
- **Signal:** Extremely noisy. Only useful for detecting late-breaking narratives (e.g., "Coach X benched star player in practice")
- **How to use:** Manual check only. Not a model input.

### Implementation in P_factors

```python
# ESPN public pick % contrarian signal
# public_pick_pct = ESPN Tournament Challenge "Who Picked Whom" data
# model_pick_pct = our model's implied advance probability

public_overweight = public_pick_pct - model_pick_pct  # positive = public likes them more

# Contrarian adjustment: fade overpicked teams, boost underpicked
sentiment_adj = -0.3 * (public_overweight / 100)
sentiment_adj = max(-0.5, min(0.5, sentiment_adj))  # cap at +/- 0.5 pts

# Only apply for significant disagreements
if abs(public_overweight) < 10:
    sentiment_adj = 0  # ignore small disagreements
```

### Blue-Blood Bias Quantification

Historical ESPN pick data shows systematic overweighting of:
- **Duke:** Picked to advance ~8-12% more than seed/rating warrants
- **Kansas:** Picked to advance ~6-10% more
- **Kentucky:** Picked to advance ~8-12% more
- **North Carolina:** Picked to advance ~5-8% more

These teams are public favorites regardless of current-year form. The contrarian signal is strongest when a blue-blood is a 5+ seed and public still picks them deep.

### YouTube Expert Transcript Scraping (CTO-requested)

**Method:** Use `youtube-transcript-api` Python library to pull auto-generated captions from top March Madness analyst videos. Then run an LLM pass to extract per-team sentiment.

**Target channels (10-20 videos total):**

| Analyst / Channel | Why | Expected Content |
|-------------------|-----|------------------|
| CBS Sports bracket breakdowns | Major network, broad reach | Full bracket picks, round-by-round |
| ESPN tournament preview shows | Largest audience | Expert panel picks, upset alerts |
| Andy Katz (March Madness 365) | NCAA's own analyst | Insider perspective, matchup analysis |
| The Athletic previews | Sharp analytical content | Data-driven picks, sleeper teams |
| Jon Rothstein | Most connected CBB reporter | Insider info, coaching relationships |
| Joe Lunardi (Bracketology) | Seed/bracket authority | Seeding insights, bubble team context |
| KenPom (if video available) | Gold standard analytics | Efficiency-based picks |

**Pipeline:**

```python
# Step 1: Pull transcripts
from youtube_transcript_api import YouTubeTranscriptApi

VIDEO_IDS = [
    # 10-20 video IDs from target channels
    # Search: "[analyst name] 2025 march madness bracket predictions"
]

transcripts = {}
for vid_id in VIDEO_IDS:
    try:
        transcripts[vid_id] = YouTubeTranscriptApi.get_transcript(vid_id)
    except Exception:
        pass  # skip unavailable transcripts

# Step 2: LLM extraction pass
# For each transcript, extract structured sentiment:
EXTRACTION_PROMPT = """
From this March Madness preview transcript, extract:
1. Teams the analyst is HIGH on (bullish picks) — list team names
2. Upset picks — which lower seeds beating which higher seeds
3. Cinderella/sleeper picks — mid-major or low-seed deep run picks
4. Championship favorites — top 1-4 picks to win it all
5. Teams to AVOID — teams analyst thinks are overrated/vulnerable

Return as JSON with team names matching official NCAA tournament names.
"""

# Step 3: Aggregate across analysts
# For each team, compute:
#   expert_bullish_count = # of analysts high on team
#   expert_bearish_count = # of analysts saying avoid
#   upset_pick_count = # of analysts picking team as upset winner/victim
#   cinderella_count = # of analysts picking as sleeper
#   championship_pick_count = # of analysts picking to win it all
```

**Output per team:**

| Field | Type | Description |
|-------|------|-------------|
| `expert_bullish_pct` | Float (0-1) | % of analysts bullish on this team |
| `expert_upset_pick` | Boolean | Majority of analysts pick this as an upset game |
| `expert_cinderella` | Boolean | 2+ analysts name as sleeper/Cinderella |
| `expert_championship_pct` | Float (0-1) | % of analysts picking to win title |
| `expert_avoid` | Boolean | 2+ analysts flag as team to avoid |

**How expert sentiment feeds into P_factors:**

```python
# Expert consensus signal (separate from ESPN public pick %)
# Only meaningful when experts DISAGREE with our model

expert_signal = 0
if expert_avoid and model_favors_team:
    expert_signal = -0.3  # experts see something we might miss
if expert_cinderella and model_underrates_team:
    expert_signal = +0.3  # experts see upset potential

# Combine with ESPN public pick signal
total_sentiment_adj = sentiment_adj + expert_signal
total_sentiment_adj = max(-0.8, min(0.8, total_sentiment_adj))  # hard cap
```

**Important constraints:**
- Transcript scraping is a PRE-TOURNAMENT batch job (run once, 1-2 days before tournament)
- Auto-captions have ~90% accuracy; LLM extraction handles noise well
- This is still inside P_factors (0.08 weight) — expert sentiment gets ~15% of that = ~0.012 effective weight
- The value is in DISAGREEMENT detection, not in following expert consensus blindly

### What Sentiment Does NOT Do

- It does NOT replace P_market (betting lines already capture expert and sharp money)
- It does NOT shift P_stats (efficiency metrics are objective)
- It is a TINY signal inside P_factors (0.08 total weight, sentiment is ~25% of that = 0.02 effective weight)
- It primarily helps identify which of our model's close calls to lean contrarian on
