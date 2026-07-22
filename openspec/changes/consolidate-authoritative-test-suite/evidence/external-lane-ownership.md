# Non-pytest validation ownership

Issue #348 is development-only. It owns no added GitHub Actions job, required
gate, path router or hosted validation evidence; its only workflow-file action
is removal of the earlier #348 router to restore the pre-#349 generic jobs.

| Concern | Local owner | Selection rule |
| --- | --- | --- |
| One contract | `make test-loop TEST=<node>` | normal edit loop |
| `vnalpha` domain | `make test-vnalpha-{data,research,application}` | affected source contract |
| Frozen `vnalpha` candidate | `make test-vnalpha` | once, after local changes are frozen |
| Package acceptance | existing manual package commands | only package, installation, dependency-layout, service-unit or release inputs |

The restored generic workflow and merge-gate policy remain outside this change
and are not a prerequisite for #348 closure.
