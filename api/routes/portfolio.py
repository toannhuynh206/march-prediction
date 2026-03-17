"""Portfolio endpoints: strategy-level bracket analysis styled for financial display."""

from __future__ import annotations

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

# Strategy display metadata (temperatures, descriptions, ticker symbols)
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


@router.get("/portfolio")
async def get_portfolio(year: int = TOURNAMENT_YEAR):
    """Portfolio-level strategy breakdown with financial-style metrics."""
    engine = get_engine()
    with engine.connect() as conn:
        # Overall totals
        totals = conn.execute(
            text(
                "SELECT COUNT(*) AS total, "
                "  COUNT(*) FILTER (WHERE is_alive) AS alive, "
                "  SUM(weight) FILTER (WHERE is_alive) AS total_weight "
                "FROM full_brackets WHERE tournament_year = :year"
            ),
            {"year": year},
        ).fetchone()
        total_brackets = totals[0]
        alive_brackets = totals[1]
        total_weight = float(totals[2]) if totals[2] else 1.0

        # Per-strategy aggregates
        strategy_rows = conn.execute(
            text(
                "SELECT strategy, "
                "  COUNT(*) AS total_count, "
                "  COUNT(*) FILTER (WHERE is_alive) AS alive_count, "
                "  AVG(weight) FILTER (WHERE is_alive) AS avg_weight, "
                "  SUM(weight) FILTER (WHERE is_alive) AS sum_weight, "
                "  AVG(total_upsets) AS avg_upsets, "
                "  MIN(total_upsets) AS min_upsets, "
                "  MAX(total_upsets) AS max_upsets, "
                "  SUM(weight * weight) FILTER (WHERE is_alive) AS sum_w2 "
                "FROM full_brackets "
                "WHERE tournament_year = :year AND strategy IS NOT NULL "
                "GROUP BY strategy "
                "ORDER BY strategy"
            ),
            {"year": year},
        ).fetchall()

        # Per-strategy champion distribution (top 5 per strategy)
        champ_rows = conn.execute(
            text(
                "SELECT fb.strategy, t.name, fb.champion_seed, "
                "  SUM(fb.weight) AS total_weight "
                "FROM full_brackets fb "
                "JOIN teams t ON t.seed = fb.champion_seed "
                "  AND t.region = fb.champion_region "
                "  AND t.tournament_year = fb.tournament_year "
                "WHERE fb.is_alive = TRUE AND fb.tournament_year = :year "
                "  AND fb.strategy IS NOT NULL "
                "GROUP BY fb.strategy, t.name, fb.champion_seed "
                "ORDER BY fb.strategy, total_weight DESC"
            ),
            {"year": year},
        ).fetchall()

        # Group champion data by strategy (take top 5 per strategy)
        champ_by_strategy: dict[str, list[dict]] = {}
        for row in champ_rows:
            strategy = row[0]
            if strategy not in champ_by_strategy:
                champ_by_strategy[strategy] = []
            if len(champ_by_strategy[strategy]) < 5:
                champ_by_strategy[strategy].append({
                    "name": row[1],
                    "seed": int(row[2]),
                    "weight": float(row[3]),
                })

        # Build strategy response objects
        strategies = []
        for row in strategy_rows:
            strategy_name = row[0]
            strat_total = int(row[1])
            strat_alive = int(row[2])
            strat_avg_w = float(row[3]) if row[3] else 0
            strat_sum_w = float(row[4]) if row[4] else 0
            strat_avg_ups = float(row[5]) if row[5] else 0
            strat_min_ups = int(row[6]) if row[6] is not None else 0
            strat_max_ups = int(row[7]) if row[7] is not None else 0
            strat_sum_w2 = float(row[8]) if row[8] else 0

            # Effective Sample Size for this strategy
            ess = (strat_sum_w ** 2) / strat_sum_w2 if strat_sum_w2 > 0 else 0

            # Normalize champion weights within this strategy
            champ_list = champ_by_strategy.get(strategy_name, [])
            for c in champ_list:
                c["probability"] = c["weight"] / strat_sum_w if strat_sum_w > 0 else 0
                del c["weight"]

            meta = STRATEGY_META.get(strategy_name, {})

            strategies.append({
                "name": strategy_name,
                "ticker": meta.get("ticker", strategy_name[:4].upper()),
                "display_name": meta.get("display_name", strategy_name),
                "description": meta.get("description", ""),
                "risk_level": meta.get("risk_level", "unknown"),
                "base_temp": meta.get("base_temp", 1.0),
                "upset_temp": meta.get("upset_temp", 1.0),
                "total_count": strat_total,
                "alive_count": strat_alive,
                "allocation_pct": strat_total / total_brackets if total_brackets else 0,
                "weight_share": strat_sum_w / total_weight if total_weight else 0,
                "survival_rate": strat_alive / strat_total if strat_total else 0,
                "avg_weight": strat_avg_w,
                "avg_upsets": round(strat_avg_ups, 2),
                "min_upsets": strat_min_ups,
                "max_upsets": strat_max_ups,
                "ess": round(ess),
                "ess_pct": round(ess / strat_alive * 100, 2) if strat_alive else 0,
                "top_champions": champ_list,
            })

    return {
        "total_brackets": total_brackets,
        "alive_brackets": alive_brackets,
        "total_weight": total_weight,
        "strategies": strategies,
    }
