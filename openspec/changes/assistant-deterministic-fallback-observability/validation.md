# Validation: deterministic fallback observability

## Status

```text
Implementation candidate: 02f57a0af1c7749063b28a8543476a5402735f47 on pull request 387
Focused owning contract: pass
Final repository and hosted lifecycle gates: blocked; tracked by #388
Phase gates: pending
Ready to archive: pending
```

## Evidence

| UTC timestamp | Commit SHA | Phase/task | Command | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| 2026-07-22T17:29:24Z | `02f57a0af1c7749063b28a8543476a5402735f47` | 1.1, 1.2, 2.1, 2.2, 2.3, 3.1, 3.2, 4.1, 4.2 | `PYTHONPATH=/home/beou/IdeaProjects/openstock/.worktrees/assistant-fallback-observability-followup/vnalpha/src make test-loop TEST=tests/test_synthesizer_and_app.py::TestAnswerSynthesizer::test_synthesizer_preserves_read_only_results_when_degraded` | 0 | 1 passed; the owning contract covers safe fallback, fail-closed cases, bounded lifecycle evidence, connected and managed persistence, CLI/TUI warnings, planner-to-market.get_regime fallback, raw-model-payload exclusion, and trace-evidence retention after audit degradation. | local command transcript |

## Remaining closure gate

Task 4.3 remains open. For implementation SHA `02f57a0af1c7749063b28a8543476a5402735f47`,
`openstock-ci` run 29942677636, `issue-closure-contract` run 29942672681,
and source-export run 29942677634 failed before any job step began; GitHub
returned no failed-job log. The local final repository gate is independently
blocked because the authoritative test inventory contains 222 contracts (cap
220) and includes an unclassified maintenance test. Issue #388 owns restoring
those gates, then rerunning them at the final PR SHA and recording successful
closure evidence.
