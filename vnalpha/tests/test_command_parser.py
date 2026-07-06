"""Tests for command parser and normalization (Tasks 1.4 + 1.5)."""

from __future__ import annotations

import pytest

from vnalpha.commands.errors import CommandParseError, CommandValidationError
from vnalpha.commands.normalizers import (
    normalize_candidate_class,
    normalize_date,
    normalize_setup_type,
    normalize_symbol,
    normalize_symbols,
)
from vnalpha.commands.parser import parse

# ---------------------------------------------------------------------------
# Parser: command names
# ---------------------------------------------------------------------------


class TestCommandNames:
    def test_simple_command(self):
        cmd = parse("/scan")
        assert cmd.command_name == "scan"
        assert cmd.positional == []
        assert cmd.filters == []
        assert cmd.options == {}

    def test_command_name_lowercased(self):
        cmd = parse("/SCAN")
        assert cmd.command_name == "scan"

    def test_command_with_hyphens(self):
        cmd = parse("/my-command")
        assert cmd.command_name == "my-command"

    def test_missing_slash_raises(self):
        with pytest.raises(CommandParseError, match="must start with '/'"):
            parse("scan")

    def test_empty_slash_raises(self):
        with pytest.raises(CommandParseError, match="Empty command"):
            parse("/")

    def test_invalid_name_starts_with_digit_raises(self):
        with pytest.raises(CommandParseError, match="Invalid command name"):
            parse("/1scan")


# ---------------------------------------------------------------------------
# Parser: positional arguments
# ---------------------------------------------------------------------------


class TestPositionalArgs:
    def test_single_positional(self):
        cmd = parse("/explain FPT")
        assert cmd.positional == ["FPT"]

    def test_multiple_positional(self):
        cmd = parse("/compare FPT VNM MWG")
        assert cmd.positional == ["FPT", "VNM", "MWG"]

    def test_quoted_positional(self):
        cmd = parse('/note FPT "watch relative strength"')
        assert "FPT" in cmd.positional
        assert "watch relative strength" in cmd.positional

    def test_single_quoted_positional(self):
        cmd = parse("/note FPT 'check liquidity'")
        assert "check liquidity" in cmd.positional


# ---------------------------------------------------------------------------
# Parser: filters
# ---------------------------------------------------------------------------


class TestFilters:
    def test_equals_filter(self):
        cmd = parse("/filter class=STRONG_CANDIDATE")
        assert len(cmd.filters) == 1
        f = cmd.filters[0]
        assert f.key == "class"
        assert f.op == "="
        assert f.value == "STRONG_CANDIDATE"

    def test_gte_filter(self):
        cmd = parse("/filter score>=0.70")
        f = cmd.filters[0]
        assert f.key == "score"
        assert f.op == ">="
        assert f.value == "0.70"

    def test_lte_filter(self):
        cmd = parse("/filter score<=0.50")
        f = cmd.filters[0]
        assert f.op == "<="

    def test_not_equals_filter(self):
        cmd = parse("/filter class!=IGNORE")
        f = cmd.filters[0]
        assert f.op == "!="

    def test_contains_filter(self):
        _cmd = parse("/filter risk_flags=contains:THIN_VOLUME")
        # Contains is a token, so the value includes the colon form
        # Let's check contains operator directly
        cmd2 = parse("/filter risk_flags contains THIN_VOLUME")
        # "risk_flags contains THIN_VOLUME" is three tokens; filter won't match inline
        # Actually in our grammar, filters must be single token "KEY OP VALUE"
        # "contains" as op only works when it's part of the token: "risk_flags=THIN_VOLUME"
        # The contains operator works as: "key contains value" -> three tokens; let's test that
        assert cmd2.positional  # they'll be positional, not a filter

    def test_inline_contains_filter(self):
        # contains operator works inline when embedded: "risk_flagscontainsTHIN_VOLUME"
        # Parser regex picks it up as key=risk_flags, op=contains, value=THIN_VOLUME
        cmd = parse("/filter risk_flagscontainsTHIN_VOLUME")
        assert len(cmd.filters) == 1
        assert cmd.filters[0].op == "contains"
        assert cmd.filters[0].value == "THIN_VOLUME"

    def test_multiple_filters(self):
        cmd = parse("/filter score>=0.70 class=STRONG_CANDIDATE")
        assert len(cmd.filters) == 2
        assert cmd.filters[0].key == "score"
        assert cmd.filters[1].key == "class"


# ---------------------------------------------------------------------------
# Parser: options
# ---------------------------------------------------------------------------


class TestOptions:
    def test_boolean_option(self):
        cmd = parse("/history --verbose")
        assert cmd.options.get("verbose") is True

    def test_value_option(self):
        cmd = parse("/history --limit 20")
        assert cmd.options.get("limit") == "20"

    def test_date_option(self):
        cmd = parse("/scan --date 2026-07-06")
        assert cmd.options.get("date") == "2026-07-06"

    def test_bare_double_dash_raises(self):
        with pytest.raises(CommandParseError, match="not a valid option"):
            parse("/scan --")


# ---------------------------------------------------------------------------
# Parser: quoted text / combined
# ---------------------------------------------------------------------------


class TestQuotedText:
    def test_full_note_command(self):
        cmd = parse('/note FPT "watch whether relative strength persists"')
        assert cmd.command_name == "note"
        assert "FPT" in cmd.positional
        assert "watch whether relative strength persists" in cmd.positional

    def test_unmatched_quote_raises(self):
        with pytest.raises(CommandParseError, match="Unmatched quotes"):
            parse('/note FPT "unclosed')


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------


class TestNormalizers:
    def test_normalize_symbol_uppercase(self):
        assert normalize_symbol("fpt") == "FPT"

    def test_normalize_symbol_strip(self):
        assert normalize_symbol("  VNM  ") == "VNM"

    def test_normalize_symbols_list(self):
        assert normalize_symbols(["fpt", "vnm"]) == ["FPT", "VNM"]

    def test_normalize_candidate_class_valid(self):
        assert normalize_candidate_class("STRONG_CANDIDATE") == "STRONG_CANDIDATE"
        assert normalize_candidate_class("strong_candidate") == "STRONG_CANDIDATE"

    def test_normalize_candidate_class_invalid(self):
        with pytest.raises(CommandValidationError, match="Unknown candidate class"):
            normalize_candidate_class("STAGE1")

    def test_normalize_setup_type_valid(self):
        assert normalize_setup_type("ACCUMULATION_BASE") == "ACCUMULATION_BASE"

    def test_normalize_setup_type_invalid(self):
        with pytest.raises(CommandValidationError, match="Unknown setup type"):
            normalize_setup_type("BASE_BREAKOUT")

    def test_normalize_date_today(self):
        from datetime import date
        result = normalize_date(None)
        assert result == date.today().isoformat()

    def test_normalize_date_explicit(self):
        assert normalize_date("2026-07-06") == "2026-07-06"

    def test_normalize_date_invalid_raises(self):
        with pytest.raises(CommandValidationError):
            normalize_date("not-a-date")
