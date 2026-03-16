"""
Load bracket, odds, stats, and matchup data from JSON research files into PostgreSQL.

Usage:
    python -m data.loader --year 2026              # full pipeline
    python -m data.loader --year 2026 --teams-only
    python -m data.loader --year 2026 --odds-only
    python -m data.loader --year 2026 --stats-only
    python -m data.loader --year 2026 --matchups-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.connection import session_scope, get_engine
from db.models import Team, TeamStats, Odds, Matchup


# =========================================================================
# Helpers
# =========================================================================

def _load_json(path: Path) -> dict[str, Any]:
    """Load and parse a JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"Missing data file: {path}")
    with open(path) as f:
        return json.load(f)


def _american_to_implied_prob(odds: int) -> float:
    """Convert American odds to implied probability."""
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return abs(odds) / (abs(odds) + 100.0)


def _parse_american_odds(odds_str: str) -> int:
    """Parse American odds string like '+330' or '-175' to int."""
    return int(odds_str.replace("+", ""))


# =========================================================================
# Team loader
# =========================================================================

def load_teams(year: int) -> dict[str, int]:
    """Load all tournament teams from bracket JSON into the teams table.

    Returns a mapping of team_name -> team_id for downstream loaders.
    """
    bracket_path = PROJECT_ROOT / "data" / "brackets" / f"{year}_bracket.json"
    bracket = _load_json(bracket_path)

    # Collect all unique teams from overall_seed_list
    teams_data: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for entry in bracket["overall_seed_list"]:
        name = entry["team"]
        if name in seen_names:
            continue
        seen_names.add(name)
        teams_data.append({
            "name": name,
            "seed": entry["seed_in_region"],
            "region": entry["region"],
            "conference": entry.get("conference"),
            "record": entry.get("record"),
            "tournament_year": year,
        })

    # Also grab First Four teams that might only appear in the first_four section
    for ff_game in bracket.get("first_four", []):
        for team_detail in ff_game.get("team_details", []):
            name = team_detail["team"]
            if name in seen_names:
                continue
            seen_names.add(name)
            teams_data.append({
                "name": name,
                "seed": ff_game["seed"],
                "region": ff_game["region"],
                "conference": team_detail.get("conference"),
                "record": team_detail.get("record"),
                "tournament_year": year,
            })

    # Insert with upsert (ON CONFLICT DO UPDATE)
    name_to_id: dict[str, int] = {}

    with session_scope() as session:
        # Clear existing teams for this year to avoid conflicts
        session.execute(
            text("DELETE FROM odds WHERE tournament_year = :year"),
            {"year": year},
        )
        session.execute(
            text("DELETE FROM matchups WHERE tournament_year = :year"),
            {"year": year},
        )
        session.execute(
            text("DELETE FROM team_stats WHERE tournament_year = :year"),
            {"year": year},
        )
        session.execute(
            text("DELETE FROM teams WHERE tournament_year = :year"),
            {"year": year},
        )

        for td in teams_data:
            team = Team(
                name=td["name"],
                seed=td["seed"],
                region=td["region"],
                conference=td["conference"],
                record=td["record"],
                tournament_year=td["tournament_year"],
            )
            session.add(team)
            session.flush()  # Get the id
            name_to_id[td["name"]] = team.id

    print(f"Loaded {len(name_to_id)} teams for {year}")
    return name_to_id


def _get_team_id_map(year: int) -> dict[str, int]:
    """Fetch existing team name -> id mapping from database."""
    name_to_id: dict[str, int] = {}
    with session_scope() as session:
        rows = session.execute(
            text("SELECT id, name FROM teams WHERE tournament_year = :year"),
            {"year": year},
        ).fetchall()
        for row in rows:
            name_to_id[row[1]] = row[0]
    return name_to_id


# =========================================================================
# Odds loader
# =========================================================================

# Name normalization: research data sometimes uses different names than bracket
_NAME_ALIASES: dict[str, str] = {
    "Miami FL": "Miami",
    "Miami OH": "Miami (OH)",
}


def _resolve_team_id(
    name: str,
    name_to_id: dict[str, int],
) -> int | None:
    """Resolve a team name from odds data to a team_id."""
    # Direct match
    if name in name_to_id:
        return name_to_id[name]
    # Alias match
    alias = _NAME_ALIASES.get(name)
    if alias and alias in name_to_id:
        return name_to_id[alias]
    # Partial match for combined First Four entries like "UMBC/Howard"
    if "/" in name:
        parts = name.split("/")
        for part in parts:
            part = part.strip()
            if part in name_to_id:
                return name_to_id[part]
    return None


def load_championship_futures(
    year: int,
    name_to_id: dict[str, int],
    odds_data: dict[str, Any],
) -> int:
    """Load championship futures odds into the odds table."""
    records: list[Odds] = []
    skipped: list[str] = []

    for entry in odds_data.get("championship_futures", []):
        team_name = entry["team"]
        team_id = _resolve_team_id(team_name, name_to_id)
        if team_id is None:
            skipped.append(team_name)
            continue

        odds_str = entry["odds"]
        odds_int = _parse_american_odds(odds_str)

        records.append(Odds(
            team_id=team_id,
            opponent_id=None,
            market="championship",
            line_type="futures",
            odds_value=float(odds_int),
            spread=None,
            implied_prob=entry.get("implied_prob"),
            fair_prob=entry.get("fair_prob"),
            tournament_year=year,
        ))

    if skipped:
        print(f"  Skipped championship futures (no team match): {skipped}")

    with session_scope() as session:
        session.add_all(records)

    return len(records)


def load_final_four_odds(
    year: int,
    name_to_id: dict[str, int],
    odds_data: dict[str, Any],
) -> int:
    """Load Final Four regional odds into the odds table."""
    records: list[Odds] = []
    skipped: list[str] = []

    for region, entries in odds_data.get("final_four_odds", {}).items():
        if region in ("source", "notes"):
            continue
        for entry in entries:
            team_name = entry["team"]
            team_id = _resolve_team_id(team_name, name_to_id)
            if team_id is None:
                skipped.append(f"{team_name} ({region})")
                continue

            odds_str = entry["odds"]
            odds_int = _parse_american_odds(odds_str)
            implied = _american_to_implied_prob(odds_int)

            records.append(Odds(
                team_id=team_id,
                opponent_id=None,
                market=f"final_four_{region.lower()}",
                line_type="futures",
                odds_value=float(odds_int),
                spread=None,
                implied_prob=implied,
                fair_prob=None,
                tournament_year=year,
            ))

    if skipped:
        print(f"  Skipped F4 odds (no team match): {skipped}")

    with session_scope() as session:
        session.add_all(records)

    return len(records)


def load_r64_lines(
    year: int,
    name_to_id: dict[str, int],
    odds_data: dict[str, Any],
) -> int:
    """Load R64 spread/moneyline data into the odds table."""
    records: list[Odds] = []
    skipped: list[str] = []

    for game in odds_data.get("r64_lines", []):
        # Skip TBD lines (First Four dependent)
        if game.get("spread") is None:
            continue

        # Parse team names from matchup string: "1 Duke vs 16 Siena"
        matchup_str = game["matchup"]
        parts = matchup_str.split(" vs ")
        if len(parts) != 2:
            skipped.append(matchup_str)
            continue

        # Extract team name (strip seed number prefix)
        team_a_raw = " ".join(parts[0].split()[1:])  # "Duke"
        team_b_raw = " ".join(parts[1].split()[1:])  # "Siena"

        team_a_id = _resolve_team_id(team_a_raw, name_to_id)
        team_b_id = _resolve_team_id(team_b_raw, name_to_id)

        if team_a_id is None or team_b_id is None:
            skipped.append(f"{team_a_raw} vs {team_b_raw}")
            continue

        fav_name = game.get("favorite", "")
        spread = game["spread"]
        ml_fav = game.get("moneyline_fav")
        ml_dog = game.get("moneyline_dog")

        # Determine which team is the favorite
        fav_id = _resolve_team_id(fav_name, name_to_id)
        if fav_id is None:
            fav_id = team_a_id

        dog_id = team_b_id if fav_id == team_a_id else team_a_id

        # Favorite line
        if ml_fav is not None:
            fav_implied = _american_to_implied_prob(ml_fav)
            records.append(Odds(
                team_id=fav_id,
                opponent_id=dog_id,
                market=f"r64_{game['region'].lower()}",
                line_type="moneyline",
                odds_value=float(ml_fav),
                spread=float(abs(spread)),
                implied_prob=fav_implied,
                fair_prob=None,
                tournament_year=year,
            ))

        # Underdog line
        if ml_dog is not None:
            dog_implied = _american_to_implied_prob(ml_dog)
            records.append(Odds(
                team_id=dog_id,
                opponent_id=fav_id,
                market=f"r64_{game['region'].lower()}",
                line_type="moneyline",
                odds_value=float(ml_dog),
                spread=float(abs(spread)),
                implied_prob=dog_implied,
                fair_prob=None,
                tournament_year=year,
            ))

    if skipped:
        print(f"  Skipped R64 lines (no team match): {skipped}")

    with session_scope() as session:
        session.add_all(records)

    return len(records)


def load_first_four_lines(
    year: int,
    name_to_id: dict[str, int],
    odds_data: dict[str, Any],
) -> int:
    """Load First Four lines into the odds table."""
    records: list[Odds] = []
    skipped: list[str] = []

    for game in odds_data.get("first_four", []):
        matchup_str = game["matchup"]
        parts = matchup_str.split(" vs ")
        if len(parts) != 2:
            skipped.append(matchup_str)
            continue

        team_a_raw = " ".join(parts[0].split()[1:])
        team_b_raw = " ".join(parts[1].split()[1:])

        team_a_id = _resolve_team_id(team_a_raw, name_to_id)
        team_b_id = _resolve_team_id(team_b_raw, name_to_id)

        if team_a_id is None or team_b_id is None:
            skipped.append(f"{team_a_raw} vs {team_b_raw}")
            continue

        fav_name = game.get("favorite", "")
        spread = game.get("spread", 0)
        ml_fav = game.get("moneyline_fav")
        ml_dog = game.get("moneyline_dog")

        fav_id = _resolve_team_id(fav_name, name_to_id)
        if fav_id is None:
            fav_id = team_a_id
        dog_id = team_b_id if fav_id == team_a_id else team_a_id

        if ml_fav is not None:
            records.append(Odds(
                team_id=fav_id,
                opponent_id=dog_id,
                market=f"first_four_{game['region'].lower()}",
                line_type="moneyline",
                odds_value=float(ml_fav),
                spread=float(abs(spread)) if spread else None,
                implied_prob=_american_to_implied_prob(ml_fav),
                fair_prob=None,
                tournament_year=year,
            ))

        if ml_dog is not None:
            records.append(Odds(
                team_id=dog_id,
                opponent_id=fav_id,
                market=f"first_four_{game['region'].lower()}",
                line_type="moneyline",
                odds_value=float(ml_dog),
                spread=float(abs(spread)) if spread else None,
                implied_prob=_american_to_implied_prob(ml_dog),
                fair_prob=None,
                tournament_year=year,
            ))

    if skipped:
        print(f"  Skipped First Four lines (no team match): {skipped}")

    with session_scope() as session:
        session.add_all(records)

    return len(records)


def load_odds(year: int, name_to_id: dict[str, int]) -> None:
    """Load all odds data from the most recent research file."""
    research_dir = PROJECT_ROOT / "data" / "research"

    # Find most recent vegas odds file
    odds_files = sorted(research_dir.glob(f"vegas_odds_{year}*.json"), reverse=True)
    if not odds_files:
        print(f"No vegas odds files found for {year}")
        return

    odds_path = odds_files[0]
    print(f"Loading odds from: {odds_path.name}")
    odds_data = _load_json(odds_path)

    # Clear existing odds for this year
    with session_scope() as session:
        session.execute(
            text("DELETE FROM odds WHERE tournament_year = :year"),
            {"year": year},
        )

    n_champ = load_championship_futures(year, name_to_id, odds_data)
    n_f4 = load_final_four_odds(year, name_to_id, odds_data)
    n_r64 = load_r64_lines(year, name_to_id, odds_data)
    n_ff = load_first_four_lines(year, name_to_id, odds_data)

    total = n_champ + n_f4 + n_r64 + n_ff
    print(f"Loaded {total} odds records: "
          f"{n_champ} championship, {n_f4} F4, {n_r64} R64, {n_ff} First Four")


# =========================================================================
# Stats loader (KenPom / BPI / Torvik)
# =========================================================================

# Name normalization for KenPom -> bracket matching
_KENPOM_NAME_ALIASES: dict[str, str] = {
    "Miami (FL)": "Miami",
    "Miami (OH)": "Miami (OH)",
    "Prairie View": "Prairie View A&M",
    "Saint Louis": "Saint Louis",
}


def load_stats(year: int, name_to_id: dict[str, int]) -> int:
    """Load KenPom/BPI stats into team_stats table from the most recent kenpom JSON."""
    research_dir = PROJECT_ROOT / "data" / "research"

    kenpom_files = sorted(research_dir.glob(f"kenpom_{year}*.json"), reverse=True)
    if not kenpom_files:
        print(f"No KenPom files found for {year}")
        return 0

    kenpom_path = kenpom_files[0]
    print(f"Loading stats from: {kenpom_path.name}")
    kenpom_data = _load_json(kenpom_path)

    # Load coaching data for tourney apps enrichment
    coaching_apps = _load_coaching_apps(year)

    # Clear existing stats for this year
    with session_scope() as session:
        session.execute(
            text("DELETE FROM team_stats WHERE tournament_year = :year"),
            {"year": year},
        )

    records: list[TeamStats] = []
    skipped: list[str] = []

    for team_entry in kenpom_data.get("teams", []):
        team_name = team_entry["team"]
        team_id = _resolve_team_id(team_name, name_to_id)

        # Try KenPom aliases
        if team_id is None:
            alias = _KENPOM_NAME_ALIASES.get(team_name)
            if alias:
                team_id = _resolve_team_id(alias, name_to_id)

        if team_id is None:
            skipped.append(team_name)
            continue

        coaching_tourney = coaching_apps.get(team_name, coaching_apps.get(
            _KENPOM_NAME_ALIASES.get(team_name, ""), None
        ))

        records.append(TeamStats(
            team_id=team_id,
            tournament_year=year,
            adj_em=team_entry.get("adj_em"),
            adj_o=team_entry.get("adj_o"),
            adj_d=team_entry.get("adj_d"),
            tempo=team_entry.get("tempo"),
            experience=team_entry.get("experience"),
            nonconf_sos=team_entry.get("nonconf_sos"),
            luck=team_entry.get("luck"),
            ft_rate=team_entry.get("ft_rate"),
            ft_pct=team_entry.get("ft_pct"),
            efg_pct=team_entry.get("efg_pct"),
            to_pct=team_entry.get("to_pct"),
            orb_pct=team_entry.get("orb_pct"),
            three_pt_pct=team_entry.get("three_pt_pct"),
            three_pt_defense=team_entry.get("three_pt_defense"),
            three_pt_rate=team_entry.get("three_pt_rate"),
            block_pct=team_entry.get("block_pct"),
            steal_pct=team_entry.get("steal_pct"),
            height_avg_inches=team_entry.get("height_avg_inches"),
            coaching_tourney_apps=coaching_tourney,
            data_verified=False,
        ))

    if skipped:
        print(f"  Skipped stats (no team match): {skipped}")

    with session_scope() as session:
        session.add_all(records)

    print(f"Loaded {len(records)} team stats records")
    return len(records)


def _load_coaching_apps(year: int) -> dict[str, int]:
    """Load coaching tournament appearances from research JSON files.

    Checks two file formats:
    1. coaching_tourney_{year}*.json — flat list: {"teams": [{"team": ..., "coaching_tourney_apps": N}]}
    2. coaching_records_{year}*.json — nested dict: {"coaches": {"key": {"school": ..., "ncaa_tournament": {"appearances": N}}}}

    Returns mapping of school name -> tournament appearances.
    """
    research_dir = PROJECT_ROOT / "data" / "research"
    result: dict[str, int] = {}

    # Prefer the newer coaching_tourney format (comprehensive, all 68 teams)
    tourney_files = sorted(research_dir.glob(f"coaching_tourney_{year}*.json"), reverse=True)
    if tourney_files:
        coaching_data = _load_json(tourney_files[0])
        print(f"  Loading coaching data from: {tourney_files[0].name}")
        for entry in coaching_data.get("teams", []):
            team = entry.get("team", "")
            apps = entry.get("coaching_tourney_apps", 0)
            if team:
                result[team] = apps
        return result

    # Fallback to older coaching_records format
    records_files = sorted(research_dir.glob(f"coaching_records_{year}*.json"), reverse=True)
    if records_files:
        coaching_data = _load_json(records_files[0])
        print(f"  Loading coaching data from: {records_files[0].name}")
        for _key, coach in coaching_data.get("coaches", {}).items():
            school = coach.get("school", "")
            appearances = coach.get("ncaa_tournament", {}).get("appearances", 0)
            result[school] = appearances

    return result


# =========================================================================
# Matchup builder (R64)
# =========================================================================

def _build_r64_matchups(
    year: int,
    name_to_id: dict[str, int],
    odds_data: dict[str, Any],
) -> int:
    """Build R64 matchup records from odds data with probability calculations."""
    records: list[Matchup] = []
    skipped: list[str] = []

    for game in odds_data.get("r64_lines", []):
        matchup_str = game["matchup"]
        parts = matchup_str.split(" vs ")
        if len(parts) != 2:
            skipped.append(matchup_str)
            continue

        # Extract team name (strip seed number prefix)
        team_a_raw = " ".join(parts[0].split()[1:])
        team_b_raw = " ".join(parts[1].split()[1:])

        team_a_id = _resolve_team_id(team_a_raw, name_to_id)
        team_b_id = _resolve_team_id(team_b_raw, name_to_id)

        if team_a_id is None or team_b_id is None:
            skipped.append(f"{team_a_raw} vs {team_b_raw}")
            continue

        # Skip TBD games
        if game.get("spread") is None:
            continue

        # Extract seeds from matchup string
        seed_a_str = parts[0].split()[0]
        seed_b_str = parts[1].split()[0]
        seed_a = int(seed_a_str) if seed_a_str.isdigit() else None
        seed_b = int(seed_b_str) if seed_b_str.isdigit() else None

        # Enforce canonical ordering: team_a_id < team_b_id
        if team_a_id > team_b_id:
            team_a_id, team_b_id = team_b_id, team_a_id
            seed_a, seed_b = seed_b, seed_a

        # Compute market probability from moneylines
        ml_fav = game.get("moneyline_fav")
        ml_dog = game.get("moneyline_dog")
        p_market = None
        if ml_fav is not None and ml_dog is not None:
            fav_name = game.get("favorite", "")
            fav_id = _resolve_team_id(fav_name, name_to_id)
            fav_implied = _american_to_implied_prob(ml_fav)
            dog_implied = _american_to_implied_prob(ml_dog)
            # De-vig: normalize so probabilities sum to 1
            total_implied = fav_implied + dog_implied
            if total_implied > 0:
                fav_fair = fav_implied / total_implied
                # p_market is P(team_a wins) — assign based on canonical order
                if fav_id == team_a_id:
                    p_market = fav_fair
                else:
                    p_market = 1.0 - fav_fair

        records.append(Matchup(
            round="R64",
            region=game.get("region"),
            team_a_id=team_a_id,
            team_b_id=team_b_id,
            seed_a=seed_a,
            seed_b=seed_b,
            p_market=p_market,
            tournament_year=year,
        ))

    if skipped:
        print(f"  Skipped matchups (no team match): {skipped}")

    # Clear existing R64 matchups for this year
    with session_scope() as session:
        session.execute(
            text("DELETE FROM matchups WHERE tournament_year = :year AND round = 'R64'"),
            {"year": year},
        )

    with session_scope() as session:
        session.add_all(records)

    print(f"Built {len(records)} R64 matchup records")
    return len(records)


def load_matchups(year: int, name_to_id: dict[str, int]) -> None:
    """Load all matchup data from the most recent research file."""
    research_dir = PROJECT_ROOT / "data" / "research"

    odds_files = sorted(research_dir.glob(f"vegas_odds_{year}*.json"), reverse=True)
    if not odds_files:
        print(f"No vegas odds files found for {year}")
        return

    odds_data = _load_json(odds_files[0])
    n_r64 = _build_r64_matchups(year, name_to_id, odds_data)
    print(f"Loaded {n_r64} total matchup records")


# =========================================================================
# Main
# =========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Load tournament data into PostgreSQL")
    parser.add_argument("--year", type=int, default=2026, help="Tournament year")
    parser.add_argument("--teams-only", action="store_true", help="Load only teams")
    parser.add_argument("--odds-only", action="store_true", help="Load only odds")
    parser.add_argument("--stats-only", action="store_true", help="Load only team stats")
    parser.add_argument("--matchups-only", action="store_true", help="Load only matchups")
    args = parser.parse_args()

    # Load .env if python-dotenv is available
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass

    # Single-phase flags require teams already in DB
    if args.odds_only or args.stats_only or args.matchups_only:
        name_to_id = _get_team_id_map(args.year)
        if not name_to_id:
            print("No teams found in database. Run without single-phase flags first.")
            sys.exit(1)
        if args.odds_only:
            load_odds(args.year, name_to_id)
        if args.stats_only:
            load_stats(args.year, name_to_id)
        if args.matchups_only:
            load_matchups(args.year, name_to_id)
    elif args.teams_only:
        load_teams(args.year)
    else:
        # Full pipeline: teams -> odds -> stats -> matchups
        name_to_id = load_teams(args.year)
        load_odds(args.year, name_to_id)
        load_stats(args.year, name_to_id)
        load_matchups(args.year, name_to_id)

    print("Done.")


if __name__ == "__main__":
    main()
