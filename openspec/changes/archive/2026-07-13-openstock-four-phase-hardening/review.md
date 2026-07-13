# Review: OpenStock four-phase hardening findings

## Verdict

OpenStock has crossed the boundary from a small MVP into a local research platform. The major subsystems are present, but several foundation risks are now more important than adding new product scope.

Current posture:

```text
Product capability:          strong for an evolving local research platform
Architecture direction:      generally sound
Repository hygiene:          unsafe
Workspace correctness:       unsafe under concurrency and lifecycle edge cases
Assistant trust boundary:    incomplete
Runtime correctness:         mixed
CI/release governance:       insufficiently enforced
```

The remediation order matters. Repository and workspace safety must be fixed before context is trusted by the assistant. Context trust and prepared-plan execution must be fixed before agent workflows expand. Correctness gaps must be fixed before evaluation is treated as authoritative. CI must then encode all prior guarantees.

## Phase 1 findings — Repository and data safety

### Finding 1.1 — Runtime workspace data is tracked in Git

Tracked paths include project-local workspace state and a second nested workspace root. These files contain user inputs, timestamps, IDs, summaries, events, and active-state pointers.

Risk:

```text
privacy leakage
state contamination across clones
nondeterministic tests
accidental secret persistence
```

Required resolution:

```text
remove runtime workspace files from index
ignore all runtime workspace roots
add repository-hygiene and secret checks
provide a migration note for existing local workspaces
```

### Finding 1.2 — Local worktrees are committed as gitlinks

`.worktrees/` entries are local implementation artifacts. Tracking them without a deliberate submodule contract creates broken clone behavior and ambiguous repository structure.

Required resolution:

```text
remove gitlinks
ignore .worktrees/
verify no gitlink exists outside an approved allowlist
```

### Finding 1.3 — Generated metadata and caches are tracked or insufficiently ignored

Examples include egg-info and potential Python/test/lint caches.

Required resolution:

```text
expand .gitignore
remove generated files from index
add CI check using git ls-files and file-mode inspection
```

### Finding 1.4 — Workspace root depends on current working directory

The default `.vnalpha/workspaces` path resolves relative to the invocation directory. Running from repository root and package subdirectory creates distinct active workspace stores.

Required resolution:

Choose exactly one documented default:

```text
user-local state root, recommended
or
repository-root-relative project state
```

The root resolver must be deterministic and testable from multiple current working directories.

### Finding 1.5 — Workspace lock is not mutually exclusive

The current lock writes or replaces a file but does not use an exclusive-create or OS lock. More importantly, mutations do not hold the lock across load, modify, save, and event append.

Required resolution:

```text
atomic lock acquisition
owner token/PID metadata
stale-lock policy
transaction context manager
all mutations use transaction boundary
no lost update under concurrent writers
```

### Finding 1.6 — Active/archive/latest lifecycle semantics are inconsistent

The generic persistence helper updates `latest.json` for any saved state, including archived state. Resume can make an archived state current without reactivation.

Required resolution:

```text
separate save from activate
archive never activates
resume either reactivates explicitly or refuses
latest always refers to an active workspace or is absent
status is read-only
```

### Finding 1.7 — Workspace retention is unbounded

Threshold constants currently generate recommendations but do not enforce retention. Recent input, warning, error, event, artifact, and task collections can grow indefinitely.

Required resolution:

```text
bounded in-memory/state collections
archive older entries
retain source references and counts
compaction must reduce active retained state
```

### Finding 1.8 — Redaction is inconsistent

Input text is redacted, but tasks, warnings, errors, context markdown, compact summaries, and exports can preserve raw sensitive-looking values.

Required resolution:

Use one redaction service for every persisted or exported text field. Tests must cover task text, warnings, errors, compact output, audit metadata, and export bundles.

### Finding 1.9 — Export leaks raw state and absolute paths

Export copies raw workspace JSON and records the local absolute source path.

Required resolution:

```text
export a redacted projection
omit absolute source paths
exclude history by default
include only policy-approved/pinned artifacts
record manifest schema version and redaction mode
```

## Phase 2 findings — Context trust and assistant lifecycle

### Finding 2.1 — Historical context and current request share one prompt string

Workspace and chat context are concatenated directly before the user request. The classifier, safety policy, persistence layer, and synthesizer see one undifferentiated string.

Risk:

```text
prompt-injection through persisted tasks or summaries
stale context changing current intent classification
privacy duplication
unclear source attribution
```

Required resolution:

Represent messages separately:

```text
system: product and safety policy
context: untrusted historical workspace/chat data
user: current request
```

Safety and intent classification must use the current request only. Synthesis may consume bounded context with explicit trust metadata.

### Finding 2.2 — Raw prompt persistence does not obey configuration

A `store_raw` setting exists, but assistant sessions always persist the full prefixed prompt.

Required resolution:

```text
store raw current request only when explicitly enabled
otherwise store redacted summary/hash/length
store context references, not duplicated context bodies
```

### Finding 2.3 — One user turn is classified and planned more than once

Plan preview is produced by one assistant invocation. Auto-execute and approval invoke the assistant again, potentially producing a different plan.

Required resolution:

```text
prepare once
persist immutable prepared turn
preview exact plan
approve exact plan
execute exact plan
synthesize from exact execution record
```

### Finding 2.4 — Approval does not guarantee plan identity

The user approves a stored plan, but runtime rebuilds the plan from the original question.

Required resolution:

Add plan identity and integrity fields:

```text
prepared_turn_id
plan_id
canonical plan JSON
plan hash
created_at
policy decision
```

Execution must verify the hash and use the stored plan object.

### Finding 2.5 — Workspace recording can block or misrepresent TUI work

The router records and displays input before checking busy state. Workspace errors occur before the main error-handling block.

Required resolution:

```text
busy check before accepted-input persistence
best-effort workspace hooks
explicit rejected/not-executed state if retained
no workspace exception may prevent command/chat execution
```

### Finding 2.6 — Corrupt workspace state can block startup

Workspace initialization lacks recovery/fallback behavior.

Required resolution:

```text
validate workspace schema
quarantine corrupt files
start temporary or new safe workspace
render operator warning
provide repair guidance
```

## Phase 3 findings — Runtime correctness

### Finding 3.1 — Data-ensure lock acquisition is non-atomic

The flow checks existence and then writes. Competing processes can both acquire.

Required resolution:

Use atomic exclusive creation or an OS-backed lock with owner metadata and safe stale-lock replacement.

### Finding 3.2 — Invalid dates silently become today's date

A malformed explicit date is converted into current date.

Required resolution:

```text
missing date may resolve by policy
invalid supplied date must raise validation error
no network or warehouse mutation after invalid date
```

### Finding 3.3 — Cache-hit eligibility is too weak

Candidate-score existence can return READY even if canonical history, benchmark history, feature snapshot, quality, or lineage are insufficient.

Required resolution:

Define an explicit cache eligibility object containing:

```text
score present and fresh
feature present
canonical bars sufficient
benchmark bars sufficient when required
quality not failed
lineage complete enough for configured policy
```

### Finding 3.4 — Artifact references can claim unavailable artifacts

Shortlist output can add sector snapshot references even when no sector snapshot exists and a zero default was used.

Required resolution:

Artifact references must be produced from confirmed query results only. Missing optional evidence must be represented in `missing_data` and caveats.

### Finding 3.5 — Compaction is summary-only

Writing `compact.md` does not reduce active workspace state or archive older entries.

Required resolution:

Compaction must have measurable before/after retention counts and archived item references while preserving pinned/user-authored data.

### Finding 3.6 — `/new` has conflicting meanings

The global command parser maps `/new` to a new workspace while chat-local behavior also uses `new` for a new chat session.

Required resolution:

Choose one stable public contract and introduce an explicit alternative such as `/chat new`.

### Finding 3.7 — TODO visibility events are noisy

Visibility events emit on every layout application, not only state transitions.

Required resolution:

Track prior state and emit only on actual visible/hidden transitions.

### Finding 3.8 — Session model override is process-global

The default override store keeps one in-process session profile without a session key.

Required resolution:

Use a context variable or session-ID-keyed store. Workspace override remains workspace-scoped; per-call override remains highest priority.

### Finding 3.9 — Grounded source refs can be auto-filled after model omission

Auto-populating all available refs lets an answer pass without proving which sources support which claims.

Required resolution:

Model-generated research answers must provide refs or be rewritten by deterministic fallback. Future claim-level source mapping should be supported without breaking the current answer schema.

## Phase 4 findings — CI, evaluation, and release governance

### Finding 4.1 — Latest branch has no authoritative required-check evidence

Code has been merged while OpenSpec validation remains unchecked and validation documents state that gates were not run.

Required resolution:

Required checks must block merge. OpenSpec validation status must be reconciled before archive/merge.

### Finding 4.2 — Lint failure remains possible on merged code

Known auto-fixable Ruff findings have existed during merge flow.

Required resolution:

Make lint a first required step and upload diagnostics. The implementation branch must remain unmergeable while lint fails.

### Finding 4.3 — Golden evaluation validates static observations, not production orchestration

The current runner proves fixture contract consistency but does not exercise production assistant boundaries.

Required resolution:

Keep fixture-contract mode and add runtime-replay mode using deterministic fakes through production classifier, planner, executor, synthesizer, groundedness, policy, and audit interfaces.

### Finding 4.4 — Golden corpus packaging is uncertain

The corpus is outside the Python package and package-data configuration does not clearly include it.

Required resolution:

Use `importlib.resources` and package the fixtures, or install the corpus to a documented data path. Tests must run against wheel/sdist/deb installation, not only source checkout.

### Finding 4.5 — Root Makefile and CI omit the evaluation gate

The evaluation target exists in a nested Makefile but not the root operator interface or workflow.

Required resolution:

Add root targets and CI steps for:

```text
fixture-contract eval
runtime-replay eval
repository hygiene
secret scan
```

### Finding 4.6 — OpenSpec task state can diverge from evidence

Tasks may be checked or code merged while validation documents remain pending.

Required resolution:

Add a deterministic OpenSpec verifier that checks unchecked tasks, deferred markers, validation command evidence, and archived-change eligibility.

## Dependency critique

The phases cannot be safely implemented in arbitrary order:

```text
Phase 1 provides safe persistent state for Phase 2.
Phase 2 provides a trustworthy execution lifecycle for Phase 3 assistant correctness.
Phase 3 defines the behavior that Phase 4 must evaluate.
Phase 4 prevents regressions and false completion claims.
```

Parallel work is acceptable only for isolated tests/docs that do not depend on unresolved runtime contracts.

## Final recommendation

Freeze new agentic/research feature scope until the following minimum gate passes:

```text
repository clean
workspace transaction/lifecycle tests pass
context trust separation tests pass
prepared-plan identity tests pass
data-lock/date/cache tests pass
full CI and eval gates required
```

The work should be reviewed as a hardening program, not as unrelated bug fixes.