# Tasks: Watchlist Synthesis and Shortlist

## 0. Governance

- [x] 0.1 Keep shortlist output research-only.
- [x] 0.2 Do not frame shortlist as buy/sell/order/allocation instruction.
- [x] 0.3 Include reason restrained and caveats for shortlisted names.

## 1. Models and persistence

- [x] 1.1 Add watchlist synthesis artifact contract.
- [x] 1.2 Add shortlist run model.
- [x] 1.3 Add shortlist candidate model or reuse shared model foundation.
- [x] 1.4 Persist shortlist run metadata.
- [x] 1.5 Persist shortlist candidate rows.

## 2. Synthesis engine

- [x] 2.1 Compute class distribution.
- [x] 2.2 Compute setup distribution.
- [x] 2.3 Compute sector clustering.
- [x] 2.4 Identify strongest names.
- [x] 2.5 Identify near-confirmation names.
- [x] 2.6 Identify extended names.
- [x] 2.7 Identify risk-flagged names.
- [x] 2.8 Generate next-session research focus.

## 3. Shortlist engine

- [x] 3.1 Build deterministic shortlist score.
- [x] 3.2 Attach setup quality.
- [x] 3.3 Attach sector/regime alignment when available.
- [x] 3.4 Attach confirmation and invalidation conditions.
- [x] 3.5 Attach why-shortlisted and why-restrained fields.
- [x] 3.6 Attach data quality and risk context.

## 4. Commands and assistant

- [x] 4.1 Add `/watchlist-summary`.
- [x] 4.2 Add `/shortlist`.
- [x] 4.3 Add `watchlist.summarize_deep` tool.
- [x] 4.4 Add `shortlist.generate` tool.
- [x] 4.5 Add assistant intents and synthesis templates.

## 5. Tests and validation

- [x] 5.1 Test summary distributions.
- [x] 5.2 Test shortlist deterministic ordering.
- [x] 5.3 Test reason/restrained fields exist.
- [x] 5.4 Test no execution language.
- [x] 5.5 Run standard validation commands and attach evidence.
