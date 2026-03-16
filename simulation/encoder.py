"""
15-bit bracket encoder/decoder.

Packs 15 game outcomes (one bit each) into a SMALLINT (int16).
Bit 0 = game 0 (R64, 1v16), ..., Bit 14 = game 14 (E8 final).

Bit value: 0 = top team wins, 1 = bottom team wins.
"""

from __future__ import annotations

import numpy as np

from simulation.bracket_structure import TOTAL_GAMES


# =========================================================================
# Single-value encode / decode
# =========================================================================

def encode(outcomes: tuple[int, ...] | list[int]) -> int:
    """Pack 15 game outcomes into a single SMALLINT.

    Args:
        outcomes: Sequence of 15 ints (each 0 or 1).

    Returns:
        Packed integer in [0, 32767].
    """
    if len(outcomes) != TOTAL_GAMES:
        raise ValueError(f"Expected {TOTAL_GAMES} outcomes, got {len(outcomes)}")

    packed = 0
    for i, bit in enumerate(outcomes):
        packed |= (bit & 1) << i
    return packed


def decode(packed: int) -> tuple[int, ...]:
    """Unpack a SMALLINT into 15 game outcomes.

    Args:
        packed: Integer in [0, 32767].

    Returns:
        Tuple of 15 ints (each 0 or 1).
    """
    return tuple((packed >> i) & 1 for i in range(TOTAL_GAMES))


def get_bit(packed: int, game_index: int) -> int:
    """Extract a single game outcome from a packed value."""
    return (packed >> game_index) & 1


# =========================================================================
# Vectorized encode / decode (NumPy)
# =========================================================================

def encode_batch(outcomes: np.ndarray) -> np.ndarray:
    """Pack N×15 outcome matrix into N packed int16 values.

    Args:
        outcomes: Array of shape (N, 15), dtype uint8 or int8, values 0 or 1.

    Returns:
        Array of shape (N,), dtype int16.
    """
    n = outcomes.shape[0]
    bit_weights = (1 << np.arange(TOTAL_GAMES, dtype=np.int16))  # [1, 2, 4, ..., 16384]
    packed = outcomes.astype(np.int16) @ bit_weights
    return packed


def decode_batch(packed: np.ndarray) -> np.ndarray:
    """Unpack N packed int16 values into N×15 outcome matrix.

    Args:
        packed: Array of shape (N,), dtype int16.

    Returns:
        Array of shape (N, 15), dtype uint8, values 0 or 1.
    """
    bit_positions = np.arange(TOTAL_GAMES, dtype=np.int16)
    # Broadcast: (N, 1) >> (15,) → (N, 15)
    outcomes = (packed[:, np.newaxis] >> bit_positions) & 1
    return outcomes.astype(np.uint8)


# =========================================================================
# Upset counting
# =========================================================================

def count_r64_upsets(packed: int) -> int:
    """Count number of R64 upsets (bits 0-7 that are 1)."""
    r64_bits = packed & 0xFF  # lower 8 bits
    return bin(r64_bits).count("1")


def count_r64_upsets_batch(packed: np.ndarray) -> np.ndarray:
    """Vectorized R64 upset counting for N brackets.

    Args:
        packed: Array of shape (N,), dtype int16.

    Returns:
        Array of shape (N,), dtype uint8, values 0-8.
    """
    r64_bits = packed.astype(np.uint16) & 0xFF
    # Bit-counting via lookup or population count
    counts = np.zeros(len(r64_bits), dtype=np.uint8)
    for bit in range(8):
        counts += ((r64_bits >> bit) & 1).astype(np.uint8)
    return counts


# =========================================================================
# Round-trip test
# =========================================================================

if __name__ == "__main__":
    import random

    print("Running encoder round-trip tests...")

    # Test all-zeros and all-ones
    assert decode(encode((0,) * 15)) == (0,) * 15
    assert decode(encode((1,) * 15)) == (1,) * 15

    # Test random values
    rng = random.Random(42)
    for _ in range(10_000):
        outcomes = tuple(rng.randint(0, 1) for _ in range(15))
        packed = encode(outcomes)
        assert 0 <= packed <= 32767
        assert decode(packed) == outcomes

    # Test vectorized
    np_rng = np.random.default_rng(42)
    batch = np_rng.integers(0, 2, size=(1000, 15), dtype=np.uint8)
    packed_batch = encode_batch(batch)
    decoded_batch = decode_batch(packed_batch)
    assert np.array_equal(batch, decoded_batch)

    # Test upset counting
    test_outcomes = (1, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0)
    p = encode(test_outcomes)
    assert count_r64_upsets(p) == 3

    print(f"All tests passed. Range: [0, {encode((1,)*15)}]")
