# Dependency closure evidence

Recorded at `2026-07-13T01:04:00Z` against base commit
`873425d62eb1aea7fc7519b62fde22ac195c7872` plus the dependency-closure
working tree.

| Gate | Result |
|---|---|
| Sandbox, command, lifecycle, approval, output, and Docker policy tests | PASS |
| Approval replay regression | PASS; a terminal job rejects a second execution |
| Session-scoped model routing | PASS for classification and synthesis |
| Real Docker hardened-boundary probe | PASS; network disabled, read-only root, UID 65532, all capabilities dropped, no-new-privileges, bounded PID/CPU/memory, and validated writable output |
| Full vnalpha suite | PASS at 100% |
| Ruff check and format | PASS |
| R4 acceptance | PASS |
| `openstock-verify --ci` | PASS; 16 OK, one environment warning, zero failures |
| Standalone Debian package | PASS; 31 bundled wheels, clean no-index venv install, both eval suites, 55 package checks |
| OpenSpec strict validation | PASS |

The real Docker probe used `DockerRunner(SubprocessDockerCommand(), "Linux")`
with a local digest-pinned image and `build_docker_run_argv`. It asserted all
required hardened argv controls before accepting the zero exit and the two
container-written output artifacts. No image pull or alternate runtime was
used.
