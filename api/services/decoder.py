"""Bracket decoder: converts 63-bit integer to human-readable picks.

Uses math_primitives for bit manipulation, team DB for name lookup.
"""

import sys
import os

# Add src/ to path so we can import math_primitives and database
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from math_primitives import (
    REGION_NAMES,
    REGION_OFFSETS,
    R64_MATCHUPS,
    PARENT_GAMES,
    decode_bracket,
    get_game_bit,
    get_regional_winner_seed,
)
from database import get_connection, DB_PATH


def _load_region_teams(db_path: str = DB_PATH) -> dict[str, dict[int, dict]]:
    """Load all teams indexed by region -> seed -> team info."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT name, seed, region, conference, record FROM teams ORDER BY region, seed"
    ).fetchall()
    conn.close()

    by_region: dict[str, dict[int, dict]] = {}
    for r in rows:
        region = r["region"]
        if region not in by_region:
            by_region[region] = {}
        by_region[region][r["seed"]] = {
            "name": r["name"],
            "seed": r["seed"],
            "region": region,
            "conference": r["conference"],
            "record": r["record"],
        }
    return by_region


def count_upsets(bracket_int: int) -> int:
    """Count total upsets in a 63-bit bracket."""
    count = 0
    for bit_pos in range(63):
        if (bracket_int >> bit_pos) & 1:
            count += 1
    return count


def decode_bracket_detail(
    bracket_int: int,
    region_teams: dict[str, dict[int, dict]] | None = None,
    db_path: str = DB_PATH,
) -> dict:
    """Decode a 63-bit bracket integer into full pick detail.

    Returns a dict with 'regions' (4 region picks) and 'final_four'.
    """
    if region_teams is None:
        region_teams = _load_region_teams(db_path)

    regional_bits, f4_bits = decode_bracket(bracket_int)

    regions = {}
    region_champions = {}

    for region_name in REGION_NAMES:
        rbits = regional_bits[region_name]
        teams = region_teams.get(region_name, {})

        # Trace game winners through the bracket
        game_winners_seed: dict[int, int] = {}
        rounds_data: dict[str, list] = {"R64": [], "R32": [], "S16": [], "E8": []}

        # R64
        for g in range(8):
            high_seed, low_seed = R64_MATCHUPS[g]
            bit = get_game_bit(rbits, g)
            winner_seed = low_seed if bit == 1 else high_seed
            game_winners_seed[g] = winner_seed

            high_team = teams.get(high_seed, {}).get("name", f"Seed {high_seed}")
            low_team = teams.get(low_seed, {}).get("name", f"Seed {low_seed}")
            winner_name = low_team if bit == 1 else high_team

            rounds_data["R64"].append({
                "game": g,
                "seeds": [high_seed, low_seed],
                "teams": [high_team, low_team],
                "winner": winner_name,
                "upset": bit == 1,
            })

        # R32, S16, E8
        round_names = {8: "R32", 9: "R32", 10: "R32", 11: "R32", 12: "S16", 13: "S16", 14: "E8"}
        for g in [8, 9, 10, 11, 12, 13, 14]:
            parent_a, parent_b = PARENT_GAMES[g]
            seed_a = game_winners_seed[parent_a]
            seed_b = game_winners_seed[parent_b]
            bit = get_game_bit(rbits, g)

            high_seed = min(seed_a, seed_b)
            low_seed = max(seed_a, seed_b)

            winner_seed = low_seed if bit == 1 else high_seed
            game_winners_seed[g] = winner_seed

            high_team = teams.get(high_seed, {}).get("name", f"Seed {high_seed}")
            low_team = teams.get(low_seed, {}).get("name", f"Seed {low_seed}")
            winner_name = low_team if bit == 1 else high_team

            rounds_data[round_names[g]].append({
                "game": g,
                "seeds": [high_seed, low_seed],
                "teams": [high_team, low_team],
                "winner": winner_name,
                "upset": bit == 1,
            })

        champion_seed = game_winners_seed[14]
        champion_name = teams.get(champion_seed, {}).get("name", f"Seed {champion_seed}")
        region_champions[region_name] = {
            "name": champion_name,
            "seed": champion_seed,
            "region": region_name,
        }

        regions[region_name] = {
            **rounds_data,
            "champion": {
                "name": champion_name,
                "seed": champion_seed,
                "region": region_name,
            },
        }

    # Final Four
    # Semi1: South vs East (bit 60)
    # Semi2: West vs Midwest (bit 61)
    # Championship: Semi1 winner vs Semi2 winner (bit 62)
    semi1_teams = [region_champions["South"]["name"], region_champions["East"]["name"]]
    semi1_bit = (f4_bits >> 0) & 1
    semi1_winner = semi1_teams[semi1_bit]

    semi2_teams = [region_champions["West"]["name"], region_champions["Midwest"]["name"]]
    semi2_bit = (f4_bits >> 1) & 1
    semi2_winner = semi2_teams[semi2_bit]

    champ_teams = [semi1_winner, semi2_winner]
    champ_bit = (f4_bits >> 2) & 1
    champ_winner = champ_teams[champ_bit]

    final_four = {
        "semi1": {"teams": semi1_teams, "winner": semi1_winner},
        "semi2": {"teams": semi2_teams, "winner": semi2_winner},
        "championship": {"teams": champ_teams, "winner": champ_winner},
    }

    return {"regions": regions, "final_four": final_four}


def get_champion_name(
    bracket_int: int,
    region_teams: dict[str, dict[int, dict]] | None = None,
    db_path: str = DB_PATH,
) -> tuple[str, int]:
    """Get the champion team name and seed from a bracket integer.

    Returns (champion_name, champion_seed).
    """
    if region_teams is None:
        region_teams = _load_region_teams(db_path)

    regional_bits, f4_bits = decode_bracket(bracket_int)

    # Find regional champions
    region_champs = {}
    for region_name in REGION_NAMES:
        rbits = regional_bits[region_name]
        champ_seed = get_regional_winner_seed(rbits)
        teams = region_teams.get(region_name, {})
        champ_name = teams.get(champ_seed, {}).get("name", f"Seed {champ_seed}")
        region_champs[region_name] = (champ_name, champ_seed)

    # Trace Final Four
    semi1_idx = (f4_bits >> 0) & 1
    semi1_regions = ["South", "East"]
    semi1_winner = region_champs[semi1_regions[semi1_idx]]

    semi2_idx = (f4_bits >> 1) & 1
    semi2_regions = ["West", "Midwest"]
    semi2_winner = region_champs[semi2_regions[semi2_idx]]

    champ_idx = (f4_bits >> 2) & 1
    finalists = [semi1_winner, semi2_winner]
    return finalists[champ_idx]
