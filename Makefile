.DEFAULT_GOAL := help

PROJECT ?= vnalpha

# ──────────────────────────────────────────────
# openstock Makefile
# ──────────────────────────────────────────────

.PHONY: help up-vnstock down-vnstock login-vnstock validate-compose \
        sync features score tui mvp1-start verify-mvp1 install-vnalpha \
        lint-vnalpha test-loop test-vnalpha \
        eval-research-answers eval-research-runtime verify-hardening verify-r0 \
        verify-r2-ci verify-r4 repo-hygiene verify-repo-consistency \
        verify-vnalpha-package build-vnalpha-deb verify-vnalpha-deb

help: ## Show this help message
	@printf "\nopenstock — local research workflow\n\n"
	@printf "  %-22s %s\n" "Target" "Description"
	@printf "  %-22s %s\n" "------" "-----------"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
	@printf "\nUsage: make <target>\n\n"

# ── Canonical Docker deployment ───────────────

up-vnstock: ## Start vnstock-service with the canonical root Compose file
	docker compose up -d vnstock-service

down-vnstock: ## Stop vnstock-service without deleting the shared warehouse
	docker compose stop vnstock-service

login-vnstock: ## Open the credentialed-provider auth/status helper
	docker compose --profile login run --rm vnstock-login status

validate-compose: ## Validate canonical Docker Compose interpolation and schema
	docker compose config --quiet

# ── vnalpha pipeline ──────────────────────────

sync: ## Sync symbols + OHLCV for VN30 + VNINDEX benchmark and build canonical dataset
	vnalpha sync symbols
	vnalpha sync ohlcv --universe VN30 --start 2024-01-01
	vnalpha sync index --symbol VNINDEX --start 2024-01-01
	vnalpha build canonical

features: ## Build features for today
	vnalpha build features --date today

score: ## Score and update watchlist for today
	vnalpha score --date today
	vnalpha watchlist --date today

tui: ## Launch the vnalpha TUI
	vnalpha tui

mvp1-start: ## One-command MVP1 chat vertical-slice startup (idempotent)
	packaging/scripts/openstock-mvp1-start

verify-mvp1: ## Read-only MVP1 chat vertical-slice preflight
	packaging/scripts/openstock-verify --mvp1

# ── development ───────────────────────────────

install-vnalpha: ## Install vnalpha in editable mode (uses uv if available)
	uv pip install -e vnalpha/ --python vnalpha/.venv/bin/python || pip install -e vnalpha/

lint-vnalpha: ## Run ruff linter and format-check on vnalpha
	cd vnalpha && ruff check . && ruff format --check .

test-loop: ## Run one owning contract test with a hard 60-second limit: TEST=path::test [PROJECT=vnalpha]
	@test -n "$(TEST)" || { \
		echo "Usage: make test-loop TEST=tests/path.py::test_contract [PROJECT=vnalpha|vnstock]"; \
		exit 2; \
	}
	@case "$(PROJECT)" in vnalpha|vnstock) ;; *) echo "PROJECT must be vnalpha or vnstock"; exit 2;; esac
	@timeout 60s sh -c 'cd "$(PROJECT)" && pytest -q --maxfail=1 "$(TEST)"'

test-vnalpha: ## Run the complete vnalpha suite; final-candidate/release use only
	cd vnalpha && pytest -q

# Legacy bounded suites remain callable for diagnosis only. Do not chain them with the full suite.
verify-r0: ## Run the legacy offline R0 diagnostic subset
	cd vnalpha && pytest -q \
		tests/test_phase5_e2e.py \
		tests/test_features.py \
		tests/test_warehouse.py \
		tests/test_command_warehouse.py \
		tests/test_r0_gaps.py

verify-r2-ci: ## Run static R2 deployment verification
	packaging/tests/test_daily_pipeline_units.sh
	packaging/scripts/openstock-verify --ci

verify-r4: ## Run the legacy R4 diagnostic subset
	cd vnalpha && pytest -q \
		tests/test_r4_permissions.py \
		tests/test_r4_session.py \
		tests/test_r4_trace.py \
		tests/test_r4_clear.py \
		tests/test_r4_persistence.py \
		tests/test_r4_controller_persistence.py

verify-vnalpha-package: ## Build and exercise a standalone Debian package
	rm -rf /tmp/openstock-hardening-deb
	mkdir -p /tmp/openstock-hardening-deb
	bash ./packaging/test/test_install_contract.sh
	./packaging/test/test_packaging.sh
	./packaging/build-deb.sh --output-dir /tmp/openstock-hardening-deb
	bash ./packaging/test/test_install_contract.sh /tmp/openstock-hardening-deb/vnalpha_*.deb

eval-research-answers: ## Evaluate offline golden fixtures
	cd vnalpha && PYTHONPATH=src python -c 'from vnalpha.cli import app; app()' eval research-answers --ci

eval-research-runtime: ## Evaluate offline runtime-replay fixtures
	cd vnalpha && PYTHONPATH=src python -c 'from vnalpha.cli import app; app()' eval research-runtime --ci

verify-hardening: ## Release-only validation; never use in the inner edit-test loop
	$(MAKE) repo-hygiene
	packaging/scripts/openstock-secret-scan
	$(MAKE) verify-repo-consistency
	$(MAKE) validate-compose
	$(MAKE) lint-vnalpha
	$(MAKE) test-vnalpha
	$(MAKE) verify-r2-ci
	$(MAKE) verify-vnalpha-package
	$(MAKE) eval-research-answers
	$(MAKE) eval-research-runtime
	python scripts/check-openspec-completion.py \
		openspec/changes/archive/2026-07-13-openstock-four-phase-hardening

repo-hygiene: ## Verify tracked paths and gitlinks against repository policy
	packaging/scripts/openstock-repo-hygiene

verify-repo-consistency: ## Check roadmap, OpenSpec, deployment and documentation invariants
	python scripts/check-repo-consistency.py

build-vnalpha-deb: ## Build the vnalpha Debian package
	./packaging/build-deb.sh

verify-vnalpha-deb: ## Verify the vnalpha Debian package structure
	bash ./packaging/test/test_install_contract.sh
	./packaging/test/test_packaging.sh
	@found=0; \
	for deb in packaging/dist/vnalpha_*.deb; do \
		[ -f "$$deb" ] || continue; \
		found=1; \
		bash ./packaging/test/test_install_contract.sh "$$deb" || exit $$?; \
	done; \
	if [ "$$found" -eq 0 ]; then \
		echo "No built package found under packaging/dist; source-tree checks only."; \
	fi
