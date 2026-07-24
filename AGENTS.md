# Agent notes for the OpenStock repository

OpenStock contains `vnalpha`, `vnstock`, OpenSpec, packaging and local development assets.

## Repository structure

| Path | Responsibility |
|---|---|
| `vnalpha/` | Research workspace, DuckDB pipeline, CLI/TUI, assistant and tests. |
| `vnstock/` | Provider-independent market-data library/service. |
| `openspec/` | Active changes, archive and accepted specifications. |
| `packaging/` | Package and deployment assets. |
| `Makefile` | Repository commands. |
| `CODING.md` | Normative coding conventions. |
| `TESTING.md` | Normative testing policy. |

## Product boundary

OpenStock is research-only. Do not add broker login, order placement, account mutation, margin, transfers or autonomous trading execution. Deterministic application services own provisioning and mutation. Fresh warehouse and tool output outrank summaries and model prose.

## Development method

OpenStock is spec-first for material changes, but it is not a TDD project.

```text
understand/specify the public contract
→ implement the smallest complete change
→ inspect or smoke-check
→ add/update the authoritative contract test
→ run focused coding and test checks once
```

Do not write failing tests as process ceremony or design production code around test-only seams.

## Debugging evidence

For every user-requested debugging, diagnosis, failure investigation, or log
analysis task, an agent MUST collect current evidence with the repository log
triage tool before source-level diagnosis:

```bash
python scripts/openstock-log-triage.py --max-lines 1000
```

- Include `--path <relevant-log>` whenever the failing surface or log location is
  known.
- For GitHub Actions failures, discover the relevant run and include
  `--github-run <run-id>`; the tool reads only failed-job output through `gh`.
- Treat the tool output as observed evidence, not a claimed root cause. Use it to
  choose the bounded reproduction and then complete normal runtime/manual QA.
- Re-run the relevant triage command after a fix when the original failure source
  can be inspected again. Never use `--fail-on-findings` as a substitute for
  diagnosis or testing.

## Coding rules for agents

[`CODING.md`](CODING.md) is the single normative coding source. Read it when adding, changing or reviewing Python code. Do not duplicate the full policy in issues or implementation notes.

Mandatory summary:

- all imports are module-level and placed at the top of the file;
- never add imports inside functions, methods, classes, conditions or after executable code;
- order imports as standard library, third-party, then project-local;
- no wildcard or unused imports;
- fix circular dependencies architecturally; never hide them with a local import;
- use Ruff formatting, Python naming conventions and typed public boundaries;
- prefer typed models/enums over free-form dictionaries and magic strings;
- keep functions focused and dependency direction one-way;
- catch specific exceptions and use logging instead of `print()`;
- avoid mutable global runtime state and generic `utils`/`helpers` modules.

For every touched Python file, run:

```bash
make lint-files PROJECT=vnalpha FILES="src/path/file.py tests/path/test_file.py"
```

Use `PROJECT=vnstock` for vnstock files. An agent MUST NOT complete work while a touched file contains a local/mid-file import or fails the focused coding check.

## Testing rules for agents

[`TESTING.md`](TESTING.md) is the single normative testing source. Read it when adding, changing, deleting or reviewing tests.

Mandatory summary:

- optimize for a small set of meaningful contract tests, not maximum coverage or edge-case enumeration;
- one public feature/function or independent risk contract owns one authoritative test;
- do not test private helpers, branches, issue numbers or the same behavior across multiple layers;
- use one table-driven test for equivalent cases;
- existing contract: expected net test-count change `<= 0`;
- new contract: maximum `+1` authoritative test;
- delete or merge duplicate tests; never hide them in nightly suites;
- a proposed test without a distinct contract MUST NOT be added;
- normal development runs one owning test with a hard 60-second limit.

Use:

```bash
make test-loop TEST=tests/path/to/test_file.py::test_contract
```

Do not run full suites, R0/R4, `verify-hardening`, packaging, research evals, repository-wide checks or GitHub Actions after each patch. Broader local validation runs once only when a frozen candidate and material risk justify it.

Before completing a behavior-changing PR, report:

```text
contract_id:
authoritative_test:
tests_removed_or_merged:
net_test_count_change:
net_test_LOC_change:
local_validation_command:
local_validation_result:
```

## Implementation guidance

[`vnalpha/docs/common-implementation-failures.md`](vnalpha/docs/common-implementation-failures.md) is a reference catalogue, not mandatory reading. Read only sections directly relevant to the changed contract or observed failure.

- verify runtime semantics rather than file or command presence;
- inspect real callable signatures and typed boundaries;
- preserve truthful statuses, evidence, remediation and fail-closed behavior;
- inspect affected surfaces, but test shared behavior once at its owner;
- create a follow-up issue for intentionally deferred defects.

## OpenSpec workflow

- `openspec/active-changes.yaml` is the registry for non-archived changes.
- Search active changes, archive and accepted specs before creating new work.
- Update overlapping work instead of creating parallel remediation specs.
- Never mark tasks complete from prose alone; attach the evidence required by the task.

Relevant slash workflows when explicitly requested:

- `/opsx-propose` — create or revise proposal/design/tasks.
- `/opsx-apply` — implement an active change in dependency order.
- `/opsx-explore` — investigate without implementation.
- `/opsx-archive` — archive completed or superseded work and synchronize accepted specs.
