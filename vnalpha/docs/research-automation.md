# Research automation

OpenStock research automation turns persisted Vietnamese equity data into reproducible evidence artifacts. It does not place orders, connect to brokers or accounts, manage portfolios, allocate capital, or provide personalized financial advice.

## Commands

```text
/feature create rs_20 = rs_20d_vs_vnindex --universe VN30
/feature validate rs_20
/experiment indicator relative strength 20 sessions vs VNINDEX --universe VN30
/pattern scan accumulation base with volatility contraction and volume dry-up --universe VN30
/hypothesis test symbols with positive rs_20 have better 20-session return
/experiment backtest FPT accumulation breakout --horizon 10
```

`/experiment backtest` is only a convenient command name. Its output is always labeled an **offline research event study**. It uses persisted warehouse data and never reads live broker, account, order, margin, transfer, allocation, or portfolio state.

## Execution boundary

The MVP workflows use approved deterministic research tools over `feature_snapshot`. They do not generate or execute arbitrary code. If a future workflow requires generated code, it must create an approval-gated sandbox job; execution cannot begin until the exact code digest, input references, image digest, and resource policy are approved.

Feature definitions containing future/forward fields, `lead(...)`, broker operations, orders, or live execution actions are rejected. Event-study requests that ask to deploy or automate trades are also rejected.

## Artifact layout

Each run writes metadata to DuckDB and files under:

```text
logs/runs/<run-id>/research/<artifact-id>/
  manifest.json
  result.json
  summary.md
  lineage.json
  validation.json
  reproducibility_manifest.json
  metrics.csv       # experiments, hypotheses, event studies
  candidates.csv    # pattern scans
```

The metadata includes the correlation ID, dataset snapshot reference, symbols, date coverage, row count, quality status, parameters, metrics, lineage, and physical output paths.

## Interpretation and caveats

Outputs are historical evidence, not recommendations. Depending on the workflow, the summary records:

- sample size and period coverage;
- incomplete or low-quality dataset warnings;
- possible lookahead and survivorship bias;
- transaction-cost exclusion;
- research-only status.

Insufficient warehouse coverage produces a warning and a rejected/partial artifact instead of claiming a successful result. Fresh warehouse and deterministic tool output remains authoritative over model prose.

## Natural-language planning

The assistant recognizes indicator experiments, feature creation/validation, hypothesis tests, pattern scans, and offline event studies. Its deterministic preview lists dataset resolution, generated-code status, expected artifacts, and caveats before execution. Requests implying live trading are refused.
