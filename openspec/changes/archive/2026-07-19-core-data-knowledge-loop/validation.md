# Validation: Core Data and Knowledge Loop

Final implementation SHA: `e4374cab1c4829d9d1b55afbeaec6f6bf7e1008d`

The exact candidate was built as Debian artifact
`vnalpha_0.1.0_amd64.deb` with SHA-256
`c5952ba570e621078e965a17563b9892e4255f6d046e0f80888a58982b3da84b`.
The sanitized clean-host report is published on issue #245.

| UTC timestamp | Commit SHA | Task/gate | Command or inspection | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| 2026-07-19T05:53:30Z | e4374cab1c4829d9d1b55afbeaec6f6bf7e1008d | 1.1–1.5 | `cd vnalpha && uv run --extra dev pytest -q` | 0 | Complete vnalpha suite passed, including daily status, idempotency, dry-run, non-session and diagnostics paths | exact-candidate command transcript and PR #247 CI |
| 2026-07-19T05:53:30Z | e4374cab1c4829d9d1b55afbeaec6f6bf7e1008d | 2.1–2.4 | installed issue tests and runtime retrieval acceptance | 0 | 42 issue tests passed; selective projection, lossless entity migration and point-in-time group retrieval passed | clean-host acceptance transcript and issue #245 report |
| 2026-07-19T05:53:30Z | e4374cab1c4829d9d1b55afbeaec6f6bf7e1008d | 3.1–3.4 | `PIP_INDEX_URL=https://pypi.org/simple make verify-vnalpha-package` | 0 | 60 package checks passed; clean Debian 12 install loaded disabled units and stable lock contention exited 75 | Debian artifact and clean-host acceptance transcript |
| 2026-07-19T05:53:30Z | e4374cab1c4829d9d1b55afbeaec6f6bf7e1008d | 4.1–4.2 | `python scripts/check-repo-consistency.py` | 0 | Canonical issue #238 roadmap URL and historical-document rules passed | exact-candidate command transcript |
| 2026-07-19T05:53:30Z | e4374cab1c4829d9d1b55afbeaec6f6bf7e1008d | 5.1–5.3 | exact-candidate clean-host acceptance inspection | 0 | Exact package installed; fixture provisioning and failure isolation, repeat execution, CLI/TUI/assistant consumption, timer state and research-only boundary passed | issue #245 comment 5014594723 |
| 2026-07-19T05:53:30Z | e4374cab1c4829d9d1b55afbeaec6f6bf7e1008d | 6.1–6.3 | `gh pr checks 247` and issue-state inspection | 0 | All five required checks passed; child issues closed in dependency order; #245 closed before #238 and #235 closed not planned | PR #247 and GitHub issue timeline |

The unrestricted live-provider probe encountered external proxy/Vietcap
timeouts and was stopped during another network-bound test. It is diagnostic
only and is not represented as successful live-data acceptance. Fixture,
offline, package and clean-host results remain the completion evidence.
