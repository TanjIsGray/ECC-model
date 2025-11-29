from __future__ import annotations

import os
import random
import csv
from dataclasses import dataclass, field
from typing import List, Sequence
from .rs import get_codec, DecodeError
from .fault_model import FaultDistribution, generate_fault, apply_fault, DEFAULT_FAULT_DISTRIBUTION


@dataclass(frozen=True)
class RSConfig:
    n: int
    k: int

    @property
    def nsym(self) -> int:
        return self.n - self.k


@dataclass(frozen=True)
class DecodePolicy:
    """Decode-time guardrails."""

    enforce_contiguous_locations: bool = False


@dataclass(frozen=True)
class DecodeOutcome:
    """Result of a decode attempt."""

    corrected: bool | None
    silent: bool = False
    suspect_locations: bool = False


def get_default_rs_configs() -> List[RSConfig]:
    return [
        RSConfig(n=34, k=32),
        RSConfig(n=36, k=32),
        RSConfig(n=68, k=64),
        RSConfig(n=72, k=64),
    ]


@dataclass
class TrialCounters:
    total_trials: int = 0
    corrected_ok: int = 0
    uncorrectable: int = 0
    silent_corruption: int = 0

    def add_corrected(self) -> None:
        self.total_trials += 1
        self.corrected_ok += 1

    def add_uncorrectable(self) -> None:
        self.total_trials += 1
        self.uncorrectable += 1

    def add_silent(self) -> None:
        self.total_trials += 1
        self.silent_corruption += 1

    def to_row(self, config: RSConfig) -> List[str]:
        t = max(self.total_trials, 1)
        corrected_rate = self.corrected_ok / t
        uncorrectable_rate = self.uncorrectable / t
        silent_rate = self.silent_corruption / t
        return [
            str(config.n),
            str(config.k),
            str(config.nsym),
            str(self.total_trials),
            str(self.corrected_ok),
            str(self.uncorrectable),
            str(self.silent_corruption),
            f"{corrected_rate:.6f}",
            f"{uncorrectable_rate:.6f}",
            f"{silent_rate:.6f}",
        ]


@dataclass
class FaultModelCounters:
    """Counters broken down by fault type."""
    total_trials: int = 0
    by_type: dict = field(default_factory=lambda: {
        "single_bit_1sym": TrialCounters(),
        "8bit_1sym": TrialCounters(),
        "8bit_2sym": TrialCounters(),
        "8bit_4sym": TrialCounters(),
        "out_of_model": TrialCounters(),
    })

    def add_result(self, fault_type: str, corrected: bool | None, silent: bool = False) -> None:
        """
        Record a trial result.
        corrected=True: corrected successfully
        corrected=False: uncorrectable
        corrected=None with silent=True: silent corruption
        """
        self.total_trials += 1
        counters = self.by_type.get(fault_type)
        if counters is None:
            return
        if corrected is True:
            counters.add_corrected()
        elif corrected is False:
            counters.add_uncorrectable()
        elif silent:
            counters.add_silent()

    def summary(self) -> dict:
        """Return summary statistics."""
        result = {"total_trials": self.total_trials}
        for fault_type, counters in self.by_type.items():
            t = max(counters.total_trials, 1)
            result[fault_type] = {
                "trials": counters.total_trials,
                "corrected": counters.corrected_ok,
                "uncorrectable": counters.uncorrectable,
                "silent": counters.silent_corruption,
                "corrected_rate": counters.corrected_ok / t,
                "uncorrectable_rate": counters.uncorrectable / t,
                "silent_rate": counters.silent_corruption / t,
            }
        return result

    def to_rows(self, config: RSConfig) -> List[List[str]]:
        """Return CSV rows, one per fault type."""
        rows = []
        for fault_type, counters in self.by_type.items():
            t = max(counters.total_trials, 1)
            rows.append([
                str(config.n),
                str(config.k),
                str(config.nsym),
                fault_type,
                str(counters.total_trials),
                str(counters.corrected_ok),
                str(counters.uncorrectable),
                str(counters.silent_corruption),
                f"{counters.corrected_ok / t:.6f}",
                f"{counters.uncorrectable / t:.6f}",
                f"{counters.silent_corruption / t:.6f}",
            ])
        return rows


def positions_contiguous(positions: Sequence[int]) -> bool:
    """Return True when the provided positions form a contiguous run."""
    if len(positions) < 2:
        return True
    ordered = sorted(positions)
    return all((b - a) == 1 for a, b in zip(ordered, ordered[1:]))


def decode_with_policy(codec, received: bytes, reference: bytes, policy: DecodePolicy) -> DecodeOutcome:
    """
    Decode helper that enforces policy checks before classifying the outcome.
    """
    try:
        decoded, positions = codec.decode(received)
    except DecodeError:
        return DecodeOutcome(corrected=False)
    suspect = policy.enforce_contiguous_locations and not positions_contiguous(positions)
    if suspect:
        return DecodeOutcome(corrected=None, silent=True, suspect_locations=True)
    if decoded == reference:
        return DecodeOutcome(corrected=True)
    return DecodeOutcome(corrected=None, silent=True)


def update_trial_counters(outcome: DecodeOutcome, counters: TrialCounters) -> None:
    """Map a DecodeOutcome into aggregate trial counters."""
    if outcome.corrected is True:
        counters.add_corrected()
    elif outcome.corrected is False:
        counters.add_uncorrectable()
    else:
        counters.add_silent()


def generate_message(k: int, rng: random.Random) -> bytes:
    return rng.randbytes(k) if hasattr(rng, "randbytes") else bytes(rng.getrandbits(8) for _ in range(k))


def apply_xor_faults(mesecc: bytearray, positions: List[int], patterns: List[int]) -> None:
    if len(positions) != len(patterns):
        raise ValueError("positions and patterns must have the same length")
    n = len(mesecc)
    for pos, pat in zip(positions, patterns):
        if pos < 0 or pos >= n:
            raise ValueError(f"fault position {pos} out of range 0..{n-1}")
        if pat == 0:
            # No-op faults are not meaningful; enforce non-zero XOR
            raise ValueError("fault pattern must be non-zero (1..255)")
        mesecc[pos] ^= (pat & 0xFF)


def choose_random_positions(n: int, count: int, rng: random.Random) -> List[int]:
    count = max(0, min(count, n))
    # unique positions within full codeword (data + ecc)
    return rng.sample(range(n), count)


def choose_random_patterns(count: int, rng: random.Random) -> List[int]:
    # choose non-zero XOR patterns
    return [rng.randrange(1, 256) for _ in range(count)]


def run_random_trials(
    config: RSConfig,
    trials: int,
    seed: int | None,
    num_errors: int = 1,
    reuse_every: int = 13,
    decode_policy: DecodePolicy | None = None,
) -> TrialCounters:
    rng = random.Random(seed)
    counters = TrialCounters()
    codec = get_codec(nsym=config.nsym, nsize=config.n)
    policy = decode_policy or DecodePolicy()

    # Reuse underlying message (and base encoded codeword) to reduce overhead
    base_message: bytes | None = None
    base_codeword: bytes | None = None

    for i in range(trials):
        if base_message is None or base_codeword is None or (reuse_every > 0 and (i % reuse_every) == 0):
            base_message = generate_message(config.k, rng)
            base_codeword = codec.encode(base_message)
        mesecc = bytearray(base_codeword)

        positions = choose_random_positions(config.n, num_errors, rng)
        patterns = choose_random_patterns(len(positions), rng)
        apply_xor_faults(mesecc, positions, patterns)

        assert base_message is not None
        outcome = decode_with_policy(codec, bytes(mesecc), base_message, policy)
        update_trial_counters(outcome, counters)
    return counters


def run_exhaustive_single_symbol(
    config: RSConfig,
    seed: int | None = None,
    decode_policy: DecodePolicy | None = None,
) -> TrialCounters:
    counters = TrialCounters()
    codec = get_codec(nsym=config.nsym, nsize=config.n)
    policy = decode_policy or DecodePolicy()
    # Use a random (but fixed-for-run) message in exhaustive mode
    rng = random.Random(seed)
    message = generate_message(config.k, rng)
    base_codeword = codec.encode(message)

    # Iterate all positions and all non-zero XOR patterns
    for pos in range(config.n):
        for pat in range(1, 256):
            arr = bytearray(base_codeword)
            arr[pos] ^= pat
            mutated = bytes(arr)
            outcome = decode_with_policy(codec, mutated, message, policy)
            update_trial_counters(outcome, counters)
    return counters


def run_fault_model_trials(
    config: RSConfig,
    trials: int,
    seed: int | None,
    dist: FaultDistribution | None = None,
    reuse_every: int = 13,
    correlated: bool = False,
    decode_policy: DecodePolicy | None = None,
) -> FaultModelCounters:
    """
    Run trials using the DRAM subarray fault model.
    
    Args:
        config: RS code configuration
        trials: Number of trials to run
        seed: PRNG seed (None for random)
        dist: Fault distribution (None for default)
        reuse_every: Regenerate message every N trials
        correlated: Enable correlated data/metadata faults
        decode_policy: Optional guardrails for interpreting decoder output
    
    Returns:
        FaultModelCounters with results broken down by fault type
    """
    if dist is None:
        dist = DEFAULT_FAULT_DISTRIBUTION
    
    rng = random.Random(seed)
    counters = FaultModelCounters()
    codec = get_codec(nsym=config.nsym, nsize=config.n)
    policy = decode_policy or DecodePolicy()
    
    base_message: bytes | None = None
    base_codeword: bytes | None = None
    
    for i in range(trials):
        # Periodically regenerate message
        if base_message is None or base_codeword is None or (reuse_every > 0 and (i % reuse_every) == 0):
            base_message = generate_message(config.k, rng)
            base_codeword = codec.encode(base_message)
        
        # Generate and apply fault
        fault = generate_fault(config.n, config.k, dist, rng, correlated=correlated)
        mesecc = bytearray(base_codeword)
        apply_fault(mesecc, fault)
        
        # Decode and record result
        assert base_message is not None
        outcome = decode_with_policy(codec, bytes(mesecc), base_message, policy)
        if outcome.corrected is True:
            counters.add_result(fault.fault_type, corrected=True)
        elif outcome.corrected is False:
            counters.add_result(fault.fault_type, corrected=False)
        else:
            counters.add_result(fault.fault_type, corrected=None, silent=outcome.silent or outcome.suspect_locations)
    
    return counters


def write_csv(rows: List[List[str]], out_path: str) -> None:
    headers = [
        "n","k","nsym","trials","corrected","uncorrected","silent",
        "corrected_rate","uncorrected_rate","silent_rate",
    ]
    if out_path == "-":
        writer = csv.writer(os.sys.stdout)
        writer.writerow(headers)
        writer.writerows(rows)
        return
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def write_fault_model_csv(rows: List[List[str]], out_path: str) -> None:
    headers = [
        "n","k","nsym","fault_type","trials","corrected","uncorrected","silent",
        "corrected_rate","uncorrected_rate","silent_rate",
    ]
    if out_path == "-":
        writer = csv.writer(os.sys.stdout)
        writer.writerow(headers)
        writer.writerows(rows)
        return
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
