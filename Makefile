.DEFAULT_GOAL := help

# ──────────────────────────────────────────────
# openstock Makefile
# ──────────────────────────────────────────────

.PHONY: help up-vnstock down-vnstock sync features score tui \
        install-vnalpha lint-vnalpha test-vnalpha

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

install-vnalpha: ## Install vnalpha in editable mode
	pip install -e vnalpha/

lint-vnalpha: ## Run ruff linter and format-check on vnalpha
	cd vnalpha && ruff check . && ruff format --check .

test-vnalpha: ## Run vnalpha test suite
	cd vnalpha && pytest -q
