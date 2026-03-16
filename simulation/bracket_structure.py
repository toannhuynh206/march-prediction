"""
NCAA bracket structure, seed maps, and bit-index mapping.

Each region has 15 games packed into a 15-bit SMALLINT:
  Bits 0-7:   R64 (8 games)
  Bits 8-11:  R32 (4 games)
  Bits 12-13: S16 (2 games)
  Bit  14:    E8  (1 game)

Bit value: 0 = "top" team wins (higher seed in R64), 1 = "bottom" team wins.
Import game-index mappings ONLY from this module — never re-define elsewhere.
"""

from __future__ import annotations

# =========================================================================
# Bracket position → seed mapping
# =========================================================================

# 16 bracket positions per region, ordered top-to-bottom in the bracket.
# Position index → seed number.
POSITION_TO_SEED: tuple[int, ...] = (
    1, 16, 8, 9, 5, 12, 4, 13, 6, 11, 3, 14, 7, 10, 2, 15,
)

# Inverse: seed → bracket position
SEED_TO_POSITION: dict[int, int] = {
    seed: pos for pos, seed in enumerate(POSITION_TO_SEED)
}

# =========================================================================
# R64 matchups (game_index → (top_position, bottom_position))
# =========================================================================

# Each R64 game pairs adjacent bracket positions.
# Game 0: pos 0 (seed 1) vs pos 1 (seed 16)
# Game 1: pos 2 (seed 8) vs pos 3 (seed 9)
# ...
R64_GAMES: tuple[tuple[int, int], ...] = tuple(
    (2 * i, 2 * i + 1) for i in range(8)
)

# R64 seed matchups (derived from positions — matches constants.R64_SEED_MATCHUPS)
R64_SEED_MATCHUPS: tuple[tuple[int, int], ...] = tuple(
    (POSITION_TO_SEED[top], POSITION_TO_SEED[bot]) for top, bot in R64_GAMES
)

# =========================================================================
# Game tree: later rounds reference winners of earlier games
# =========================================================================

# game_index → (source_game_a, source_game_b)
# Winner of source_game_a is "top", winner of source_game_b is "bottom".
GAME_TREE: dict[int, tuple[int, int]] = {
    8: (0, 1),      # R32: winner G0 vs winner G1
    9: (2, 3),      # R32: winner G2 vs winner G3
    10: (4, 5),     # R32: winner G4 vs winner G5
    11: (6, 7),     # R32: winner G6 vs winner G7
    12: (8, 9),     # S16: winner G8 vs winner G9
    13: (10, 11),   # S16: winner G10 vs winner G11
    14: (12, 13),   # E8:  winner G12 vs winner G13
}

# =========================================================================
# Round → game indices
# =========================================================================

ROUND_GAME_INDICES: dict[str, tuple[int, ...]] = {
    "R64": (0, 1, 2, 3, 4, 5, 6, 7),
    "R32": (8, 9, 10, 11),
    "S16": (12, 13),
    "E8": (14,),
}

TOTAL_GAMES: int = 15

# =========================================================================
# Champion seed extraction
# =========================================================================

CHAMPION_GAME_INDEX: int = 14  # E8 final — winner is region champion

# Champion tier classification
CHAMPION_TIER_SEEDS: dict[str, frozenset[int]] = {
    "1": frozenset({1}),
    "2-3": frozenset({2, 3}),
    "4-6": frozenset({4, 5, 6}),
    "7+": frozenset({7, 8, 9, 10, 11, 12, 13, 14, 15, 16}),
}


def classify_champion_tier(seed: int) -> str:
    """Return the champion tier string for a given seed."""
    for tier, seeds in CHAMPION_TIER_SEEDS.items():
        if seed in seeds:
            return tier
    return "7+"


def get_champion_seed_from_outcomes(outcomes: tuple[int, ...]) -> int:
    """Trace through 15 game outcomes to find the region champion's seed.

    Args:
        outcomes: Tuple of 15 ints (0 or 1), one per game.

    Returns:
        Seed number of the region champion.
    """
    # Track which seed occupies each bracket position after each round.
    # Start with R64 positions.
    seeds = list(POSITION_TO_SEED)  # 16 seeds at 16 positions

    # After R64: 8 winners advance
    r32_seeds: list[int] = []
    for game_idx in range(8):
        top_pos, bot_pos = R64_GAMES[game_idx]
        winner_seed = seeds[bot_pos] if outcomes[game_idx] else seeds[top_pos]
        r32_seeds.append(winner_seed)

    # After R32: 4 winners advance
    s16_seeds: list[int] = []
    for i, game_idx in enumerate(range(8, 12)):
        src_a = (game_idx - 8) * 2
        src_b = src_a + 1
        winner_seed = r32_seeds[src_b] if outcomes[game_idx] else r32_seeds[src_a]
        s16_seeds.append(winner_seed)

    # After S16: 2 winners advance
    e8_seeds: list[int] = []
    for i, game_idx in enumerate(range(12, 14)):
        src_a = (game_idx - 12) * 2
        src_b = src_a + 1
        winner_seed = s16_seeds[src_b] if outcomes[game_idx] else s16_seeds[src_a]
        e8_seeds.append(winner_seed)

    # E8 final: champion
    champion_seed = e8_seeds[1] if outcomes[14] else e8_seeds[0]
    return champion_seed
