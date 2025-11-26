## ECC_model — Status and Next Steps

### Summary
- XOR fault injection at selectable positions (supports multiple errors).
- Random mode with message reuse (default every 13 trials) to reduce overhead.
- Exhaustive single‑error mode iterates all positions × 255 non‑zero patterns.
- Correction positions exposed via a unified codec API (Rust pyo3 extension).
- CLI flags:
  - `--errors`, `--reuse-every`, `--mode {random|exhaustive}`, `--rs-codes`, `--trials`, `--seed`, `--csv-out`.

### Quickstart
1) Python setup
   - Create/activate venv, then:
   - `pip install -U pip`
   - `pip install maturin`
   - `maturin develop -m rust/Cargo.toml`
   - `pip install -e .`
2) Run
   - `ecc-model --mode random --trials 1000 --csv-out -`

### Notes
- If `pip install -e .` fails with TOML parse errors, ensure `pyproject.toml` is UTF‑8 without BOM.

### Next Steps (proposed)
- Implement native Rust RS (GF(256) tables, Berlekamp–Massey, Chien, Forney) returning true error locations.
- Add policy engine:
  - Penalize/flag contiguous burst patterns (lengths 1/2/4) aligned to multiples of those lengths.
  - Tune to reduce silent errors on real‑world fault distributions.
- Add burst injectors:
  - Deterministic: `--positions`, `--patterns`
  - Patterned: `--burst {1|2|4}`, `--stride {1|2|4}`, `--start-align`
- Reporting:
  - Output corrected positions per trial (optional CSV/JSON stream mode).
  - Summaries per burst length/alignment.
- Tests/Benchmarks:
  - Unit tests for codec and policy logic.
  - Perf benchmarks across (n,k) configurations.

### Key Files
- `src/ecc_model/core.py` — harness, counters, injection logic
- `src/ecc_model/rs.py` — codec factory (Rust)
- `src/ecc_model/cli.py` — CLI entry
- `rust/` — pyo3 module `ecc_model._rs`
