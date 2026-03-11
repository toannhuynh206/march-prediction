"""
Round-by-round upset calibration targets.

Historical upset data (2021-2025) analyzed per round to model the "upset decay
curve" — upsets are concentrated in R64 and drop off sharply in later rounds.

Key insight for 2026: talent concentration at the top (NIL + transfer portal)
means chalk in later rounds, but R64 stays chaotic because mid-majors can
still punch once. Expect a 2024-shaped tournament: ~9 R64 upsets, then the
wall comes down.

All data structures are immutable. Functions return new objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Historical upset data (2021-2025) — round by round
# ---------------------------------------------------------------------------
# "Upset" = higher-numbered seed wins the game.
# Includes 8v9 games (coin flips) for completeness.

@dataclass(frozen=True)
class TournamentUpsetProfile:
    """Immutable record of upsets in a single tournament year."""
    year: int
    champion_seed: int
    r64: int       # Round of 64 (32 games)
    r32: int       # Round of 32 (16 games)
    s16: int       # Sweet 16 (8 games)
    e8: int        # Elite 8 (4 games)
    f4: int        # Final Four (2 games)
    final: int     # Championship (1 game)

    @property
    def total(self) -> int:
        return self.r64 + self.r32 + self.s16 + self.e8 + self.f4 + self.final

    @property
    def r64_upset_rate(self) -> float:
        return self.r64 / 32

    @property
    def r32_upset_rate(self) -> float:
        return self.r32 / 16

    @property
    def s16_upset_rate(self) -> float:
        return self.s16 / 8

    @property
    def e8_upset_rate(self) -> float:
        return self.e8 / 4

    @property
    def f4_upset_rate(self) -> float:
        return self.f4 / 2


HISTORICAL_UPSETS = (
    TournamentUpsetProfile(
        year=2021, champion_seed=1,
        r64=10, r32=5, s16=2, e8=1, f4=1, final=0,
        # Record chaos: Oral Roberts (15), UCLA (11→Final), Oregon State (12→E8)
        # Loyola (8) beat #1 Illinois. Syracuse (11) to S16.
    ),
    TournamentUpsetProfile(
        year=2022, champion_seed=1,
        r64=7, r32=5, s16=1, e8=2, f4=0, final=0,
        # St. Peter's (15→E8), UNC (8) beat #1 Baylor, Miami (10) to E8
        # Iowa State (11) to S16, Michigan (11) to S16
    ),
    TournamentUpsetProfile(
        year=2023, champion_seed=4,
        r64=6, r32=3, s16=2, e8=1, f4=1, final=0,
        # FDU (16) beat #1 Purdue, Princeton (15→S16), Furman (13)
        # FAU (9→F4), UConn won as 4-seed
    ),
    TournamentUpsetProfile(
        year=2024, champion_seed=1,
        r64=9, r32=1, s16=0, e8=2, f4=1, final=0,
        # Most R64 upsets in recent memory but chalk R32/S16
        # NC State (11→Final), Oakland (14) beat Kentucky
        # Pattern: chaos day 1, then talent wins
    ),
    TournamentUpsetProfile(
        year=2025, champion_seed=1,
        r64=7, r32=1, s16=0, e8=0, f4=0, final=0,
        # Historically chalk: all four 1-seeds made Final Four (first since 2008)
        # Only meaningful late upset: Arkansas (10) over St. John's (2) in R32
        # Talent concentration at top was dominant
    ),
)


# ---------------------------------------------------------------------------
# Computed averages from historical data
# ---------------------------------------------------------------------------

def compute_historical_averages(
    profiles: tuple[TournamentUpsetProfile, ...] = HISTORICAL_UPSETS,
) -> dict[str, float]:
    """Compute mean upsets per round across historical data.

    Returns new dict, no mutation.
    """
    n = len(profiles)
    return {
        "r64_mean": sum(p.r64 for p in profiles) / n,
        "r32_mean": sum(p.r32 for p in profiles) / n,
        "s16_mean": sum(p.s16 for p in profiles) / n,
        "e8_mean": sum(p.e8 for p in profiles) / n,
        "f4_mean": sum(p.f4 for p in profiles) / n,
        "final_mean": sum(p.final for p in profiles) / n,
        "total_mean": sum(p.total for p in profiles) / n,
        "r64_rate": sum(p.r64_upset_rate for p in profiles) / n,
        "r32_rate": sum(p.r32_upset_rate for p in profiles) / n,
        "s16_rate": sum(p.s16_upset_rate for p in profiles) / n,
        "e8_rate": sum(p.e8_upset_rate for p in profiles) / n,
        "f4_rate": sum(p.f4_upset_rate for p in profiles) / n,
    }


HISTORICAL_AVERAGES = compute_historical_averages()
# r64_mean ~7.8, r32_mean ~3.0, s16_mean ~1.0, e8_mean ~1.2, f4_mean ~0.6


# ---------------------------------------------------------------------------
# 2026 prediction targets — user thesis
# ---------------------------------------------------------------------------
# Thesis: talent concentration (NIL + portal) makes later rounds chalk,
# but R64 stays chaotic. Shape resembles 2024: high R64, low everything else.
# With variance: ±2 in R64, ±1 in later rounds.

@dataclass(frozen=True)
class RoundUpsetTarget:
    """Target upset count for a single round with variance band."""
    round_name: str
    games_in_round: int
    target_upsets: float       # central estimate
    low: int                   # optimistic (fewer upsets) bound
    high: int                  # pessimistic (more upsets) bound
    confidence: float          # how confident in this range (0-1)

    @property
    def target_rate(self) -> float:
        return self.target_upsets / self.games_in_round

    @property
    def low_rate(self) -> float:
        return self.low / self.games_in_round

    @property
    def high_rate(self) -> float:
        return self.high / self.games_in_round


UPSET_TARGETS_2026 = (
    RoundUpsetTarget(
        round_name="R64",
        games_in_round=32,
        target_upsets=9,       # 2024-like: lots of day-1 chaos
        low=7,                 # floor: even 2025 (chalk year) had 7
        high=11,               # ceiling: approaching 2021 territory
        confidence=0.75,
    ),
    RoundUpsetTarget(
        round_name="R32",
        games_in_round=16,
        target_upsets=2,       # slightly above 2024/2025 (both had 1)
        low=1,                 # chalk scenario
        high=4,                # if Cinderellas survive (2021/2022 pattern)
        confidence=0.65,
    ),
    RoundUpsetTarget(
        round_name="S16",
        games_in_round=8,
        target_upsets=1,       # historical average is ~1
        low=0,                 # 2024/2025 both had 0
        high=2,                # 2021/2023 had 2
        confidence=0.60,
    ),
    RoundUpsetTarget(
        round_name="E8",
        games_in_round=4,
        target_upsets=1,       # surprisingly high historically (~1.2 avg)
        low=0,                 # 2025 had 0
        high=2,                # 2022 had 2
        confidence=0.55,
    ),
    RoundUpsetTarget(
        round_name="F4",
        games_in_round=2,
        target_upsets=0,       # chalk at the top in talent-concentrated era
        low=0,
        high=1,                # always possible but unlikely
        confidence=0.50,
    ),
    RoundUpsetTarget(
        round_name="Final",
        games_in_round=1,
        target_upsets=0,       # 1-seed wins in most years
        low=0,
        high=1,
        confidence=0.50,
    ),
)


# ---------------------------------------------------------------------------
# Round decay multiplier
# ---------------------------------------------------------------------------
# The core model insight: upset probability should decay round-over-round.
# In R64, a 12-seed has ~36% chance. But by S16, surviving underdogs face
# elite talent and the rate drops. This function provides the decay curve.

# Decay multipliers: how much to scale base upset probability each round.
# 1.0 = use base probability as-is. <1.0 = reduce upset chance.
# Derived from historical rate ratios vs R64.

ROUND_UPSET_DECAY = {
    "R64": 1.00,    # baseline — use model probabilities as-is
    "R32": 0.78,    # ~19% rate vs ~24% in R64 → 0.78x decay
    "S16": 0.52,    # ~13% rate → sharper drop (talent wall)
    "E8": 0.45,     # ~12% rate but small sample; stays similar to S16
    "F4": 0.35,     # chalk dominates; only elite survive
    "Final": 0.30,  # almost always the better seed wins
}

# 2026-adjusted decay: even more chalk in later rounds due to talent concentration
ROUND_UPSET_DECAY_2026 = {
    "R64": 1.00,    # keep R64 chaotic (2024-like)
    "R32": 0.70,    # slightly more chalk than historical (talent wall earlier)
    "S16": 0.40,    # steeper drop — top teams dominate from here
    "E8": 0.35,     # very chalky
    "F4": 0.25,     # expect 1/2-seeds dominating
    "Final": 0.20,  # near-certain better seed wins
}


# ---------------------------------------------------------------------------
# Per-seed upset rates by round (what our simulation should produce)
# ---------------------------------------------------------------------------
# These are TARGET rates for validation — after generating brackets, check
# that seed advancement rates match these within tolerance.

SEED_ADVANCEMENT_TARGETS_2026 = {
    # seed: {round: probability of advancing past this round}
    # Probabilities are cumulative survival rates from tournament start

    1: {"R64": 0.99, "R32": 0.92, "S16": 0.80, "E8": 0.55, "F4": 0.35},
    2: {"R64": 0.94, "R32": 0.78, "S16": 0.55, "E8": 0.30, "F4": 0.15},
    3: {"R64": 0.86, "R32": 0.60, "S16": 0.35, "E8": 0.15, "F4": 0.06},
    4: {"R64": 0.80, "R32": 0.50, "S16": 0.25, "E8": 0.10, "F4": 0.04},
    5: {"R64": 0.64, "R32": 0.35, "S16": 0.12, "E8": 0.04, "F4": 0.01},
    6: {"R64": 0.63, "R32": 0.25, "S16": 0.08, "E8": 0.02, "F4": 0.01},
    7: {"R64": 0.61, "R32": 0.22, "S16": 0.06, "E8": 0.02, "F4": 0.005},
    8: {"R64": 0.50, "R32": 0.10, "S16": 0.03, "E8": 0.01, "F4": 0.003},
    9: {"R64": 0.50, "R32": 0.10, "S16": 0.03, "E8": 0.01, "F4": 0.003},
    10: {"R64": 0.39, "R32": 0.12, "S16": 0.04, "E8": 0.01, "F4": 0.003},
    11: {"R64": 0.37, "R32": 0.12, "S16": 0.04, "E8": 0.01, "F4": 0.003},
    12: {"R64": 0.36, "R32": 0.08, "S16": 0.02, "E8": 0.005, "F4": 0.001},
    13: {"R64": 0.20, "R32": 0.04, "S16": 0.008, "E8": 0.001, "F4": 0.0},
    14: {"R64": 0.14, "R32": 0.02, "S16": 0.003, "E8": 0.0, "F4": 0.0},
    15: {"R64": 0.06, "R32": 0.01, "S16": 0.002, "E8": 0.0, "F4": 0.0},
    16: {"R64": 0.01, "R32": 0.002, "S16": 0.0, "E8": 0.0, "F4": 0.0},
}


# ---------------------------------------------------------------------------
# Upset shape profiles — "worlds" the tournament can fall into
# ---------------------------------------------------------------------------
# Instead of one target, model 3 possible tournament shapes with weights.
# The simulation stratifier samples across these shapes.

@dataclass(frozen=True)
class TournamentShape:
    """A possible shape for how the tournament plays out.

    Used by the stratifier to allocate bracket budget across upset scenarios.
    """
    name: str
    weight: float              # probability of this shape occurring
    r64_upsets: int
    r32_upsets: int
    s16_upsets: int
    e8_upsets: int
    f4_upsets: int
    description: str

    @property
    def total_upsets(self) -> int:
        return (
            self.r64_upsets + self.r32_upsets + self.s16_upsets
            + self.e8_upsets + self.f4_upsets
        )


TOURNAMENT_SHAPES_2026 = (
    TournamentShape(
        name="chalk",
        weight=0.35,
        r64_upsets=7, r32_upsets=1, s16_upsets=0, e8_upsets=0, f4_upsets=0,
        description=(
            "2025-like: top seeds dominate. 7 R64 upsets (mostly 8v9 and 5v12) "
            "but talent wins from R32 onward. All 1-seeds in Final Four."
        ),
    ),
    TournamentShape(
        name="moderate",
        weight=0.45,
        r64_upsets=9, r32_upsets=2, s16_upsets=1, e8_upsets=1, f4_upsets=0,
        description=(
            "2024-like: chaotic R64 (9 upsets) with a couple Cinderellas surviving "
            "to S16/E8, but top 2 seeds dominate Final Four. Most likely shape."
        ),
    ),
    TournamentShape(
        name="chaos",
        weight=0.20,
        r64_upsets=10, r32_upsets=4, s16_upsets=2, e8_upsets=1, f4_upsets=1,
        description=(
            "2021/2022-like: correlated upset chains. Multiple Cinderella runs. "
            "A double-digit seed reaches Final Four. ~18 total upsets."
        ),
    ),
)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_round_upset_counts(
    simulated_upsets: dict[str, int],
    total_brackets: int,
    targets: tuple[RoundUpsetTarget, ...] = UPSET_TARGETS_2026,
) -> list[dict]:
    """Validate simulated upset counts against round targets.

    simulated_upsets: {"R64": avg_upsets_per_bracket, "R32": ..., ...}
    Returns list of validation results.
    """
    results = []
    for target in targets:
        actual = simulated_upsets.get(target.round_name, 0)
        in_range = target.low <= actual <= target.high
        near_target = abs(actual - target.target_upsets) <= 1.5

        if in_range and near_target:
            status = "PASS"
        elif in_range:
            status = "WARN"
        else:
            status = "FAIL"

        results.append({
            "round": target.round_name,
            "target": target.target_upsets,
            "actual": actual,
            "range": f"[{target.low}, {target.high}]",
            "status": status,
        })

    return results


def apply_round_decay(
    base_upset_prob: float,
    round_name: str,
    use_2026_targets: bool = True,
) -> float:
    """Apply round-specific decay to a base upset probability.

    Returns adjusted probability. Does not mutate inputs.
    """
    decay_table = ROUND_UPSET_DECAY_2026 if use_2026_targets else ROUND_UPSET_DECAY
    multiplier = decay_table.get(round_name, 1.0)
    return base_upset_prob * multiplier
