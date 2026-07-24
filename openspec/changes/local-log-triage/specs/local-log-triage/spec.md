## ADDED Requirements

### Requirement: Read-only bounded log intake

The `openstock-log-triage` script SHALL analyze repeatable explicit log paths and
its documented local OpenStock defaults without changing files, services, GitHub
state, or provider state. It SHALL limit each input to a bounded tail and report an
unavailable selected source as a finding rather than terminating unrelated analysis.

#### Scenario: Explicit path contains an error record
- **WHEN** an operator provides an existing log file that contains an error record
- **THEN** the script reports a finding with the file source and line location
- **AND** the script does not change the input file

#### Scenario: Selected source is unavailable
- **WHEN** an operator provides a missing log path
- **THEN** the script reports an `INPUT` finding that identifies the unavailable path
- **AND** completes analysis of every readable source

### Requirement: Sanitized normalized findings

The script SHALL normalize recognized JSONL and plain-text failure signals into
deduplicated findings with a finite severity and category, source evidence, bounded
sanitized text, occurrence count, and a next diagnostic command. It SHALL redact
credentials, authorization values, tokens, passwords, cookies, and secret-bearing
URL components before rendering or serializing findings.

#### Scenario: Repeated credential-bearing failure is analyzed
- **WHEN** a log contains repeated failure lines that include a credential-bearing URL
- **THEN** the output contains one deduplicated finding with the occurrence count
- **AND** the credential is absent from both Markdown and JSON output

### Requirement: Optional failed GitHub Actions intake

When an operator provides a numeric `--github-run` value, the script SHALL request
only failed-job output through `gh run view <run-id> --log-failed`. It SHALL treat a
missing executable, command failure, or unavailable run as a sanitized local finding
and SHALL not perform any GitHub write action.

#### Scenario: Failed CI log reports a lint error
- **WHEN** explicitly selected failed GitHub Actions output includes a Ruff error
- **THEN** the script reports a `CI_STATIC` error finding with a command to reproduce
  the relevant local check

### Requirement: Deterministic render and caller-controlled status

The script SHALL render an ordered Markdown report by default and an equivalent JSON
document when `--json` is selected. It SHALL exit successfully after analysis unless
`--fail-on-findings` is selected and at least one error-severity finding exists.

#### Scenario: Automation requests failure status
- **WHEN** `--fail-on-findings` is selected and analysis finds an error
- **THEN** the script renders the finding report
- **AND** exits with a non-zero status

### Requirement: Codex debugging workflow collects triage evidence

The repository agent instructions SHALL require Codex to invoke
`openstock-log-triage` before source-level work for every user-requested debugging,
diagnosis, failure investigation, or log-analysis task. The instructions SHALL
require explicit local paths and GitHub Actions run IDs when known and SHALL state
that triage evidence does not replace reproduction or manual QA.

#### Scenario: Agent receives a debugging request
- **WHEN** Codex begins a debugging or diagnosis task in this repository
- **THEN** it invokes the log triage tool before source-level diagnosis
- **AND** uses the resulting findings to choose the next bounded investigation
