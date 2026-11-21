import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.order_item import OrderItem
from app.services.errors import OrderError
from app.services.pricing_service import normalize_requested_items, price_order

MAX_IDEMPOTENCY_KEY_LENGTH = 64


def _generate_order_number():
    stamp = datetime.now(timezone.utc).strftime("%y%m%d")
    return f"TU{stamp}{secrets.token_hex(4).upper()}"


def _hash_token(raw_token):
    # Only the hash is stored. The raw token is returned to the student once.
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _validate_idempotency_key(key):
    if key is None:
        return None
    key = key.strip()
    if not key or len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise OrderError(
            "INVALID_IDEMPOTENCY_KEY",
            f"Idempotency-Key must be 1 to {MAX_IDEMPOTENCY_KEY_LENGTH} characters.",
        )
    return key


def _find_existing_order(student_id, key):
    return Order.query.filter_by(student_id=student_id, idempotency_key=key).first()


def create_order(student_id, raw_items, idempotency_key=None):
    """Create a pending_payment order.

    Returns (order, raw_tracking_token).
    raw_tracking_token is None when an existing order is returned for a retried key,
    because the raw token was already shown to the student the first time.
    """
    key = _validate_idempotency_key(idempotency_key)

    if key:
        existing = _find_existing_order(student_id, key)
        if existing:
            return existing, None

    requested = normalize_requested_items(raw_items)
    priced = price_order(requested)

    raw_token = secrets.token_urlsafe(32)

    order = Order(
        order_number=_generate_order_number(),
        student_id=student_id,
        idempotency_key=key,
        subtotal_paise=priced.subtotal_paise,
        discount_paise=priced.discount_paise,
        tax_paise=priced.tax_paise,
        total_paise=priced.total_paise,
        payment_status=PaymentStatus.PENDING,
        order_status=OrderStatus.PENDING_PAYMENT,
        tracking_token_hash=_hash_token(raw_token),
    )

    for line in priced.lines:
        order.items.append(
            OrderItem(
                menu_item_id=line.menu_item_id,
                item_name_snapshot=line.item_name,
                unit_price_snapshot_paise=line.unit_price_paise,
                quantity=line.quantity,
                line_total_paise=line.line_total_paise,
            )
        )

    db.session.add(order)

    try:
        db.session.commit()
    except IntegrityError:
        # A parallel request with the same key may have won the race.
        db.session.rollback()
        if key:
            existing = _find_existing_order(student_id, key)
            if existing:
                return existing, None
        raise OrderError(
            "ORDER_CREATE_FAILED",
            "Could not create the order. Please try again.",
            500,
        )
    except Exception:
        db.session.rollback()
        raise

    return order, raw_token
