# ECC_model

ECC_model is a CLI tool to evaluate Reed–Solomon (RS) error correction behavior using realistic DRAM fault models.

## Features
- **Fault model mode**: Simulates DRAM subarray faults with configurable distribution
- **Correlated faults**: Models metadata corruption correlated with data faults
- **Random and exhaustive test modes**
- **Native Rust RS codec** via pyo3 (GF(256), Berlekamp-Massey, Chien, Forney)

Supported RS codes: (34,32), (36,32), (68,64), (72,64)

## Requirements
- Python 3.12+
- Rust toolchain: `rustup` + `maturin`

## Quick Start

```bash
# Clone and setup
cd ECC_model
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
pip install -U pip maturin
maturin develop
ecc-model --help
```

## Usage

### Fault model mode (default)
Simulates realistic DRAM fault distribution:
```bash
# Run with default distribution on all RS codes
ecc-model --rs-codes ALL --trials 10000 --csv-out -

# Custom fault distribution: 1bit, 1sym, 2sym, 4sym, other
ecc-model --dist 9000,800,100,50,50 --trials 10000 --csv-out results.csv

# Enable correlated data/metadata faults
ecc-model --correlated --rs-codes 34,32 --trials 10000 --csv-out -
```

### Random mode
Uniform random symbol errors:
```bash
ecc-model --mode random --errors 2 --trials 5000 --csv-out -
```

### Exhaustive mode
All single-symbol error patterns:
```bash
ecc-model --mode exhaustive --rs-codes 34,32 --csv-out results.csv
```

### Enforce contiguous correction spans
Flag decode attempts that report scattered correction locations:
```bash
ecc-model --enforce-contiguous-locations --mode fault-model --trials 5000 --csv-out -
```
When enabled, any decode that reports non-contiguous correction locations is treated as a suspected false correction (counted as silent corruption).

## Fault Distribution

Default distribution (per 10,000 faults):
| Type | Count | Description |
|------|-------|-------------|
| single_bit_1sym | 9000 | 1 symbol, 1 bit flipped |
| 8bit_1sym | 800 | 1 symbol, random 8-bit pattern |
| 8bit_2sym | 100 | 2 contiguous symbols (2-aligned) |
| 8bit_4sym | 50 | 4 contiguous symbols (4-aligned) |
| out_of_model | 50 | 5-6 contiguous or 4+ scattered |

## Project Layout
```
src/ecc_model/
  cli.py          # CLI entrypoint
  core.py         # test harness, counters
  fault_model.py  # DRAM fault distribution model
  rs.py           # codec wrapper
rust/src/
  lib.rs          # pyo3 module
  rs.rs           # RS encode/decode (Berlekamp-Massey)
  gf256.rs        # GF(256) arithmetic
```

## Troubleshooting

- **ModuleNotFoundError: No module named 'ecc_model._rs'**
  Run `maturin develop` in the active venv.

- **Command not found: ecc-model**
  Ensure venv is active. Windows: `.\.venv\Scripts\ecc-model.exe --help`
