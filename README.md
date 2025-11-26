# ECC_model

ECC_model is a small CLI and library to evaluate Reed–Solomon (RS) error correction behavior on realistic fault patterns.

It supports:
- Random and exhaustive test modes
- XOR-based fault injection at selectable positions (1+ error symbols)
- Message reuse to reduce encode overhead
- Reporting of corrected symbol positions

Tested RS codes:
- (34,32), (36,32), (68,64), (72,64)

## Requirements
- Python 3.12+
- Windows, macOS, or Linux
- Rust toolchain: `rustup` + `maturin`

## Quick Start

Windows CMD:
```bat
cd C:\path\to\ECC_model
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -U pip
pip install maturin
maturin develop -m rust/Cargo.toml
pip install -e .
ecc-model --help
```

Windows PowerShell:
```powershell
cd C:\path\to\ECC_model
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install maturin
maturin develop -m rust/Cargo.toml
pip install -e .
ecc-model --help
```

macOS/Linux:
```bash
cd /path/to/ECC_model
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install maturin
maturin develop -m rust/Cargo.toml
pip install -e .
ecc-model --help
```

If `ecc-model` is not found, try:
```bat
where ecc-model
.\.venv\Scripts\ecc-model.exe --help
```

## Usage examples

- Random mode, default 1 error per trial:
```bash
ecc-model --mode random --trials 10000 --csv-out -
```

- Random mode with multiple errors and message reuse:
```bash
ecc-model --mode random --errors 3 --reuse-every 13 --trials 5000 --csv-out -
```

- Exhaustive single-error over all positions and 255 non-zero patterns:
```bash
ecc-model --mode exhaustive --csv-out results.csv
```

- Select RS codes to evaluate:
```bash
ecc-model --rs-codes 34,32 --rs-codes 68,64 --mode random --trials 2000 --csv-out -
```

## Project layout
```
src/ecc_model/
  cli.py        # CLI entrypoint
  core.py       # test harness, counters, injection logic
  rs.py         # codec factory (Rust-backed)
rust/
  Cargo.toml
  src/lib.rs    # pyo3 module exporting encode/decode with correction indices
pyproject.toml  # package metadata
```

## Troubleshooting

- ModuleNotFoundError: No module named 'ecc_model._rs'
  - Build the Rust extension via `maturin develop -m rust/Cargo.toml` in the active venv.

- Command not found: ecc-model
  - Ensure your venv is active. On Windows, try `.\.venv\Scripts\ecc-model.exe --help`.

## Notes on error patterns and policies
The harness injects XOR faults at arbitrary codeword positions (data+ECC). You can explore policies aimed at real‑world contiguous bursts (lengths 1, 2, 4) aligned to multiples of those lengths by using multi‑error random injections and, later, custom injectors or filters over corrected positions.
