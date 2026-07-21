## Context

vnalpha collected 3,296 tests across 276 files at the recorded baseline.
That collection contains issue-number, R0/R4/Phase, adapter and schema
duplication that makes ordinary development slow without increasing confidence.
Issue #348 requires 180–220 authoritative public/risk contracts, with a hard
cap of 250. The normal local loop is one owning contract and must finish or
time out within 60 seconds.

The repository already provides root Make targets, GitHub Actions, package
acceptance scripts and scripts/check-repo-consistency.py. This change makes
those existing seams consume one bounded inventory; it does not change product
behavior or the read-only research boundary.

## Decisions

### 1. One TOML inventory owns every retained vnalpha contract

vnalpha/tests/suites/authoritative.toml contains one [[contract]] table for
each retained exact pytest node. It records a stable identifier and one of
application, data or research. The current inventory has 213 entries.

The parser rejects malformed TOML, non-normalized nodes, missing files,
duplicate identifiers, duplicate nodes, unsupported domains and a count outside
180–220 or above the hard cap of 250. Exact node collection remains pytest's
responsibility; an invalid node makes the selected pytest command fail.

### 2. One small runner resolves all or selected domains

scripts/run-test-suite.py validates the inventory, prints a plan for review,
or invokes pytest once with the selected exact nodes. make test-vnalpha is
reserved for final candidates and release validation. The three domain targets
use --domain data, --domain research or --domain application.

make test-loop TEST=<nodeid> remains independent of the inventory runner and
is the sole edit-test command. It fails fast after 60 seconds. It must not
expand into aggregate, packaging, evaluation, R0 or R4 work.

### 3. Tests and checks receive an explicit disposition

The collection inventory records KEEP for each manifest node. All other
collected nodes receive DELETE, MERGE or REPLACE evidence before they are
removed. Issue-number, R0/R4/Phase and file-glob wrapper names are not durable
contract identities. A retained legacy risk node is moved or renamed only after
its specific public/risk contract is preserved.

The obsolete broad suite manifest, its runner tests and its duplicate
repository-check tests are deleted. The real consistency command is the
authoritative checker; it runs unconditionally in CI.

### 4. CI routes domains without a smoke duplicate

scripts/classify-test-impact.py is the policy source for normalized changed
paths. Docs/OpenSpec-only work selects only consistency. Ordinary vnalpha
source work selects compact vnalpha domains. Changes to tests, fixtures,
manifests, routing, Make or workflow files select the complete authoritative
inventory because they can change validation semantics.

The workflow has no separate smoke lane, so a PR never runs a second R0/R4
subset around the same contracts. The Required job accepts only success or
GitHub's deliberate skipped conclusion.

### 5. Debian acceptance stays package-owned

The Debian workflow triggers for packaging, Make, dependency-layout and its own
workflow configuration. It does not trigger merely because vnalpha/src/**
changes. Build/install/upgrade checks remain release and package-input gates.

### 6. Migrated DuckDB fixture reuse remains isolated

The existing session fixture creates a migrated template once, and compatible
tests receive a copied warehouse file. Fresh migration, idempotency, upgrade,
rollback, crash, reopen, locking and multiprocessing contracts retain dedicated
inputs. A mutation-isolation contract proves copies do not share state.

## Risks and mitigations

- Removing a unique financial or security boundary is prevented by recording a
  retained contract node before deletion.
- An omitted or stale inventory node is prevented by the consistency checker
  and the selected pytest command.
- Incorrect path routing fails closed for unknown and infrastructure paths.
- Package validation remains available for release/package inputs without
  charging ordinary source changes its cost.

## Validation and closure

The final candidate must strictly validate this OpenSpec, run the bounded owner
test and compact affected-domain lane locally, and record the complete
authoritative suite and any routed package validation honestly. GitHub Actions
must pass on the exact pushed commit before #348 is closed and the change is
archived.
