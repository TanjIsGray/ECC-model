"""
DRAM subarray fault model for Reed-Solomon ECC testing.

Fault types (default distribution):
  - single_bit_1sym: Single bit flip in 1 subarray
  - random_8bit_1sym: Random 8-bit pattern in 1 subarray  
  - random_8bit_2sym: Random 8-bit patterns in 2 contiguous subarrays (2-aligned)
  - random_8bit_4sym: Random 8-bit patterns in 4 contiguous subarrays (4-aligned)
  - out_of_model: 5-6 contiguous symbols or 4+ scattered symbols

Alignment rules:
  - 1-symbol: any position 0..n-1
  - 2-symbol: start at even position (0, 2, 4, ...)
  - 4-symbol: start at position divisible by 4 (0, 4, 8, ...)
  - 5/6-symbol (out-of-model contiguous): any start position
  - scattered (out-of-model): random non-contiguous positions
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Tuple
import sys


FAULT_TYPE_NAMES = ["single_bit_1sym", "random_8bit_1sym", "random_8bit_2sym", 
                    "random_8bit_4sym", "out_of_model"]

FAULT_TYPE_DESCRIPTIONS = {
    "single_bit_1sym": "1 symbol, 1 bit flipped",
    "random_8bit_1sym": "1 symbol, random 8-bit pattern",
    "random_8bit_2sym": "2 contiguous symbols (2-aligned), random patterns",
    "random_8bit_4sym": "4 contiguous symbols (4-aligned), random patterns",
    "out_of_model": "5-6 contiguous or 4+ scattered symbols",
}


@dataclass
class FaultDistribution:
    """Defines the fault type distribution (counts sum to total)."""
    single_bit_1sym: int = 9000
    random_8bit_1sym: int = 800
    random_8bit_2sym: int = 100
    random_8bit_4sym: int = 50
    out_of_model: int = 50

    @property
    def total(self) -> int:
        return (self.single_bit_1sym + self.random_8bit_1sym + 
                self.random_8bit_2sym + self.random_8bit_4sym + self.out_of_model)

    def thresholds(self) -> List[Tuple[str, int]]:
        """Return cumulative thresholds for sampling."""
        acc = 0
        result = []
        for name in FAULT_TYPE_NAMES:
            acc += getattr(self, name)
            result.append((name, acc))
        return result

    def print_summary(self, file=None) -> None:
        """Print distribution summary with percentages."""
        if file is None:
            file = sys.stdout
        total = self.total
        print("Fault Distribution:", file=file)
        print(f"  Total: {total}", file=file)
        for name in FAULT_TYPE_NAMES:
            count = getattr(self, name)
            pct = 100.0 * count / total if total > 0 else 0.0
            desc = FAULT_TYPE_DESCRIPTIONS[name]
            print(f"  {name}: {count} ({pct:.3f}%) - {desc}", file=file)
        print(file=file)

    @classmethod
    def from_tuple(cls, values: Tuple[int, int, int, int, int]) -> "FaultDistribution":
        """Create from tuple: (1bit, 1sym, 2sym, 4sym, other)."""
        return cls(
            single_bit_1sym=values[0],
            random_8bit_1sym=values[1],
            random_8bit_2sym=values[2],
            random_8bit_4sym=values[3],
            out_of_model=values[4],
        )


@dataclass
class Fault:
    """A fault to apply: list of (position, xor_pattern) pairs."""
    fault_type: str
    errors: List[Tuple[int, int]]  # [(position, pattern), ...]


def random_single_bit() -> int:
    """Return a random single-bit pattern (one of 8 possibilities)."""
    return 1 << random.randint(0, 7)


def random_8bit_nonzero(rng: random.Random) -> int:
    """Return a random non-zero 8-bit pattern."""
    return rng.randint(1, 255)


def generate_fault(n: int, dist: FaultDistribution, rng: random.Random) -> Fault:
    """
    Generate a fault according to the distribution.
    
    Args:
        n: Codeword length (e.g., 34 for RS(34,32))
        dist: Fault distribution
        rng: Random number generator
    
    Returns:
        Fault object with type and error positions/patterns
    """
    # Sample fault type
    sample = rng.randint(1, dist.total)
    fault_type = "out_of_model"
    for name, threshold in dist.thresholds():
        if sample <= threshold:
            fault_type = name
            break
    
    errors: List[Tuple[int, int]] = []
    
    if fault_type == "single_bit_1sym":
        # Single bit flip in one random symbol
        pos = rng.randint(0, n - 1)
        pattern = random_single_bit()
        errors = [(pos, pattern)]
    
    elif fault_type == "random_8bit_1sym":
        # Random 8-bit pattern in one random symbol
        pos = rng.randint(0, n - 1)
        pattern = random_8bit_nonzero(rng)
        errors = [(pos, pattern)]
    
    elif fault_type == "random_8bit_2sym":
        # Random 8-bit patterns in 2 contiguous symbols, 2-aligned
        # Valid start positions: 0, 2, 4, ..., up to n-2 (must fit 2 symbols)
        max_start = ((n - 1) // 2) * 2  # largest even position where we can fit 2
        if max_start > n - 2:
            max_start = n - 2
        start = (rng.randint(0, max_start // 2)) * 2
        for i in range(2):
            pos = start + i
            if pos < n:
                errors.append((pos, random_8bit_nonzero(rng)))
    
    elif fault_type == "random_8bit_4sym":
        # Random 8-bit patterns in 4 contiguous symbols, 4-aligned
        # Valid start positions: 0, 4, 8, ...
        # May extend past n; we only apply positions < n
        max_start_idx = (n - 1) // 4  # number of valid 4-aligned starts
        start = rng.randint(0, max_start_idx) * 4
        for i in range(4):
            pos = start + i
            if pos < n:
                errors.append((pos, random_8bit_nonzero(rng)))
    
    else:  # out_of_model
        # 50% chance: 5-6 contiguous symbols (any alignment)
        # 50% chance: 4-8 scattered (non-contiguous) symbols
        if rng.random() < 0.5:
            # Contiguous 5 or 6 symbols
            num_syms = rng.choice([5, 6])
            max_start = n - num_syms
            if max_start < 0:
                max_start = 0
                num_syms = n
            start = rng.randint(0, max_start) if max_start > 0 else 0
            for i in range(num_syms):
                pos = start + i
                if pos < n:
                    errors.append((pos, random_8bit_nonzero(rng)))
        else:
            # Scattered 4-8 symbols at random positions
            num_errors = rng.randint(4, min(8, n))
            positions = rng.sample(range(n), num_errors)
            for pos in positions:
                errors.append((pos, random_8bit_nonzero(rng)))
    
    return Fault(fault_type=fault_type, errors=errors)


def apply_fault(codeword: bytearray, fault: Fault) -> None:
    """Apply a fault to a codeword (in-place XOR)."""
    n = len(codeword)
    for pos, pattern in fault.errors:
        if 0 <= pos < n and pattern != 0:
            codeword[pos] ^= pattern


# Default distribution
DEFAULT_FAULT_DISTRIBUTION = FaultDistribution()


