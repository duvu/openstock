# External validation-lane ownership

This record assigns the non-`vnalpha` lanes that are intentionally outside the
pytest suite manifest. The ownership is narrow and has no duplicate aggregate
runner.

| Lane | Canonical owner | Routing trigger | Contract boundary |
| --- | --- | --- | --- |
| `vnstock-contracts` | `openstock-ci` job `vnstock` | `domains` contains `vnstock-contracts` or `full` is true | provider capability, provider runtime hardening, corporate-action, and built-in-provider contracts; then source/wheel build |
| `packaging` | `vnalpha-debian-package` workflow job `package` | package source, `vnalpha/src/**`, project metadata/lockfile, Makefile, or workflow change | source contract, packaging groups, Debian build, installed offline runtime, install/upgrade/broken-wheel rollback |

The `vnstock` job's exact contract selection is the six paths listed in
`.github/workflows/openstock-ci.yml` under `Provider and canonical contract tests`;
it is not included in a `vnalpha` pytest plan. The Debian workflow is
path-filtered because it is an additional package-acceptance workflow, not a
required check that must exist for documentation-only pull requests.

`make verify-vnalpha-package` remains the local/release equivalent and owns the
source-contract, structural, package-build and built-artifact checks once per
invocation. `make verify-hardening` calls that target once after the canonical
`vnalpha` runner and one `openstock-verify --ci` invocation.
