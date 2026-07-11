# Specification: OpenStock four-phase hardening

## ADDED Requirements

# Phase 1 — Repository and data safety

### Requirement: Runtime and generated state shall not be tracked in Git

The repository SHALL exclude local runtime state, worktree metadata, generated package metadata, and caches from tracked source.

#### Scenario: Runtime workspace paths are absent from tracked files

- **GIVEN** repository hygiene verification runs
- **WHEN** tracked paths are inspected
- **THEN** `.vnalpha/**` and `vnalpha/.vnalpha/**` SHALL NOT be tracked.

#### Scenario: Local worktrees are absent from tracked files

- **GIVEN** tracked Git entries are inspected
- **THEN** `.worktrees/**` SHALL NOT be tracked.

#### Scenario: Unapproved gitlinks fail verification

- **GIVEN** a tracked entry has Git mode `160000`
- **WHEN** it is not present in the approved-submodule manifest
- **THEN** repository hygiene verification SHALL fail.

#### Scenario: Generated metadata is absent

- **GIVEN** repository hygiene verification runs
- **THEN** egg-info, Python bytecode, and test/lint cache paths SHALL NOT be tracked.

---

### Requirement: Repository hygiene and sensitive-content checks shall be executable

The repository SHALL provide deterministic commands that detect recurrence of denied paths, gitlinks, and sensitive content.

#### Scenario: Hygiene command succeeds on a clean tree

- **GIVEN** no denied tracked paths or unapproved gitlinks exist
- **WHEN** `make repo-hygiene` runs
- **THEN** it SHALL exit zero.

#### Scenario: Hygiene command fails on a denied tracked path

- **GIVEN** a denied runtime path is seeded as tracked input to the verifier
- **WHEN** verification runs
- **THEN** it SHALL exit nonzero with the offending path.

#### Scenario: Secret scanner fails on seeded credential

- **GIVEN** a test fixture contains a prohibited credential pattern
- **WHEN** the configured scanner runs
- **THEN** it SHALL fail without printing the full secret value.

---

### Requirement: Workspace root shall be deterministic

Workspace storage SHALL resolve independently of current working directory.

#### Scenario: Default root is stable across working directories

- **GIVEN** no explicit root or environment override is configured
- **WHEN** root resolution occurs from repository root, package directory, and an unrelated directory
- **THEN** the same canonical root SHALL be returned.

#### Scenario: Explicit argument wins

- **GIVEN** an explicit root argument is supplied
- **WHEN** root resolution occurs
- **THEN** the explicit root SHALL be used.

#### Scenario: Environment override wins over default

- **GIVEN** `VNALPHA_WORKSPACE_ROOT` is configured
- **WHEN** no explicit argument is supplied
- **THEN** the environment path SHALL be used.

#### Scenario: Legacy roots are not silently merged

- **GIVEN** multiple legacy project-local roots exist
- **WHEN** migration discovery runs
- **THEN** the system SHALL report them and require an explicit migration decision.

---

### Requirement: Workspace mutations shall be transactionally locked

Every read-modify-write workspace operation SHALL execute under a mutually exclusive owner-aware lock.

#### Scenario: Only one process acquires a workspace lock

- **GIVEN** two processes attempt to acquire the same workspace lock concurrently
- **WHEN** acquisition completes
- **THEN** exactly one process SHALL own the lock at a time.

#### Scenario: Mutations do not lose updates

- **GIVEN** concurrent writers add independent inputs, tasks, warnings, or artifacts
- **WHEN** all operations complete
- **THEN** every successful mutation SHALL be present in final state.

#### Scenario: Old owner cannot release new lock

- **GIVEN** a stale lock is replaced by a new owner
- **WHEN** the old owner attempts release
- **THEN** the new owner's lock SHALL remain.

#### Scenario: Lock is released after exception

- **GIVEN** a mutation raises after lock acquisition
- **WHEN** cleanup completes
- **THEN** the owning lock SHALL be released and state SHALL remain valid.

---

### Requirement: Workspace lifecycle shall maintain valid active/archive/latest state

Workspace save, activation, archival, resumption, and status inspection SHALL be separate operations with explicit transitions.

#### Scenario: Archiving does not activate archived workspace

- **GIVEN** an active workspace is archived
- **WHEN** archive completes
- **THEN** `latest` SHALL NOT point to that archived workspace.

#### Scenario: Latest points only to active workspace

- **GIVEN** a latest pointer exists
- **WHEN** lifecycle invariants are checked
- **THEN** it SHALL reference an existing valid active workspace.

#### Scenario: Status is read-only

- **GIVEN** `/context status` runs
- **WHEN** state and event files are compared before and after
- **THEN** latest pointer and lifecycle event count SHALL remain unchanged.

#### Scenario: Archived resume is explicit

- **GIVEN** a workspace is archived
- **WHEN** the user requests resume
- **THEN** the system SHALL either explicitly reactivate it or return a clear validation error; it SHALL NOT silently make archived state current.

#### Scenario: New workspace leaves exactly one active latest workspace

- **GIVEN** an active workspace exists
- **WHEN** `/context new` completes
- **THEN** the prior workspace SHALL be compacted/archived according to policy and exactly one new active workspace SHALL be latest.

---

### Requirement: Workspace context shall be bounded and compaction shall reduce retained state

Workspace state SHALL enforce retention limits and compaction SHALL archive older entries rather than only writing a summary.

#### Scenario: Recent inputs are bounded

- **GIVEN** input count exceeds configured maximum
- **WHEN** a mutation or compaction completes
- **THEN** active state SHALL retain at most the configured number and SHALL preserve archive references for older entries.

#### Scenario: Pinned and user-authored items survive compaction

- **GIVEN** pinned artifacts, open tasks, assumptions, or user notes exist
- **WHEN** compaction runs
- **THEN** those protected items SHALL remain active.

#### Scenario: Compaction reports measurable reduction

- **GIVEN** workspace state exceeds retention limits
- **WHEN** compaction runs
- **THEN** its result SHALL include before, retained, and archived counts and SHALL show a reduction in active retained state.

#### Scenario: Repeated compaction is idempotent without new data

- **GIVEN** no state changed since prior compaction
- **WHEN** compaction runs again
- **THEN** it SHALL NOT create duplicate archive entries.

---

### Requirement: All persisted and exported workspace text shall be redaction-aware

Inputs, tasks, warnings, errors, assumptions, summaries, markdown, audit metadata, and export projections SHALL use one canonical redaction boundary.

#### Scenario: Sensitive task text is redacted

- **GIVEN** a task contains a sensitive-looking token
- **WHEN** it is persisted and rendered into context/compact output
- **THEN** the raw token SHALL NOT appear.

#### Scenario: Sensitive error text is redacted

- **GIVEN** an error contains a credential-like value
- **WHEN** it is stored or audited
- **THEN** the raw value SHALL NOT appear.

#### Scenario: Export contains no absolute source path

- **GIVEN** a workspace export is created
- **WHEN** the manifest is inspected
- **THEN** it SHALL contain only relative bundle paths and SHALL NOT contain the local absolute workspace path.

#### Scenario: Export excludes history by default

- **GIVEN** the workspace contains recent input history and events
- **WHEN** default export runs
- **THEN** raw input/event history SHALL NOT be included.

#### Scenario: Export includes only approved artifact paths

- **GIVEN** pinned artifacts include invalid, absolute, traversal, or symlink paths
- **WHEN** export runs
- **THEN** unsafe paths SHALL be excluded.

# Phase 2 — Context trust and assistant lifecycle

### Requirement: Current user request shall be separated from historical context

Workspace and chat context SHALL be represented as bounded untrusted historical context, not concatenated into the current user instruction.

#### Scenario: Safety evaluates current request only

- **GIVEN** workspace context contains an unsafe instruction but current request is safe
- **WHEN** deterministic safety policy runs
- **THEN** the current request SHALL be evaluated independently and context text SHALL NOT be executed as instruction.

#### Scenario: Classification evaluates current request only

- **GIVEN** workspace context contains text naming a different intent
- **WHEN** classification runs
- **THEN** intent SHALL be based on the current user request.

#### Scenario: Synthesis receives context with trust metadata

- **GIVEN** bounded workspace or chat context exists
- **WHEN** synthesis messages are built
- **THEN** historical context SHALL be marked untrusted, potentially stale, and subordinate to fresh tool output.

---

### Requirement: Raw prompt persistence shall obey configuration

Assistant-session persistence SHALL not store full raw prefixed context unless explicitly configured.

#### Scenario: Raw storage disabled

- **GIVEN** `store_raw=false`
- **WHEN** an assistant session is created
- **THEN** persistence SHALL store a redacted summary/hash/length and context references, not the full raw prompt or context body.

#### Scenario: Raw storage enabled

- **GIVEN** `store_raw=true`
- **WHEN** an assistant session is created
- **THEN** only the configured/redacted current request MAY be stored; full workspace/chat context SHALL NOT be duplicated.

#### Scenario: Historical rows remain readable

- **GIVEN** legacy assistant-session rows exist
- **WHEN** the new repository reads them
- **THEN** it SHALL remain backward compatible.

---

### Requirement: Assistant turns shall be prepared once and executed exactly

Classification, planning, preview, approval, and execution SHALL share one immutable prepared turn.

#### Scenario: Auto-execute classifies and plans once

- **GIVEN** safe auto-execute mode
- **WHEN** one user turn completes
- **THEN** classifier and planner SHALL each be invoked exactly once.

#### Scenario: Plan-only returns exact prepared plan

- **GIVEN** plan-only mode
- **WHEN** preparation completes
- **THEN** the rendered plan SHALL be the canonical persisted plan associated with a plan hash.

#### Scenario: Approval executes exact approved plan

- **GIVEN** a prepared plan is previewed and approved
- **WHEN** execution begins
- **THEN** the exact stored plan object/hash SHALL be executed without reclassification or replanning.

#### Scenario: Hash mismatch fails closed

- **GIVEN** pending plan content or identity changes after preview
- **WHEN** approval occurs
- **THEN** execution SHALL be refused and an audit event SHALL record the mismatch.

#### Scenario: Cancellation clears pending prepared state

- **GIVEN** a prepared plan is pending
- **WHEN** user cancels
- **THEN** pending plan identity and context SHALL be cleared without executing tools.

---

### Requirement: Workspace integration shall not block TUI operation

Workspace recording and loading SHALL degrade safely.

#### Scenario: Busy input is not recorded as accepted work

- **GIVEN** the router is busy
- **WHEN** another input is submitted
- **THEN** it SHALL be rejected before accepted-input persistence, or explicitly stored as `NOT_EXECUTED`.

#### Scenario: Workspace record failure does not block command

- **GIVEN** workspace persistence raises
- **WHEN** a command/chat request is otherwise valid
- **THEN** execution SHALL continue and a non-blocking warning SHALL be shown/logged.

#### Scenario: Corrupt workspace does not block TUI startup

- **GIVEN** latest workspace JSON is malformed or invalid
- **WHEN** TUI starts
- **THEN** the file SHALL be quarantined/preserved, a temporary or new safe workspace SHALL be used, and the TUI SHALL mount with a warning.

# Phase 3 — Runtime correctness

### Requirement: Data-ensure locking shall be atomic and owner-safe

Data provisioning SHALL use an atomic mutually exclusive lock.

#### Scenario: Only one ensure flow wins

- **GIVEN** two processes ensure the same symbol/date concurrently
- **WHEN** lock acquisition completes
- **THEN** exactly one process SHALL execute provisioning actions.

#### Scenario: Stale owner cannot delete replacement lock

- **GIVEN** a stale data lock is replaced
- **WHEN** old owner releases
- **THEN** replacement lock SHALL remain until its owner releases.

---

### Requirement: Explicit invalid dates shall fail before side effects

Malformed explicit dates SHALL NOT be replaced with current date.

#### Scenario: Invalid date causes validation error

- **GIVEN** an explicit invalid date such as `2026-13-40`
- **WHEN** analysis/data provisioning is requested
- **THEN** a validation error SHALL be returned.

#### Scenario: Invalid date runs no actions

- **GIVEN** an invalid explicit date
- **WHEN** the request fails validation
- **THEN** sync, build, feature, and score action call counts SHALL remain zero.

#### Scenario: Missing date follows default policy

- **GIVEN** no date is supplied
- **WHEN** date normalization runs
- **THEN** the configured default/today policy MAY resolve a date.

---

### Requirement: Cache hits shall require complete supporting evidence

Candidate-score existence alone SHALL NOT qualify as a READY cache hit.

#### Scenario: Orphan score is rejected

- **GIVEN** candidate score exists but feature snapshot is missing
- **WHEN** cache eligibility is evaluated
- **THEN** cache hit SHALL be rejected with reason.

#### Scenario: Insufficient canonical history rejects cache

- **GIVEN** score exists but canonical bars are below policy threshold
- **WHEN** cache eligibility is evaluated
- **THEN** cache hit SHALL be rejected.

#### Scenario: Required benchmark missing rejects cache

- **GIVEN** relative-strength policy requires benchmark data and benchmark bars are insufficient
- **WHEN** cache eligibility is evaluated
- **THEN** cache hit SHALL be rejected.

#### Scenario: Bad quality or lineage rejects cache

- **GIVEN** supporting quality is failed or lineage does not meet policy
- **WHEN** cache eligibility is evaluated
- **THEN** cache hit SHALL be rejected.

#### Scenario: Complete evidence preserves fast cache hit

- **GIVEN** score is fresh and all supporting conditions pass
- **WHEN** ensure runs
- **THEN** no provisioning action SHALL run and cache hit SHALL be reported.

---

### Requirement: Artifact references shall correspond to confirmed persisted artifacts

Research outputs SHALL not emit a reference merely because a default value was used.

#### Scenario: Missing sector snapshot has no sector reference

- **GIVEN** shortlist generation finds no persisted sector snapshot
- **WHEN** output is produced
- **THEN** no sector snapshot artifact ref SHALL be emitted.

#### Scenario: Missing sector snapshot is disclosed

- **GIVEN** no sector snapshot exists
- **WHEN** shortlist output is produced
- **THEN** `missing_data` and caveats SHALL disclose the omitted/defaulted sector component.

#### Scenario: Audit references match tool payload references

- **GIVEN** a research answer audit is persisted
- **WHEN** artifact refs are inspected
- **THEN** each ref SHALL originate from an executed tool output backed by confirmed data.

---

### Requirement: Public command and operational event semantics shall be consistent

#### Scenario: `/new` creates workspace

- **WHEN** `/new` is submitted
- **THEN** it SHALL behave as `/context new`.

#### Scenario: `/chat new` creates chat session

- **WHEN** `/chat new` is submitted
- **THEN** it SHALL start a new chat session without creating a workspace.

#### Scenario: TODO visibility events emit only on transitions

- **GIVEN** repeated layout applications do not change visibility
- **WHEN** layout is recomputed
- **THEN** no additional visible/hidden event SHALL be emitted.

---

### Requirement: Model session overrides shall be isolated

A session-scoped model override SHALL affect only the intended session/context.

#### Scenario: Two sessions use different overrides

- **GIVEN** session A selects `small` and session B selects `reasoning`
- **WHEN** both resolve routes in one process
- **THEN** each SHALL receive its own profile.

#### Scenario: Session cleanup removes override

- **GIVEN** a session override exists
- **WHEN** the session ends
- **THEN** the override SHALL no longer affect future sessions.

#### Scenario: Workspace override remains workspace-scoped

- **GIVEN** different workspaces have different overrides
- **WHEN** active workspace changes
- **THEN** effective workspace profile SHALL follow the active workspace.

---

### Requirement: Model-generated research answers shall provide source references

Model-generated research answers SHALL not pass solely because runtime auto-filled references after parsing.

#### Scenario: Missing model refs triggers fallback or failure

- **GIVEN** a model-generated research answer omits `grounded_source_refs`
- **WHEN** groundedness validation runs
- **THEN** the answer SHALL be rejected and deterministic fallback or fail-closed behavior SHALL occur.

#### Scenario: Deterministic fallback may add bounded refs

- **GIVEN** deterministic fallback builds an answer from tool payloads
- **WHEN** it assigns refs
- **THEN** only bounded refs from executed tools/artifacts SHALL be used.

# Phase 4 — CI, evaluation, and release governance

### Requirement: Golden evaluation corpus shall be available in installed packages

Default evaluation SHALL not depend on repository-relative paths.

#### Scenario: Wheel installation runs fixture eval

- **GIVEN** vnalpha wheel is installed in an isolated environment
- **WHEN** `vnalpha eval research-answers --ci` runs
- **THEN** packaged fixtures SHALL be discovered and evaluated.

#### Scenario: Missing package data fails packaging tests

- **GIVEN** golden files are absent from built distribution
- **WHEN** installed-package evaluation runs
- **THEN** CI SHALL fail.

---

### Requirement: Evaluation shall support fixture-contract and runtime-replay modes

#### Scenario: Fixture-contract mode remains deterministic

- **GIVEN** typed static observations
- **WHEN** fixture evaluation runs
- **THEN** it SHALL validate fixture integrity without network or live warehouse calls.

#### Scenario: Runtime-replay uses production boundaries

- **GIVEN** a runtime-replay case with deterministic fakes/seeded warehouse
- **WHEN** evaluation runs
- **THEN** it SHALL exercise production preparation, planning, execution, synthesis, groundedness, policy, and audit interfaces.

#### Scenario: Runtime replay prohibits network

- **GIVEN** runtime-replay mode
- **WHEN** any code attempts external network access
- **THEN** the case SHALL fail.

#### Scenario: Every research intent has runtime seed case

- **GIVEN** the runtime corpus
- **WHEN** coverage is checked
- **THEN** every supported research-intelligence intent SHALL have at least one passing case.

#### Scenario: Negative cases are enforced

- **GIVEN** cases for context injection, missing refs, fabricated numbers, invalid dates, missing sector data, and unsafe scenario wording
- **WHEN** runtime evaluation runs
- **THEN** expected rejection, disclosure, or deterministic rewrite behavior SHALL be asserted.

---

### Requirement: Root commands and CI shall enforce all hardening gates

#### Scenario: Root Make targets exist

- **WHEN** root Makefile is inspected
- **THEN** `repo-hygiene`, `eval-research-answers`, `eval-research-runtime`, and `verify-hardening` SHALL exist.

#### Scenario: CI runs required gates

- **WHEN** a PR changes vnalpha, OpenSpec, packaging, scripts, or workflows
- **THEN** CI SHALL run hygiene, secret scan, focused tests, lint, full tests, R4, packaging verification, fixture eval, runtime eval, installed-package eval, and OpenSpec verification.

#### Scenario: Failure uploads diagnostics

- **GIVEN** a required CI gate fails
- **WHEN** workflow completes
- **THEN** concise diagnostic logs SHALL be available.

#### Scenario: Required check failure blocks merge

- **GIVEN** any required check is failing or absent
- **WHEN** merge is attempted
- **THEN** repository policy SHALL block merge.

---

### Requirement: OpenSpec completion shall be evidence-consistent

A deterministic verifier SHALL prevent task and validation state from diverging.

#### Scenario: Checked tasks with pending validation fail

- **GIVEN** tasks are checked while validation states commands were not run
- **WHEN** OpenSpec verifier runs
- **THEN** it SHALL exit nonzero.

#### Scenario: Unchecked non-deferred tasks block completion

- **GIVEN** a change is marked completion-ready with unchecked tasks
- **WHEN** verifier runs
- **THEN** it SHALL fail.

#### Scenario: Deferred task requires structured record

- **GIVEN** a task is deferred
- **WHEN** verifier reads it
- **THEN** reason, owner, dependency, risk window, and approval reference SHALL be required.

#### Scenario: Validation evidence identifies tested commit

- **GIVEN** a validation command is marked passed
- **WHEN** evidence is parsed
- **THEN** timestamp, exact command, exit status, result summary, and tested commit SHA SHALL be present.

#### Scenario: Archive readiness requires complete evidence

- **GIVEN** an OpenSpec change is proposed for archive
- **WHEN** required evidence is missing
- **THEN** archive readiness SHALL fail.

---

### Requirement: Final hardening validation shall pass as one reproducible gate

#### Scenario: `verify-hardening` passes

- **GIVEN** all implementation tasks are complete
- **WHEN** `make verify-hardening` runs on the final commit
- **THEN** every required hardening, test, evaluation, packaging, and OpenSpec check SHALL exit zero.

#### Scenario: Validation is attached to final SHA

- **GIVEN** final implementation is ready for review
- **WHEN** `validation.md` is inspected
- **THEN** evidence SHALL refer to the final tested commit SHA and successful required GitHub checks.

#### Scenario: No unresolved P0/P1 remains

- **GIVEN** the OpenSpec is ready to archive
- **WHEN** `review.md` findings are reconciled
- **THEN** every P0/P1 SHALL be closed or have an explicitly approved defer record permitted by this specification.