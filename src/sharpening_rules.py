"""
Sharpening rules engine for bracket simulation constraints.

These rules constrain the bracket generation space to eliminate
"impossible" or extremely unlikely brackets, focusing simulation
budget on realistic outcomes.

Key rules:
  1. 1-seed and 2-seed AUTO-ADVANCE past R64 (user mandate — gambling on this)
  2. No 16-seed past R32 (never happened in modern era beyond one game)
  3. At least one 12-over-5 upset per tournament (happens ~85% of years)
  4. Seed ceiling by round (no 14+ seed in Elite 8, etc.)
  5. Maximum upset count caps by round

These rules modify the probability matrix before simulation:
  - P=1.0 for guaranteed advances (1/2 seeds in R64)
  - P=0.0 for impossible outcomes (16-seed in S16)
  - Minimum probabilities for "at least one" upset constraints
"""

from dataclasses import dataclass
from typing import Optional

from math_primitives import R64_MATCHUPS


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SharpeningRule:
    """Immutable rule definition."""
    name: str
    description: str
    round_scope: str           # which round this applies to
    rule_type: str             # "auto_advance", "ceiling", "min_upset", "max_upset"
    seeds_affected: tuple      # which seeds are affected
    value: float               # probability override or threshold


# The user's core mandate: 1-seeds and 2-seeds auto-advance R64
AUTO_ADVANCE_RULES = [
    SharpeningRule(
        name="1_seed_auto_R64",
        description="1-seeds always win R64 (1 vs 16 historically 99.3%)",
        round_scope="R64",
        rule_type="auto_advance",
        seeds_affected=(1,),
        value=1.0,
    ),
    SharpeningRule(
        name="2_seed_auto_R64",
        description="2-seeds always win R64 (2 vs 15 historically 93.5%)",
        round_scope="R64",
        rule_type="auto_advance",
        seeds_affected=(2,),
        value=1.0,
    ),
]

# Seed ceilings: maximum round a seed can reach
CEILING_RULES = [
    SharpeningRule(
        name="16_seed_ceiling_R32",
        description="No 16-seed past R64 (only 1 in history: UMBC 2018)",
        round_scope="R32",
        rule_type="ceiling",
        seeds_affected=(16,),
        value=0.0,
    ),
    SharpeningRule(
        name="15_seed_ceiling_S16",
        description="No 15-seed past R32 (Saint Peter's 2022 was a unicorn)",
        round_scope="S16",
        rule_type="ceiling",
        seeds_affected=(15,),
        value=0.0,
    ),
    SharpeningRule(
        name="14_seed_ceiling_S16",
        description="No 14-seed past R32 (never happened)",
        round_scope="S16",
        rule_type="ceiling",
        seeds_affected=(14,),
        value=0.0,
    ),
    SharpeningRule(
        name="13_seed_ceiling_E8",
        description="No 13-seed past S16 (never happened)",
        round_scope="E8",
        rule_type="ceiling",
        seeds_affected=(13,),
        value=0.0,
    ),
]

# Upset frequency constraints
UPSET_FREQUENCY_RULES = [
    SharpeningRule(
        name="min_12_over_5",
        description="At least one 12-over-5 upset per tournament (~85% of years)",
        round_scope="R64",
        rule_type="min_upset",
        seeds_affected=(5, 12),
        value=1.0,  # minimum count
    ),
    SharpeningRule(
        name="max_1_seed_losses_R64",
        description="At most 0 1-seed losses in R64 (we set to 0 via auto-advance)",
        round_scope="R64",
        rule_type="max_upset",
        seeds_affected=(1, 16),
        value=0.0,
    ),
]

ALL_RULES = AUTO_ADVANCE_RULES + CEILING_RULES + UPSET_FREQUENCY_RULES


# ---------------------------------------------------------------------------
# Rule application to probability matrix
# ---------------------------------------------------------------------------

def apply_auto_advance(
    prob_matrix: dict[tuple[int, int], float],
    rules: list[SharpeningRule],
    tournament_round: str,
) -> dict[tuple[int, int], float]:
    """Apply auto-advance rules: set P=1.0 for guaranteed winners.

    Returns a new probability matrix with overrides applied.
    """
    updated = dict(prob_matrix)

    for rule in rules:
        if rule.rule_type != "auto_advance":
            continue
        if rule.round_scope != tournament_round:
            continue

        for matchup_key, p in prob_matrix.items():
            seed_a, seed_b = matchup_key
            higher_seed = min(seed_a, seed_b)

            if higher_seed in rule.seeds_affected:
                # Higher seed guaranteed to win
                updated[matchup_key] = rule.value

    return updated


def apply_seed_ceilings(
    prob_matrix: dict[tuple[int, int], float],
    rules: list[SharpeningRule],
    tournament_round: str,
    active_seeds: set[int],
) -> dict[tuple[int, int], float]:
    """Apply seed ceiling rules: eliminate seeds that can't reach this round.

    Returns a new probability matrix with blocked seeds getting P=0.
    """
    updated = dict(prob_matrix)

    blocked_seeds = set()
    for rule in rules:
        if rule.rule_type != "ceiling":
            continue
        if rule.round_scope != tournament_round:
            continue
        blocked_seeds.update(rule.seeds_affected)

    # For any matchup involving a blocked seed, the other team wins
    for matchup_key in prob_matrix:
        seed_a, seed_b = matchup_key
        if seed_a in blocked_seeds and seed_a in active_seeds:
            updated[matchup_key] = 0.0  # seed_a can't be here, seed_b wins
        elif seed_b in blocked_seeds and seed_b in active_seeds:
            updated[matchup_key] = 1.0  # seed_b can't be here, seed_a wins

    return updated


def apply_all_rules(
    prob_matrix: dict[tuple[int, int], float],
    tournament_round: str,
    active_seeds: Optional[set[int]] = None,
) -> dict[tuple[int, int], float]:
    """Apply all sharpening rules to a probability matrix.

    Returns a new probability matrix (original is not mutated).
    """
    if active_seeds is None:
        active_seeds = set(range(1, 17))

    result = apply_auto_advance(prob_matrix, ALL_RULES, tournament_round)
    result = apply_seed_ceilings(result, ALL_RULES, tournament_round, active_seeds)

    return result


# ---------------------------------------------------------------------------
# Bracket validation
# ---------------------------------------------------------------------------

def validate_bracket(
    regional_winners: dict[str, int],
    regional_upsets: dict[str, list[tuple[int, int]]],
) -> tuple[bool, list[str]]:
    """Validate a complete bracket against sharpening rules.

    regional_winners: region -> champion seed
    regional_upsets: region -> list of (higher_seed, lower_seed) upsets

    Returns (is_valid, list of violation messages).
    """
    violations = []

    # Check auto-advance: no 1 or 2 seed should lose in R64
    for region, upsets in regional_upsets.items():
        for high_seed, low_seed in upsets:
            if high_seed in (1, 2) and low_seed in (15, 16):
                violations.append(
                    f"{region}: {high_seed}-seed lost to {low_seed}-seed in R64 "
                    f"(violates auto-advance rule)"
                )

    # Check seed ceilings
    for region, champ_seed in regional_winners.items():
        if champ_seed >= 14:
            violations.append(
                f"{region}: {champ_seed}-seed won the region "
                f"(violates seed ceiling)"
            )

    # Check minimum upset requirement (at least one 12-over-5 across tournament)
    all_upsets = []
    for upsets in regional_upsets.values():
        all_upsets.extend(upsets)

    has_12_over_5 = any(
        high == 5 and low == 12 for high, low in all_upsets
    )
    if not has_12_over_5:
        violations.append(
            "No 12-over-5 upset in tournament (happens ~85% of years)"
        )

    return len(violations) == 0, violations


# ---------------------------------------------------------------------------
# Probability matrix sharpening summary
# ---------------------------------------------------------------------------

def get_sharpening_summary(tournament_round: str) -> list[str]:
    """Get human-readable summary of rules active for a given round."""
    active = []
    for rule in ALL_RULES:
        if rule.round_scope == tournament_round:
            active.append(f"[{rule.rule_type}] {rule.description}")
    return active


def get_r64_locked_outcomes() -> dict[int, int]:
    """Get R64 game outcomes that are locked by sharpening rules.

    Returns dict mapping game_index -> outcome (0=favorite wins).
    Used to constrain bracket generation.
    """
    locked = {}
    for game_idx, (high_seed, low_seed) in enumerate(R64_MATCHUPS):
        # 1-seed auto-advance: game 0 (1v16) is always 0 (favorite wins)
        if high_seed == 1:
            locked[game_idx] = 0
        # 2-seed auto-advance: game 7 (2v15) is always 0 (favorite wins)
        if high_seed == 2:
            locked[game_idx] = 0
    return locked
