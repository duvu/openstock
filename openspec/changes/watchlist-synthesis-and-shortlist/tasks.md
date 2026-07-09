# Tasks: Watchlist Synthesis and Shortlist

## 0. Governance

- [ ] 0.1 Keep shortlist output research-only.
- [ ] 0.2 Do not frame shortlist as buy/sell/order/allocation instruction.
- [ ] 0.3 Include reason restrained and caveats for shortlisted names.

## 1. Models and persistence

- [ ] 1.1 Add watchlist synthesis artifact contract.
- [ ] 1.2 Add shortlist run model.
- [ ] 1.3 Add shortlist candidate model or reuse shared model foundation.
- [ ] 1.4 Persist shortlist run metadata.
- [ ] 1.5 Persist shortlist candidate rows.

## 2. Synthesis engine

- [ ] 2.1 Compute class distribution.
- [ ] 2.2 Compute setup distribution.
- [ ] 2.3 Compute sector clustering.
- [ ] 2.4 Identify strongest names.
- [ ] 2.5 Identify near-confirmation names.
- [ ] 2.6 Identify extended names.
- [ ] 2.7 Identify risk-flagged names.
- [ ] 2.8 Generate next-session research focus.

## 3. Shortlist engine

- [ ] 3.1 Build deterministic shortlist score.
- [ ] 3.2 Attach setup quality.
- [ ] 3.3 Attach sector/regime alignment when available.
- [ ] 3.4 Attach confirmation and invalidation conditions.
- [ ] 3.5 Attach why-shortlisted and why-restrained fields.
- [ ] 3.6 Attach data quality and risk context.

## 4. Commands and assistant

- [ ] 4.1 Add `/watchlist-summary`.
- [ ] 4.2 Add `/shortlist`.
- [ ] 4.3 Add `watchlist.summarize_deep` tool.
- [ ] 4.4 Add `shortlist.generate` tool.
- [ ] 4.5 Add assistant intents and synthesis templates.

## 5. Tests and validation

- [ ] 5.1 Test summary distributions.
- [ ] 5.2 Test shortlist deterministic ordering.
- [ ] 5.3 Test reason/restrained fields exist.
- [ ] 5.4 Test no execution language.
- [ ] 5.5 Run standard validation commands and attach evidence.
