"""Utility functions used across the application."""


def compute_total(amounts: list[float]) -> float:
    """Compute the total from a list of amounts.

    Used by: src/app.py, api/handlers.py, tests/test_utils.py
    This function is the target of the M5 Grep scavenger hunt.
    """
    return round(sum(amounts), 2)


def format_currency(amount: float, symbol: str = "\u00a3") -> str:
    """Format a number as currency."""
    return f"{symbol}{amount:,.2f}"


def validate_order_id(order_id: str) -> bool:
    """Check if an order ID matches the expected format."""
    return order_id.startswith("ORD-") and len(order_id) == 12
