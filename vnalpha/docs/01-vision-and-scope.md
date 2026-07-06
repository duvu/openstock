# 01. Vision and scope

## Product name

The project name is **vnalpha**.

## Vision

`vnalpha` is an AI-assisted research operating system for Vietnamese equities. Its first mission is to detect, score, validate, and explain technical price/volume patterns in a consistent and auditable way.

The system should help answer questions such as:

- Which stocks are building constructive accumulation bases?
- Which stocks are breaking out with real volume confirmation?
- Which stocks are stronger than VN-Index and their own sector?
- Which breakouts are failing?
- Which detected patterns historically produced positive forward returns?
- Which signals should be downgraded because of market regime, weak liquidity, or poor data quality?

## Non-goals

The MVP must not implement:

- automated order placement;
- broker login or account access;
- portfolio execution;
- intraday high-frequency trading;
- LLM-based direct buy/sell decisions;
- investment advice or recommendation claims;
- production trading based on unofficial or unlicensed data feeds.

## Core design principles

### 1. Data first

Every signal must be traceable to validated market data.

A pattern produced from unknown, unvalidated, or unaudited data should not enter the watchlist.

### 2. Rule engine before AI

The core pattern detector must be deterministic and testable. AI should explain and critique signals; it should not generate the raw trading signal.

### 3. Every pattern needs an outcome

A detected pattern is not useful until the system tracks what happened next.

For every pattern instance, the system should evaluate forward outcomes after 5, 10, 20, and 60 trading sessions.

### 4. Detect failures, not only attractive setups

The system must detect failed breakouts and invalidated patterns. This is essential for improving signal quality and reducing false positives.

### 5. Market regime matters

A breakout setup in an uptrend is not equivalent to the same setup in a downtrend. Market regime should adjust scores and risk flags.

### 6. AI is an analyst layer

LLMs are useful for:

- explaining pattern evidence;
- producing risk critiques;
- summarizing daily market conditions;
- comparing current setups with historical outcomes;
- writing journal notes;
- helping the user query research data in natural language.

LLMs should not override risk controls or generate unverified price predictions.

## MVP definition

The first MVP should include:

1. end-of-day data ingestion;
2. `vnstock` adapter integration;
3. data quality gating;
4. canonical OHLCV store;
5. feature computation;
6. market regime classification;
7. detection of three initial patterns:
   - accumulation base;
   - breakout confirmation;
   - failed breakout;
8. pattern scoring;
9. forward outcome tracking;
10. Streamlit dashboard;
11. AI explanation and risk critique.

## Success criteria

MVP is successful when it can:

- scan a defined Vietnamese equity universe end-of-day;
- generate a daily watchlist with traceable features and quality status;
- show pattern detail with chart context and invalidation level;
- track outcomes after 5/10/20 sessions;
- report false breakout rate and excess return versus VN-Index;
- explain each selected pattern in Vietnamese;
- keep AI outside the deterministic signal-generation path.
