# Authoritative inventory disposition

Baseline collection recorded for issue #348: 3,296 pytest nodes across 276
vnalpha test files. The final authoritative inventory contains 211 exact nodes,
all collected from the reduced tree.

| Disposition | Scope | Evidence |
| --- | --- | --- |
| KEEP | Every node in `vnalpha/tests/suites/authoritative.toml` | One public or distinct approved risk contract per exact node; the manifest and collection both contain 211 nodes. |
| DELETE | Every baseline pytest node absent from the authoritative inventory | 3,085 duplicate, issue-number, R0/R4/Phase, adapter, schema, literal or implementation-detail cases were removed. |
| MERGE | Broad glob manifest, old runner self-tests and duplicate repository-check tests | Replaced by one small parser/checker invoked through repository consistency. |
| REPLACE | Old file-level suite/aggregate/smoke wrappers | Replaced by domain selection over exact inventory nodes. |

The 67 baseline files without a retained node were deleted. In files with a
retained node, AST-guided pruning removed every other collected `test_*`
definition while preserving non-test fixtures and helpers. A static inventory
check rejects a new unclassified test definition before CI selects pytest.

Legacy R0/R4/Phase tests retained only where their contract remains distinct:

- point-in-time benchmark date and minimal migration;
- invalid CLI universe;
- complete session lifecycle, trace persistence, per-session clear isolation,
  credential-safe persistence, unsafe-tool refusal and no local panel dispatch;
- pipeline candidate production, audit reference integrity, cache eligibility,
  process lock exclusion and grounded source rejection.
