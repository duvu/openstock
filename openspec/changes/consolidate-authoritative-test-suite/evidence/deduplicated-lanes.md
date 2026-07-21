# Compact lane evidence

Working branch: `feat/issue-348-test-feedback-loop`

The former broad file-glob runner, standalone R0/R4 targets and separate smoke
job have been deleted. The only aggregate vnalpha plan is the authoritative
contract inventory; selected domains are disjoint subsets of that inventory.

| Check | Result |
| --- | ---: |
| Authoritative contracts | 211 |
| Data contracts | 73 |
| Research contracts | 24 |
| Application contracts | 114 |
| Actual collected vnalpha nodes | 211 |
| Manifest/collection difference | 0 |
| R0/R4/Phase aggregate wrappers | 0 |
| Debian trigger for ordinary `vnalpha/src/**` | absent |

Commands recorded without executing a broad test body:

```bash
cd vnalpha
uv run python ../scripts/run-test-suite.py --plan
uv run pytest --collect-only -q -o addopts='--import-mode=importlib'
```

The normal developer command remains:

```bash
make test-loop TEST=tests/path.py::test_owner
```

It is bounded by 60 seconds and does not invoke aggregate, package, evaluation,
R0 or R4 validation.
