"""
Portfolio strategy: funnel-shaped bracket generation.

Core insight: R64 gambles are the variation engine for later rounds.
A 12-over-5 upset pick cascades into completely different R32/S16/E8
matchups that no public bracket explores.

Two clusters:
  Cluster A (baseline, 60%): Agree on ~28-30/32 R64 games. Survive Day 1.
    Later-round variation comes from temperature softening.
  Cluster B (gamble, 40%): Deliberately pick 2-4 R64 upsets in coin-flip
    games. These upsets structurally generate unique later-round paths.
    Brackets that survive Day 1 are disproportionately valuable.

Per-round temperature controls sampling sharpness:
  tau < 1 -> sharpens toward favorite (concentrated)
  tau = 1 -> use probabilities as-is
  tau > 1 -> softens toward 50/50 (diversified)

Formula: P_adj = P^(1/tau) / (P^(1/tau) + (1-P)^(1/tau))
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Per-round temperature (controls bracket diversity)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RoundTemperature:
    """Temperature setting for a single round."""
    round_name: str
    chalk_tau: float      # temperature for Cluster A (chalk brackets)
    gamble_tau: float     # temperature for Cluster B (gamble brackets)


# Baseline: neutral R64 (average upsets), warming through later rounds
# Gamble: warm R64 (more upsets), slightly warm later rounds
#   (later rounds get natural diversity from R64 upset cascades)

ROUND_TEMPERATURES = (
    RoundTemperature(round_name="R64",   chalk_tau=1.00, gamble_tau=1.40),
    RoundTemperature(round_name="R32",   chalk_tau=1.15, gamble_tau=1.10),
    RoundTemperature(round_name="S16",   chalk_tau=1.30, gamble_tau=1.20),
    RoundTemperature(round_name="E8",    chalk_tau=1.50, gamble_tau=1.30),
    RoundTemperature(round_name="F4",    chalk_tau=1.80, gamble_tau=1.50),
    RoundTemperature(round_name="Final", chalk_tau=2.00, gamble_tau=1.60),
)

TEMPERATURE_BY_ROUND = {t.round_name: t for t in ROUND_TEMPERATURES}


# ---------------------------------------------------------------------------
# Portfolio cluster definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClusterConfig:
    """Configuration for a bracket cluster."""
    name: str
    budget_fraction: float    # fraction of total budget
    description: str
    # Which temperature column to use
    use_gamble_temps: bool


# Default mutation rate: 6% chance of flipping any coin-flip game
# This is the X-factor — models buzzer beaters, bad ref calls, off nights.
# Only affects games where P is in [0.40, 0.60] range.
DEFAULT_MUTATION_RATE = 0.06


CLUSTER_CONFIGS = (
    ClusterConfig(
        name="baseline",
        budget_fraction=0.60,
        description=(
            "Baseline cluster: targets the historical average upset count "
            "(~3 per region). Uses neutral R64 temperature (tau=1.0) with "
            "6% mutation X-factor on coin-flip games. Later rounds warm up "
            "for path diversity. This is the bread and butter."
        ),
        use_gamble_temps=False,
    ),
    ClusterConfig(
        name="gamble",
        budget_fraction=0.40,
        description=(
            "Gamble cluster: deliberately picks more R64 upsets in coin-flip "
            "games (warm R64 temperature). These upsets cascade into unique "
            "later-round matchups. Surviving brackets are 10x more valuable "
            "because they occupy unexplored territory. Also uses 6% mutation."
        ),
        use_gamble_temps=True,
    ),
)


# ---------------------------------------------------------------------------
# Temperature transform
# ---------------------------------------------------------------------------

def apply_temperature(p: float, tau: float) -> float:
    """Apply temperature scaling to a probability.

    P_adj = P^(1/tau) / (P^(1/tau) + (1-P)^(1/tau))

    tau < 1: sharpens (0.75 -> ~0.82), concentrates on favorite
    tau = 1: no change
    tau > 1: softens (0.75 -> ~0.67), more upset-friendly

    Clamps input to [0.001, 0.999] to avoid log(0).
    Returns new probability, no mutation.
    """
    if tau == 1.0:
        return p

    p_clamped = max(0.001, min(0.999, p))
    inv_tau = 1.0 / tau

    p_scaled = p_clamped ** inv_tau
    q_scaled = (1.0 - p_clamped) ** inv_tau
    denominator = p_scaled + q_scaled

    return p_scaled / denominator


def build_tempered_prob_matrix(
    base_probs: dict[tuple[int, int], float],
    round_name: str,
    use_gamble_temps: bool,
) -> dict[tuple[int, int], float]:
    """Apply temperature to all probabilities in a matrix for a given round.

    Returns a new dict. Does not mutate base_probs.
    """
    temp_config = TEMPERATURE_BY_ROUND.get(round_name)
    if temp_config is None:
        return dict(base_probs)

    tau = temp_config.gamble_tau if use_gamble_temps else temp_config.chalk_tau

    return {
        matchup: apply_temperature(prob, tau)
        for matchup, prob in base_probs.items()
    }


# ---------------------------------------------------------------------------
# Budget allocation across clusters
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClusterBudget:
    """Budget allocation for a single cluster."""
    cluster: ClusterConfig
    bracket_count: int
    temperature_schedule: dict[str, float]  # round_name -> tau


def allocate_cluster_budgets(
    total_budget: int = 51_500_000,
) -> tuple[ClusterBudget, ...]:
    """Split regional budget across clusters.

    Returns tuple of ClusterBudget. Does not mutate anything.
    """
    budgets = []

    for config in CLUSTER_CONFIGS:
        count = int(total_budget * config.budget_fraction)
        schedule = {}
        for temp in ROUND_TEMPERATURES:
            tau = temp.gamble_tau if config.use_gamble_temps else temp.chalk_tau
            schedule[temp.round_name] = tau

        budgets.append(ClusterBudget(
            cluster=config,
            bracket_count=count,
            temperature_schedule=schedule,
        ))

    # Fix rounding: assign remainder to chalk cluster
    allocated = sum(b.bracket_count for b in budgets)
    if allocated < total_budget:
        remainder = total_budget - allocated
        old_chalk = budgets[0]
        budgets[0] = ClusterBudget(
            cluster=old_chalk.cluster,
            bracket_count=old_chalk.bracket_count + remainder,
            temperature_schedule=old_chalk.temperature_schedule,
        )

    return tuple(budgets)


# ---------------------------------------------------------------------------
# Diversity metrics
# ---------------------------------------------------------------------------

def expected_r64_agreement(p_matrix: dict[tuple[int, int], float], tau: float) -> float:
    """Estimate fraction of R64 games where brackets agree (pick the same team).

    Higher = more concentrated. Lower = more diverse.
    For each game, agreement rate = max(P_adj, 1-P_adj).
    """
    from math_primitives import R64_MATCHUPS

    agreement = 0.0
    for high_seed, low_seed in R64_MATCHUPS:
        p = p_matrix.get((high_seed, low_seed), 0.5)
        p_adj = apply_temperature(p, tau)
        agreement += max(p_adj, 1.0 - p_adj)

    return agreement / 8.0  # 8 games per region


def expected_unique_r64_paths(
    p_matrix: dict[tuple[int, int], float],
    tau: float,
    n_brackets: int,
) -> float:
    """Estimate expected number of unique R64 outcome combinations.

    Uses the coupon-collector approximation:
    E[unique] = total_paths * (1 - (1 - 1/total_paths)^n)

    But since paths aren't equiprobable, we use:
    E[unique] = sum over all paths s: (1 - (1-P(s))^n)
    which we approximate via entropy.
    """
    from math_primitives import R64_MATCHUPS

    # Compute entropy of R64 outcome distribution
    entropy = 0.0
    for high_seed, low_seed in R64_MATCHUPS:
        p = p_matrix.get((high_seed, low_seed), 0.5)
        p_adj = apply_temperature(p, tau)
        if 0 < p_adj < 1:
            entropy -= p_adj * math.log2(p_adj) + (1 - p_adj) * math.log2(1 - p_adj)

    # Effective number of equiprobable paths
    effective_paths = 2 ** entropy

    # Expected unique paths (coupon collector with equiprobable approximation)
    if effective_paths < 1:
        return 1.0
    expected = effective_paths * (1.0 - (1.0 - 1.0 / effective_paths) ** n_brackets)
    return min(expected, n_brackets)


# ---------------------------------------------------------------------------
# Summary / reporting
# ---------------------------------------------------------------------------

def print_portfolio_summary(
    total_budget: int = 51_500_000,
    sample_probs: dict[tuple[int, int], float] | None = None,
) -> None:
    """Print portfolio strategy overview."""
    budgets = allocate_cluster_budgets(total_budget)

    print("=" * 70)
    print("PORTFOLIO STRATEGY — FUNNEL DIVERSITY")
    print("=" * 70)

    for cb in budgets:
        print(f"\n--- {cb.cluster.name.upper()} CLUSTER ---")
        print(f"  Budget: {cb.bracket_count:,} brackets ({cb.cluster.budget_fraction:.0%})")
        print(f"  {cb.cluster.description}")
        print(f"  Temperature schedule:")
        for round_name, tau in cb.temperature_schedule.items():
            direction = "cold" if tau < 1 else ("neutral" if tau == 1 else "warm")
            print(f"    {round_name:>6}: tau={tau:.2f} ({direction})")

    if sample_probs:
        print("\n--- DIVERSITY METRICS (sample region) ---")
        for cb in budgets:
            tau_r64 = cb.temperature_schedule["R64"]
            agreement = expected_r64_agreement(sample_probs, tau_r64)
            unique = expected_unique_r64_paths(sample_probs, tau_r64, cb.bracket_count)
            print(f"\n  {cb.cluster.name}:")
            print(f"    R64 agreement rate: {agreement:.1%}")
            print(f"    Expected unique R64 paths: ~{unique:,.0f}")

    # Show temperature effect on a sample probability
    print("\n--- TEMPERATURE EFFECT (P=0.75 example) ---")
    for tau in [0.70, 1.00, 1.30, 1.50, 1.80, 2.00]:
        p_adj = apply_temperature(0.75, tau)
        print(f"  tau={tau:.2f}: P=0.750 -> P_adj={p_adj:.3f}")

    print("\n" + "=" * 70)
    print("R64 gambles cascade into unique later-round matchups.")
    print("Chalk cluster survives Day 1. Gamble cluster explores uncharted paths.")
    print("=" * 70)


if __name__ == "__main__":
    # Demo with sample probabilities
    sample = {
        (1, 16): 0.99, (8, 9): 0.50, (5, 12): 0.64,
        (4, 13): 0.79, (6, 11): 0.63, (3, 14): 0.85,
        (7, 10): 0.61, (2, 15): 0.94,
    }
    print_portfolio_summary(total_budget=3_000_000, sample_probs=sample)
