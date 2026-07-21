from __future__ import annotations

from vnalpha.tui.widgets.output_stream import OutputStream


def test_transcript_is_unboxed_so_result_blocks_own_visual_emphasis() -> None:
    assert "border: round" not in OutputStream.DEFAULT_CSS
