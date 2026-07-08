"""Tests for InputHistory — shell-like input history navigation."""

from __future__ import annotations

from vnalpha.tui.input_history import InputHistory


class TestPush:
    def test_push_stores_text(self):
        h = InputHistory()
        h.push("/explain FPT")
        assert h.items() == ["/explain FPT"]

    def test_push_strips_whitespace(self):
        h = InputHistory()
        h.push("  /explain FPT  ")
        assert h.items() == ["/explain FPT"]

    def test_push_ignores_empty(self):
        h = InputHistory()
        h.push("")
        h.push("   ")
        h.push("\t\n")
        assert len(h) == 0

    def test_push_deduplicates_consecutive(self):
        h = InputHistory()
        h.push("/explain FPT")
        h.push("/explain FPT")
        h.push("/explain FPT")
        assert h.items() == ["/explain FPT"]

    def test_push_allows_non_consecutive_duplicates(self):
        h = InputHistory()
        h.push("/explain FPT")
        h.push("/explain MWG")
        h.push("/explain FPT")
        assert h.items() == ["/explain FPT", "/explain MWG", "/explain FPT"]

    def test_push_enforces_max_items(self):
        h = InputHistory(max_items=3)
        h.push("a")
        h.push("b")
        h.push("c")
        h.push("d")
        assert h.items() == ["b", "c", "d"]
        assert len(h) == 3

    def test_push_resets_navigation(self):
        h = InputHistory()
        h.push("first")
        h.push("second")
        h.previous("")  # enter navigation
        assert h.navigating
        h.push("third")
        assert not h.navigating


class TestPrevious:
    def test_previous_returns_none_when_empty(self):
        h = InputHistory()
        assert h.previous("draft") is None

    def test_previous_returns_newest_first(self):
        h = InputHistory()
        h.push("first")
        h.push("second")
        h.push("third")
        assert h.previous("") == "third"

    def test_previous_walks_backward(self):
        h = InputHistory()
        h.push("first")
        h.push("second")
        h.push("third")
        assert h.previous("") == "third"
        assert h.previous("") == "second"
        assert h.previous("") == "first"

    def test_previous_clamps_at_oldest(self):
        h = InputHistory()
        h.push("only")
        assert h.previous("") == "only"
        assert h.previous("") == "only"
        assert h.previous("") == "only"

    def test_previous_saves_draft(self):
        h = InputHistory()
        h.push("history")
        h.previous("my draft")
        # Draft is saved internally, next() past newest will restore it
        result = h.next()  # move past newest → restore draft
        assert result == "my draft"


class TestNext:
    def test_next_returns_none_when_not_navigating(self):
        h = InputHistory()
        assert h.next() is None

    def test_next_moves_forward(self):
        h = InputHistory()
        h.push("first")
        h.push("second")
        h.push("third")
        h.previous("")  # third
        h.previous("")  # second
        assert h.next() == "third"

    def test_next_restores_draft_past_newest(self):
        h = InputHistory()
        h.push("first")
        h.push("second")
        h.previous("my draft text")  # -> second
        result = h.next()  # past newest -> restore draft
        assert result == "my draft text"
        assert not h.navigating

    def test_next_exits_navigation(self):
        h = InputHistory()
        h.push("item")
        h.previous("draft")
        h.next()  # past newest
        assert not h.navigating

    def test_full_round_trip(self):
        h = InputHistory()
        h.push("first")
        h.push("second")
        h.push("third")
        # Navigate backward
        assert h.previous("draft") == "third"
        assert h.previous("draft") == "second"
        assert h.previous("draft") == "first"
        # Navigate forward
        assert h.next() == "second"
        assert h.next() == "third"
        assert h.next() == "draft"  # restores draft
        assert not h.navigating


class TestResetNavigation:
    def test_reset_clears_navigation_state(self):
        h = InputHistory()
        h.push("item")
        h.previous("draft")
        assert h.navigating
        h.reset_navigation()
        assert not h.navigating

    def test_after_reset_previous_starts_from_newest(self):
        h = InputHistory()
        h.push("first")
        h.push("second")
        h.previous("")  # -> second
        h.previous("")  # -> first
        h.reset_navigation()
        # New navigation starts from newest
        assert h.previous("") == "second"


class TestEdgeCases:
    def test_max_items_minimum_is_1(self):
        h = InputHistory(max_items=0)
        h.push("item")
        assert len(h) == 1

    def test_history_with_special_characters(self):
        h = InputHistory()
        h.push("/explain [FPT] {MWG}")
        h.push("đánh giá FPT hôm nay")
        assert h.items() == ["/explain [FPT] {MWG}", "đánh giá FPT hôm nay"]

    def test_navigation_with_single_item(self):
        h = InputHistory()
        h.push("only")
        assert h.previous("draft") == "only"
        assert h.previous("draft") == "only"  # clamp
        assert h.next() == "draft"  # past newest
        assert not h.navigating
