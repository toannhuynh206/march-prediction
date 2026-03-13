"""
NBA talent and tournament experience adjustments for power index.

Two factors that historical data shows matter significantly in March:

1. NBA Draft Talent Adjustment:
   Teams with projected NBA draft picks have a ceiling advantage in
   single-elimination formats. The best player on the court often
   decides close games, and NBA-caliber talent creates matchup problems
   that can't be schemed away.

2. Tournament Veteran Bonus:
   Teams with players who have meaningful March Madness minutes benefit
   from reduced pressure anxiety and better in-game adjustments.
   This matters more in later rounds where experience compounds.

Both factors are additive adjustments to power index, not probability.
They flow through the logistic model to affect win probabilities.

All functions are pure. No mutation.
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# NBA Draft Talent Adjustment
# ---------------------------------------------------------------------------
# Rationale: a team with the #1 overall pick has a ceiling that mid-majors
# simply can't match. This is separate from AdjEM because KenPom doesn't
# fully capture "this guy will take over a game" moments.
#
# Historical evidence: 2022 (Banchero/Duke), 2023 (Wembanyama effect on
# draft class), 2024 (Zaccharie Risacher), 2025 (Cooper Flagg/Duke).
# Teams with top-3 picks rarely lose before S16.

@dataclass(frozen=True)
class DraftPickBoost:
    """Power index boost for a projected draft pick."""
    pick_tier: str        # "top_3", "top_10", "top_20", "top_30"
    base_boost: float     # power index points to add


DRAFT_PICK_BOOSTS = (
    DraftPickBoost(pick_tier="top_3", base_boost=1.5),
    DraftPickBoost(pick_tier="top_10", base_boost=1.0),
    DraftPickBoost(pick_tier="top_20", base_boost=0.5),
    DraftPickBoost(pick_tier="top_30", base_boost=0.25),
)

DRAFT_TIER_MAP = {b.pick_tier: b.base_boost for b in DRAFT_PICK_BOOSTS}

# Multi-pick decay: each additional draft pick on a roster contributes
# less marginal value. First pick = 100%, second = 60%, third = 30%.
# Beyond 3 picks is vanishingly rare (2015 Kentucky had 4).
MULTI_PICK_DECAY = (1.0, 0.6, 0.3)


def compute_nba_talent_boost(
    draft_picks: tuple[str, ...],
) -> float:
    """Compute total power index boost from projected NBA draft picks.

    draft_picks: tuple of tier strings, sorted best-to-worst.
        e.g., ("top_3", "top_20") for a team with a lottery pick and
        a late first-rounder.

    Returns: power index boost (additive).

    >>> compute_nba_talent_boost(("top_3",))
    1.5
    >>> compute_nba_talent_boost(("top_3", "top_20"))
    1.8
    >>> compute_nba_talent_boost(("top_10", "top_20", "top_30"))
    1.225
    >>> compute_nba_talent_boost(())
    0.0
    """
    total = 0.0
    for i, tier in enumerate(draft_picks):
        base = DRAFT_TIER_MAP.get(tier, 0.0)
        decay = MULTI_PICK_DECAY[i] if i < len(MULTI_PICK_DECAY) else 0.15
        total += base * decay
    return total


# ---------------------------------------------------------------------------
# Tournament Experience Bonus
# ---------------------------------------------------------------------------
# Rationale: teams with players who have logged meaningful March minutes
# handle tournament pressure better. This is a round-dependent effect:
# barely matters in R64 (everyone's nervous), but compounds in S16+
# where the stage gets bigger and only experienced teams maintain composure.
#
# Requires 3+ players with prior tournament minutes to qualify.
# "Star" players with deep runs (E8+) matter more.

@dataclass(frozen=True)
class ExperienceBonus:
    """Round-dependent experience bonus."""
    round_name: str
    bonus: float          # power index boost if team qualifies
    min_experienced_players: int  # minimum players with March minutes


EXPERIENCE_BONUSES = (
    ExperienceBonus(round_name="R64", bonus=0.0, min_experienced_players=3),
    ExperienceBonus(round_name="R32", bonus=0.0, min_experienced_players=3),
    ExperienceBonus(round_name="S16", bonus=1.0, min_experienced_players=3),
    ExperienceBonus(round_name="E8", bonus=1.5, min_experienced_players=3),
    ExperienceBonus(round_name="F4", bonus=2.0, min_experienced_players=3),
    ExperienceBonus(round_name="Championship", bonus=2.0, min_experienced_players=3),
)

EXPERIENCE_BY_ROUND = {b.round_name: b for b in EXPERIENCE_BONUSES}

# Deep run bonus: extra boost if players have E8+ experience (not just R64)
DEEP_RUN_MULTIPLIER = 1.3  # 30% more if team has E8+ veterans


@dataclass(frozen=True)
class PlayerExperience:
    """A player's tournament experience record."""
    name: str
    march_minutes: int         # total NCAA tournament minutes played
    deepest_round: str         # "R64", "R32", "S16", "E8", "F4", "Championship"
    tournaments_played: int    # number of distinct tournaments


ROUND_DEPTH_ORDER = {
    "R64": 1, "R32": 2, "S16": 3, "E8": 4, "F4": 5, "Championship": 6,
}


def compute_experience_bonus(
    players: tuple[PlayerExperience, ...],
    tournament_round: str,
) -> float:
    """Compute power index bonus from tournament experience.

    players: tuple of PlayerExperience records for the team.
    tournament_round: current round being simulated.

    Returns: power index boost (additive). 0.0 if not enough experienced players.

    >>> from talent_factors import PlayerExperience
    >>> p1 = PlayerExperience("A", 120, "E8", 2)
    >>> p2 = PlayerExperience("B", 80, "S16", 1)
    >>> p3 = PlayerExperience("C", 40, "R32", 1)
    >>> compute_experience_bonus((p1, p2, p3), "S16")
    1.3
    >>> compute_experience_bonus((p1, p2), "S16")
    0.0
    >>> compute_experience_bonus((p1, p2, p3), "R64")
    0.0
    """
    config = EXPERIENCE_BY_ROUND.get(tournament_round)
    if config is None or config.bonus == 0.0:
        return 0.0

    # Count players with meaningful March experience
    experienced = [p for p in players if p.march_minutes >= 20]

    if len(experienced) < config.min_experienced_players:
        return 0.0

    bonus = config.bonus

    # Deep run multiplier: if any player has E8+ experience
    has_deep_run = any(
        ROUND_DEPTH_ORDER.get(p.deepest_round, 0) >= ROUND_DEPTH_ORDER["E8"]
        for p in experienced
    )
    if has_deep_run:
        bonus *= DEEP_RUN_MULTIPLIER

    return bonus


# ---------------------------------------------------------------------------
# Star player factor
# ---------------------------------------------------------------------------
# A team's best player matters disproportionately in March. KenPom captures
# team efficiency but doesn't fully weight the "one guy can take over" effect.
# This is correlated with but distinct from the NBA draft factor.

@dataclass(frozen=True)
class StarPlayerBoost:
    """Boost based on having a dominant individual player."""
    usage_rate_threshold: float     # usage rate above this = star
    efficiency_threshold: float     # offensive rating above this = efficient star
    boost: float                    # power index boost


STAR_PLAYER_TIERS = (
    # Usage 30%+ and ORtg 120+ = dominant alpha (Flagg, Boozer-level)
    StarPlayerBoost(usage_rate_threshold=30.0, efficiency_threshold=120.0, boost=1.2),
    # Usage 28%+ and ORtg 115+ = very good alpha
    StarPlayerBoost(usage_rate_threshold=28.0, efficiency_threshold=115.0, boost=0.8),
    # Usage 25%+ and ORtg 110+ = solid primary option
    StarPlayerBoost(usage_rate_threshold=25.0, efficiency_threshold=110.0, boost=0.4),
)


def compute_star_player_boost(
    usage_rate: float,
    offensive_rating: float,
) -> float:
    """Compute power index boost for a team's best player.

    usage_rate: best player's usage rate (percentage).
    offensive_rating: best player's offensive rating (KenPom individual).

    Returns: power index boost. Uses highest qualifying tier.

    >>> compute_star_player_boost(32.0, 125.0)
    1.2
    >>> compute_star_player_boost(26.0, 112.0)
    0.4
    >>> compute_star_player_boost(20.0, 105.0)
    0.0
    """
    for tier in STAR_PLAYER_TIERS:
        if (usage_rate >= tier.usage_rate_threshold
                and offensive_rating >= tier.efficiency_threshold):
            return tier.boost
    return 0.0


# ---------------------------------------------------------------------------
# Combined talent adjustment
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TalentAdjustment:
    """Combined talent adjustment for a team."""
    nba_talent_boost: float
    experience_bonus: float
    star_player_boost: float

    @property
    def total(self) -> float:
        return self.nba_talent_boost + self.experience_bonus + self.star_player_boost


def compute_talent_adjustment(
    draft_picks: tuple[str, ...] = (),
    players_experience: tuple[PlayerExperience, ...] = (),
    tournament_round: str = "R64",
    star_usage_rate: float = 0.0,
    star_offensive_rating: float = 0.0,
) -> TalentAdjustment:
    """Compute all talent adjustments for a team.

    Returns immutable TalentAdjustment with component breakdowns.
    """
    return TalentAdjustment(
        nba_talent_boost=compute_nba_talent_boost(draft_picks),
        experience_bonus=compute_experience_bonus(players_experience, tournament_round),
        star_player_boost=compute_star_player_boost(star_usage_rate, star_offensive_rating),
    )
