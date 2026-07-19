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

**Prevent it:** define safety over the final rendered and persisted value.
Sanitize independently allowlisted fields before composing them; for opaque
text, retain a bounded prefix and treat an incomplete credential at that
boundary as sensitive instead of splicing an unredacted tail back in. Escape
each retained sanitized field atomically, then assert the final character limit
and parse the result with the real renderer. Route database summaries, JSONL
errors and other stored projections through the same credential boundary.
Include adversarial fixtures whose truncation boundary lands inside an escape
sequence, quoted multi-word credential, URI user-info, Basic token, JWT or PEM
body, not just short markup examples.

## 21. A path test mocks away the dispatcher it is meant to verify

A post-approval regression can appear green while replacing the approval
dispatcher with a no-op. The test then proves only the shared exception
presenter, not whether a safe data plan is incorrectly sent to a sandbox-only
approval service before execution.

**Prevent it:** exercise each mode-specific dispatcher through its real public
entry point. Mock only external providers or deterministic failure sources, not
the branch that selects safe-plan versus sandbox approval semantics. Assert the
provider/tool was reached and that lifecycle state left `PREPARED` truthfully.

## 22. A redaction label overstates the fields actually redacted

Redacting an exception message and stacktrace is insufficient when the same
record stores raw context, likely cause, or suggested next step while declaring
`redaction_status='redacted'`. Replacing a legacy sanitizer can also silently
drop established credential spellings such as `bearer=...`.

**Prevent it:** apply the selected content mode recursively to every
content-bearing field before persistence. Preserve legacy credential-form
coverage when consolidating sanitizers, and test the complete serialized record
rather than a selected pair of fields.

## 23. A credential regex ignores protocol grammar and benign consumers

A broad standalone-auth regex can both miss valid short or dotted tokens and
rewrite ordinary research text such as `Basic analysis`. A cropped-URI heuristic
can likewise mistake `http://localhost:6900` for truncated user information.
Because the shared sanitizer also serves normal CLI/TUI output, either mistake
becomes a product-wide compatibility defect.

**Prevent it:** model Basic and Bearer token grammars separately, validate
standalone Basic payloads as decoded `user:password`, and cover the full Bearer
`b64token` alphabet. Restrict incomplete-URI heuristics to credential-bearing
HTTP(S) and DSN schemes, distinguish parsed host/port and bracketed-IPv6
endpoints, and fail closed when an `@` remains inside a malformed authority.
Pair every positive credential fixture with negative prose, title, URL and
renderer regressions.

## 24. Safe fragments become unsafe after cropping or composition

A bounded scan can cut a long credential into a fragment that no longer passes
protocol validation even though its visible prefix survives. Separately escaped
fields can also form valid Rich markup only after a reason, remediation or
correlation value is joined to its neighbors.

**Prevent it:** make end-of-scan credential handling conservative, and verify
the final composed renderer input rather than only each field. Test credential
markers and first protocol delimiters on both sides of every scan boundary, and
test adversarial incomplete markup across every field boundary.

## 25. A content-mode primitive erases structural metadata

A string redaction helper cannot infer whether its caller is passing message
content or a required event type, status or correlation ID. Making metadata mode
blank every string can crash typed models and destroy truthful audit identity far
outside the record that motivated the change.

**Prevent it:** apply content omission at a typed record boundary where field
semantics are known. Run non-default content modes through real consumers and
assert that content is omitted only where required while IDs, hashes, types and
statuses remain usable.

## 26. Sensitive-key expansion leaks or erases unrelated structured values

Delimiter-only normalization misses common JSON spellings such as
`authHeader`, while applying every sensitive word as a prefix can classify
ordinary operational fields such as `token_budgets` or `auth_status` as
credentials. A second legacy substring matcher can silently override a correct
canonical decision. The same helpers often serve exception records, command
renderers, logs and clipboards, so either direction invalidates multiple
surfaces.

**Prevent it:** normalize common key casing before matching, keep exact and
suffix compatibility, and require a credential-bearing affix for prefix
matching. Make every consumer delegate to the canonical classifier. Pair nested
credential positives with real structured-consumer negatives, including
operational status and budget fields.

## 27. Structured redaction treats map keys as harmless metadata

Replacing a sensitive field's value does not make a record safe when the key
itself contains `password=...`, an authorization token, terminal controls or
markup. A record can therefore claim `redacted` while its serialized key names
still carry the original secret.

**Prevent it:** sanitize JSON-valid key names before persistence as well as
classifying their values, preserve safe non-string keys where the boundary
allows them, and assert over the complete serialized record with controlled
secrets in both keys and values.

## 28. A valid timer file is not a packaged, safe scheduling feature

Keeping systemd units only in a source directory proves neither that the Debian
artifact installs them nor that upgrades preserve operator choice. Timer-to-
service `Requires=` edges, installable oneshot services, local-time schedules,
and lock-file unlinking can also create activation cycles, unexpected enablement,
timezone drift, or overlapping writers even when `systemd-analyze verify` passes.

**Prevent it:** inspect the built package payload, keep the service without an
`[Install]` section, install but do not enable or start the timer, declare the
IANA timezone in `OnCalendar`, use one stable `flock` inode, and test maintainer
scripts for install, upgrade and removal. Verify the exact packaged `ExecStart`,
partial-success exit code, timer schedule, lock contention, and operator
enable/disable/inspection commands.

## 29. A package built on one Python ABI is not portable to its declared hosts

`pip download` resolves binary wheels for the build interpreter by default. A
package assembled on Python 3.12 can therefore contain only `cp312` wheels while
its Debian 12 target creates a Python 3.11 virtual environment. Structural
payload checks still pass, but offline installation fails on the first binary
dependency.

**Prevent it:** declare the package's supported interpreter range, resolve
binary wheels explicitly for every supported ABI and target platform, and
reject artifacts missing any required ABI. Install the exact built artifact in
the oldest supported clean host, exercise packaged commands and evaluations,
and keep release metadata honest about commit and tree state.

## 30. Moving an OpenSpec directory is mistaken for completed archival

An archive command can move a change and synchronize a capability spec even
when `validation.md` is missing, task IDs are not machine-readable, successful
rows use working-tree placeholders, or publication gates still say `Pending`.
The directory layout then looks finished while the repository completion
verifier correctly rejects it.

**Prevent it:** before moving a change, run
`scripts/check-openspec-completion.py` against the active directory and require
a pass. Ensure every checked task has a canonical task ID and an evidence row,
every successful row names an existing exact commit, the final implementation
SHA is recorded, and no phase or publication gate remains pending. After the
move, run the verifier again against the archive path, validate the synchronized
accepted spec strictly, replace generated purpose placeholders, and remove the
change from `active-changes.yaml`.

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
- [ ] Enumerate mode-specific dispatchers and approval services before mocking any boundary.
- [ ] Confirm bounded behavior and the read-only research boundary.
- [ ] Write the negative and backward-compatibility test matrix.
- [ ] Pair credential positives with benign prose, endpoint, and renderer negatives.
- [ ] Exercise credentials and markup across scan and structured-field boundaries.
- [ ] Run every changed content mode through real consumers and preserve structural metadata.
- [ ] Isolate offline tests from ambient localhost services and vendor state.

## During implementation

- [ ] Normalize inputs once at the boundary.
- [ ] Do not parse warnings for control flow.
- [ ] Do not equate row existence with readiness.
- [ ] Do not default non-throwing work to success.
- [ ] Reuse one service and one correlation ID across surfaces.
- [ ] Sanitize public errors, database summaries, and file-backed error logs through one credential boundary.
- [ ] Apply the declared redaction mode to every content-bearing field in each persisted record.
- [ ] Derive nested sensitive-key checks from the canonical vocabulary and accept JSON-valid key types.
- [ ] Redact structured fields before any crop can orphan their credential marker or delimiter.
- [ ] Apply bounding and escaping in an order that leaves the final rendered value safe.
- [ ] Verify independently safe fields remain safe after final composition.
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
- [ ] Exercise real safe-plan and sandbox post-approval dispatch without mocking the selector.
- [ ] Run and report required full validation gates honestly.
- [ ] Check CI on the exact commit; skipped is not passed.
- [ ] Update OpenSpec evidence and pass the completion verifier before and after archival.
- [ ] Create and link follow-up issues for deferred defects.
- [ ] Add new recurring patterns to this page.

A ticket is complete only when runtime semantics, negative paths, backward compatibility, truthful evidence, and the read-only boundary are verified.
