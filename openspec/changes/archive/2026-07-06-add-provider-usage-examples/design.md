## Context

vnstock has 7 distinct data providers (KBS, VCI, DNSE, MSN, FMP, TCBS, FMarket) each with different capabilities, constructor signatures, and method names. Currently, no runnable examples exist in the repo. Users must read scattered source files and docstrings to discover how to call each provider. The `examples/` directory does not exist.

## Goals / Non-Goals

**Goals:**
- Create a standalone `examples/` directory with one Python script per provider
- Each script runs end-to-end against the real API and prints/returns actual data
- Cover every registered provider type and method exposed by that provider
- Include a top-level `examples/README.md` as an index
- Use only `vnstock`'s own public API (no internal imports)

**Non-Goals:**
- Jupyter notebooks (plain `.py` scripts only — easier to run and diff)
- Automated testing of the examples (they call live APIs)
- Mocked/offline examples
- Coverage of broker, account, or order APIs (not in this package)
- Tutorial-style prose documentation

## Decisions

### Directory structure: flat scripts per provider

Each provider gets one self-contained script: `examples/<provider>_example.py`. A flat layout is simpler to navigate than per-provider subdirectories. The `examples/README.md` acts as the index.

**Alternative considered**: Jupyter notebooks. Rejected — notebooks are harder to review in PRs, require extra dependencies (`jupyter`), and don't run in CI.

### Script structure: runnable `if __name__ == "__main__"` block

Each script uses a `main()` function called from `if __name__ == "__main__"`, making it both importable and directly runnable. Each method call is wrapped in its own try/except so one failing endpoint doesn't abort the whole demo.

**Alternative**: One giant demo script. Rejected — users typically want examples for one provider at a time.

### Default symbols: `FPT`, `VCB`, `TCB`

These are liquid, large-cap symbols present on all exchanges and in all providers. Consistent across scripts so users can compare output.

### FMP requires env var `FMP_API_KEY`

The FMP script checks for the env var and prints a clear message if missing, rather than crashing. Other providers (KBS, VCI, DNSE, MSN, TCBS) are open/guest-accessible.

### FMarket uses `Fund` class directly

`vnstock.explorer.fmarket.Fund` is not routed through the Unified UI (it's a standalone fund data explorer). The example imports it directly, consistent with how it's used in practice.

### Output format: `print()` with section headers

Scripts print labeled section headers and `df.head()` / `df.to_string()` to stdout. No plotting, no file writes.

## Risks / Trade-offs

- **API rate limits** → Each script calls at most ~5 endpoints; guest rate limits are 20 req/min which is sufficient for a single provider demo run
- **API drift** → Example scripts may break if provider endpoints change; mitigated by try/except per call and the existing drift-detection framework
- **TCBS intraday is experimental** → Annotated with a comment in the script

## Migration Plan

No migration needed — purely additive new directory. No existing code changes.
