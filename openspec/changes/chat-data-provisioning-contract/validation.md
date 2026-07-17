# Validation Ledger

PR #168 merged the issue #163 implementation with required CI green. Current
follow-on validation for issue #175 covers nullable, malformed, duplicate,
empty, oversized, and service-unavailable remediation inputs. The shared
operation returns typed failure without exposing raw provider exceptions and
bounds remediation to eight items, 512 characters per item, and 2,048 total
characters.

| Command | Result |
|---|---|
| `cd vnalpha && uv run pytest -q tests/test_issue_163_chat_provisioning.py` | `18 passed` |
| `openspec validate chat-data-provisioning-contract --strict` | valid |

Exact-candidate installed-host acceptance remains owned by #162/#181 and is not
inferred from these focused tests.
