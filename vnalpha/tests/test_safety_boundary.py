"""Safety and language boundary tests for vnalpha.

Ensures the library uses research-only language throughout.
"""
import inspect
import pytest


FORBIDDEN_TERMS = ["buy signal", "sell signal", "buy order", "sell order", "portfolio", "investment advice", "place order", "execute order"]
SOFT_FORBIDDEN = ["buy", "sell", "order", "recommend", "portfolio"]


def get_all_source_modules():
    """Return all importable vnalpha source modules."""
    import pkgutil
    import vnalpha
    modules = []
    for importer, modname, ispkg in pkgutil.walk_packages(
        path=vnalpha.__path__,
        prefix="vnalpha.",
        onerror=lambda x: None,
    ):
        try:
            import importlib
            mod = importlib.import_module(modname)
            modules.append((modname, mod))
        except ImportError:
            pass
    return modules


def test_no_hard_forbidden_terms():
    """No module contains hard-forbidden trading terms in string literals."""
    modules = get_all_source_modules()
    for modname, mod in modules:
        try:
            src = inspect.getsource(mod)
        except (OSError, TypeError):
            continue
        for term in FORBIDDEN_TERMS:
            assert term not in src, f"Forbidden term '{term}' found in {modname}"


def test_candidate_output_includes_evidence():
    """Composite score output includes sub-score evidence."""
    from vnalpha.scoring.score import compute_composite_score
    features = {
        "close": 100.0, "ma20": 97.0, "ma50": 94.0, "ma100": 88.0,
        "ma20_slope": 0.002, "ma50_slope": 0.001,
        "volume_ma20": 1_000_000.0, "volume_ratio": 1.8,
        "atr14": 1.5, "return_20d": 0.08, "return_60d": 0.12,
        "rs_20d_vs_vnindex": 0.03, "rs_60d_vs_vnindex": 0.05,
        "distance_to_ma20": 0.031, "distance_to_52w_high": -0.02,
        "base_range_30d": 0.05, "close_strength": 0.75, "volatility_20d": 0.012,
    }
    result = compute_composite_score(features)
    assert "trend_score" in result
    assert "relative_strength_score" in result
    assert "volume_score" in result
    assert "risk_flags" in result


def test_candidate_output_includes_lineage():
    """Watchlist save includes lineage_json."""
    from vnalpha.warehouse.connection import in_memory_connection
    from vnalpha.warehouse.migrations import run_migrations
    from vnalpha.scoring.generate_watchlist import save_watchlist

    conn = in_memory_connection()
    run_migrations(conn=conn)

    candidates = [{
        "symbol": "FPT", "date": "2024-01-02", "score": 0.65,
        "candidate_class": "STAGE2", "setup_type": "TREND_CONTINUATION",
        "trend_score": 0.8, "relative_strength_score": 0.6,
        "volume_score": 0.7, "risk_flags": [],
    }]
    save_watchlist(conn, "2024-01-02", candidates, min_score=0.0)

    rows = conn.execute("SELECT lineage_json FROM daily_watchlist WHERE date = '2024-01-02'").fetchall()
    assert len(rows) == 1
    import json
    lineage = json.loads(rows[0][0])
    assert "trend_score" in lineage
    conn.close()


def test_no_provider_specific_imports_in_vnalpha():
    """vnalpha must not import vnstock internal provider classes."""
    modules = get_all_source_modules()
    forbidden_imports = [
        "from vnstock.providers",
        "from vnstock.explorer",
        "PluginRegistry",
        "PluginRouter",
    ]
    for modname, mod in modules:
        try:
            src = inspect.getsource(mod)
        except (OSError, TypeError):
            continue
        for fi in forbidden_imports:
            assert fi not in src, f"Forbidden import '{fi}' found in {modname}"
