"""
DRAM subarray fault model for Reed-Solomon ECC testing.

Fault types (default distribution):
  - single_bit_1sym: Single bit flip in 1 subarray
  - 8bit_1sym: Random 8-bit pattern in 1 subarray  
  - 8bit_2sym: Random 8-bit patterns in 2 contiguous subarrays (2-aligned)
  - 8bit_4sym: Random 8-bit patterns in 4 contiguous subarrays (4-aligned)
  - out_of_model: 5-6 contiguous symbols or 4+ scattered symbols

Alignment rules:
  - 1-symbol: any position
  - 2-symbol: start at even position (0, 2, 4, ...)
  - 4-symbol: start at position divisible by 4 (0, 4, 8, ...)
  - 5/6-symbol (out-of-model contiguous): any start position
  - scattered (out-of-model): random non-contiguous positions

Correlated faults (--correlated):
  When enabled, data faults (except single-bit) may also cause metadata faults.
  Probability = nsym/k (e.g., 2/32 for RS(34,32), 8/64 for RS(72,64)).
  Primary faults generated only in data region; correlated faults appear
  in metadata with matching fault width and alignment.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Tuple
import sys


FAULT_TYPE_NAMES = ["single_bit_1sym", "8bit_1sym", "8bit_2sym", 
                    "8bit_4sym", "out_of_model"]

FAULT_TYPE_DESCRIPTIONS = {
    "single_bit_1sym": "1 symbol, 1 bit flipped",
    "8bit_1sym": "1 symbol, random 8-bit pattern",
    "8bit_2sym": "2 contiguous symbols (2-aligned), random patterns",
    "8bit_4sym": "4 contiguous symbols (4-aligned), random patterns",
    "out_of_model": "5-6 contiguous or 4+ scattered symbols",
}


@dataclass
class FaultDistribution:
    """Defines the fault type distribution (counts sum to total)."""
    single_bit_1sym: int = 9000
    eight_bit_1sym: int = 800
    eight_bit_2sym: int = 100
    eight_bit_4sym: int = 50
    out_of_model: int = 50

    @property
    def total(self) -> int:
        return (self.single_bit_1sym + self.eight_bit_1sym + 
                self.eight_bit_2sym + self.eight_bit_4sym + self.out_of_model)
    
    def get_count(self, name: str) -> int:
        """Get count by fault type name."""
        mapping = {
            "single_bit_1sym": self.single_bit_1sym,
            "8bit_1sym": self.eight_bit_1sym,
            "8bit_2sym": self.eight_bit_2sym,
            "8bit_4sym": self.eight_bit_4sym,
            "out_of_model": self.out_of_model,
        }
        return mapping.get(name, 0)

    def thresholds(self) -> List[Tuple[str, int]]:
        """Return cumulative thresholds for sampling."""
        acc = 0
        result = []
        for name in FAULT_TYPE_NAMES:
            acc += self.get_count(name)
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
            count = self.get_count(name)
            pct = 100.0 * count / total if total > 0 else 0.0
            desc = FAULT_TYPE_DESCRIPTIONS[name]
            print(f"  {name}: {count} ({pct:.3f}%) - {desc}", file=file)
        print(file=file)

    @classmethod
    def from_tuple(cls, values: Tuple[int, int, int, int, int]) -> "FaultDistribution":
        """Create from tuple: (1bit, 1sym, 2sym, 4sym, other)."""
        return cls(
            single_bit_1sym=values[0],
            eight_bit_1sym=values[1],
            eight_bit_2sym=values[2],
            eight_bit_4sym=values[3],
            out_of_model=values[4],
        )


@dataclass
class Fault:
    """A fault to apply: list of (position, xor_pattern) pairs."""
    fault_type: str
    errors: List[Tuple[int, int]]  # [(position, pattern), ...]


def random_single_bit(rng: random.Random) -> int:
    """Return a random single-bit pattern (one of 8 possibilities)."""
    return 1 << rng.randint(0, 7)


def random_8bit_nonzero(rng: random.Random) -> int:
    """Return a random non-zero 8-bit pattern."""
    return rng.randint(1, 255)


def generate_fault(
    n: int,
    k: int,
    dist: FaultDistribution,
    rng: random.Random,
    correlated: bool = False,
) -> Fault:
    """
    Generate a fault according to the distribution.
    
    Args:
        n: Codeword length (e.g., 34 for RS(34,32))
        k: Data length (e.g., 32 for RS(34,32))
        dist: Fault distribution
        rng: Random number generator
        correlated: If True, enable correlated data/metadata faults
    
    Returns:
        Fault object with type and error positions/patterns
    """
    nsym = n - k  # Number of metadata/ECC symbols
    
    # Sample fault type
    sample = rng.randint(1, dist.total)
    fault_type = "out_of_model"
    for name, threshold in dist.thresholds():
        if sample <= threshold:
            fault_type = name
            break
    
    errors: List[Tuple[int, int]] = []
    
    # Determine the region for primary faults
    # If correlated mode: primary faults only in data region [0, k)
    # Otherwise: faults anywhere in codeword [0, n)
    if correlated and fault_type != "single_bit_1sym":
        primary_region = k  # Data bytes only
    else:
        primary_region = n  # Full codeword
    
    # Width of fault (for correlation)
    fault_width = 1
    
    if fault_type == "single_bit_1sym":
        # Single bit flip in one random symbol (no correlation)
        pos = rng.randint(0, primary_region - 1)
        pattern = random_single_bit(rng)
        errors = [(pos, pattern)]
        fault_width = 1
    
    elif fault_type == "8bit_1sym":
        # Random 8-bit pattern in one random symbol
        pos = rng.randint(0, primary_region - 1)
        pattern = random_8bit_nonzero(rng)
        errors = [(pos, pattern)]
        fault_width = 1
    
    elif fault_type == "8bit_2sym":
        # Random 8-bit patterns in 2 contiguous symbols, 2-aligned
        max_start = ((primary_region - 1) // 2) * 2
        if max_start > primary_region - 2:
            max_start = max(0, primary_region - 2)
        if max_start < 0:
            max_start = 0
        start = (rng.randint(0, max(0, max_start // 2))) * 2
        for i in range(2):
            pos = start + i
            if pos < primary_region:
                errors.append((pos, random_8bit_nonzero(rng)))
        fault_width = 2
    
    elif fault_type == "8bit_4sym":
        # Random 8-bit patterns in 4 contiguous symbols, 4-aligned
        max_start_idx = max(0, (primary_region - 1) // 4)
        start = rng.randint(0, max_start_idx) * 4
        for i in range(4):
            pos = start + i
            if pos < primary_region:
                errors.append((pos, random_8bit_nonzero(rng)))
        fault_width = 4
    
    else:  # out_of_model
        # 50% chance: 5-6 contiguous symbols (any alignment)
        # 50% chance: 4-8 scattered (non-contiguous) symbols
        if rng.random() < 0.5:
            # Contiguous 5 or 6 symbols
            num_syms = rng.choice([5, 6])
            max_start = primary_region - num_syms
            if max_start < 0:
                max_start = 0
                num_syms = min(num_syms, primary_region)
            start = rng.randint(0, max_start) if max_start > 0 else 0
            for i in range(num_syms):
                pos = start + i
                if pos < primary_region:
                    errors.append((pos, random_8bit_nonzero(rng)))
            fault_width = num_syms
        else:
            # Scattered 4-8 symbols at random positions
            num_errors = rng.randint(4, min(8, primary_region))
            positions = rng.sample(range(primary_region), num_errors)
            for pos in positions:
                errors.append((pos, random_8bit_nonzero(rng)))
            fault_width = 0  # Scattered, no correlation
    
    # Apply correlated metadata fault if enabled
    # Single-bit faults don't participate; scattered out-of-model don't either
    if correlated and fault_type != "single_bit_1sym" and fault_width > 0:
        correlation_prob = nsym / k
        if rng.random() < correlation_prob:
            # Generate correlated fault in metadata region [k, n)
            # Same width, similar alignment within metadata
            if fault_width == 1:
                # 1-symbol: random position in metadata
                meta_pos = k + rng.randint(0, nsym - 1)
                errors.append((meta_pos, random_8bit_nonzero(rng)))
            elif fault_width == 2:
                # 2-symbol: 2-aligned within metadata
                # Find valid 2-aligned starts in [k, n)
                meta_start_options = [k + i for i in range(0, nsym - 1, 2) if k + i + 1 < n]
                if meta_start_options:
                    meta_start = rng.choice(meta_start_options)
                    for i in range(2):
                        if meta_start + i < n:
                            errors.append((meta_start + i, random_8bit_nonzero(rng)))
            elif fault_width == 4:
                # 4-symbol: 4-aligned within metadata
                # Find valid 4-aligned starts in [k, n)
                meta_start_options = [k + i for i in range(0, nsym - 3, 4) if k + i + 3 < n]
                if meta_start_options:
                    meta_start = rng.choice(meta_start_options)
                    for i in range(4):
                        if meta_start + i < n:
                            errors.append((meta_start + i, random_8bit_nonzero(rng)))
                elif nsym > 0:
                    # Not enough metadata for 4-aligned; apply what we can
                    for i in range(min(fault_width, nsym)):
                        errors.append((k + i, random_8bit_nonzero(rng)))
            else:
                # 5-6 symbol contiguous: apply as much as fits in metadata
                num_meta = min(fault_width, nsym)
                for i in range(num_meta):
                    if k + i < n:
                        errors.append((k + i, random_8bit_nonzero(rng)))
    
    return Fault(fault_type=fault_type, errors=errors)


def apply_fault(codeword: bytearray, fault: Fault) -> None:
    """Apply a fault to a codeword (in-place XOR)."""
    n = len(codeword)
    for pos, pattern in fault.errors:
        if 0 <= pos < n and pattern != 0:
            codeword[pos] ^= pattern


# Default distribution
DEFAULT_FAULT_DISTRIBUTION = FaultDistribution()
