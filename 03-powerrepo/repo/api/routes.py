"""API route definitions."""

ROUTES = {
    "GET /orders": "handlers.list_orders",
    "GET /orders/<id>": "handlers.get_order",
    "POST /orders": "handlers.create_order",
    "PUT /orders/<id>": "handlers.update_order",
    "DELETE /orders/<id>": "handlers.delete_order",
}
