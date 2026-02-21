"""
Unit tests for tools/dice_roller.py — Pure Python dice parser/roller.

No mocks needed. Tests use random.seed() for deterministic rolls.
"""

import random

from tools.dice_roller import parse_and_roll, format_roll_detail


class TestParseAndRoll:
    """Test the dice formula parser and roller."""

    def test_simple_d20(self):
        result = parse_and_roll("1d20")
        assert 1 <= result["total"] <= 20
        assert result["formula"] == "1d20"
        assert len(result["dice"]) == 1
        assert result["dice"][0]["faces"] == 20
        assert len(result["dice"][0]["results"]) == 1

    def test_with_positive_modifier(self):
        random.seed(42)
        result = parse_and_roll("1d20+5")
        die_value = result["dice"][0]["results"][0]["result"]
        assert result["total"] == die_value + 5
        assert result["formula"] == "1d20+5"

    def test_with_negative_modifier(self):
        random.seed(42)
        result = parse_and_roll("1d8-2")
        die_value = result["dice"][0]["results"][0]["result"]
        assert result["total"] == die_value - 2
        assert result["dice"][0]["faces"] == 8

    def test_multiple_dice(self):
        result = parse_and_roll("2d6+3")
        assert len(result["dice"][0]["results"]) == 2
        die1 = result["dice"][0]["results"][0]["result"]
        die2 = result["dice"][0]["results"][1]["result"]
        assert result["total"] == die1 + die2 + 3
        assert result["dice"][0]["faces"] == 6

    def test_implicit_count(self):
        """d20 without leading number should default to 1 die."""
        result = parse_and_roll("d20")
        assert len(result["dice"]) == 1
        assert len(result["dice"][0]["results"]) == 1
        assert result["dice"][0]["faces"] == 20

    def test_flat_integer(self):
        result = parse_and_roll("5")
        assert result["total"] == 5
        assert result["dice"] == []
        assert result["isCritical"] is False
        assert result["isFumble"] is False

    def test_flat_zero(self):
        result = parse_and_roll("0")
        assert result["total"] == 0
        assert result["dice"] == []

    def test_critical_detection(self):
        """Natural 20 on a single d20 is a critical."""
        # Brute-force: seed random until we get a 20
        for seed in range(1000):
            random.seed(seed)
            result = parse_and_roll("1d20")
            if result["dice"][0]["results"][0]["result"] == 20:
                assert result["isCritical"] is True
                assert result["isFumble"] is False
                return
        raise AssertionError("Could not find a seed that rolls 20")  # pragma: no cover

    def test_fumble_detection(self):
        """Natural 1 on a single d20 is a fumble."""
        for seed in range(1000):
            random.seed(seed)
            result = parse_and_roll("1d20")
            if result["dice"][0]["results"][0]["result"] == 1:
                assert result["isFumble"] is True
                assert result["isCritical"] is False
                return
        raise AssertionError("Could not find a seed that rolls 1")  # pragma: no cover

    def test_no_crit_on_multi_dice(self):
        """Critical/fumble only applies to single d20 rolls."""
        for _ in range(50):
            result = parse_and_roll("2d20")
            assert result["isCritical"] is False
            assert result["isFumble"] is False

    def test_no_crit_on_non_d20(self):
        """d6 rolls should never be critical even if they roll max."""
        for _ in range(50):
            result = parse_and_roll("1d6")
            assert result["isCritical"] is False
            assert result["isFumble"] is False

    def test_invalid_formula_fallback(self):
        result = parse_and_roll("banana")
        assert result["total"] == 10
        assert result["dice"] == []
        assert result["isCritical"] is False

    def test_case_insensitive(self):
        random.seed(42)
        upper = parse_and_roll("1D20+5")
        random.seed(42)
        lower = parse_and_roll("1d20+5")
        assert upper["total"] == lower["total"]

    def test_whitespace_stripped(self):
        result = parse_and_roll("  1d20  ")
        assert 1 <= result["total"] <= 20

    def test_dice_results_marked_active(self):
        result = parse_and_roll("1d20")
        assert result["dice"][0]["results"][0]["active"] is True

    def test_four_d6(self):
        result = parse_and_roll("4d6")
        assert len(result["dice"][0]["results"]) == 4
        for r in result["dice"][0]["results"]:
            assert 1 <= r["result"] <= 6


class TestFormatRollDetail:
    """Test the human-readable roll formatter."""

    def test_simple_roll(self):
        random.seed(42)
        result = parse_and_roll("1d20+5")
        detail = format_roll_detail("1d20+5", result)
        assert "1d20+5:" in detail
        assert "+5" in detail
        assert f"= {result['total']}" in detail

    def test_flat_integer(self):
        result = parse_and_roll("5")
        detail = format_roll_detail("5", result)
        assert detail == "5 = 5"

    def test_no_modifier(self):
        random.seed(42)
        result = parse_and_roll("1d20")
        detail = format_roll_detail("1d20", result)
        # No modifier means no +/- suffix
        die_val = result["dice"][0]["results"][0]["result"]
        assert f"[{die_val}]" in detail
        assert f"= {result['total']}" in detail

    def test_multiple_dice_format(self):
        random.seed(42)
        result = parse_and_roll("2d6+3")
        detail = format_roll_detail("2d6+3", result)
        assert "2d6+3:" in detail
        assert "+3" in detail
        # Should contain comma-separated dice values
        assert ", " in detail or "]" in detail
