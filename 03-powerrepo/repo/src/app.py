"""Main application module."""
from src.utils import compute_total, format_currency


def process_order(items: list[dict]) -> dict:
    """Process an order and return the summary."""
    total = compute_total([item["price"] * item["quantity"] for item in items])
    return {
        "item_count": len(items),
        "total": format_currency(total),
        "status": "processed",
    }


def get_order_summary(order_id: str) -> dict:
    """Retrieve and summarize an order."""
    return {"order_id": order_id, "status": "pending"}
