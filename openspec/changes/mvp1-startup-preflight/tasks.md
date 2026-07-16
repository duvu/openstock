# Tasks: MVP1 startup and preflight (issue #166)

- [x] 1. Add `--mvp1` mode + MVP1 checks (service, warehouse path/disk,
      migration readiness, knowledge, LLM, backup/restore, release) to
      `openstock-verify`; honour `--ci`.
- [x] 2. Add `openstock-mvp1-start`: validate/create paths, ensure service
      health, migrate warehouse, run preflight, launch TUI or print command;
      idempotent and non-destructive.
- [x] 3. Register the new script in the verify syntax check; add
      `mvp1-start`/`verify-mvp1` Makefile targets.
- [x] 4. Document the one-command startup in README and OPERATOR runbook.
- [x] 5. Add packaging tests: `--mvp1 --ci` exits 0 with no `[FAIL]`, startup
      help/rejection, and an idempotent-startup fixture test with fake binaries.
- [ ] 6. Record an installed-host smoke run (start, preflight, TUI launch, clean
      restart) + final CI on the merge SHA in `validation.md` (pending PR/host).
