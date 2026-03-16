"""Pydantic request/response models for the March Madness API."""

from pydantic import BaseModel


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
    upset_count: int
    champion: str
    champion_seed: int
    is_alive: bool


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


class StatsResponse(BaseModel):
    total: int
    alive_count: int
    games_played: int
    upsets_so_far: int
    champion_odds: list[dict]
    upset_distribution: list[dict]


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class GameResultRequest(BaseModel):
    region: str = ""
    round: str
    game_index: int = 0
    winner_seed: int
    loser_seed: int = 0
    winner_name: str | None = None
    loser_name: str | None = None


class GameResultResponse(BaseModel):
    eliminated: int
    alive_remaining: int
    game: str
