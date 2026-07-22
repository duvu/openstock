# Authoritative inventory disposition

The pre-consolidation baseline was 3,303 collected pytest nodes across 275
`vnalpha` test files. The current local manifest contains 220 exact source
nodes: 120 application, 76 data and 24 research. `run-test-suite.py --plan`
emits 220 unique nodes.

| Disposition | Scope | Evidence |
| --- | --- | --- |
| KEEP | Every node in `vnalpha/tests/suites/authoritative.toml` | One public or distinct approved risk contract per exact source node. |
| MERGE | Three duplicate Textual app-mount smoke tests | One workspace-context startup owner mounts the same public application path. |
| REPLACE | Broad file-glob suite and aggregate wrappers | Local domain selection resolves exact manifest nodes. |
| DELETE | Legacy duplicate, issue-labelled, literal and implementation-detail test nodes absent from the source-aware inventory | The validator rejects any remaining unclassified `test_*` definition. |

The validator uses the test file path as part of each definition identity. A
matching function or method name in another test file cannot satisfy a manifest
entry. This caught a moved intent test and five unrecorded current-main nodes
before a domain lane could execute.

Distinct retained legacy risks include point-in-time benchmark dates and
minimal migration; current-session lifecycle, trace persistence, credential
redaction and unsafe-tool refusal; pipeline candidate production, audit
reference integrity, cache eligibility, process lock exclusion and grounded
source rejection.
