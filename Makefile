.DEFAULT_GOAL := help

# ──────────────────────────────────────────────
# openstock Makefile
# ──────────────────────────────────────────────

.PHONY: help up-vnstock down-vnstock sync features score tui \
        install-vnalpha lint-vnalpha test-vnalpha \
        eval-research-answers eval-research-runtime verify-hardening verify-r0 \
        verify-r2-ci verify-r4 repo-hygiene verify-vnalpha-package \
        build-vnalpha-deb verify-vnalpha-deb

help: ## Show this help message
	@printf "\nopenstock — local research workflow\n\n"
	@printf "  %-22s %s\n" "Target" "Description"
	@printf "  %-22s %s\n" "------" "-----------"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
	@printf "\nUsage: make <target>\n\n"

# ── vnstock-service ───────────────────────────

up-vnstock: ## Start vnstock-service (Docker)
	docker compose -f vnstock/docker-compose.yml up -d

down-vnstock: ## Stop vnstock-service (Docker)
	docker compose -f vnstock/docker-compose.yml down

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

# ── vnalpha dev ───────────────────────────────

install-vnalpha: ## Install vnalpha in editable mode (uses uv if available)
	uv pip install -e vnalpha/ --python vnalpha/.venv/bin/python || pip install -e vnalpha/

lint-vnalpha: ## Run ruff linter and format-check on vnalpha
	cd vnalpha && ruff check . && ruff format --check .

test-vnalpha: ## Run vnalpha test suite
	cd vnalpha && pytest -q

verify-r0: ## Run offline R0 pipeline confidence tests (no network required)
	cd vnalpha && pytest -q \
		tests/test_phase5_e2e.py \
		tests/test_features.py \
		tests/test_warehouse.py \
		tests/test_command_warehouse.py \
		tests/test_r0_gaps.py

verify-r2-ci: ## Run static CI verification for R2 deploy correctness
	packaging/scripts/openstock-verify --ci

verify-r4: ## Run R4 chat-workspace acceptance tests (no network required)
	cd vnalpha && pytest -q \
		tests/test_r4_permissions.py \
		tests/test_r4_session.py \
		tests/test_r4_trace.py \
		tests/test_r4_clear.py \
		tests/test_r4_persistence.py \
		tests/test_r4_controller_persistence.py

verify-vnalpha-package: ## Build and exercise an offline Debian packaging fixture
	rm -rf /tmp/openstock-hardening-deb
	mkdir -p /tmp/openstock-hardening-deb
	./packaging/build-deb.sh --offline --output-dir /tmp/openstock-hardening-deb
	./packaging/test/test_packaging.sh /tmp/openstock-hardening-deb/vnalpha_*.deb

eval-research-answers: ## Evaluate offline golden fixtures
	cd vnalpha && PYTHONPATH=src python -c 'from vnalpha.cli import app; app()' eval research-answers --ci

eval-research-runtime: ## Evaluate offline runtime-replay fixtures
	cd vnalpha && PYTHONPATH=src python -c 'from vnalpha.cli import app; app()' eval research-runtime --ci

verify-hardening: ## Run hardening verification gates in dependency order
	$(MAKE) repo-hygiene
	packaging/scripts/openstock-secret-scan
	$(MAKE) lint-vnalpha
	$(MAKE) verify-r0
	$(MAKE) verify-r2-ci
	$(MAKE) test-vnalpha
	$(MAKE) verify-r4
	packaging/scripts/openstock-verify --ci
	$(MAKE) verify-vnalpha-package
	$(MAKE) eval-research-answers
	$(MAKE) eval-research-runtime
	python -m pytest -q scripts/tests/test_check_openspec_completion.py
	python scripts/check-openspec-completion.py \
		openspec/changes/openstock-four-phase-hardening

repo-hygiene: ## Verify tracked paths and gitlinks against repository policy
	packaging/scripts/openstock-repo-hygiene

build-vnalpha-deb: ## Build the vnalpha Debian package
	./packaging/build-deb.sh

verify-vnalpha-deb: ## Verify the vnalpha Debian package structure
	./packaging/test/test_packaging.sh packaging/dist/vnalpha_*.deb 2>/dev/null || \
		./packaging/test/test_packaging.sh
