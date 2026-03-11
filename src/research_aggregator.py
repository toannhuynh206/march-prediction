"""
Research aggregator for 2026 NCAA Tournament predictions.

Collects predictions from the best publicly available models and
Vegas odds, then blends them into our probability matrices.

Data sources (ranked by predictive value):
  1. Vegas spreads/moneylines — R64 game lines (gold tier)
  2. KenPom ratings — AdjEM, AdjO, AdjD, Tempo
  3. Bart Torvik ratings — T-Rank, WAB
  4. ESPN BPI — Power index with schedule strength
  5. NCAA NET rankings — Official committee metric
  6. Sagarin ratings — ELO-based composite
  7. Futures odds — Championship/region winner probabilities

Aggregation strategy:
  - R64: Vegas game lines dominate (55% weight)
  - R32+: Blend ratings from all sources, weight by historical accuracy
  - Apply isotonic calibration (borrowed from OddsGods)

Tournament year: 2026
"""

from dataclasses import dataclass, field
from typing import Optional
import json
import os
from pathlib import Path

from round_probability import TeamProfile


# ---------------------------------------------------------------------------
# Data source definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DataSource:
    """Definition of a prediction data source."""
    name: str
    source_type: str       # "ratings", "odds", "model", "rankings"
    reliability: float     # 0-1, historical accuracy weight
    url_pattern: str       # where to find the data
    has_game_lines: bool   # does this source provide game-specific lines?


SOURCES = [
    DataSource(
        name="vegas_spreads",
        source_type="odds",
        reliability=0.95,
        url_pattern="https://www.vegasinsider.com/college-basketball/odds/las-vegas/",
        has_game_lines=True,
    ),
    DataSource(
        name="kenpom",
        source_type="ratings",
        reliability=0.90,
        url_pattern="https://kenpom.com/",
        has_game_lines=False,
    ),
    DataSource(
        name="torvik",
        source_type="ratings",
        reliability=0.88,
        url_pattern="https://barttorvik.com/",
        has_game_lines=False,
    ),
    DataSource(
        name="espn_bpi",
        source_type="model",
        reliability=0.85,
        url_pattern="https://www.espn.com/mens-college-basketball/bpi",
        has_game_lines=False,
    ),
    DataSource(
        name="ncaa_net",
        source_type="rankings",
        reliability=0.82,
        url_pattern="https://www.ncaa.com/rankings/basketball-men/d1/ncaa-mens-basketball-net-rankings",
        has_game_lines=False,
    ),
    DataSource(
        name="sagarin",
        source_type="ratings",
        reliability=0.85,
        url_pattern="https://sagarin.com/sports/cbsend.htm",
        has_game_lines=False,
    ),
    DataSource(
        name="futures",
        source_type="odds",
        reliability=0.80,
        url_pattern="https://www.vegasinsider.com/college-basketball/odds/futures/",
        has_game_lines=False,
    ),
]


# ---------------------------------------------------------------------------
# Team research data container
# ---------------------------------------------------------------------------

@dataclass
class TeamResearchData:
    """All collected research data for one team."""
    name: str
    seed: int
    region: str

    # KenPom
    kenpom_adj_em: Optional[float] = None
    kenpom_adj_o: Optional[float] = None
    kenpom_adj_d: Optional[float] = None
    kenpom_tempo: Optional[float] = None
    kenpom_rank: Optional[int] = None

    # Torvik
    torvik_rating: Optional[float] = None
    torvik_rank: Optional[int] = None
    torvik_wab: Optional[float] = None  # wins above bubble

    # ESPN BPI
    bpi_rating: Optional[float] = None
    bpi_rank: Optional[int] = None

    # NET
    net_rank: Optional[int] = None

    # Sagarin
    sagarin_rating: Optional[float] = None
    sagarin_rank: Optional[int] = None

    # Vegas
    championship_odds: Optional[float] = None  # implied probability
    region_odds: Optional[float] = None
    final_four_odds: Optional[float] = None

    # Custom Elo (computed from season results)
    elo: Optional[float] = None

    # Season performance
    record_wins: Optional[int] = None
    record_losses: Optional[int] = None
    conference: Optional[str] = None
    tourney_appearances: Optional[int] = None

    # Defensive metrics (for later-round premium)
    defensive_rating: Optional[float] = None
    experience_score: Optional[float] = None

    # Season results for h2h and common opponent analysis
    season_results: list = field(default_factory=list)

    # Data completeness
    sources_collected: list = field(default_factory=list)

    def completeness(self) -> float:
        """What fraction of data fields are populated."""
        fields = [
            self.kenpom_adj_em, self.kenpom_rank,
            self.torvik_rating, self.torvik_rank,
            self.bpi_rating, self.net_rank,
            self.championship_odds, self.elo,
        ]
        filled = sum(1 for f in fields if f is not None)
        return filled / len(fields)

    def to_team_profile(self) -> TeamProfile:
        """Convert to TeamProfile for probability computation."""
        return TeamProfile(
            name=self.name,
            seed=self.seed,
            region=self.region,
            adj_em=self.kenpom_adj_em,
            adj_o=self.kenpom_adj_o,
            adj_d=self.kenpom_adj_d,
            tempo=self.kenpom_tempo,
            kenpom_rank=self.kenpom_rank,
            torvik_rank=self.torvik_rank,
            bpi_rank=self.bpi_rank,
            net_rank=self.net_rank,
            elo=self.elo,
            defensive_rating=self.defensive_rating or self.kenpom_adj_d,
            experience_score=self.experience_score,
            conference=self.conference,
            tourney_appearances=self.tourney_appearances,
            season_results=self.season_results,
        )


# ---------------------------------------------------------------------------
# Elo computation (borrowed from OddsGods, enhanced)
# ---------------------------------------------------------------------------

ELO_INITIAL = 1500
ELO_HOME_ADVANTAGE = 50
ELO_SEASON_REGRESSION = 0.85  # carry 85% of prior Elo into new season

# K-factor phases (from OddsGods)
K_EARLY = 50     # first 5 games
K_MID = 40       # games 5-19
K_LATE = 15      # 20+ games

# Cross-conference boost (from OddsGods — prevents mid-major inflation)
CROSS_CONFERENCE_BOOST = 1.75


def compute_elo_update(
    elo_winner: float,
    elo_loser: float,
    winner_location: str,
    games_played: int,
    same_conference: bool,
) -> tuple[float, float]:
    """Compute Elo rating update after a game.

    Returns (new_winner_elo, new_loser_elo) — new objects, no mutation.
    """
    # Adjust for home court
    adjusted_winner = elo_winner
    adjusted_loser = elo_loser
    if winner_location == "home":
        adjusted_winner += ELO_HOME_ADVANTAGE
    elif winner_location == "away":
        adjusted_loser += ELO_HOME_ADVANTAGE

    # Expected score
    expected_winner = 1.0 / (1.0 + 10 ** ((adjusted_loser - adjusted_winner) / 400))

    # K-factor based on phase
    if games_played < 5:
        k_phase = K_EARLY
    elif games_played < 20:
        k_phase = K_MID
    else:
        k_phase = K_LATE

    # Cross-conference multiplier
    cc_mult = CROSS_CONFERENCE_BOOST if not same_conference else 1.0

    # Quality multiplier (higher avg Elo = more meaningful game)
    avg_elo = (elo_winner + elo_loser) / 2
    q_mult = 1.0 + (avg_elo - 1500) / 2000  # slight boost for top matchups

    k = k_phase * cc_mult * q_mult

    # Update
    delta = k * (1.0 - expected_winner)
    return elo_winner + delta, elo_loser - delta


# ---------------------------------------------------------------------------
# Research data persistence
# ---------------------------------------------------------------------------

RESEARCH_DIR = Path(__file__).parent.parent / "data" / "research"
RESEARCH_FILE = RESEARCH_DIR / "team_research_2026.json"
PROGRESS_FILE = RESEARCH_DIR / "research_progress.json"


def save_research_data(teams: dict[str, TeamResearchData]) -> None:
    """Save all team research data to JSON."""
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

    data = {}
    for name, team in teams.items():
        team_dict = {
            "name": team.name,
            "seed": team.seed,
            "region": team.region,
            "kenpom_adj_em": team.kenpom_adj_em,
            "kenpom_adj_o": team.kenpom_adj_o,
            "kenpom_adj_d": team.kenpom_adj_d,
            "kenpom_tempo": team.kenpom_tempo,
            "kenpom_rank": team.kenpom_rank,
            "torvik_rating": team.torvik_rating,
            "torvik_rank": team.torvik_rank,
            "torvik_wab": team.torvik_wab,
            "bpi_rating": team.bpi_rating,
            "bpi_rank": team.bpi_rank,
            "net_rank": team.net_rank,
            "sagarin_rating": team.sagarin_rating,
            "sagarin_rank": team.sagarin_rank,
            "championship_odds": team.championship_odds,
            "region_odds": team.region_odds,
            "final_four_odds": team.final_four_odds,
            "elo": team.elo,
            "record_wins": team.record_wins,
            "record_losses": team.record_losses,
            "conference": team.conference,
            "tourney_appearances": team.tourney_appearances,
            "defensive_rating": team.defensive_rating,
            "experience_score": team.experience_score,
            "season_results": team.season_results,
            "sources_collected": team.sources_collected,
            "completeness": team.completeness(),
        }
        data[name] = team_dict

    with open(RESEARCH_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_research_data() -> dict[str, TeamResearchData]:
    """Load team research data from JSON."""
    if not RESEARCH_FILE.exists():
        return {}

    with open(RESEARCH_FILE) as f:
        data = json.load(f)

    teams = {}
    for name, d in data.items():
        team = TeamResearchData(
            name=d["name"],
            seed=d["seed"],
            region=d["region"],
        )
        for key in (
            "kenpom_adj_em", "kenpom_adj_o", "kenpom_adj_d", "kenpom_tempo",
            "kenpom_rank", "torvik_rating", "torvik_rank", "torvik_wab",
            "bpi_rating", "bpi_rank", "net_rank",
            "sagarin_rating", "sagarin_rank",
            "championship_odds", "region_odds", "final_four_odds",
            "elo", "record_wins", "record_losses", "conference",
            "tourney_appearances", "defensive_rating", "experience_score",
        ):
            if key in d:
                setattr(team, key, d[key])

        team.season_results = d.get("season_results", [])
        team.sources_collected = d.get("sources_collected", [])
        teams[name] = team

    return teams


def save_progress(progress: dict) -> None:
    """Save research progress checkpoint."""
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def load_progress() -> dict:
    """Load research progress checkpoint."""
    if not PROGRESS_FILE.exists():
        return {"sources_completed": [], "teams_completed": [], "last_updated": None}
    with open(PROGRESS_FILE) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Aggregated probability computation
# ---------------------------------------------------------------------------

def aggregate_team_rating(team: TeamResearchData) -> float:
    """Compute a single aggregated rating from all sources.

    Weights sources by their reliability score.
    Returns normalized rating on ~0-40 AdjEM scale.
    """
    ratings = []
    weights = []

    # KenPom AdjEM (most predictive)
    if team.kenpom_adj_em is not None:
        ratings.append(team.kenpom_adj_em)
        weights.append(0.90)

    # Torvik (very close to KenPom)
    if team.torvik_rating is not None:
        ratings.append(team.torvik_rating)
        weights.append(0.88)

    # BPI
    if team.bpi_rating is not None:
        ratings.append(team.bpi_rating)
        weights.append(0.85)

    # Sagarin
    if team.sagarin_rating is not None:
        ratings.append(team.sagarin_rating)
        weights.append(0.85)

    if not ratings:
        return 0.0

    total_weight = sum(weights)
    return sum(r * w for r, w in zip(ratings, weights)) / total_weight
