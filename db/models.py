"""
SQLAlchemy ORM models for March Madness bracket simulation.

Maps to the schema defined in db/migrations/001_initial_schema.sql.
Brackets table uses PostgreSQL LIST partitioning by region.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# =========================================================================
# Teams
# =========================================================================

class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    seed: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    region: Mapped[str] = mapped_column(Text, nullable=False)
    conference: Mapped[str | None] = mapped_column(Text)
    record: Mapped[str | None] = mapped_column(Text)
    tournament_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2026)

    stats: Mapped[TeamStats | None] = relationship(
        "TeamStats", back_populates="team", uselist=False
    )

    __table_args__ = (
        UniqueConstraint("name", "tournament_year", name="uq_team_name_year"),
    )


# =========================================================================
# Team Stats
# =========================================================================

class TeamStats(Base):
    __tablename__ = "team_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    tournament_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2026)

    # KenPom core
    adj_em: Mapped[float | None] = mapped_column(Float)
    adj_o: Mapped[float | None] = mapped_column(Float)
    adj_d: Mapped[float | None] = mapped_column(Float)
    tempo: Mapped[float | None] = mapped_column(Float)

    # Power index factors
    experience: Mapped[float | None] = mapped_column(Float)
    nonconf_sos: Mapped[int | None] = mapped_column(Integer)
    luck: Mapped[float | None] = mapped_column(Float)
    ft_rate: Mapped[float | None] = mapped_column(Float)
    ft_pct: Mapped[float | None] = mapped_column(Float)
    efg_pct: Mapped[float | None] = mapped_column(Float)
    to_pct: Mapped[float | None] = mapped_column(Float)
    orb_pct: Mapped[float | None] = mapped_column(Float)
    three_pt_rate: Mapped[float | None] = mapped_column(Float)
    three_pt_pct: Mapped[float | None] = mapped_column(Float)
    three_pt_defense: Mapped[float | None] = mapped_column(Float)
    three_pt_variance: Mapped[float | None] = mapped_column(Float)
    block_pct: Mapped[float | None] = mapped_column(Float)
    steal_pct: Mapped[float | None] = mapped_column(Float)
    coaching_tourney_apps: Mapped[int | None] = mapped_column(Integer)
    height_avg_inches: Mapped[float | None] = mapped_column(Float)
    conf_tourney_games: Mapped[int | None] = mapped_column(Integer)

    # Public pick data
    espn_pick_pct_r32: Mapped[float | None] = mapped_column(Float)
    espn_pick_pct_s16: Mapped[float | None] = mapped_column(Float)
    espn_pick_pct_f4: Mapped[float | None] = mapped_column(Float)

    # Computed
    power_index: Mapped[float | None] = mapped_column(Float)
    data_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    team: Mapped[Team] = relationship("Team", back_populates="stats")

    __table_args__ = (
        UniqueConstraint("team_id", "tournament_year", name="uq_stats_team_year"),
    )


# =========================================================================
# Market Odds
# =========================================================================

class Odds(Base):
    __tablename__ = "odds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    opponent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"))
    market: Mapped[str] = mapped_column(Text, nullable=False)
    line_type: Mapped[str] = mapped_column(Text, nullable=False)
    odds_value: Mapped[float | None] = mapped_column(Float)
    spread: Mapped[float | None] = mapped_column(Float)
    implied_prob: Mapped[float | None] = mapped_column(Float)
    fair_prob: Mapped[float | None] = mapped_column(Float)
    tournament_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2026)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )


# =========================================================================
# Matchups
# =========================================================================

class Matchup(Base):
    __tablename__ = "matchups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    round: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[str | None] = mapped_column(Text)
    game_index: Mapped[int | None] = mapped_column(SmallInteger)
    team_a_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    team_b_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    seed_a: Mapped[int | None] = mapped_column(SmallInteger)
    seed_b: Mapped[int | None] = mapped_column(SmallInteger)
    p_market: Mapped[float | None] = mapped_column(Float)
    p_stats: Mapped[float | None] = mapped_column(Float)
    p_matchup: Mapped[float | None] = mapped_column(Float)
    p_factors: Mapped[float | None] = mapped_column(Float)
    p_final: Mapped[float | None] = mapped_column(Float)
    actual_winner_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("teams.id"))
    tournament_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2026)

    __table_args__ = (
        CheckConstraint("team_a_id < team_b_id", name="ck_matchup_canonical_order"),
    )


# =========================================================================
# Brackets (partitioned by region — ORM maps to parent table)
# =========================================================================

class Bracket(Base):
    __tablename__ = "brackets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    region: Mapped[str] = mapped_column(Text, primary_key=True)
    outcomes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    stratum_id: Mapped[int | None] = mapped_column(Integer)
    cluster: Mapped[str | None] = mapped_column(Text)
    probability: Mapped[float | None] = mapped_column(Float)
    expected_score: Mapped[float | None] = mapped_column(Float)
    is_alive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tournament_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2026)


# =========================================================================
# Game Results (for live bracket pruning)
# =========================================================================

class GameResult(Base):
    __tablename__ = "game_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2026)
    region: Mapped[str] = mapped_column(Text, nullable=False)
    round: Mapped[str] = mapped_column(Text, nullable=False)
    game_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    winner_seed: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    loser_seed: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    winner_name: Mapped[str | None] = mapped_column(Text)
    loser_name: Mapped[str | None] = mapped_column(Text)
    winner_score: Mapped[int | None] = mapped_column(SmallInteger)
    loser_score: Mapped[int | None] = mapped_column(SmallInteger)
    entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    __table_args__ = (
        UniqueConstraint(
            "tournament_year", "region", "round", "game_number",
            name="uq_game_result_slot",
        ),
    )


# =========================================================================
# Strata / Worlds (simulation budget tracking)
# =========================================================================

# =========================================================================
# Full Tournament Brackets (63 games: 4×15 regional + 3 F4)
# =========================================================================

class FullBracket(Base):
    __tablename__ = "full_brackets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    east_outcomes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    south_outcomes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    west_outcomes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    midwest_outcomes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    f4_outcomes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    champion_seed: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    champion_region: Mapped[str] = mapped_column(Text, nullable=False)
    total_upsets: Mapped[int | None] = mapped_column(SmallInteger)
    strategy: Mapped[str | None] = mapped_column(Text)
    is_alive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tournament_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2026)

    __table_args__ = (
        CheckConstraint("f4_outcomes BETWEEN 0 AND 7", name="ck_f4_range"),
    )


class Stratum(Base):
    __tablename__ = "strata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2026)
    region: Mapped[str] = mapped_column(Text, nullable=False)
    r64_upsets: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    champion_tier: Mapped[str] = mapped_column(Text, nullable=False)
    prior_prob: Mapped[float] = mapped_column(Float, nullable=False)
    target_count: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_count: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint(
            "tournament_year", "region", "r64_upsets", "champion_tier",
            name="uq_stratum_world",
        ),
    )
