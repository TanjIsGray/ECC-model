## ECC_model — Status

### Implemented
- Native Rust RS codec (GF(256), Berlekamp-Massey, Chien search, Forney algorithm)
- DRAM subarray fault model with configurable distribution
- Correlated data/metadata faults (probability = nsym/k)
- Three test modes: fault-model (default), random, exhaustive
- CSV output with per-fault-type breakdown

### CLI Flags
- `--mode {fault-model|random|exhaustive}` — test mode
- `--dist 1BIT,1SYM,2SYM,4SYM,OTHER` — fault distribution counts
- `--correlated` — enable correlated metadata faults
- `--rs-codes {34,32|36,32|68,64|72,64|ALL}` — RS codes to test
- `--trials N` — number of trials
- `--seed N` — PRNG seed
- `--csv-out PATH` — output file (- for stdout)

### Fault Types
| Name | Description |
|------|-------------|
| single_bit_1sym | 1 bit flip in 1 symbol |
| 8bit_1sym | Random 8-bit pattern in 1 symbol |
| 8bit_2sym | 2 contiguous symbols, 2-aligned |
| 8bit_4sym | 4 contiguous symbols, 4-aligned |
| out_of_model | 5-6 contiguous or 4+ scattered |

### Key Files
- `src/ecc_model/cli.py` — CLI entry
- `src/ecc_model/core.py` — test harness, counters
- `src/ecc_model/fault_model.py` — fault distribution and generation
- `src/ecc_model/rs.py` — codec wrapper
- `rust/src/rs.rs` — RS encode/decode
- `rust/src/gf256.rs` — GF(256) arithmetic
