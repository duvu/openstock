# Compact local lane evidence

The sole aggregate `vnalpha` plan is the authoritative contract inventory;
selected domains are disjoint subsets of that inventory.

| Check | Result |
| --- | ---: |
| Authoritative contracts | 220 |
| Data contracts | 78 |
| Research contracts | 24 |
| Application contracts | 118 |
| Unique nodes in local plan | 220 |
| R0/R4/Phase aggregate wrappers | 0 |

Commands that inspect the local plan without executing test bodies:

```bash
cd vnalpha
uv run --extra dev python ../scripts/run-test-suite.py --plan
```

The normal developer command remains:

```bash
make test-loop TEST=tests/path.py::test_owner
```

It is bounded by 60 seconds and does not invoke aggregate, package, evaluation,
R0 or R4 validation. This change has no CI routing or hosted-lane owner.
