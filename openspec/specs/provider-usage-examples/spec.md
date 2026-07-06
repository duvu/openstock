## ADDED Requirements

### Requirement: Examples directory exists with provider scripts

The repository SHALL contain an `examples/` directory at the repo root with one Python script per data provider and an index README.

#### Scenario: Examples directory present
- **WHEN** a user clones the repository
- **THEN** the `examples/` directory exists with at least one `.py` file per supported provider

#### Scenario: Index README present
- **WHEN** a user opens `examples/README.md`
- **THEN** they see a table listing each provider, its script, credential requirements, and available methods

---

### Requirement: Each provider script is self-contained and runnable

Each `examples/<provider>_example.py` SHALL run to completion with `python examples/<provider>_example.py` using only the installed `vnstock` package.

#### Scenario: Script runs without error
- **WHEN** the script is executed from the repo root with a valid Python environment
- **THEN** it prints section headers and DataFrame output for each method call without raising an unhandled exception

#### Scenario: Single method failure does not abort script
- **WHEN** one API endpoint returns an error or rate-limit response
- **THEN** the script prints the error message and continues to the next method call

---

### Requirement: KBS provider example covers all public methods

The `examples/kbs_example.py` script SHALL demonstrate: `Quote.history()`, `Quote.intraday()`, `Trading.price_board()`, `Listing.all_symbols()`, `Listing.symbols_by_industries()`, `Company.overview()`, `Company.shareholders()`, `Finance.balance_sheet()`, `Finance.income_statement()`, `Finance.cash_flow()`, `Finance.ratio()`.

#### Scenario: History call returns OHLCV DataFrame
- **WHEN** `Quote("FPT").history(start="2024-01-01", end="2024-06-30")` is called
- **THEN** the returned DataFrame has columns `time, open, high, low, close, volume`

#### Scenario: Price board call returns multi-symbol DataFrame
- **WHEN** `Trading().price_board(["FPT", "VCB", "TCB"])` is called
- **THEN** the returned DataFrame contains at least one row per symbol

---

### Requirement: VCI provider example covers all public methods

The `examples/vci_example.py` script SHALL demonstrate: `Quote.history()`, `Quote.intraday()`, `Trading.price_board()`, `Listing.all_symbols()`, `Listing.symbols_by_industries()`, `Company.overview()`, `Company.shareholders()`, `Finance.balance_sheet()`, `Finance.income_statement()`, `Finance.cash_flow()`, `Finance.ratio()`.

#### Scenario: VCI history uses source=vci
- **WHEN** `Quote("FPT", source="vci").history(...)` is called
- **THEN** data is fetched from VCI endpoint and returned as OHLCV DataFrame

#### Scenario: VCI intraday demo
- **WHEN** `Quote("FPT", source="vci").intraday()` is called
- **THEN** output is either a DataFrame of intraday trades or a handled session-boundary error

---

### Requirement: DNSE provider example covers all public methods

The `examples/dnse_example.py` script SHALL demonstrate: `Quote.history()`, `Quote.intraday()`, `Trading.price_board()`.

#### Scenario: DNSE history returns OHLCV
- **WHEN** `Quote("FPT", source="dnse").history(start="2024-01-01", end="2024-06-30")` is called
- **THEN** a DataFrame with OHLCV columns is returned

---

### Requirement: MSN provider example covers all public methods

The `examples/msn_example.py` script SHALL demonstrate: `Quote.history()`, `Listing.search_symbol()`, `Listing.info()`.

#### Scenario: MSN quote uses symbol_id
- **WHEN** MSN quote history is called
- **THEN** script resolves `symbol_id` from `Listing.search_symbol()` before calling `Quote.history()`

---

### Requirement: TCBS provider example covers all public methods

The `examples/tcbs_example.py` script SHALL demonstrate: `Quote.history()`, `Quote.intraday()` (labeled experimental), `Trading.price_board()`, `Listing.all_symbols()`, `Listing.symbol_industry()`, `Company.overview()`, `Company.shareholders()`, `Company.dividends()`, `Finance.balance_sheet()`, `Finance.income_statement()`, `Finance.cash_flow()`, `Finance.ratio()`, `Screener.scan()` (labeled experimental).

#### Scenario: TCBS history 3-endpoint fallback demonstrated
- **WHEN** `Quote("FPT", source="tcbs").history(...)` is called
- **THEN** script prints which endpoint responded

#### Scenario: Screener scan demo
- **WHEN** `Screener().scan(filters={})` is called
- **THEN** a DataFrame of stock symbols matching the criteria is returned

---

### Requirement: FMP provider example covers all public methods

The `examples/fmp_example.py` script SHALL demonstrate: `Quote.history()`, `Quote.intraday()`, `Quote.full()`. The script SHALL check for `FMP_API_KEY` env var and print a clear message if missing.

#### Scenario: Missing API key handled gracefully
- **WHEN** `FMP_API_KEY` is not set in the environment
- **THEN** the script prints a setup message and exits cleanly without traceback

#### Scenario: FMP history demo
- **WHEN** `FMP_API_KEY` is set and `Quote("FPT", source="fmp").history(...)` is called
- **THEN** an OHLCV DataFrame is returned

---

### Requirement: FMarket provider example covers all public methods

The `examples/fmarket_example.py` script SHALL demonstrate: `Fund.listing()`, `Fund.filter()`, `Fund.nav_report()`, `Fund.top_holding()`, `Fund.industry_holding()`, `Fund.asset_holding()`.

#### Scenario: Fund listing returns DataFrame
- **WHEN** `Fund().listing()` is called
- **THEN** a DataFrame of fund names, codes, and metadata is returned

#### Scenario: NAV report for a specific fund
- **WHEN** `Fund().nav_report(symbol="SSIAM-VNX50")` is called
- **THEN** a DataFrame of NAV history is returned
