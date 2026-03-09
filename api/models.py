"""Pydantic request/response models for the March Madness API."""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

class TeamInfo(BaseModel):
    name: str
    seed: int
    region: str
    conference: str | None = None
    record: str | None = None


class GamePick(BaseModel):
    game: int
    seeds: list[int]
    teams: list[str]
    winner: str
    upset: bool


class RegionPicks(BaseModel):
    R64: list[GamePick]
    R32: list[GamePick]
    S16: list[GamePick]
    E8: list[GamePick]
    champion: TeamInfo


class FinalFourPick(BaseModel):
    teams: list[str]
    winner: str


class FinalFourPicks(BaseModel):
    semi1: FinalFourPick
    semi2: FinalFourPick
    championship: FinalFourPick


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class BracketSummary(BaseModel):
    id: int
    rank: int
    expected_score: float
    probability: float
    pool_value: float | None = None
    upset_count: int
    champion: str
    champion_seed: int
    is_alive: bool
    region_scores: dict[str, float]


class BracketListResponse(BaseModel):
    brackets: list[BracketSummary]
    cursor: str | None = None
    has_more: bool
    total: int
    alive_count: int


class BracketDetailResponse(BaseModel):
    id: int
    expected_score: float
    probability: float
    is_alive: bool
    regions: dict[str, RegionPicks]
    final_four: FinalFourPicks


class MatchupProb(BaseModel):
    game_index: int
    round: str
    region: str
    team_a: str
    seed_a: int
    team_b: str
    seed_b: int
    p_market: float | None = None
    p_stats: float | None = None
    p_matchup: float | None = None
    p_factors: float | None = None
    p_final: float | None = None


class TournamentBracketResponse(BaseModel):
    year: int
    regions: dict[str, list[TeamInfo]]
    matchups: list[MatchupProb]


class RegionSurvivalStats(BaseModel):
    region: str
    teams: list[dict]


class StatsResponse(BaseModel):
    total_brackets: int
    alive_brackets: int
    survival_rate: float
    results_entered: int
    champion_odds: list[dict]
    upset_distribution: list[dict]
    regions: dict[str, RegionSurvivalStats] | None = None


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class GameResultRequest(BaseModel):
    region: str
    round: str
    game_index: int
    winner_seed: int


class GameResultResponse(BaseModel):
    eliminated: int
    alive_remaining: int
    game: str
