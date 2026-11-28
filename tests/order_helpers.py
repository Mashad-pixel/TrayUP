"""Order helpers for tests using the current authenticated order workflow."""
from app.services.order_service import create_order as _create_order


def create_order_for(student_id, raw_items, idempotency_key=None):
    return _create_order(student_id, raw_items, idempotency_key=idempotency_key)
