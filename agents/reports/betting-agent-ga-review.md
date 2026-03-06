# Sports Betting Agent: Review of Genetic Algorithm & Biology Agent Proposals

**Agent:** Sports Betting & Market Intelligence Agent
**Date:** 2026-03-06
**Reviewing:** Biology Agent role definition, Division-First Optimization, Genetic Algorithm framework, Real-time adaptation proposals

---

## Executive Summary

The Biology Agent's GA framework is strong and naturally aligns with how betting markets operate. Markets are themselves evolutionary systems -- thousands of sharp bettors placing capital on outcomes, with the "fittest" opinions (those backed by the most informed money) moving the line. The GA's adaptive mutation rates, island model, and fitness landscape concepts all have direct, actionable mappings to market signals. This review provides concrete recommendations for wiring betting market data into every layer of the GA.

---

## 1. How Real-Time Betting Line Movements Should Inform GA Mutation Rates

### The Core Signal: Line Movement = New Information

When a spread or moneyline moves, it means the market has received new information and re-priced the game. This is the single most important signal for the GA.

**A 3+ point line movement signals one of the following:**

1. **Injury or availability news** -- A key player is out, questionable, or upgraded. This is the most common cause of large moves. A 3+ point swing typically means a starter-caliber player's status has changed. For the GA, this should trigger a **significant mutation rate increase** for that specific game gene (and all downstream games involving that team), because the pre-tournament power index is now stale for that team.

2. **Sharp syndicate action** -- Professional betting groups have identified a mispricing and are hammering the line. When a line moves 3+ points against the public side, it almost always means sharp money. This signals that the "true" probability of an upset is materially different from what the opening line implied. The GA should increase mutation probability for that game proportional to the magnitude of the move.

3. **Public avalanche (less informative)** -- Occasionally a 3+ point move happens because casual bettors overwhelm the market on a popular team. Books may move the line to manage liability rather than reflect true probability. This is distinguishable from sharp action (see Section 6 on sharp vs. public).

**Recommended formula for line-movement-adjusted mutation rate:**

```
game_mutation_rate = base_seed_rate * line_movement_multiplier

where:
  line_movement_multiplier = 1.0 + (abs(line_move) / reference_spread) * sensitivity_param

  reference_spread = opening spread for that game
  sensitivity_param = 0.5 (tunable; start conservative)
```

**Example:** A 5-seed vs 12-seed game opens at -4.5 and moves to -1.5 (3-point move toward the 12-seed).
- base_seed_rate for 5v12 = 0.385
- line_movement_multiplier = 1.0 + (3.0 / 4.5) * 0.5 = 1.33
- adjusted_mutation_rate = 0.385 * 1.33 = 0.512

This appropriately pushes the mutation rate above coin-flip territory, reflecting the market's reassessment.

**Directional encoding matters:** If the line moves toward the underdog, increase the mutation rate (more likely upset). If the line moves toward the favorite, decrease it. The formula should be signed:

```
signed_multiplier = 1.0 + (line_move_toward_underdog / reference_spread) * sensitivity_param
game_mutation_rate = base_seed_rate * max(signed_multiplier, 0.1)  # floor to prevent zero
```

---

## 2. Using Live In-Game Betting Market Data to Update Fitness Functions

### Yes -- Live Odds Shifts Are the Fastest Information Signal Available

Live (in-game) betting markets update continuously and reflect real-time game state far faster than any model can. Here is how to integrate them:

**During-Tournament Fitness Function Update:**

The Biology Agent's fitness function has a "during tournament" mode: `P(bracket | observed results so far)`. Live betting data can enhance this before games are final:

1. **Pre-result fitness adjustment:** When a game is in progress and the live moneyline has shifted dramatically (e.g., a 12-seed leads a 5-seed by 10 at halftime, live ML now -400 for the 12-seed), we can begin pre-computing fitness for brackets that have that upset. This gives us a head start on the next GA generation.

2. **Halftime line as a "soft result":** Treat the halftime market-implied probability as a partial observation. Brackets containing the outcome the live market favors get a partial fitness boost. This allows the GA to begin evolving toward the likely new reality before the game ends.

3. **Practical implementation:**
   - Poll live odds at halftime and at the under-8-minute media timeout of the second half
   - Convert live moneyline to no-vig probability
   - If live implied probability exceeds 85% for either side, treat as a "soft lock" and begin the next GA generation cycle with that outcome weighted at 85% certainty

**Fitness function integration:**

```
fitness(bracket) = product over all games of:
  - For completed games: 1.0 if correct, 0.0 if wrong (hard constraint)
  - For in-progress games: live_implied_prob if bracket matches live favorite, (1 - live_implied_prob) otherwise
  - For future games: model_probability as before
```

**Caveat:** Live betting markets for NCAA tournament games can be thin (low liquidity), especially for early-round games between lower seeds. Pinnacle and Circa are the sharpest books; use their lines if available. Avoid using DraftKings/FanDuel live lines as primary signals -- they carry wider vig and are more reactive to public money.

---

## 3. Does the Market Show Evidence of "Chaos Momentum"?

### The Evidence Is Mixed but Actionable

**What the betting market data shows:**

1. **Within a single day:** There is modest evidence that early-session upsets correlate with later-session upsets on the same day. Sharp bettors have observed that when the first game window (12:00 PM ET games) produces multiple upsets, the later windows see slightly elevated upset rates. However, the effect size is small (2-5 percentage points above baseline).

2. **Day 1 to Day 2 carryover:** The Biology Agent's formula `mutation_rate_day2 = base_rate * (observed_upsets_day1 / expected_upsets_day1)` is directionally correct. Betting markets partially price this in -- you will see Day 2 lines shade slightly toward underdogs if Day 1 was chaotic. But markets do NOT fully price it, creating an edge.

3. **Mechanism vs. coincidence:** The "chaos momentum" effect likely has a real mechanism: when a tournament year is upset-heavy, it is often because the field is genuinely more balanced than seedings suggest (committee seeding errors, conference strength misassessment). This is a field-level property, not game-level randomness. The GA's adaptive mutation rate correctly captures this.

4. **Year-level clustering:** Looking at historical data, upset-heavy tournaments (2011, 2013, 2014, 2018, 2023) tend to be upset-heavy across multiple rounds, not just Day 1. Chalk-heavy tournaments (2007, 2009, 2019) tend to stay chalky. This supports using Day 1 results to calibrate the entire remaining tournament's mutation rates.

**Recommendation:** The Biology Agent's chaos multiplier formula is good. I would add a market-based cross-check:

```
market_chaos_signal = average(abs(closing_line - opening_line)) across Day 1 games
  # If lines moved a lot on Day 1, it means the market was uncertain -- more chaos likely

chaos_multiplier = 0.5 * (observed_upsets / expected_upsets) + 0.5 * (market_chaos_signal / historical_avg_movement)
```

This blends actual results with market uncertainty signals for a more robust chaos estimate.

---

## 4. Market Signals That Should Trigger Mutation Rate Changes

### Signals That INCREASE Mutation Rate (More Upsets Expected)

| Signal | Detection Method | Mutation Rate Adjustment |
|--------|-----------------|-------------------------|
| Reverse line movement (line moves opposite to money %) | Sharp money tracker (Action Network, Pregame.com) | +30-50% for that game |
| Steam move on underdog (sudden 2+ point move in 30 min) | Real-time odds monitoring API | +40-60% for that game |
| Key player injury/illness for favorite | News feeds + line movement | +50-100% for that game |
| Conference tournament upset by the same underdog team | Historical (already occurred) | +15-25% for that team's games |
| High total (over/under) with pace mismatch | Odds screen + tempo data | +10-20% (variance amplifier) |
| Day 1 upset cluster (3+ upsets above expectation) | Count results vs. seed-based expectation | +20-40% globally for Day 2 |
| Regional futures shift (see Section 5) | Futures market monitoring | +15-30% for affected region |

### Signals That DECREASE Mutation Rate (Chalk Expected)

| Signal | Detection Method | Mutation Rate Adjustment |
|--------|-----------------|-------------------------|
| Line moves further toward favorite | Odds tracking | -10-30% for that game |
| Sharp money ON the favorite | Money % vs line movement alignment | -15-25% for that game |
| Favorite's best player upgraded to "probable" | Injury reports | -20-40% for that game |
| Day 1 mostly chalk (2+ fewer upsets than expected) | Count results | -15-30% globally for Day 2 |
| Low total with defensive matchup | Odds screen + tempo data | -10-15% (variance suppressor) |

---

## 5. Regional Futures as Calibration Data for Division-First Strategy

### Yes -- Regional Futures Are Extremely Useful

Regional futures (e.g., "Duke to win the East Region" at +350) are directly applicable to the island model GA and provide calibration that game-by-game lines do not.

**Why regional futures matter for division-first:**

1. **They encode path probability, not just game probability.** A team's regional future price reflects the market's assessment of their probability of winning 4 consecutive games against the likely opponents. This is exactly what the island model GA is trying to simulate.

2. **Calibration method:**
   - Convert all teams' regional futures to no-vig implied probabilities within each region (they should sum to ~100% after vig removal)
   - These probabilities become the target distribution for the GA's regional champion output
   - If the GA's evolved population produces "Duke wins the East" 30% of the time but the market says 25%, the GA is over-indexing on Duke -- increase mutation rate in games Duke would need to win

3. **Fitness function enhancement for island model:**

```
regional_fitness(bracket_region) = model_fitness * (1 + alpha * alignment_with_futures)

where:
  alignment_with_futures = correlation between GA population's champion distribution
                          and market-implied champion distribution for that region
  alpha = 0.3 (tunable weight)
```

4. **Cross-regional migration signal:** If one region's futures market is highly concentrated (one team at 40%+ implied probability), that region is "stable" -- lower mutation rate. If the region has 4+ teams between 10-20%, it is chaotic -- higher mutation rate. This directly informs the island-specific mutation rates.

**Practical data sources for regional futures:**
- DraftKings and FanDuel post regional winner futures by Selection Sunday
- Pinnacle (offshore, sharpest) offers them with tighter vig
- Circa Sports (Las Vegas) offers some of the sharpest futures markets
- The Action Network and VegasInsider aggregate multiple books

---

## 6. Sharp vs. Public Money: Different Effects on the GA

### This Distinction Is Critical

Not all line movement is equal. The GA must differentiate between sharp and public money.

**Sharp money characteristics:**
- Moves the line with relatively small dollar amounts
- Typically placed early (opener or early morning) or right before tipoff
- Often goes against the public side
- Creates "reverse line movement" (public on Team A but line moves toward Team B)
- Concentrated at Pinnacle, Circa, and other sharp-friendly books

**Public money characteristics:**
- Moves the line with large aggregate dollar amounts from many small bettors
- Skews toward favorites, big-name schools, and teams with recent TV exposure
- Creates line movement that aligns with betting percentage (80% on Team A, line moves toward Team A)

**How each should affect the GA differently:**

| Money Type | GA Impact | Rationale |
|-----------|-----------|-----------|
| Sharp money on underdog | Increase mutation rate 30-50% for that game | Sharps have identified a genuine mispricing; upset more likely than model thinks |
| Sharp money on favorite | Decrease mutation rate 20-30% for that game | Sharps confirm the favorite; chalk outcome more certain |
| Public money on favorite (no sharp confirmation) | Slight INCREASE in mutation rate (+5-10%) | Public money inflates the favorite's line, potentially creating value on the underdog; the "true" line may be closer |
| Public money on underdog (rare) | No adjustment or slight decrease | This is unusual and often reflects a trendy upset pick; the market may already overprice the upset |

**Detection heuristic (without paid data):**
- Compare betting percentage (available free on Action Network, Covers) to line movement direction
- If 75%+ of bets are on Team A but the line moves toward Team B = sharp money on Team B
- If betting % and line movement align = likely public-driven

**Detection with premium data:**
- Pregame.com provides money % vs ticket % splits
- If ticket % favors one side but money % favors the other = sharp money on the money % side (fewer, larger bets)

---

## 7. Practical Data Pipeline for Real-Time Odds Into Mutation Rates

### Architecture Recommendation

```
Data Sources            Pipeline              GA Integration
-----------            --------              --------------

Odds API (The Odds API) --> Poller (every 5 min pre-game,    --> Line Movement
  - Opening lines              every 30 sec in-game)             Calculator
  - Current lines                    |                               |
  - Multiple books                   v                               v
                            Odds Normalizer                   Mutation Rate
Action Network / Covers --> (remove vig, average             Adjuster Module
  - Betting %'s               across books)                       |
  - Ticket counts                    |                               v
                                     v                         GA Engine
News Feeds (ESPN,       --> Sharp/Public                    (per-game mutation
  Twitter/X)                Classifier                       rates updated)
  - Injury updates              |
  - Lineup changes              v
                          Signal Aggregator
                          (combines all signals
                           into mutation_rate
                           adjustment vector)
```

**Specific implementation steps:**

1. **Data source: The Odds API (https://the-odds-api.com/)**
   - Free tier: 500 requests/month (sufficient for pre-tournament setup)
   - Paid tier ($20/month): real-time odds from 15+ books
   - Returns JSON with moneylines, spreads, totals for all NCAA tournament games
   - Covers Pinnacle, DraftKings, FanDuel, BetMGM, and others

2. **Polling schedule:**
   - Pre-tournament (Selection Sunday to Round 1): Poll every 6 hours, capture opening and current lines
   - Tournament Day, pre-game: Poll every 15 minutes starting 4 hours before tipoff
   - Tournament Day, in-game: Poll every 60 seconds (live odds)

3. **Processing pipeline:**
   - For each game, calculate: `line_move = current_spread - opening_spread`
   - Apply no-vig conversion: for two-way moneylines, use the multiplicative method:
     ```
     implied_A = ML_to_prob(odds_A)
     implied_B = ML_to_prob(odds_B)
     no_vig_A = implied_A / (implied_A + implied_B)
     ```
   - Compare betting % to line movement direction to classify sharp vs. public
   - Output: a 63-element vector of mutation rate adjustments, one per game

4. **Integration with GA:**
   - Before each GA generation, pull the latest mutation rate adjustment vector
   - Multiply each game's base mutation rate by its adjustment factor
   - Log all adjustments for post-tournament analysis and model tuning

5. **Fallback if API is unavailable:**
   - Manually enter opening lines from VegasInsider or DonBest at tournament start
   - Manually update any 2+ point line moves (these are rare enough to track by hand)
   - Focus on the 8-10 games per round most likely to see significant movement

---

## 8. Betting Market Patterns the Biology Agent's Framework Could Exploit

### Patterns That Pure Stats Miss but Markets + GA Can Capture

**8a. Correlated Upset Structures (Co-Upset Matrix)**

The Biology Agent's "co-upset matrix" idea from the AlphaFold MSA analogy maps to a real betting market phenomenon: **correlated parlays and same-game dependencies.**

- Sportsbooks price correlated parlays at different rates than independent parlays because they know outcomes are not independent
- When a conference is systematically overseeded (e.g., the committee gives a conference 6 bids but sharp bettors think only 3 are deserving), upsets of those teams are positively correlated
- The GA's co-upset matrix should be seeded with: (a) historical co-occurrence data from the Stats Agent AND (b) conference-level market mispricing signals (if multiple teams from the same conference have lines that move toward underdogs, the conference itself may be overvalued)
- This is something pure stat models like KenPom cannot capture because they evaluate teams individually

**8b. Matchup-Specific Variance (Attention Mechanism Analogy)**

The Biology Agent's attention mechanism over game interactions maps to how sharp bettors evaluate matchup-specific edges:

- A team that plays extreme slow-pace defense (sub-60 possessions per game) creates high-variance games regardless of talent differential
- Betting totals (over/under) encode this: games with low totals have compressed scoring distributions and higher upset probability
- The GA attention weights between games should incorporate: if Game A is a low-total, high-variance matchup, the winner of Game A enters Game B as a less predictable entity -- the mutation rate for Game B should be slightly elevated regardless of which team advances
- **Actionable signal:** For each game, pull the over/under total. Games with totals in the bottom quartile of tournament games should have their mutation rates increased by 10-15%. This is a market signal that pure power ratings ignore.

**8c. Cascade Mutation and "Tired Upset Winner" Effect**

The Biology Agent's cascade mutation operator (flip a lower-round game, cascade upward) aligns with a known betting market pattern:

- When a lower-seeded team wins an upset, sportsbooks adjust their next-round line but often UNDER-adjust. The market prices the upset winner as "better than their seed" but does not fully account for the physical toll of playing in a tight game
- Sharp bettors exploit this by fading upset winners in the next round (especially if the upset went to overtime or required a second-half comeback)
- For the GA: when a cascade mutation propagates an upset winner upward, the mutation rate for their NEXT game should get a small boost (+5-10%) to reflect the "live dog dies" tendency

**8d. Selection Sunday Market Reaction as Initial Calibration**

Between Selection Sunday and Round 1, the betting market rapidly prices every game. The line movement during this 4-day window is extremely informative:

- Large opening moves (2+ points within 48 hours of Selection Sunday) signal that the committee's seedings disagree with the market -- these are the games where the GA should deviate most from seed-based priors
- This is the ideal moment to calibrate Generation 0 of the GA: the initial population should reflect post-Selection-Sunday market prices, not raw seed-based probabilities

**8e. Conference Tournament Fatigue (Market Underweights This)**

Teams that play deep into their conference tournaments (4-5 games in 4-5 days) and then face a quick turnaround to Round 1 have a measurable performance deficit that betting markets partially but not fully price in. The GA can exploit this:

- Check each team's conference tournament path (games played, rest days before Round 1)
- If a team played 4+ conference tournament games AND has minimal rest, increase mutation rate for their Round 1 game by 10-15%
- Markets account for this somewhat (lines move 0.5-1 point) but research suggests the true effect is larger

---

## 9. Summary: Recommended Integration Points

| GA Component | Market Signal Integration | Priority |
|-------------|--------------------------|----------|
| Base mutation rate per game | Opening spread converted to no-vig implied upset probability | HIGH -- do this first |
| Adaptive mutation rate | Line movement magnitude and direction | HIGH -- core innovation |
| Sharp/public classifier | Betting % vs line movement direction | HIGH -- prevents false signals |
| Chaos multiplier (Day 1 to Day 2) | Blend actual upset count with average line movement | MEDIUM -- enhances Biology Agent formula |
| Island model regional rates | Regional futures concentration (Herfindahl index of champion probs) | MEDIUM -- natural fit for division-first |
| Fitness function | Market-implied probabilities as a fitness component | MEDIUM -- improves selection pressure |
| Live in-game updating | Halftime live moneylines as soft observations | MEDIUM -- useful but adds complexity |
| Co-upset matrix seeding | Conference-level market mispricing detection | LOW -- valuable but hard to automate |
| Cascade mutation bonus | Over/under totals as variance proxy | LOW -- small effect size but theoretically sound |

---

## 10. Open Questions for Other Agents

**For the Biology Agent:**
- What is the minimum population size per island that maintains sufficient diversity when market signals are narrowing mutation rates? If the market strongly favors chalk in a region, the island GA risks premature convergence.
- How should the elitism rate adjust when market confidence is high (concentrated futures) vs. low (dispersed futures)?

**For the Math Agent:**
- Does incorporating market-implied probabilities into the fitness function violate any assumptions of the importance sampling framework? The IS weights were calibrated to the logistic power-index model, not to market probabilities.
- Can we prove that the market-adjusted mutation rates still satisfy the ergodicity conditions needed for the GA to explore the full bracket space?

**For the Stats Agent:**
- Can you provide historical data on betting line accuracy by seed matchup? Specifically: for 5-vs-12 games where the line was under 3 points, what was the actual upset rate? This calibrates our line-movement sensitivity parameter.
- Do you have data on "reverse line movement" games in past tournaments and their upset rate?

**For the Lead SWE:**
- The real-time odds pipeline needs a lightweight polling service that can run alongside the GA. Is a simple Python script with `requests` + `schedule` sufficient, or do we need a message queue (e.g., Redis pub/sub) to decouple odds ingestion from GA computation?
- Storage: we need to log every odds snapshot for post-tournament analysis. Estimate ~500KB per polling cycle x ~200 cycles per tournament day = ~100MB total. Trivial storage but needs structured format (suggest SQLite or just CSV).

---

## Conclusion

The Biology Agent's GA framework is not just compatible with betting market integration -- it is significantly enhanced by it. The adaptive mutation rate system is the single most natural integration point: betting lines are literally the market's estimate of upset probability, and line movements are the market updating that estimate in real time. By wiring The Odds API into the mutation rate adjuster, we turn the GA from a model-only optimizer into a market-informed evolutionary system that adapts to new information faster than any static Monte Carlo approach.

The division-first island model is also strengthened by regional futures, which provide a top-down calibration target that individual game lines cannot. The combination of bottom-up (game-level line movements adjusting mutation rates) and top-down (regional futures calibrating island-level champion distributions) creates a feedback loop that should materially improve bracket accuracy.

Priority recommendation: Start with The Odds API integration and the sharp/public classifier. These two components deliver the highest marginal value and can be implemented before the tournament begins on March 18.
