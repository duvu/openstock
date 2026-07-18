# Common implementation failures and prevention playbook

This page records recurring failure patterns found during OpenStock/vnalpha implementation and review. Human contributors and AI agents must read it before implementing or closing a ticket.

OpenStock remains inside the **read-only research boundary**. Deterministic application services own data provisioning and mutation. The assistant must not gain broker, order, account, portfolio, margin, transfer, execution, unrestricted SQL, filesystem, shell, or arbitrary network capabilities.

## 1. Closing a ticket because files exist

A class, command, flag, or checked OpenSpec task is not proof that the acceptance contract works. Repeated defects appeared only in runtime, negative paths, legacy commands, or alternate surfaces.

**Prevent it:** map every acceptance criterion to implementation, a regression test, runtime evidence, or a linked follow-up issue. Do not close from PR prose alone.

## 2. CLI, TUI, assistant, and legacy paths drift apart

Parallel implementations create inconsistent validation, date handling, defaults, status, errors, audit events, and output.

**Prevent it:** use one typed application service. Enumerate every surface and add parity tests:

```text
new CLI | legacy CLI | TUI | assistant preflight | tool call | readiness | packaged runtime
```

## 3. Fail-closed handling wraps only the inner call

Failures often escaped from argument conversion, date resolution, database reads, cache checks, evidence rendering, output reload, or serialization even though the provider/builder was wrapped.

**Prevent it:** protect the complete lifecycle:

```text
correlation → validation → date resolution → read/check → bounded work
→ reload → policy evaluation → typed result → terminal audit
```

Required failures stop downstream execution. Public output and audit summaries must not contain raw exception/provider details.

## 4. Boundary types are assumed

Recurring examples:

- raw strings compared to enums with `is`;
- `"REQUIRED"` passed where an enum is expected;
- ISO strings passed to builders requiring `datetime.date`;
- `None` converted to `"None"` and then parsed numerically;
- code using APIs unavailable on declared Python versions.

**Prevent it:** inspect real dependency signatures, normalize once at the boundary, pass typed values internally, test the received type, and include null/malformed/compatibility fixtures.

## 5. Status is optimistic or false

Non-throwing work was sometimes reported as `SUCCESS` despite errors, skipped symbols, rejected rows, incomplete quality, or empty data. Artifact quality values such as `COMPLETE` and `OK` were also incorrectly treated as interchangeable.

**Prevent it:** derive status from typed evidence. Preserve meaningful distinctions such as:

```text
SUCCESS | PARTIAL | FAILED | EMPTY | INVALID | SKIPPED | NOT_REQUESTED
```

Use artifact-specific quality policies. Do not treat row existence as usability.

## 6. Evidence and lineage are flattened or discarded

One global freshness/lineage value was projected onto unrelated artifacts, while provider, ingestion run, generated time, methodology version, coverage, and source dates were lost.

**Prevent it:** keep independent evidence per artifact, including requested/observed dates, counts, freshness, quality, coverage, provider, ingestion run, generated time, methodology/build version, source symbol/benchmark, lineage, and typed issues.

A cache hit is a policy decision, not a row-existence check.

## 7. Warning text controls behavior

Searching messages for words such as `failed`, `benchmark`, `market`, or `sector` made control flow dependent on wording and risked leaking internal details.

**Prevent it:** use typed issue codes for attribution and blocking decisions. Warnings are presentation only. Map typed issues to allowlisted public messages.

## 8. Remediation does not fix the root cause

Recurring failures included nonexistent command namespaces, wrong flags, incomplete multi-step repairs, generic rebuild commands for missing upstream data, and remediation for ready or unrequested artifacts.

**Prevent it:** model remediation as ordered typed steps. Every rendered command must exist, use valid arguments, address the typed root cause, preserve dependencies, and remain bounded.

## 9. Audit lifecycle is late or fragmented

Start events were emitted after work began, correlation IDs differed across child operations, builder failure/revalidation events were missing, and terminal status did not always match the result.

**Prevent it:** establish one correlation ID before the first fallible operation. Record start-before-work, child action, output revalidation, and truthful terminal events under that ID.

## 10. Backward compatibility is inferred from delegation

Migrating a legacy command to a shared service changed default scope, no-argument behavior, output, date aliases, exit handling, or all-symbol semantics. One concrete regression attempted `tuple(None)` where no selector previously meant all active symbols.

**Prevent it:** test every migrated command with defaults, optional arguments, invalid input, empty/partial/failure outcomes, exit codes, and output relied on by scripts. Delegation alone is not compatibility.

## 11. Focused tests create false confidence

Changed-file tests passed while full tests were incomplete, lint remained red, downstream CI was skipped, or the test itself asserted the wrong product semantics.

**Prevent it:** record exact evidence separately:

1. focused regressions;
2. full component tests;
3. lint/format;
4. integration/R4;
5. packaging/runtime verification;
6. strict OpenSpec validation;
7. GitHub Actions on the exact commit.

Use `passed`, `failed`, `skipped`, `inconclusive`, or `not run`. Never infer that an unrun gate passed.

## 12. Review findings have no disposition

Some unresolved comments are false positives; others are real runtime defects. Both require an explicit decision.

**Prevent it:** classify every finding as `fix now`, `documented false positive`, `follow-up issue`, or `out of scope with owner`. Do not silently merge unresolved substantive findings.

## 13. TUI terminal ownership is ignored

Direct stderr logging and unbounded widgets can corrupt the Textual frame or overlap the composer, footer, TODO rail, and log screen.

**Prevent it:** Textual is the sole terminal renderer; TUI diagnostics are file-backed; CLI console logging remains surface-specific; layout regions and scroll ownership are bounded and tested at multiple terminal sizes.

## 14. LLM output is trusted before validation

Empty completion, invalid JSON, same-model fallback, raw provider payload logging, and promotion of model prose to factual memory have all caused defects.

**Prevent it:** validate non-empty schema-compliant output, ensure fallback routes are distinct, keep normal logs metadata-only, and require source plus temporal metadata before promoting factual memory.

## 15. Time and historical semantics are implicit

Requested date, Vietnam market date, observed bar date, generated time, publication time, and event time were sometimes mixed or resolved repeatedly.

**Prevent it:** carry separate typed fields and resolve the effective market date once. Historical retrieval must exclude information published after the requested as-of date.

## 16. Enum and registry expansion misses consumers

Adding an enum member can break fixed maps, renderers, permissions, remediation, catalogs, or serializers.

**Prevent it:** update and test the complete registry matrix: validator, adapter, status/action map, remediation, renderer, audit, CLI/TUI catalog, permission policy, serialization, and tests.

## 17. Offline tests inherit process-global vendor quotas

Mocked provider tests can still execute a third-party decorator before the
mock boundary. Its process-global request counter then makes a full suite fail
or skip based on test order even though isolated tests pass.

**Prevent it:** reset third-party process-global quota state between offline
tests while retaining normal enforcement inside each test and every explicitly
marked live test. Keep network I/O mocked, run the complete suite in one
process, and treat order-dependent quota failures as test-isolation defects
rather than product evidence.

## 18. Offline tests inherit a developer's live localhost service

An offline fail-closed test can silently call a service already running on the
default localhost port. The same test then fails locally, passes on a clean CI
worker, and proves neither intended path deterministically.

**Prevent it:** make each offline fixture own its provider boundary. Use an
in-process wire fake for response behavior or an explicitly unreachable local
endpoint for fail-closed behavior. Never let the ambient default service URL
decide an offline test's expected status.

## 19. Exception conversion destroys public/private provenance

A lower layer may wrap both expected domain failures and arbitrary runtime
exceptions in the same broad error type. If a presentation boundary later
treats that type as public, provider internals, credentials, paths, or opaque
debug data can escape despite regex redaction. Direct boundary tests miss the
defect when they inject an exception after the unsafe conversion already
happened.

**Prevent it:** carry an explicit structured public-failure type containing only
allowlisted reason, remediation, correlation and evidence fields. Keep ordinary
tool errors and arbitrary exceptions on the generic presentation path, even if
an internal compatibility wrapper converts them to a private assistant error
type. Test from the real
nested producer through conversion, persistence and rendering, including every
approval and legacy branch. Treat text sanitization as defense in depth, not as
the trust decision.

## 20. A later transform undoes an earlier safety transform

Escaping markup before length truncation can still be unsafe: a slice may drop
the escape prefix while retaining the tag opener, turning inert text back into
an active Rich link or style. Similar ordering mistakes can split redaction
markers, encoded delimiters, or structured tokens.

**Prevent it:** define safety over the final rendered and persisted value. Bound
source segments first, escape each retained segment atomically, then assert the
final character limit and parse the result with the real renderer. Include
adversarial fixtures whose truncation boundary lands inside an escape sequence,
not just short markup examples.

# Mandatory checklist

## Before coding

- [ ] Read the complete issue and mandatory comments.
- [ ] Confirm dependencies and the next roadmap item.
- [ ] Enumerate every execution surface and legacy path.
- [ ] Inspect real callable signatures and return shapes.
- [ ] Define typed request, result, status, issue, and evidence contracts.
- [ ] Define required/optional/not-requested semantics.
- [ ] Define the complete failure and audit boundary.
- [ ] Preserve expected/actionable versus unexpected exception provenance across every wrapper.
- [ ] Confirm bounded behavior and the read-only research boundary.
- [ ] Write the negative and backward-compatibility test matrix.
- [ ] Isolate offline tests from ambient localhost services and vendor state.

## During implementation

- [ ] Normalize inputs once at the boundary.
- [ ] Do not parse warnings for control flow.
- [ ] Do not equate row existence with readiness.
- [ ] Do not default non-throwing work to success.
- [ ] Reuse one service and one correlation ID across surfaces.
- [ ] Sanitize public errors and audit summaries.
- [ ] Apply bounding and escaping in an order that leaves the final rendered value safe.
- [ ] Render only explicitly public structured failures; keep arbitrary nested exceptions generic.
- [ ] Make remediation typed, ordered, executable, and root-cause-specific.
- [ ] Preserve legacy defaults unless explicitly changed.
- [ ] Reload and revalidate persisted output after builders run.

## Before merge or closure

- [ ] Exercise every supported command, including no-argument/default paths.
- [ ] Prove invalid input fails before provider calls or mutation.
- [ ] Exercise empty, partial, failed, and legacy-row cases.
- [ ] Give every review finding an explicit disposition.
- [ ] Review test expectations for semantic correctness.
- [ ] Parse bounded public text with the real renderer and assert no active markup.
- [ ] Run and report required full validation gates honestly.
- [ ] Check CI on the exact commit; skipped is not passed.
- [ ] Update OpenSpec evidence.
- [ ] Create and link follow-up issues for deferred defects.
- [ ] Add new recurring patterns to this page.

A ticket is complete only when runtime semantics, negative paths, backward compatibility, truthful evidence, and the read-only boundary are verified.
