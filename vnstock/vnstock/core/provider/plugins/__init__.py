"""
Internal provider plugin adapters for the vnstock plugin architecture.

Phase 1 ships with a single plugin: KBSOHLCVPlugin.

Future phases will add VCI, DNSE, TCBS and other provider plugins here.
"""

from vnstock.core.provider.plugins.kbs_ohlcv import KBSOHLCVPlugin

__all__ = ["KBSOHLCVPlugin"]
