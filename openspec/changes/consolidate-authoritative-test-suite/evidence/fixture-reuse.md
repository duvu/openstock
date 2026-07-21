# DuckDB fixture-reuse evidence

The session-scoped `migrated_warehouse_template` runs the current migrations
once per pytest worker. `migrated_warehouse_connection_factory` copies that
closed DuckDB file into the requesting test's temporary directory and returns a
fresh connection. `migrated_warehouse_connection` is the one-copy convenience
fixture used by compatible application-contract tests.

The authoritative isolation contract is
`tests/test_migrated_warehouse_fixture.py::test_migrated_warehouse_copies_isolate_mutations`.
It writes `symbol_master` through one copy and proves a separately copied
warehouse remains empty. The command below passed in 2.0 seconds on this branch:

```bash
make test-loop TEST=tests/test_migrated_warehouse_fixture.py::test_migrated_warehouse_copies_isolate_mutations
```

The fixture is used only by `test_assistant_completion_gate.py` and
`test_command_completion_gate.py`, which require a current schema but do not
assert fresh migration, idempotency, crash, reopen, locking, multiprocessing,
upgrade or rollback behavior.
