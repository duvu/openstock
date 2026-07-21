"""Safety and language boundary tests for vnalpha.

Ensures the library uses research-only language throughout.
"""

import inspect
import os

FORBIDDEN_TERMS = [
    "buy signal",
    "sell signal",
    "buy order",
    "sell order",
    "portfolio",
    "investment advice",
    "place order",
    "execute order",
]
SOFT_FORBIDDEN = ["buy", "sell", "order", "recommend", "portfolio"]
TOOL_POLICY_PATH_SUFFIX = os.path.join("assistant", "tool_policy.py")
SAFETY_POLICY_PATH_SUFFIX = os.path.join("policy", "safety_policy.py")
EXEMPT_POLICY_MODULES = {
    "vnalpha.assistant.tool_policy",
    "vnalpha.policy.safety_policy",
}


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
        if modname in EXEMPT_POLICY_MODULES:
            continue
        try:
            src = inspect.getsource(mod)
        except (OSError, TypeError):
            continue
        for term in FORBIDDEN_TERMS:
            assert term not in src, f"Forbidden term '{term}' found in {modname}"
