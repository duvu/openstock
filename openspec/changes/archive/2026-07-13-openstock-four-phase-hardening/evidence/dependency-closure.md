# Final local dependency-closure gate

The dependency branch re-ran the repository hardening matrix after correcting
CI portability, secret-scan failure handling, approval replay, model routing,
completion evidence enforcement, and standalone Debian packaging.

The final local gate consists of repository hygiene, redacted fail-closed secret
scanning with and without ripgrep, Ruff, the complete vnalpha test suite, R0/R2/R4
verification, installed-package evals, runtime replay evals, and strict OpenSpec
validation. External PR and GitHub required-check evidence is intentionally kept
under task 6.13 until the published final SHA is green.
