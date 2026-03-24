#!/usr/bin/env python3
"""
Validate alive_brackets_2026.csv against the BRACKET_ENCODING.md spec.
Checks: bit ranges, champion derivation, upset counts, auto-advance rules,
probability sanity, strategy distribution, champion distribution, uniqueness.
"""

import csv
import math
import sys
from collections import Counter
from pathlib import Path

CSV_PATH = Path(__file__).parent / "data" / "alive_brackets_2026.csv"

# R64 seed matchups per bit position (bit 0..7)
# Each tuple: (top_seed, bottom_seed). bit=0 => top wins, bit=1 => bottom wins.
R64_SEEDS = [
    (1, 16),  # bit 0
    (8, 9),   # bit 1
    (5, 12),  # bit 2
    (4, 13),  # bit 3
    (6, 11),  # bit 4
    (3, 14),  # bit 5
    (7, 10),  # bit 6
    (2, 15),  # bit 7
]

REGIONS = ["east", "south", "west", "midwest"]

EXPECTED_STRATEGY_PCT = {
    "chalk": 0.30,
    "standard": 0.35,
    "smart_upset": 0.10,
    "cinderella": 0.15,
    "chaos": 0.10,
}


def get_bit(value: int, bit_pos: int) -> int:
    """Return bit at position bit_pos (0-indexed from LSB)."""
    return (value >> bit_pos) & 1


def simulate_region(outcome: int) -> tuple[int, int]:
    """
    Given a 15-bit regional outcome, simulate the bracket and return
    (champion_seed, upset_count).

    Returns the seed of the regional champion and how many upsets occurred.
    """
    upsets = 0

    # R64: bits 0-7
    r64_winners = []
    for i in range(8):
        bit = get_bit(outcome, i)
        top_seed, bottom_seed = R64_SEEDS[i]
        if bit == 0:
            winner_seed = top_seed
        else:
            winner_seed = bottom_seed
            # Upset = lower seed (higher number) beats higher seed (lower number)
            # bit=1 means bottom team won; bottom team is the lower seed (higher number)
            # so this IS an upset
            upsets += 1
        r64_winners.append(winner_seed)

    # R32: bits 8-11
    # bit 8: winner of (bit0 result) vs (bit1 result) => r64_winners[0] vs r64_winners[1]
    # bit 9: winner of (bit2 result) vs (bit3 result) => r64_winners[2] vs r64_winners[3]
    # bit 10: winner of (bit4 result) vs (bit5 result) => r64_winners[4] vs r64_winners[5]
    # bit 11: winner of (bit6 result) vs (bit7 result) => r64_winners[6] vs r64_winners[7]
    r32_winners = []
    for i in range(4):
        bit = get_bit(outcome, 8 + i)
        top_team = r64_winners[2 * i]
        bottom_team = r64_winners[2 * i + 1]
        if bit == 0:
            winner_seed = top_team
        else:
            winner_seed = bottom_team
        # Upset if the higher-numbered seed beat the lower-numbered seed
        if winner_seed > min(top_team, bottom_team):
            # winner has higher seed number than opponent => upset
            # Actually: the lower seed number is the better team. An upset is when
            # the team with the HIGHER seed number wins.
            # If bit=0, winner=top_team. If top_team > bottom_team, that's an upset.
            # If bit=1, winner=bottom_team. If bottom_team > top_team, that's an upset.
            pass
        # More precisely: an upset occurs when the worse-seeded team (higher number) wins
        loser_seed = bottom_team if bit == 0 else top_team
        if winner_seed > loser_seed:
            upsets += 1
        r32_winners.append(winner_seed)

    # S16: bits 12-13
    # bit 12: r32_winners[0] vs r32_winners[1]
    # bit 13: r32_winners[2] vs r32_winners[3]
    s16_winners = []
    for i in range(2):
        bit = get_bit(outcome, 12 + i)
        top_team = r32_winners[2 * i]
        bottom_team = r32_winners[2 * i + 1]
        if bit == 0:
            winner_seed = top_team
        else:
            winner_seed = bottom_team
        loser_seed = bottom_team if bit == 0 else top_team
        if winner_seed > loser_seed:
            upsets += 1
        s16_winners.append(winner_seed)

    # E8: bit 14
    # s16_winners[0] vs s16_winners[1]
    bit = get_bit(outcome, 14)
    top_team = s16_winners[0]
    bottom_team = s16_winners[1]
    if bit == 0:
        champion_seed = top_team
    else:
        champion_seed = bottom_team
    loser_seed = bottom_team if bit == 0 else top_team
    if champion_seed > loser_seed:
        upsets += 1

    return champion_seed, upsets


def derive_champion(east_out, south_out, west_out, midwest_out, f4_out):
    """
    Derive champion seed and champion region from the 5 outcome columns.
    Also returns total upset count.

    F4 mapping:
    - bit 0: East champion vs South champion (0=East wins)
    - bit 1: West champion vs Midwest champion (0=West wins)
    - bit 2: Championship — Semi1 winner vs Semi2 winner (0=Semi1 wins)
    """
    region_outcomes = {
        "East": east_out,
        "South": south_out,
        "West": west_out,
        "Midwest": midwest_out,
    }

    region_champions = {}
    total_upsets = 0

    for region_name, outcome in region_outcomes.items():
        champ_seed, upsets = simulate_region(outcome)
        region_champions[region_name] = champ_seed
        total_upsets += upsets

    # F4 Semi 1: East vs South (bit 0)
    bit0 = get_bit(f4_out, 0)
    if bit0 == 0:
        semi1_winner_region = "East"
        semi1_loser_region = "South"
    else:
        semi1_winner_region = "South"
        semi1_loser_region = "East"

    semi1_winner_seed = region_champions[semi1_winner_region]
    semi1_loser_seed = region_champions[semi1_loser_region]
    if semi1_winner_seed > semi1_loser_seed:
        total_upsets += 1

    # F4 Semi 2: West vs Midwest (bit 1)
    bit1 = get_bit(f4_out, 1)
    if bit1 == 0:
        semi2_winner_region = "West"
        semi2_loser_region = "Midwest"
    else:
        semi2_winner_region = "Midwest"
        semi2_loser_region = "West"

    semi2_winner_seed = region_champions[semi2_winner_region]
    semi2_loser_seed = region_champions[semi2_loser_region]
    if semi2_winner_seed > semi2_loser_seed:
        total_upsets += 1

    # Championship: Semi1 winner vs Semi2 winner (bit 2)
    bit2 = get_bit(f4_out, 2)
    if bit2 == 0:
        champ_region = semi1_winner_region
    else:
        champ_region = semi2_winner_region

    champ_seed = region_champions[champ_region]

    # Upset check for championship
    if bit2 == 0:
        loser_seed = region_champions[semi2_winner_region]
    else:
        loser_seed = region_champions[semi1_winner_region]
    if champ_seed > loser_seed:
        total_upsets += 1

    return champ_seed, champ_region, total_upsets


def main():
    print("=" * 70)
    print("BRACKET CSV VALIDATION")
    print("=" * 70)
    print(f"File: {CSV_PATH}")
    print()

    # Counters
    total_rows = 0
    bit_range_errors = 0
    champion_seed_mismatches = 0
    champion_region_mismatches = 0
    upset_count_mismatches = 0
    auto_advance_violations = 0
    prob_errors = 0
    weight_errors = 0
    strategy_counts = Counter()
    champion_seed_counts = Counter()
    one_seed_champ_count = 0
    seen_outcomes = set()
    duplicate_count = 0

    # Track first N errors of each type for reporting
    MAX_EXAMPLES = 5
    champion_mismatch_examples = []
    upset_mismatch_examples = []
    auto_advance_examples = []
    bit_range_examples = []
    prob_error_examples = []

    with open(CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            row_id = row["id"]

            east_out = int(row["east_outcomes"])
            south_out = int(row["south_outcomes"])
            west_out = int(row["west_outcomes"])
            midwest_out = int(row["midwest_outcomes"])
            f4_out = int(row["f4_outcomes"])

            try:
                prob = float(row["probability"])
            except (ValueError, TypeError):
                prob = float("nan")

            try:
                weight = float(row["weight"])
            except (ValueError, TypeError):
                weight = float("nan")

            csv_champ_seed = int(row["champion_seed"])
            csv_champ_region = row["champion_region"]
            csv_total_upsets = int(row["total_upsets"])
            strategy = row["strategy"]

            # --- Check 1: Bit range validity ---
            regional_vals = [
                ("east", east_out), ("south", south_out),
                ("west", west_out), ("midwest", midwest_out)
            ]
            for rname, rval in regional_vals:
                if rval < 0 or rval > 32767:
                    bit_range_errors += 1
                    if len(bit_range_examples) < MAX_EXAMPLES:
                        bit_range_examples.append(f"  Row {row_id}: {rname}={rval} (out of 0-32767)")
            if f4_out < 0 or f4_out > 7:
                bit_range_errors += 1
                if len(bit_range_examples) < MAX_EXAMPLES:
                    bit_range_examples.append(f"  Row {row_id}: f4={f4_out} (out of 0-7)")

            # --- Check 2: Champion derivation ---
            derived_seed, derived_region, derived_upsets = derive_champion(
                east_out, south_out, west_out, midwest_out, f4_out
            )

            if derived_seed != csv_champ_seed:
                champion_seed_mismatches += 1
                if len(champion_mismatch_examples) < MAX_EXAMPLES:
                    champion_mismatch_examples.append(
                        f"  Row {row_id}: CSV says seed={csv_champ_seed}, derived={derived_seed} "
                        f"(E={east_out} S={south_out} W={west_out} M={midwest_out} F4={f4_out})"
                    )

            if derived_region.lower() != csv_champ_region.lower():
                champion_region_mismatches += 1
                if len(champion_mismatch_examples) < MAX_EXAMPLES:
                    champion_mismatch_examples.append(
                        f"  Row {row_id}: CSV says region={csv_champ_region}, derived={derived_region} "
                        f"(E={east_out} S={south_out} W={west_out} M={midwest_out} F4={f4_out})"
                    )

            # --- Check 3: Upset count ---
            if derived_upsets != csv_total_upsets:
                upset_count_mismatches += 1
                if len(upset_mismatch_examples) < MAX_EXAMPLES:
                    upset_mismatch_examples.append(
                        f"  Row {row_id}: CSV says upsets={csv_total_upsets}, derived={derived_upsets} "
                        f"(E={east_out} S={south_out} W={west_out} M={midwest_out} F4={f4_out})"
                    )

            # --- Check 4: Auto-advance rules ---
            # 1-seeds (bit 0) and 2-seeds (bit 7) must always be 0 in R64
            for rname, rval in regional_vals:
                bit0 = get_bit(rval, 0)  # 1v16
                bit7 = get_bit(rval, 7)  # 2v15
                if bit0 != 0:
                    auto_advance_violations += 1
                    if len(auto_advance_examples) < MAX_EXAMPLES:
                        auto_advance_examples.append(
                            f"  Row {row_id}: {rname} bit0=1 (16-seed beat 1-seed!) val={rval}"
                        )
                if bit7 != 0:
                    auto_advance_violations += 1
                    if len(auto_advance_examples) < MAX_EXAMPLES:
                        auto_advance_examples.append(
                            f"  Row {row_id}: {rname} bit7=1 (15-seed beat 2-seed!) val={rval}"
                        )

            # --- Check 5: Probability sanity ---
            if math.isnan(prob) or math.isinf(prob) or prob <= 0:
                prob_errors += 1
                if len(prob_error_examples) < MAX_EXAMPLES:
                    prob_error_examples.append(f"  Row {row_id}: probability={row['probability']}")
            if math.isnan(weight) or math.isinf(weight) or weight <= 0:
                weight_errors += 1
                if len(prob_error_examples) < MAX_EXAMPLES:
                    prob_error_examples.append(f"  Row {row_id}: weight={row['weight']}")

            # --- Check 6 & 7: Strategy and champion tracking ---
            strategy_counts[strategy] += 1
            champion_seed_counts[derived_seed] += 1
            if derived_seed == 1:
                one_seed_champ_count += 1

            # --- Check 8: Uniqueness ---
            outcome_key = (east_out, south_out, west_out, midwest_out, f4_out)
            if outcome_key in seen_outcomes:
                duplicate_count += 1
            else:
                seen_outcomes.add(outcome_key)

    # ============================
    # REPORT
    # ============================
    print(f"Total rows analyzed: {total_rows:,}")
    print()

    # Check 1
    print("-" * 50)
    print("CHECK 1: Bit Range Validity")
    if bit_range_errors == 0:
        print("  PASS — All regional outcomes in [0, 32767] and f4 in [0, 7]")
    else:
        print(f"  FAIL — {bit_range_errors} out-of-range values found")
        for ex in bit_range_examples:
            print(ex)
    print()

    # Check 2
    print("-" * 50)
    print("CHECK 2: Champion Derivation")
    print(f"  Champion seed mismatches:   {champion_seed_mismatches}")
    print(f"  Champion region mismatches:  {champion_region_mismatches}")
    if champion_seed_mismatches == 0 and champion_region_mismatches == 0:
        print("  PASS — All champion seeds and regions match derived values")
    else:
        print("  FAIL — Mismatches found!")
        for ex in champion_mismatch_examples:
            print(ex)
    print()

    # Check 3
    print("-" * 50)
    print("CHECK 3: Upset Count")
    if upset_count_mismatches == 0:
        print(f"  PASS — All {total_rows:,} upset counts match derived values")
    else:
        print(f"  FAIL — {upset_count_mismatches} rows have wrong upset count")
        for ex in upset_mismatch_examples:
            print(ex)
    print()

    # Check 4
    print("-" * 50)
    print("CHECK 4: Auto-Advance Rules (1-seeds and 2-seeds win R64)")
    if auto_advance_violations == 0:
        print(f"  PASS — No 16-over-1 or 15-over-2 upsets in any of {total_rows * 4:,} regional checks")
    else:
        print(f"  FAIL — {auto_advance_violations} violations found")
        for ex in auto_advance_examples:
            print(ex)
    print()

    # Check 5
    print("-" * 50)
    print("CHECK 5: Probability / Weight Sanity")
    if prob_errors == 0 and weight_errors == 0:
        print("  PASS — All probabilities > 0, all weights > 0, no NaN/Inf")
    else:
        print(f"  FAIL — {prob_errors} probability errors, {weight_errors} weight errors")
        for ex in prob_error_examples:
            print(ex)
    print()

    # Check 6
    print("-" * 50)
    print("CHECK 6: Strategy Distribution")
    print(f"  {'Strategy':<15} {'Count':>8} {'Actual%':>8} {'Expected%':>10} {'Delta':>8}")
    for strat in sorted(EXPECTED_STRATEGY_PCT.keys()):
        count = strategy_counts.get(strat, 0)
        actual_pct = count / total_rows * 100 if total_rows > 0 else 0
        expected_pct = EXPECTED_STRATEGY_PCT[strat] * 100
        delta = actual_pct - expected_pct
        flag = " ***" if abs(delta) > 5 else ""
        print(f"  {strat:<15} {count:>8,} {actual_pct:>7.1f}% {expected_pct:>9.1f}% {delta:>+7.1f}%{flag}")

    # Any unknown strategies?
    unknown = set(strategy_counts.keys()) - set(EXPECTED_STRATEGY_PCT.keys())
    if unknown:
        print(f"  WARNING: Unknown strategies found: {unknown}")

    # Check if any strategy is more than 5pp off
    max_delta = 0
    for strat in EXPECTED_STRATEGY_PCT:
        count = strategy_counts.get(strat, 0)
        actual_pct = count / total_rows if total_rows > 0 else 0
        delta = abs(actual_pct - EXPECTED_STRATEGY_PCT[strat])
        max_delta = max(max_delta, delta)

    if max_delta <= 0.05:
        print("  PASS — All strategies within 5pp of expected distribution")
    else:
        print(f"  WARN — Max deviation is {max_delta*100:.1f}pp (> 5pp threshold)")
    print()

    # Check 7
    print("-" * 50)
    print("CHECK 7: Champion Distribution (1-seeds >= 40%)")
    one_seed_pct = one_seed_champ_count / total_rows * 100 if total_rows > 0 else 0
    print(f"  1-seed champions: {one_seed_champ_count:,} / {total_rows:,} = {one_seed_pct:.1f}%")
    print(f"  Top champion seeds:")
    for seed, count in sorted(champion_seed_counts.items(), key=lambda x: -x[1])[:10]:
        pct = count / total_rows * 100
        print(f"    Seed {seed:>2}: {count:>8,} ({pct:.1f}%)")
    if one_seed_pct >= 40:
        print("  PASS — 1-seeds win >= 40% of brackets")
    else:
        print(f"  FAIL — 1-seeds win only {one_seed_pct:.1f}% (< 40% threshold)")
    print()

    # Check 8
    print("-" * 50)
    print("CHECK 8: Uniqueness")
    unique_count = len(seen_outcomes)
    print(f"  Unique outcome tuples: {unique_count:,}")
    print(f"  Duplicate rows: {duplicate_count:,}")
    if duplicate_count == 0:
        print("  PASS — All brackets are unique")
    else:
        dup_pct = duplicate_count / total_rows * 100
        print(f"  WARN — {duplicate_count:,} duplicates ({dup_pct:.1f}% of rows)")
    print()

    # ============================
    # FINAL SUMMARY
    # ============================
    print("=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    checks = [
        ("Bit Range Validity", bit_range_errors == 0),
        ("Champion Derivation", champion_seed_mismatches == 0 and champion_region_mismatches == 0),
        ("Upset Count", upset_count_mismatches == 0),
        ("Auto-Advance Rules", auto_advance_violations == 0),
        ("Probability Sanity", prob_errors == 0 and weight_errors == 0),
        ("Strategy Distribution", max_delta <= 0.05),
        ("Champion Distribution (1-seed >= 40%)", one_seed_pct >= 40),
        ("Uniqueness", duplicate_count == 0),
    ]

    all_pass = True
    for name, passed in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {name}")

    print()
    if all_pass:
        print("VERDICT: ALL CHECKS PASSED — Data is internally consistent.")
    else:
        failed = [name for name, passed in checks if not passed]
        print(f"VERDICT: {len(failed)} CHECK(S) FAILED — {', '.join(failed)}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
