"""Tests for the main application module."""
from src.app import process_order


def test_process_order_basic():
    items = [
        {"name": "Widget", "price": 10.00, "quantity": 2},
        {"name": "Gadget", "price": 25.00, "quantity": 1},
    ]
    result = process_order(items)
    assert result["item_count"] == 2
    assert result["total"] == "\u00a345.00"
    assert result["status"] == "processed"


def test_process_order_empty():
    result = process_order([])
    assert result["item_count"] == 0
    assert result["total"] == "\u00a30.00"
