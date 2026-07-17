from __future__ import annotations


def _record_ddl(table_name: str, identifier: str) -> str:
    return (
        f"CREATE TABLE IF NOT EXISTS {table_name} ("
        f"{identifier} VARCHAR PRIMARY KEY, "
        "as_of_date DATE NOT NULL, symbol VARCHAR, scope_id VARCHAR, "
        "correlation_id VARCHAR NOT NULL, quality_status VARCHAR NOT NULL, "
        "created_at TIMESTAMPTZ NOT NULL, payload_json VARCHAR NOT NULL)"
    )


ALL_DDL_RESEARCH_MODELS = (
    _record_ddl("research_market_regime_snapshot", "market_regime_snapshot_id"),
    _record_ddl("research_sector_strength_snapshot", "sector_strength_snapshot_id"),
    _record_ddl("research_symbol_level_snapshot", "symbol_level_snapshot_id"),
    _record_ddl("research_setup_analysis", "setup_analysis_id"),
    _record_ddl("research_shortlist_candidate", "shortlist_candidate_id"),
    _record_ddl("research_shortlist_decision_report", "shortlist_decision_report_id"),
    _record_ddl("research_scenario_plan", "scenario_plan_id"),
    _record_ddl("research_setup_evidence_snapshot", "setup_evidence_snapshot_id"),
)

__all__ = ["ALL_DDL_RESEARCH_MODELS"]
