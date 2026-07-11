# Tasks: Model routing profiles

## 0. Governance

- [x] 0.1 Keep model selection deterministic and outside LLM control.
- [x] 0.2 Keep provider-specific model IDs in configuration rather than business logic.
- [x] 0.3 Preserve backward compatibility with `VNALPHA_LLM_MODEL` and existing gateway calls.
- [x] 0.4 Keep raw arbitrary model-ID overrides disabled by default.
- [x] 0.5 Avoid logging prompt or response content in model-route events.
- [x] 0.6 Keep the deterministic planner LLM-free.

## 1. Routing models and configuration

- [x] 1.1 Define `ModelProfile`: `small`, `default`, `reasoning`, and `long_context`.
- [x] 1.2 Define route stage and task-type vocabulary.
- [x] 1.3 Enrich `ModelRouteDecision` with provider, override source, and fallback chain.
- [x] 1.4 Load profile model IDs from preferred `VNALPHA_MODEL_*` environment variables.
- [x] 1.5 Preserve backward-compatible `VNALPHA_LLM_MODEL*` aliases.
- [x] 1.6 Add configurable per-profile fallback chains.
- [x] 1.7 Validate required profile model IDs and fallback references.
- [x] 1.8 Skip fallback profiles that resolve to an already-attempted model ID.

## 2. Deterministic routing policy

- [x] 2.1 Route intent classification and title generation to `small`.
- [x] 2.2 Route ordinary synthesis to `default`.
- [x] 2.3 Route deep analysis, multi-symbol comparison, shortlist, scenarios, and diagnosis to `reasoning`.
- [x] 2.4 Route small watchlist summaries to `default` and large summaries to `reasoning`.
- [x] 2.5 Route workspace compaction to explicitly configured `long_context`, otherwise `reasoning`.
- [x] 2.6 Support complexity metadata such as symbol count, artifact count, context bytes, and deep-reasoning flag.
- [x] 2.7 Preserve `default` as the safe route for unknown stages/tasks.

## 3. Overrides

- [x] 3.1 Implement session profile override.
- [x] 3.2 Implement workspace-persisted profile override.
- [x] 3.3 Enforce precedence: per-call, session, workspace, policy, default.
- [x] 3.4 Implement override reset for session, workspace, or all scopes.
- [x] 3.5 Restrict overrides to configured profile names.
- [x] 3.6 Emit override set/clear events without raw prompt content.

## 4. Gateway integration and fallback

- [x] 4.1 Resolve a route before every production gateway call.
- [x] 4.2 Put the resolved model ID in the HTTP request payload.
- [x] 4.3 Retry retryable failures for the selected model.
- [x] 4.4 Advance through the configured fallback chain after retry exhaustion or model/provider unavailability.
- [x] 4.5 Do not silently fallback for non-retryable authentication/authorization failures.
- [x] 4.6 Return the actual successful route in usage metadata.
- [x] 4.7 Track the most recent successful route decision.
- [x] 4.8 Persist the actual successful model in `llm_trace` when routed usage is available.
- [x] 4.9 Preserve `FakeLLMClient` compatibility while capturing route metadata for tests.

## 5. Assistant stage integration

- [x] 5.1 Classifier passes `classify/intent_classification` routing metadata.
- [x] 5.2 Classifier retries invalid JSON once with explicit `default` profile.
- [x] 5.3 Synthesizer maps plan intent to a task type.
- [x] 5.4 Synthesizer passes symbol count, artifact count, context bytes, and reasoning need.
- [x] 5.5 Complex comparison/research synthesis routes to `reasoning`.
- [x] 5.6 Normal grounded answers remain on `default` unless overridden.

## 6. Workspace compaction

- [x] 6.1 Preserve deterministic compaction as the default path.
- [x] 6.2 Allow an injected LLM client for routed compaction.
- [x] 6.3 Route LLM compaction as `compact/workspace_compaction`.
- [x] 6.4 Fall back to deterministic summary when routed compaction fails.
- [x] 6.5 Add `/context compact --llm` as an explicit routed compaction path.
- [x] 6.6 Record route metadata in the workspace compaction event when available.

## 7. Model commands

- [x] 7.1 Register `/model` in the shared command registry.
- [x] 7.2 Implement `/model status`.
- [x] 7.3 Implement `/model profiles`.
- [x] 7.4 Implement `/model use <profile>` with session/workspace scope.
- [x] 7.5 Implement profile shorthand such as `/model reasoning`.
- [x] 7.6 Implement `/model reset` with scoped reset.
- [x] 7.7 Implement `/model explain-route <stage-or-task>`.
- [x] 7.8 Add `/models` alias for profile listing.
- [x] 7.9 Validate profile, scope, stage, and configuration errors as command validation failures.

## 8. Observability

- [x] 8.1 Emit `MODEL_ROUTE_SELECTED`.
- [x] 8.2 Emit `MODEL_CALL_STARTED`.
- [x] 8.3 Emit `MODEL_CALL_SUCCEEDED` with latency and usage when available.
- [x] 8.4 Emit `MODEL_CALL_FAILED`.
- [x] 8.5 Emit `MODEL_FALLBACK_USED`.
- [x] 8.6 Emit `MODEL_OVERRIDE_SET` and `MODEL_OVERRIDE_CLEARED`.
- [x] 8.7 Include stage, task type, profile, model ID, provider, route reason, override source, and fallback metadata.
- [x] 8.8 Redact unapproved metadata keys such as raw prompt/content.

## 9. Tests

- [x] 9.1 Add tests for profile config and legacy environment compatibility.
- [x] 9.2 Add tests for stage/task/complexity routing.
- [x] 9.3 Add tests for explicit/session/workspace override precedence.
- [x] 9.4 Add tests for workspace override persistence and reset.
- [x] 9.5 Add tests for fallback ordering and duplicate-model suppression.
- [x] 9.6 Add test proving the gateway sends the selected model ID and uses fallback.
- [x] 9.7 Add classifier invalid-JSON retry test.
- [x] 9.8 Add `/model` command tests.
- [x] 9.9 Add routed workspace compaction test.
- [x] 9.10 Add route metadata redaction and audit event tests.

## 10. Documentation

- [x] 10.1 Add `vnalpha/docs/model-routing-profiles.md`.
- [x] 10.2 Document profiles and environment configuration.
- [x] 10.3 Document routing matrix and complexity promotion.
- [x] 10.4 Document override precedence and commands.
- [x] 10.5 Document fallback behavior and single-model compatibility.
- [x] 10.6 Document observability and workspace compaction integration.

## 11. Validation

- [ ] 11.1 Run focused model-routing and compaction tests.
- [ ] 11.2 Run `make test-vnalpha`.
- [ ] 11.3 Run `make lint-vnalpha`.
- [ ] 11.4 Run `make verify-r4`.
- [ ] 11.5 Run `openstock-verify --ci`.
- [ ] 11.6 Record successful command output in `validation.md`.

The validation tasks remain unchecked until the commands are executed in an environment with the repository checkout and its development dependencies.
