"""API request handlers."""
from src.utils import compute_total


def list_orders():
    """List all orders."""
    return {"data": [], "error": None}


def get_order(order_id: str):
    """Get a single order by ID."""
    return {"data": {"order_id": order_id}, "error": None}


def create_order(items: list[dict]):
    """Create a new order."""
    total = compute_total([item["price"] for item in items])
    return {"data": {"total": total, "status": "created"}, "error": None}


def update_order(order_id: str, updates: dict):
    """Update an existing order."""
    return {"data": {"order_id": order_id, **updates}, "error": None}


def delete_order(order_id: str):
    """Delete an order."""
    return {"data": None, "error": None}
