"""Tests for utility functions."""
from src.utils import compute_total, format_currency, validate_order_id


def test_compute_total():
    assert compute_total([10.0, 20.0, 30.0]) == 60.0


def test_compute_total_empty():
    assert compute_total([]) == 0.0


def test_compute_total_rounding():
    assert compute_total([0.1, 0.2]) == 0.3


def test_format_currency():
    assert format_currency(1234.56) == "\u00a31,234.56"


def test_format_currency_custom_symbol():
    assert format_currency(100.00, "$") == "$100.00"


def test_validate_order_id_valid():
    assert validate_order_id("ORD-12345678") is True


def test_validate_order_id_invalid():
    assert validate_order_id("12345") is False
