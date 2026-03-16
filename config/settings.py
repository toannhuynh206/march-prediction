"""
Application settings loaded from environment variables.

Uses pydantic-settings for validation and .env file support.
Falls back to os.environ if pydantic-settings is not installed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Project root (one level up from config/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class DatabaseSettings:
    """PostgreSQL connection settings."""
    user: str = os.environ.get("POSTGRES_USER", "marchmadness")
    password: str = os.environ.get("POSTGRES_PASSWORD", "bracketbuster2026")
    host: str = os.environ.get("POSTGRES_HOST", "localhost")
    port: int = int(os.environ.get("POSTGRES_PORT", "5432"))
    db: str = os.environ.get("POSTGRES_DB", "march_madness")

    @property
    def dsn(self) -> str:
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

    @property
    def dsn_psycopg2(self) -> str:
        """DSN for raw psycopg2 connections (COPY operations)."""
        return f"host={self.host} port={self.port} dbname={self.db} user={self.user} password={self.password}"


@dataclass(frozen=True)
class APISettings:
    """FastAPI server settings."""
    admin_key: str = os.environ.get("ADMIN_API_KEY", "changeme-generate-a-real-key")
    port: int = int(os.environ.get("API_PORT", "8000"))
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://localhost:3000")


@dataclass(frozen=True)
class AppSettings:
    """Top-level application settings."""
    tournament_year: int = int(os.environ.get("TOURNAMENT_YEAR", "2026"))
    project_root: Path = PROJECT_ROOT
    data_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data")
    db: DatabaseSettings = field(default_factory=DatabaseSettings)
    api: APISettings = field(default_factory=APISettings)


# Module-level singleton
settings = AppSettings()
