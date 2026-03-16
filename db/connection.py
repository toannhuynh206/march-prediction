"""
PostgreSQL connection pool using SQLAlchemy.

Reads credentials from environment variables (or .env via pydantic-settings).
Provides a single engine + sessionmaker for the entire application.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# Auto-load .env so POSTGRES_PORT etc. are available
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass


def _build_dsn() -> str:
    """Build PostgreSQL DSN from environment variables."""
    user = os.environ.get("POSTGRES_USER", "marchmadness")
    password = os.environ.get("POSTGRES_PASSWORD", "bracketbuster2026")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "march_madness")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def create_app_engine(
    dsn: str | None = None,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_pre_ping: bool = True,
) -> Engine:
    """Create a SQLAlchemy engine with connection pooling.

    Args:
        dsn: Override the auto-built DSN. Useful for tests.
        pool_size: Number of persistent connections in the pool.
        max_overflow: Additional connections allowed beyond pool_size.
        pool_pre_ping: Test connections before checkout (handles stale conns).

    Returns:
        Configured SQLAlchemy Engine.
    """
    return create_engine(
        dsn or _build_dsn(),
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=pool_pre_ping,
        echo=False,
    )


# ---------------------------------------------------------------------------
# Module-level singleton (lazy init)
# ---------------------------------------------------------------------------

_engine: Engine | None = None
_SessionFactory: sessionmaker | None = None


def get_engine() -> Engine:
    """Return the module-level engine, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = create_app_engine()
    return _engine


def get_session_factory() -> sessionmaker:
    """Return the module-level session factory."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionFactory


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager that provides a transactional session.

    Commits on success, rolls back on exception, always closes.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_raw_connection():
    """Get a raw psycopg2 connection for COPY operations.

    Returns a psycopg2 connection from the engine's pool.
    Caller must close() the connection when done.
    """
    engine = get_engine()
    return engine.raw_connection()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def check_connection() -> bool:
    """Verify database connectivity. Returns True on success."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Reset (for tests)
# ---------------------------------------------------------------------------

def reset_engine() -> None:
    """Dispose the current engine and clear singletons. For testing only."""
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None


if __name__ == "__main__":
    if check_connection():
        print("PostgreSQL connection successful.")
        engine = get_engine()
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version()")).scalar()
            print(f"Server: {version}")
    else:
        print("Could not connect to PostgreSQL.")
        print(f"DSN: {_build_dsn().replace(os.environ.get('POSTGRES_PASSWORD', ''), '***')}")
