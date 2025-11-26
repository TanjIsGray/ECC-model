import argparse
import sys
from typing import List, Optional
from .core import (
    RSConfig,
    get_default_rs_configs,
    run_random_trials,
    run_exhaustive_single_symbol,
    run_fault_model_trials,
    write_csv,
    write_fault_model_csv,
)
from .fault_model import FaultDistribution


def parse_dist(value: str) -> FaultDistribution:
    """Parse distribution string: '9000,800,100,50,50' -> FaultDistribution."""
    parts = value.split(",")
    if len(parts) != 5:
        raise argparse.ArgumentTypeError(
            f"--dist requires exactly 5 comma-separated integers: 1bit,1sym,2sym,4sym,other (got {len(parts)})"
        )
    try:
        values = tuple(int(p.strip()) for p in parts)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"--dist values must be integers: {e}")
    return FaultDistribution.from_tuple(values)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ecc-model",
        description="ECC_model: RS error correction simulation with realistic fault models",
    )
    parser.add_argument(
        "--mode",
        choices=["random", "exhaustive", "fault-model"],
        default="fault-model",
        help="random: uniform random faults; exhaustive: all single-symbol patterns; fault-model: DRAM subarray fault distribution",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=10000,
        help="Number of trials (ignored by exhaustive mode)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="PRNG seed",
    )
    parser.add_argument(
        "--errors",
        type=int,
        default=1,
        help="Number of error symbols per trial (random mode only)",
    )
    parser.add_argument(
        "--reuse-every",
        type=int,
        default=13,
        help="Reuse message for this many trials to reduce overhead",
    )
    parser.add_argument(
        "--csv-out",
        default="-",
        help="Output CSV path or - for stdout",
    )
    parser.add_argument(
        "--rs-codes",
        action="append",
        choices=["34,32", "36,32", "68,64", "72,64"],
        help="Restrict to specific codes; may be provided multiple times. Default: all",
    )
    parser.add_argument(
        "--dist",
        type=parse_dist,
        default=None,
        metavar="1BIT,1SYM,2SYM,4SYM,OTHER",
        help="Fault distribution as 5 comma-separated counts: "
             "single-bit-1sym, random-8bit-1sym, random-8bit-2sym, random-8bit-4sym, out-of-model. "
             "Default: 9000,800,100,50,50",
    )
    return parser


def parse_rs_selection(args) -> List[RSConfig]:
    all_cfgs = get_default_rs_configs()
    if not args.rs_codes:
        return all_cfgs
    selected = set(args.rs_codes)
    mapping = {f"{c.n},{c.k}": c for c in all_cfgs}
    return [mapping[key] for key in [*selected] if key in mapping]


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    configs = parse_rs_selection(args)

    if args.mode == "fault-model":
        dist = args.dist if args.dist is not None else FaultDistribution()
        
        # Print distribution summary to stderr so it doesn't interfere with CSV on stdout
        dist.print_summary(file=sys.stderr)
        
        rows: List[List[str]] = []
        for cfg in configs:
            counters = run_fault_model_trials(
                cfg,
                trials=args.trials,
                seed=args.seed,
                dist=dist,
                reuse_every=max(1, args.reuse_every),
            )
            rows.extend(counters.to_rows(cfg))
        write_fault_model_csv(rows, args.csv_out)
    else:
        rows = []
        for cfg in configs:
            if args.mode == "random":
                counters = run_random_trials(
                    cfg,
                    trials=args.trials,
                    seed=args.seed,
                    num_errors=max(1, args.errors),
                    reuse_every=max(1, args.reuse_every),
                )
            else:  # exhaustive
                if args.errors != 1:
                    raise SystemExit("exhaustive mode supports only --errors=1")
                counters = run_exhaustive_single_symbol(cfg, seed=args.seed)
            rows.append(counters.to_row(cfg))
        write_csv(rows, args.csv_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
