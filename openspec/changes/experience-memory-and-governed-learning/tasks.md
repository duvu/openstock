# Tasks: Experience memory and governed learning

A checked task requires the named code, focused tests and exact-SHA evidence. Issue/PR prose alone is not evidence.

## 0. Spec gate

- [ ] Validate this change strictly and attach exact command/result/environment evidence.
- [ ] Confirm no overlap or contradiction with active queue, data-coverage, outcomes, replay and portfolio changes.
- [ ] Keep the read-only research and no-autonomous-promotion boundaries explicit.

## 1. Experience ledger foundation

- [ ] Add append-oriented migrations for `research_episode`, `prediction_record` and `decision_feedback`.
- [ ] Add typed models and repositories with immutable insert semantics.
- [ ] Add deterministic episode identity/hash and bounded JSON fields.
- [ ] Add current-symbol/watchlist adapters that reference exact artifact and policy versions.
- [ ] Ensure `ACCEPTED`/`PENDING` operational episodes create no market prediction.
- [ ] Test duplicate/idempotent insertion, invalid lineage, correction feedback and immutable history.

## 2. Prediction contracts

- [ ] Register the finite initial prediction-type vocabulary.
- [ ] Implement deterministic adapters from candidate, typed current-symbol and portfolio artifacts.
- [ ] Persist target definition, horizon, benchmark, policy and evidence references.
- [ ] Prohibit prediction extraction from rendered LLM prose.
- [ ] Test score-versus-probability separation and unsupported prediction rejection.

## 3. Feedback and outcome linkage

- [ ] Persist explicit feedback with source and typed feedback kind.
- [ ] Keep user feedback separate from market outcome tables and evaluation labels.
- [ ] Link candidate outcomes to predictions by exact subject/date/horizon/benchmark/policy lineage.
- [ ] Add portfolio outcome linkage only when portfolio artifacts exist.
- [ ] Persist stable unlinked/ambiguous reason codes.
- [ ] Preserve linkage revision history when source outcomes are invalidated.
- [ ] Test exact match, ambiguous match, revised outcome, missing horizon and idempotent relinking.

## 4. Evaluation runs

- [ ] Add immutable `evaluation_run` storage and typed result models.
- [ ] Implement count/coverage, hit rate, realized/excess return, drawdown and favorable-excursion metrics.
- [ ] Add score/confidence calibration buckets without interpreting raw scores as probabilities.
- [ ] Add policy/setup/regime/sector/horizon slices with sample counts.
- [ ] Add turnover and cost-adjusted metrics where the source artifact supports them.
- [ ] Add drift comparison against a prior accepted evaluation window.
- [ ] Fail closed or report `INSUFFICIENT_SAMPLE` when configured minimum evidence is absent.
- [ ] Test point-in-time exclusion, cost model versioning, slice consistency and immutable reruns.

## 5. Learning candidates

- [ ] Add immutable `learning_candidate` models/repository.
- [ ] Support initial explainable candidate types: threshold, weight, constraint and regime-rule changes.
- [ ] Require parent policy/version, experiment specification and exact evaluation references.
- [ ] Allow LLM-assisted rationale only as non-authoritative proposal text.
- [ ] Test missing-parent, unsupported candidate type, duplicate candidate hash and adverse-evidence preservation.

## 6. Governed policy lifecycle

- [ ] Add immutable `policy_version` records and lifecycle validation.
- [ ] Support `DRAFT`, `EXPERIMENTAL`, `ACCEPTED`, `RETIRED`, `REJECTED`.
- [ ] Require reproducible replay/walk-forward/challenger evidence before acceptance.
- [ ] Require explicit approval reference for promotion.
- [ ] Keep the prior accepted version active when validation or promotion fails.
- [ ] Add explicit rollback/retire flow without deleting historical versions.
- [ ] Test invalid transitions, missing approval, failed promotion, rollback and concurrent promotion exclusion.

## 7. User and portfolio memory

- [ ] Add explicit-user preference storage separate from market evidence and policy evaluation.
- [ ] Support preference update, deletion and effective-date history.
- [ ] Prohibit inferred risk-tolerance escalation from clicks/watchlists/actions.
- [ ] Link portfolio runs to realized portfolio outcomes and attribution when those schemas exist.
- [ ] Label paper, user-supplied and model-target portfolios distinctly.
- [ ] Test preference separation, portfolio provenance and no-execution claims.

## 8. Application and UX surfaces

- [ ] Add shared application services for episode inspection, prediction history, evaluation show/compare and learning-candidate review.
- [ ] Add bounded CLI commands, for example:

```text
vnalpha learn episodes ...
vnalpha learn evaluate ...
vnalpha learn compare ...
vnalpha learn candidates ...
vnalpha learn policy ...
```

- [ ] Make TUI/assistant delegate to the same typed services.
- [ ] Ensure synthesis always exposes sample size, caveats, policy version and evaluation status.
- [ ] Test CLI/TUI/assistant parity and unsupported autonomous-action refusal.

## 9. Maintenance and operations

- [ ] Integrate bounded episode/outcome linkage with finalization without making learning a prerequisite for core market-session success.
- [ ] Route all DuckDB writes through the #343 write coordinator.
- [ ] Add retention policy that preserves reproducibility for episodes, predictions, evaluations and policy transitions.
- [ ] Add backup/restore and migration compatibility evidence.
- [ ] Add diagnostics for unlinked predictions, stale evaluations and policy drift.

## 10. Validation and completion

- [ ] Focused tests for every contract and failure scenario.
- [ ] Full vnalpha tests, lint and repository consistency on exact final SHA.
- [ ] Point-in-time replay fixture proving no future outcome/policy leakage.
- [ ] Champion/challenger fixture proving no automatic promotion.
- [ ] User-feedback fixture proving preference is not market truth.
- [ ] Archive only after implemented requirements are synchronized into accepted main specs and remaining debt is recorded.
