import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models.collection_token import CollectionToken
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.order_status_history import OrderStatusHistory
from app.services.errors import OrderError


def utcnow():
    return datetime.now(timezone.utc)


def as_utc(value):
    """SQLite returns naive datetimes. Treat them as UTC so comparisons work."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hash_token(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _derive_token(order_id, nonce):
    """Build the raw token from SECRET_KEY, the order ID, and the stored nonce.

    The same inputs always give the same token, so the student sees the same QR
    after reloading. Without SECRET_KEY, the token can't be predicted.
    """
    secret = current_app.config["SECRET_KEY"].encode("utf-8")
    message = f"collection:{order_id}:{nonce}".encode("utf-8")
    digest = hmac.new(secret, message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _active_token_for(order_id):
    now = utcnow()
    unused = (
        CollectionToken.query.filter_by(order_id=order_id, used_at=None)
        .order_by(CollectionToken.id.desc())
        .all()
    )
    for token in unused:
        if as_utc(token.expires_at) > now:
            return token
    return None


def issue_collection_token(order_id):
    """Create a new token and expire any older unused ones.

    Returns the raw token. Only its hash is stored. The caller must commit.
    """
    now = utcnow()

    for old in CollectionToken.query.filter_by(order_id=order_id, used_at=None).all():
        if as_utc(old.expires_at) > now:
            old.expires_at = now

    nonce = secrets.token_hex(16)
    raw_token = _derive_token(order_id, nonce)
    expiry_minutes = current_app.config["COLLECTION_TOKEN_EXPIRY_MINUTES"]

    db.session.add(CollectionToken(
        order_id=order_id,
        token_nonce=nonce,
        token_hash=_hash_token(raw_token),
        expires_at=now + timedelta(minutes=expiry_minutes),
        created_at=now,
    ))
    return raw_token


def get_student_collection_qr(order_id, student_id):
    """Return (raw_token, token_row, order) for the student's own ready and paid order."""
    try:
        order = Order.query.filter_by(id=order_id, student_id=student_id).first()
        if order is None:
            raise OrderError("ORDER_NOT_FOUND", "Order not found.", 404)

        if (
            order.payment_status != PaymentStatus.PAID
            or order.order_status != OrderStatus.READY
        ):
            raise OrderError(
                "COLLECTION_NOT_AVAILABLE",
                "Your collection code appears once your order is ready.",
                409,
            )

        token = _active_token_for(order.id)
        if token is None:
            raw_token = issue_collection_token(order.id)
            db.session.commit()
            token = _active_token_for(order.id)
        else:
            raw_token = _derive_token(order.id, token.token_nonce)

        return raw_token, token, order

    except Exception:
        db.session.rollback()
        raise


def _find_token(raw_token):
    token = CollectionToken.query.filter_by(token_hash=_hash_token(raw_token)).first()
    if token is None:
        raise OrderError("INVALID_TOKEN", "This collection code is not valid.", 400)
    return token


def _check_token_usable(token, order):
    if token.used_at is not None:
        raise OrderError("TOKEN_ALREADY_USED", "This collection code has already been used.", 409)

    if as_utc(token.expires_at) <= utcnow():
        raise OrderError("TOKEN_EXPIRED", "This collection code has expired. Ask the student to refresh it.", 409)

    if order is None or order.payment_status != PaymentStatus.PAID:
        raise OrderError("ORDER_NOT_PAID", "This order has not been paid.", 409)

    if order.order_status != OrderStatus.READY:
        raise OrderError("ORDER_NOT_READY", "This order is not ready for collection.", 409)


def preview_collection(raw_token):
    """Staff scan the code and see the order. Nothing is changed."""
    token = _find_token(raw_token)
    order = db.session.get(Order, token.order_id)
    _check_token_usable(token, order)
    return order


def confirm_collection(raw_token, staff_user_id):
    """Staff confirm the handover. The token and order are updated together, once."""
    try:
        token = (
            CollectionToken.query.filter_by(token_hash=_hash_token(raw_token))
            .with_for_update()
            .first()
        )
        if token is None:
            raise OrderError("INVALID_TOKEN", "This collection code is not valid.", 400)

        order = Order.query.filter_by(id=token.order_id).with_for_update().first()
        _check_token_usable(token, order)

        now = utcnow()

        # Mark the token used only if it still is unused. Zero rows updated means another request won.
        token_rows = (
            CollectionToken.query.filter(
                CollectionToken.id == token.id,
                CollectionToken.used_at.is_(None),
            ).update({"used_at": now}, synchronize_session=False)
        )
        if token_rows != 1:
            raise OrderError("TOKEN_ALREADY_USED", "This collection code has already been used.", 409)

        order_rows = (
            Order.query.filter(
                Order.id == order.id,
                Order.order_status == OrderStatus.READY,
                Order.payment_status == PaymentStatus.PAID,
            ).update(
                {"order_status": OrderStatus.COLLECTED, "updated_at": now},
                synchronize_session=False,
            )
        )
        if order_rows != 1:
            raise OrderError("ORDER_NOT_READY", "This order is not ready for collection.", 409)

        db.session.add(OrderStatusHistory(
            order_id=order.id,
            previous_status=OrderStatus.READY,
            new_status=OrderStatus.COLLECTED,
            changed_by=staff_user_id,
            changed_at=now,
            notes="Collected with QR code",
        ))

        db.session.commit()
        return db.session.get(Order, order.id)

    except Exception:
        db.session.rollback()
        raise
