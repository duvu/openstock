# Validation: deterministic fallback observability

## Status

```text
Implementation candidate: PR #387 at 85083c751e7ba695c282b60c410088698a8179de
Focused owning contract: pass
Final repository and hosted lifecycle gates: blocked; tracked by #388
Phase gates: pending
Ready to archive: pending
```

## Evidence

| UTC timestamp | Commit SHA | Phase/task | Command | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| 2026-07-22T17:18:34Z | `85083c751e7ba695c282b60c410088698a8179de` | 1.1, 1.2, 2.1, 2.2, 2.3, 3.1, 3.2, 4.1, 4.2 | `PYTHONPATH=/home/beou/IdeaProjects/openstock/.worktrees/assistant-fallback-observability-followup/vnalpha/src make test-loop TEST=tests/test_synthesizer_and_app.py::TestAnswerSynthesizer::test_synthesizer_preserves_read_only_results_when_degraded` | 0 | 1 passed; the owning contract covers deterministic safe-result fallback, fail-closed cases, bounded lifecycle evidence, connected and managed lifecycle persistence, CLI/TUI warning data, and the planner-to-market.get_regime fallback path. | local command transcript |

## Remaining closure gate

Task 4.3 remains open. On PR #387, `openstock-ci` run 29941560038,
`issue-closure-contract` run 29941560145, and source-export run 29941560394
all failed before any job step began; GitHub returned no failed-job log. The
local final repository gate is independently blocked because the authoritative
test inventory contains 222 contracts (cap 220) and includes an unclassified
maintenance test. Issue #388 owns restoring those gates, then rerunning them
at the final PR SHA and recording successful closure evidence.
