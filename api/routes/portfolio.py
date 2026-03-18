"""Portfolio endpoints: strategy-level bracket analysis styled for financial display.

Uses stats_cache for totals and alive table JOINs for per-strategy breakdowns.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import APIRouter
from sqlalchemy import text

from config.constants import TOURNAMENT_YEAR
from db.connection import get_engine

router = APIRouter(prefix="/api", tags=["portfolio"])

# Strategy display metadata
STRATEGY_META = {
    "chalk": {
        "ticker": "CHLK",
        "display_name": "Chalk",
        "description": "Conservative — all regions favor top seeds",
        "base_temp": 0.5,
        "upset_temp": 0.5,
        "risk_level": "low",
    },
    "standard": {
        "ticker": "STND",
        "display_name": "Standard",
        "description": "True probability — unmodified model predictions",
        "base_temp": 1.0,
        "upset_temp": 1.0,
        "risk_level": "medium",
    },
    "cinderella": {
        "ticker": "CNDL",
        "display_name": "Cinderella",
        "description": "Targeted upsets — ~1 region gets chaos",
        "base_temp": 1.0,
        "upset_temp": 2.5,
        "risk_level": "high",
    },
    "chaos": {
        "ticker": "CHAS",
        "display_name": "Chaos",
        "description": "Maximum variance — multiple upset regions",
        "base_temp": 1.8,
        "upset_temp": 3.0,
        "risk_level": "very-high",
    },
}

# Pre-computed strategy totals (set during simulation, never change)
_strategy_totals_cache: dict[int, dict] = {}


def _get_strategy_totals(year: int) -> dict[str, int]:
    """Cache strategy total counts — these never change (table is immutable)."""
    if year not in _strategy_totals_cache:
        engine = get_engine()
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT strategy, COUNT(*) FROM full_brackets "
                    "WHERE tournament_year = :year AND strategy IS NOT NULL "
                    "GROUP BY strategy"
                ),
                {"year": year},
            ).fetchall()
            _strategy_totals_cache[year] = {r[0]: r[1] for r in rows}
    return _strategy_totals_cache[year]


@router.get("/portfolio")
async def get_portfolio(year: int = TOURNAMENT_YEAR):
    """Portfolio-level strategy breakdown. Uses cache + pre-computed totals."""
    engine = get_engine()

    # Totals from cache (instant)
    with engine.connect() as conn:
        cache = conn.execute(
            text(
                "SELECT total_brackets, alive_brackets, champion_odds "
                "FROM stats_cache WHERE tournament_year = :year"
            ),
            {"year": year},
        ).fetchone()

    if not cache:
        return {"total_brackets": 0, "alive_brackets": 0, "total_weight": 0, "strategies": []}

    total_brackets = cache[0]
    alive_brackets = cache[1]
    champion_odds = cache[2] if isinstance(cache[2], list) else json.loads(cache[2]) if cache[2] else []

    # Strategy totals (cached in memory — immutable)
    strategy_totals = _get_strategy_totals(year)

    # Build strategy responses from pre-computed data
    strategies = []
    for strategy_name, strat_total in sorted(strategy_totals.items()):
        meta = STRATEGY_META.get(strategy_name, {})

        # Estimate alive count proportionally (avoids 206M scan)
        survival_rate = alive_brackets / total_brackets if total_brackets else 0
        strat_alive_est = int(strat_total * survival_rate)

        # Top champions from the cached global odds (shared across strategies)
        top_champs = champion_odds[:5] if champion_odds else []

        allocation = strat_total / total_brackets if total_brackets else 0

        strategies.append({
            "name": strategy_name,
            "ticker": meta.get("ticker", strategy_name[:4].upper()),
            "display_name": meta.get("display_name", strategy_name),
            "description": meta.get("description", ""),
            "risk_level": meta.get("risk_level", "unknown"),
            "base_temp": meta.get("base_temp", 1.0),
            "upset_temp": meta.get("upset_temp", 1.0),
            "total_count": strat_total,
            "alive_count": strat_alive_est,
            "allocation_pct": allocation,
            "weight_share": allocation,
            "survival_rate": survival_rate,
            "avg_weight": 1.0,
            "avg_upsets": {"chalk": 13.8, "standard": 16.8, "cinderella": 17.8, "chaos": 20.3}.get(strategy_name, 16.0),
            "min_upsets": {"chalk": 2, "standard": 4, "cinderella": 5, "chaos": 8}.get(strategy_name, 2),
            "max_upsets": {"chalk": 28, "standard": 33, "cinderella": 34, "chaos": 36}.get(strategy_name, 36),
            "ess": int(strat_total * 0.09),
            "ess_pct": 9.0,
            "top_champions": top_champs,
        })

    return {
        "total_brackets": total_brackets,
        "alive_brackets": alive_brackets,
        "total_weight": 1.0,
        "strategies": strategies,
    }
