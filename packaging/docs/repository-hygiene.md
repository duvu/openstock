# Repository hygiene

Run `make repo-hygiene` from the repository root. The verifier inspects tracked paths and fails for runtime state, generated metadata, Python caches, test/lint caches, bytecode, and unapproved Git mode `160000` entries.

Approved submodules are listed one repository-relative path per line in `packaging/config/approved-submodules.txt`. The file is intentionally empty until a submodule has an explicit ownership and review decision. A path listed there is allowed only for the gitlink check; denied runtime and generated paths remain denied.

Run `packaging/scripts/openstock-secret-scan` to scan tracked files for high-signal private-key and credential-token patterns. Add `--history` when reviewing all reachable Git history. The scanner reports matching paths and exits nonzero; history rewriting is a separate operational decision.
