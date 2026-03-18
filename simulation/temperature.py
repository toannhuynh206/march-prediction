"""
Temperature transforms and strategy profiles for bracket diversification.

Temperature T reshapes probability distributions:
- T < 1: concentrates mass on likely outcomes (chalk)
- T = 1: original probabilities (standard)
- T > 1: flattens toward uniform (more upsets)

Strategy profiles allocate the 206M budget across temperature
settings to ensure diverse coverage of plausible futures,
like a portfolio spread across different market scenarios.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# =========================================================================
# Temperature transforms
# =========================================================================

def apply_temperature(
    probs: np.ndarray,
    temperature: float,
) -> np.ndarray:
    """Apply temperature scaling to a probability distribution.

    P_T(i) = p_i^(1/T) / sum_j p_j^(1/T)

    Args:
        probs: (N,) probability distribution summing to ~1.0.
        temperature: T=1 original, T<1 sharper, T>1 flatter.

    Returns:
        (N,) temperature-adjusted distribution summing to 1.0.
    """
    if abs(temperature - 1.0) < 1e-10:
        result = probs.copy()
        result /= result.sum()
        return result

    # Work in log space with log-sum-exp for numerical stability
    log_probs = np.log(np.maximum(probs, 1e-30))
    scaled = log_probs / temperature
    scaled -= scaled.max()
    exp_scaled = np.exp(scaled)
    return exp_scaled / exp_scaled.sum()


def apply_temperature_binary(
    p: np.ndarray,
    temperature: float,
) -> np.ndarray:
    """Apply temperature to binary game probabilities.

    P_T(A wins) = p^(1/T) / (p^(1/T) + (1-p)^(1/T))

    Args:
        p: (N,) P(A wins) for N games.
        temperature: Scaling parameter.

    Returns:
        (N,) temperature-adjusted probabilities.
    """
    if abs(temperature - 1.0) < 1e-10:
        return p.copy()

    p_clipped = np.clip(p, 1e-15, 1.0 - 1e-15)

    log_p = np.log(p_clipped) / temperature
    log_1mp = np.log(1.0 - p_clipped) / temperature

    # log-sum-exp stability
    max_log = np.maximum(log_p, log_1mp)
    exp_p = np.exp(log_p - max_log)
    exp_1mp = np.exp(log_1mp - max_log)

    return exp_p / (exp_p + exp_1mp)


# =========================================================================
# Strategy profiles
# =========================================================================

@dataclass(frozen=True)
class StrategyProfile:
    """One bracket sampling strategy with per-region temperature control.

    Each region independently flips a coin (p_upset) to decide whether
    it samples at base_temperature or upset_temperature. This models
    real tournaments where a cinderella run typically happens in 1 region,
    not all 4 simultaneously.

    The F4 gets its own temperature, independent of regional assignments.
    Usually kept at 1.0 — the power index differential already captures
    strength mismatches when an upset region champion reaches the F4.

    Attributes:
        name: Human-readable label.
        base_temperature: Temperature for "normal" regions.
        upset_temperature: Temperature for regions flagged as upset-heavy.
        p_upset: Probability each region independently gets upset_temperature.
        f4_temperature: Temperature for Final Four game probabilities.
        fraction: Fraction of total budget allocated to this profile.
    """

    name: str
    base_temperature: float
    upset_temperature: float
    p_upset: float
    f4_temperature: float
    fraction: float


# Portfolio of strategies — diversifies across plausible futures.
#
# Each region independently flips p_upset to decide its temperature.
# Expected upset regions per bracket = 4 × p_upset.
#
# Profile design validated via Hellinger distance analysis:
#   All pairwise Hellinger distances > 0.10 (no redundant profiles).
#   Temperature distributions converge at high T (near-uniform),
#   so a single chaos profile covers the extreme tail efficiently.
#
# Rebalanced for ESS health: standard profile gets 35% (perfect ESS),
# extreme temperatures tightened to prevent weight collapse
# (max upset_T reduced from 4.5 to 3.0, chaos base from 2.5 to 1.8).
#
# chalk:       All regions sharply favor strong seeds. F4 also sharp.
# standard:    True probability sampling. weight=1.0, perfect ESS.
# cinderella:  ~1 region gets moderate upsets, 3 stay normal (realistic).
# chaos:       ~1.6 regions elevated, F4 also volatile.
DEFAULT_PROFILES: tuple[StrategyProfile, ...] = (
    StrategyProfile(
        name="chalk",
        base_temperature=0.5,
        upset_temperature=0.5,
        p_upset=0.0,
        f4_temperature=0.5,
        fraction=0.30,
    ),
    StrategyProfile(
        name="standard",
        base_temperature=1.0,
        upset_temperature=1.0,
        p_upset=0.0,
        f4_temperature=1.0,
        fraction=0.35,
    ),
    StrategyProfile(
        # "Smart upset" — warm temperature ONLY on coin-flip games
        # (8v9, 7v10, 6v11, 5v12). These are the games where Vegas
        # spreads are < 5 points and upsets happen 35-52% of the time.
        # The rest of the bracket stays chalk (T=0.7).
        # This produces brackets that look chalky overall but have
        # 2-3 strategically placed upsets in the games that actually flip.
        # p_upset=0.0 because we don't randomly warm regions —
        # the upset_temperature applies to ALL regions equally but
        # only affects coin-flip games (the temperature math naturally
        # has more effect on 50/50 games than 95/5 games).
        name="smart_upset",
        base_temperature=0.7,
        upset_temperature=2.0,
        p_upset=0.15,
        f4_temperature=0.8,
        fraction=0.10,
    ),
    StrategyProfile(
        name="cinderella",
        base_temperature=1.0,
        upset_temperature=2.5,
        p_upset=0.25,
        f4_temperature=1.0,
        fraction=0.15,
    ),
    StrategyProfile(
        name="chaos",
        base_temperature=1.8,
        upset_temperature=3.0,
        p_upset=0.40,
        f4_temperature=1.5,
        fraction=0.10,
    ),
)


def compute_profile_budgets(
    total_budget: int,
    profiles: tuple[StrategyProfile, ...] = DEFAULT_PROFILES,
) -> list[tuple[StrategyProfile, int]]:
    """Compute exact bracket count for each strategy profile.

    Assigns rounding remainder to the largest profile.

    Returns:
        List of (profile, bracket_count) tuples.
    """
    budgets = [(p, int(total_budget * p.fraction)) for p in profiles]
    allocated = sum(n for _, n in budgets)
    remainder = total_budget - allocated

    if remainder != 0 and budgets:
        idx = max(range(len(budgets)), key=lambda i: budgets[i][1])
        profile, count = budgets[idx]
        budgets[idx] = (profile, count + remainder)

    return budgets


# =========================================================================
# Distribution diagnostics
# =========================================================================

def distribution_stats(
    original: np.ndarray,
    adjusted: np.ndarray,
) -> dict[str, float]:
    """Compare original and temperature-adjusted distributions.

    Returns:
        Dict with entropy ratio, top-1 concentration, and KL divergence.
    """
    orig = np.maximum(original, 1e-30)
    adj = np.maximum(adjusted, 1e-30)

    entropy_orig = -float(np.sum(orig * np.log(orig)))
    entropy_adj = -float(np.sum(adj * np.log(adj)))

    top1_orig = float(np.max(orig))
    top1_adj = float(np.max(adj))

    # KL(adjusted || original)
    kl = float(np.sum(adj * np.log(adj / orig)))

    return {
        "entropy_original": entropy_orig,
        "entropy_adjusted": entropy_adj,
        "entropy_ratio": entropy_adj / max(entropy_orig, 1e-30),
        "top1_original": top1_orig,
        "top1_adjusted": top1_adj,
        "kl_divergence": kl,
    }
