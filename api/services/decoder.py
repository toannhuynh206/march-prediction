"""Bracket decoder: per-region SMALLINT + 3-bit F4 → human-readable picks.

Decodes 4 per-region packed SMALLINTs (15 bits each) plus a 3-bit
F4 packed value into full bracket detail with team names.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.constants import F4_SEMI_PAIRINGS, TOURNAMENT_YEAR
from db.connection import get_engine
from simulation.bracket_structure import (
    GAME_TREE,
    R64_SEED_MATCHUPS,
)
from simulation.encoder import get_bit
from sqlalchemy import text


def load_region_teams(year: int = TOURNAMENT_YEAR) -> dict[str, dict[int, dict]]:
    """Load all teams indexed by region -> seed -> team info."""
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT name, seed, region, conference, record "
                "FROM teams WHERE tournament_year = :year "
                "ORDER BY region, seed"
            ),
            {"year": year},
        ).fetchall()

    by_region: dict[str, dict[int, dict]] = {}
    for r in rows:
        region = r[2]
        if region not in by_region:
            by_region[region] = {}
        by_region[region][r[1]] = {
            "name": r[0],
            "seed": r[1],
            "region": region,
            "conference": r[3],
            "record": r[4],
        }
    return by_region


def decode_region(
    packed: int,
    teams: dict[int, dict],
) -> dict[str, Any]:
    """Decode a 15-bit packed SMALLINT into region picks.

    Returns dict with R64, R32, S16, E8 game lists and champion info.
    """
    game_winners: dict[int, int] = {}
    rounds_data: dict[str, list] = {"R64": [], "R32": [], "S16": [], "E8": []}

    # R64: 8 games (bits 0-7)
    for g in range(8):
        top_seed, bot_seed = R64_SEED_MATCHUPS[g]
        bit = get_bit(packed, g)
        winner_seed = bot_seed if bit == 1 else top_seed
        game_winners[g] = winner_seed

        top_name = teams.get(top_seed, {}).get("name", f"Seed {top_seed}")
        bot_name = teams.get(bot_seed, {}).get("name", f"Seed {bot_seed}")
        winner_name = bot_name if bit == 1 else top_name

        rounds_data["R64"].append({
            "game": g,
            "seeds": [top_seed, bot_seed],
            "teams": [top_name, bot_name],
            "winner": winner_name,
            "upset": bit == 1,
        })

    # R32 (games 8-11), S16 (12-13), E8 (14)
    round_map = {
        8: "R32", 9: "R32", 10: "R32", 11: "R32",
        12: "S16", 13: "S16",
        14: "E8",
    }
    for g in range(8, 15):
        src_a, src_b = GAME_TREE[g]
        seed_a = game_winners[src_a]
        seed_b = game_winners[src_b]
        bit = get_bit(packed, g)

        winner_seed = seed_b if bit == 1 else seed_a
        game_winners[g] = winner_seed

        name_a = teams.get(seed_a, {}).get("name", f"Seed {seed_a}")
        name_b = teams.get(seed_b, {}).get("name", f"Seed {seed_b}")
        winner_name = name_b if bit == 1 else name_a

        is_upset = winner_seed > min(seed_a, seed_b)

        rounds_data[round_map[g]].append({
            "game": g,
            "seeds": [seed_a, seed_b],
            "teams": [name_a, name_b],
            "winner": winner_name,
            "upset": is_upset,
        })

    champion_seed = game_winners[14]
    champion_name = teams.get(champion_seed, {}).get("name", f"Seed {champion_seed}")

    return {
        **rounds_data,
        "champion": {
            "name": champion_name,
            "seed": champion_seed,
        },
    }


def decode_full_bracket(
    east_packed: int,
    south_packed: int,
    west_packed: int,
    midwest_packed: int,
    f4_packed: int,
    region_teams: dict[str, dict[int, dict]],
) -> dict[str, Any]:
    """Decode a full bracket into human-readable picks.

    Returns dict with 'regions' and 'final_four'.
    """
    region_packs = {
        "East": east_packed,
        "South": south_packed,
        "West": west_packed,
        "Midwest": midwest_packed,
    }

    regions = {}
    region_champions: dict[str, dict] = {}
    for region, packed in region_packs.items():
        teams = region_teams.get(region, {})
        decoded = decode_region(packed, teams)
        regions[region] = decoded
        region_champions[region] = decoded["champion"]

    # Final Four
    semi1_a, semi1_b = F4_SEMI_PAIRINGS[0]  # East, South
    semi2_a, semi2_b = F4_SEMI_PAIRINGS[1]  # West, Midwest

    semi1_teams = [
        region_champions[semi1_a]["name"],
        region_champions[semi1_b]["name"],
    ]
    semi1_bit = (f4_packed >> 0) & 1
    semi1_winner = semi1_teams[semi1_bit]

    semi2_teams = [
        region_champions[semi2_a]["name"],
        region_champions[semi2_b]["name"],
    ]
    semi2_bit = (f4_packed >> 1) & 1
    semi2_winner = semi2_teams[semi2_bit]

    champ_teams = [semi1_winner, semi2_winner]
    champ_bit = (f4_packed >> 2) & 1
    champ_winner = champ_teams[champ_bit]

    final_four = {
        "semi1": {"teams": semi1_teams, "winner": semi1_winner},
        "semi2": {"teams": semi2_teams, "winner": semi2_winner},
        "championship": {"teams": champ_teams, "winner": champ_winner},
    }

    return {"regions": regions, "final_four": final_four}


def get_champion_name_from_db(
    champion_seed: int,
    champion_region: str,
    region_teams: dict[str, dict[int, dict]],
) -> str:
    """Look up champion team name from pre-computed seed and region."""
    teams = region_teams.get(champion_region, {})
    team = teams.get(champion_seed, {})
    return team.get("name", f"({champion_seed}) {champion_region}")
