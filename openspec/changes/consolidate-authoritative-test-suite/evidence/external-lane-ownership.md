# Non-pytest validation ownership

Issue #348 is development-only. It owns no GitHub Actions job, required gate,
path router, workflow artifact or hosted validation evidence.

| Concern | Local owner | Selection rule |
| --- | --- | --- |
| One contract | `make test-loop TEST=<node>` | normal edit loop |
| `vnalpha` domain | `make test-vnalpha-{data,research,application}` | affected source contract |
| Frozen `vnalpha` candidate | `make test-vnalpha` | once, after local changes are frozen |
| Package acceptance | existing manual package commands | only package, installation, dependency-layout, service-unit or release inputs |

The generic workflow and merge-gate policy remain outside this change and are
not a prerequisite for #348 closure.
