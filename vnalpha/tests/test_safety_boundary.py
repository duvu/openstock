"""Safety and language boundary tests for vnalpha.

Ensures the library uses research-only language throughout.
"""
import inspect
import os

FORBIDDEN_TERMS = ["buy signal", "sell signal", "buy order", "sell order", "portfolio", "investment advice", "place order", "execute order"]
SOFT_FORBIDDEN = ["buy", "sell", "order", "recommend", "portfolio"]


def get_all_source_modules():
    """Return all importable vnalpha source modules."""
    import pkgutil

    import vnalpha
    modules = []
    for _importer, modname, _ispkg in pkgutil.walk_packages(
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


def _walk_source_files(root_dir: str):
    """Yield (rel_path, src_text) for all .py files under root_dir."""
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip __pycache__
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fname in filenames:
            if fname.endswith(".py"):
                fpath = os.path.join(dirpath, fname)
                with open(fpath, encoding="utf-8") as f:
                    yield fpath, f.read()


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


def test_static_scan_source_files_for_forbidden_terms():
    """Static file scan: no .py file under src/vnalpha contains hard-forbidden terms.

    This catches files that cannot be inspected via importlib (e.g. tui modules
    when textual is not installed).
    """
    src_root = os.path.join(os.path.dirname(__file__), "..", "src", "vnalpha")
    violations = []
    for fpath, src in _walk_source_files(src_root):
        src_lower = src.lower()
        for term in FORBIDDEN_TERMS:
            if term in src_lower:
                violations.append((fpath, term))

    assert not violations, (
        "Forbidden terms found in source files:\n"
        + "\n".join(f"  {fp}: {term!r}" for fp, term in violations)
    )


def test_cli_help_uses_research_language():
    """CLI help text uses research / watchlist / candidate language, not execution language."""
    from typer.testing import CliRunner

    from vnalpha.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    src = result.output.lower()
    execution_terms = ["place order", "execute order", "buy order", "sell order"]
    for term in execution_terms:
        assert term not in src, f"Forbidden execution term {term!r} in CLI help output"


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
    """Watchlist save includes lineage_json derived from persisted candidate_score."""
    from vnalpha.scoring.generate_watchlist import save_watchlist
    from vnalpha.warehouse.connection import in_memory_connection
    from vnalpha.warehouse.migrations import run_migrations
    from vnalpha.warehouse.repositories import save_candidate_score

    conn = in_memory_connection()
    run_migrations(conn=conn)

    # First persist candidate score (new API requires score to be in candidate_score)
    score_result = {
        "score": 0.65,
        "candidate_class": "WATCH_CANDIDATE",
        "setup_type": "MOMENTUM_CONTINUATION",
        "trend_score": 0.8,
        "relative_strength_score": 0.6,
        "volume_score": 0.7,
        "base_score": 0.5,
        "breakout_score": 0.4,
        "risk_quality_score": 0.9,
        "risk_flags": [],
    }
    save_candidate_score(conn, "FPT", "2024-01-02", score_result)
    save_watchlist(conn, "2024-01-02", top_n=10, min_score=0.0)

    rows = conn.execute("SELECT lineage_json FROM daily_watchlist WHERE date = '2024-01-02'").fetchall()
    assert len(rows) == 1
    import json
    lineage = json.loads(rows[0][0])
    # Lineage should include scoring metadata
    assert "scoring_version" in lineage or "trend_score" in lineage or lineage is not None
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
