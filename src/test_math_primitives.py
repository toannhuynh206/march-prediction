"""Tests for math_primitives module."""

import math
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from math_primitives import (
    logit, sigmoid, moneyline_to_implied, de_vig_multiplicative,
    de_vig_power, de_vig, spread_to_prob, power_index_prob,
    log_odds_blend, encode_bracket, decode_bracket,
    get_regional_winner_seed, compute_regional_bracket_prob,
    enumerate_regional_brackets, score_regional_bracket,
    R64_MATCHUPS, ROUND_POINTS,
)


def approx(a, b, tol=1e-6):
    return abs(a - b) < tol


# ---------------------------------------------------------------------------
# Logit / Sigmoid
# ---------------------------------------------------------------------------

def test_logit_sigmoid_inverse():
    for p in [0.1, 0.25, 0.5, 0.75, 0.9, 0.99]:
        assert approx(sigmoid(logit(p)), p), f"Failed for p={p}"
    print("PASS: logit/sigmoid inverse")


def test_logit_symmetry():
    assert approx(logit(0.5), 0.0)
    assert approx(logit(0.75), -logit(0.25))
    print("PASS: logit symmetry")


def test_sigmoid_extremes():
    assert sigmoid(500) == 1.0
    assert sigmoid(-500) == 0.0
    assert approx(sigmoid(0), 0.5)
    print("PASS: sigmoid extremes")


# ---------------------------------------------------------------------------
# De-vig
# ---------------------------------------------------------------------------

def test_moneyline_to_implied():
    # -150 favorite: 150/250 = 0.6
    assert approx(moneyline_to_implied(-150), 0.6)
    # +130 underdog: 100/230 ~ 0.4348
    assert approx(moneyline_to_implied(130), 100/230)
    # -110 / +110 (standard vig)
    p_fav = moneyline_to_implied(-110)
    p_dog = moneyline_to_implied(-110)
    assert p_fav + p_dog > 1.0, "Implied probs should sum > 1 (vig)"
    print("PASS: moneyline_to_implied")


def test_de_vig_multiplicative():
    p_a, p_b = de_vig_multiplicative(0.55, 0.50)
    assert approx(p_a + p_b, 1.0), "Fair probs must sum to 1"
    assert p_a > p_b, "Favorite should still be favored after de-vig"
    print("PASS: de_vig multiplicative")


def test_de_vig_power():
    p_a, p_b = de_vig_power(0.80, 0.25)
    assert approx(p_a + p_b, 1.0, tol=1e-4), f"Power de-vig sum: {p_a+p_b}"
    assert p_a > p_b
    print("PASS: de_vig power")


def test_de_vig_auto():
    # Light favorite: should use multiplicative
    fa, fb = de_vig(-150, 130)
    assert approx(fa + fb, 1.0, tol=1e-4)
    assert fa > fb

    # Heavy favorite: should use power method
    fa2, fb2 = de_vig(-400, 300)
    assert approx(fa2 + fb2, 1.0, tol=1e-4)
    assert fa2 > fb2
    print("PASS: de_vig auto")


# ---------------------------------------------------------------------------
# Spread to probability
# ---------------------------------------------------------------------------

def test_spread_to_prob():
    # Even matchup (spread = 0) -> 50%
    assert approx(spread_to_prob(0), 0.5)
    # Favorite (spread = -5.5) -> > 50%
    p = spread_to_prob(-5.5)
    assert p > 0.5
    assert p < 1.0
    # Underdog (spread = +5.5) -> < 50%
    assert approx(spread_to_prob(5.5), 1 - p)
    # Large spread
    p_big = spread_to_prob(-15)
    assert p_big > 0.9
    print("PASS: spread_to_prob")


# ---------------------------------------------------------------------------
# Power index probability
# ---------------------------------------------------------------------------

def test_power_index_prob():
    # Equal teams
    assert approx(power_index_prob(50, 50), 0.5)
    # Stronger team A
    p = power_index_prob(60, 50)
    assert p > 0.5
    # Symmetry
    assert approx(power_index_prob(60, 50) + power_index_prob(50, 60), 1.0)
    print("PASS: power_index_prob")


# ---------------------------------------------------------------------------
# Log-odds blend
# ---------------------------------------------------------------------------

def test_log_odds_blend_neutral():
    # All components at 0.5 -> blend should be 0.5
    result = log_odds_blend(0.5, 0.5, 0.5, 0.5)
    assert approx(result, 0.5)
    print("PASS: log_odds_blend neutral")


def test_log_odds_blend_weights():
    # Market says 0.7, all else neutral -> result should be between 0.5 and 0.7
    result = log_odds_blend(0.7, 0.5, 0.5, 0.5, tier="game_lines")
    assert 0.5 < result < 0.7
    # With higher market weight (live), result should be closer to 0.7
    result_live = log_odds_blend(0.7, 0.5, 0.5, 0.5, tier="live_tournament")
    assert result_live > result
    print("PASS: log_odds_blend weights")


def test_log_odds_blend_no_market():
    # No market tier: w_m=0, so P_market is irrelevant
    r1 = log_odds_blend(0.9, 0.6, 0.5, 0.5, tier="no_market")
    r2 = log_odds_blend(0.1, 0.6, 0.5, 0.5, tier="no_market")
    assert approx(r1, r2), "With w_m=0, market prob should not affect result"
    print("PASS: log_odds_blend no_market")


def test_log_odds_blend_clamping():
    # Extreme inputs should be clamped to [0.005, 0.995]
    result = log_odds_blend(0.999, 0.999, 0.999, 0.999)
    assert result <= 0.995
    result2 = log_odds_blend(0.001, 0.001, 0.001, 0.001)
    assert result2 >= 0.005
    print("PASS: log_odds_blend clamping")


# ---------------------------------------------------------------------------
# Bracket encoding
# ---------------------------------------------------------------------------

def test_encode_decode_roundtrip():
    regional = {"South": 12345, "East": 32000, "West": 1, "Midwest": 16384}
    f4 = 5  # 101 in binary
    encoded = encode_bracket(regional, f4)
    dec_regional, dec_f4 = decode_bracket(encoded)
    for region in regional:
        assert dec_regional[region] == regional[region], f"Mismatch for {region}"
    assert dec_f4 == f4
    print("PASS: encode/decode roundtrip")


def test_all_chalk_bracket():
    # All zeros = all favorites win = all chalk
    regional_int = 0
    winner = get_regional_winner_seed(regional_int)
    assert winner == 1, f"All chalk should produce 1-seed champion, got {winner}"
    print("PASS: all chalk bracket -> 1-seed wins")


def test_single_upset():
    # Bit 0 = 1 means 16-seed beats 1-seed
    regional_int = 1  # only bit 0 set
    # Game 0 is 1v16, upset means 16-seed wins
    # Then game 8 is winner of game 0 (16) vs winner of game 1 (8 or 9)
    # With bit 8 = 0: higher seed wins game 8, which is min(16, 8) = 8
    # Game 12 = winner of 8 vs winner of 9, bit 12 = 0: higher seed
    # Game 14 = winner of 12 vs winner of 13, bit 14 = 0: higher seed
    # So the 16-seed doesn't survive (loses to 8/9 seed in R32)
    winner = get_regional_winner_seed(regional_int)
    assert winner == 1 or winner != 16, "16 seed shouldn't win the region with only R64 upset"
    print("PASS: single upset bracket")


def test_all_upsets():
    # All bits set = all upsets
    regional_int = 0x7FFF  # 15 bits all 1
    winner = get_regional_winner_seed(regional_int)
    # R64: 16, 9, 12, 13, 11, 14, 10, 15 advance
    # R32 game 8: 16 vs 9, upset -> max(16,9)=16 wins
    # R32 game 9: 12 vs 13, upset -> max(12,13)=13 wins
    # R32 game 10: 11 vs 14, upset -> max(11,14)=14 wins
    # R32 game 11: 10 vs 15, upset -> max(10,15)=15 wins
    # S16 game 12: 16 vs 13, upset -> max(16,13)=16 wins
    # S16 game 13: 14 vs 15, upset -> max(14,15)=15 wins
    # E8 game 14: 16 vs 15, upset -> max(16,15)=16 wins
    assert winner == 16, f"All upsets should produce 16-seed champion, got {winner}"
    print("PASS: all upsets -> 16-seed wins")


# ---------------------------------------------------------------------------
# Regional bracket probability
# ---------------------------------------------------------------------------

def test_regional_bracket_prob_chalk():
    # All chalk bracket with uniform 80% favorite win rate
    prob_matrix = {}
    for high, low in R64_MATCHUPS:
        prob_matrix[(high, low)] = 0.8

    # Also need later-round matchups (chalk path)
    # R32: 1v8, 5v4, 6v3, 2v7
    for pair in [(1,8), (4,5), (3,6), (2,7), (1,4), (2,3), (1,2)]:
        prob_matrix[pair] = 0.8

    p = compute_regional_bracket_prob(0, prob_matrix)
    expected = 0.8 ** 15
    assert approx(p, expected, tol=1e-10), f"Got {p}, expected {expected}"
    print("PASS: chalk bracket probability")


def test_regional_bracket_prob_sums():
    # All brackets should have probabilities that sum to ~1 (with rounding)
    prob_matrix = {}
    for high, low in R64_MATCHUPS:
        prob_matrix[(high, low)] = 0.7

    # Need all possible matchup probs
    for s1 in range(1, 17):
        for s2 in range(s1+1, 17):
            if (s1, s2) not in prob_matrix:
                prob_matrix[(s1, s2)] = 0.6

    brackets = enumerate_regional_brackets(prob_matrix)
    total_prob = sum(p for _, p in brackets)
    assert approx(total_prob, 1.0, tol=0.01), f"Total prob = {total_prob}, should be ~1.0"
    assert len(brackets) == 32768
    print(f"PASS: enumeration sums to {total_prob:.6f} (32768 brackets)")


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def test_scoring_perfect():
    actual = 12345
    score = score_regional_bracket(actual, actual)
    # Perfect score: 8*10 + 4*20 + 2*40 + 1*80 = 80+80+80+80 = 320
    expected = 8*10 + 4*20 + 2*40 + 1*80
    assert score == expected, f"Perfect regional score should be {expected}, got {score}"
    print(f"PASS: perfect regional score = {expected}")


def test_scoring_zero():
    # Completely opposite bracket
    actual = 0
    prediction = 0x7FFF
    score = score_regional_bracket(prediction, actual)
    assert score == 0, f"Opposite bracket should score 0, got {score}"
    print("PASS: opposite bracket scores 0")


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_logit_sigmoid_inverse()
    test_logit_symmetry()
    test_sigmoid_extremes()
    test_moneyline_to_implied()
    test_de_vig_multiplicative()
    test_de_vig_power()
    test_de_vig_auto()
    test_spread_to_prob()
    test_power_index_prob()
    test_log_odds_blend_neutral()
    test_log_odds_blend_weights()
    test_log_odds_blend_no_market()
    test_log_odds_blend_clamping()
    test_encode_decode_roundtrip()
    test_all_chalk_bracket()
    test_single_upset()
    test_all_upsets()
    test_regional_bracket_prob_chalk()
    test_regional_bracket_prob_sums()
    test_scoring_perfect()
    test_scoring_zero()
    print("\n=== ALL TESTS PASSED ===")
