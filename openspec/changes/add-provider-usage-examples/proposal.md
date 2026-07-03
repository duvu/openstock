## Why

vnstock now supports multiple data providers (KBS, VCI, DNSE, MSN, FMP, TCBS, FMarket) but has no runnable example code showing how to actually use each one. New users must read scattered docstrings and source code to discover what each provider offers and how to call it — a poor first experience that increases support load.

## What Changes

- Add an `examples/` directory at the repo root containing provider-specific Jupyter notebooks and/or Python scripts
- Each example file demonstrates a complete, runnable workflow for one provider: authentication/setup (if needed), OHLCV history, price board / real-time quotes, company info, financial data, and any provider-unique features (screener, fund data, etc.)
- A top-level `examples/README.md` index links all examples, shows quick-start one-liners, and notes which providers require credentials
- Docstring cross-references from key provider classes point to the example files

## Capabilities

### New Capabilities

- `provider-usage-examples`: Runnable Python scripts/notebooks in `examples/` covering every provider with real-data calls, including output samples and inline comments explaining each step

### Modified Capabilities

## Impact

- New `examples/` directory (no changes to package source)
- Providers covered: KBS, VCI, DNSE, MSN, FMP, TCBS, FMarket (misc/fmarket)
- No new dependencies; examples use only the installed `vnstock` package
- FMP examples require `FMP_API_KEY` env var; all others are open/guest-accessible
- `README.md` gets a small "Examples" section linking to the directory
