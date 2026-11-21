import hashlib
import hmac
from datetime import datetime, timezone

import razorpay
import requests
from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.order_status_history import OrderStatusHistory
from app.models.payment import Payment, PaymentRecordStatus
from app.models.payment_attempt import AttemptStatus, PaymentAttempt
from app.models.webhook_event import WebhookEvent, WebhookStatus
from app.services.errors import OrderError

CURRENCY = "INR"

# Razorpay rejects charges below ₹1.00 (100 paise).
MIN_AMOUNT_PAISE = 100

# Failures when calling Razorpay: API errors from the SDK, or network problems.
PROVIDER_ERRORS = (
    razorpay.errors.BadRequestError,
    razorpay.errors.GatewayError,
    razorpay.errors.ServerError,
    requests.RequestException,
)


def utcnow():
    return datetime.now(timezone.utc)


def get_razorpay_client():
    key_id = current_app.config.get("RAZORPAY_KEY_ID", "")
    key_secret = current_app.config.get("RAZORPAY_KEY_SECRET", "")
    if not key_id or not key_secret:
        raise OrderError(
            "PAYMENTS_NOT_CONFIGURED",
            "Online payments are not configured on this server.",
            503,
        )
    return razorpay.Client(auth=(key_id, key_secret))


def _hmac_sha256_hex(secret, message_bytes):
    return hmac.new(secret.encode("utf-8"), message_bytes, hashlib.sha256).hexdigest()


def _signatures_match(expected, received):
    # compare_digest raises TypeError on non-ASCII text, so reject that first.
    if not isinstance(received, str) or not received.isascii():
        return False
    return hmac.compare_digest(expected, received)


def verify_checkout_signature(provider_order_id, provider_payment_id, signature):
    """Razorpay Checkout signature: HMAC-SHA256 of 'order_id|payment_id' with the key secret."""
    secret = current_app.config.get("RAZORPAY_KEY_SECRET", "")
    if not secret:
        raise OrderError(
            "PAYMENTS_NOT_CONFIGURED",
            "Online payments are not configured on this server.",
            503,
        )
    message = f"{provider_order_id}|{provider_payment_id}".encode("utf-8")
    return _signatures_match(_hmac_sha256_hex(secret, message), signature)


def verify_webhook_signature(raw_body, signature):
    """Razorpay webhook signature: HMAC-SHA256 of the raw request body with the webhook secret."""
    secret = current_app.config.get("RAZORPAY_WEBHOOK_SECRET", "")
    if not secret:
        raise OrderError(
            "WEBHOOKS_NOT_CONFIGURED",
            "Webhook processing is not configured on this server.",
            503,
        )
    return _signatures_match(_hmac_sha256_hex(secret, raw_body), signature)


def create_payment_order(order_id, student_id):
    """Create (or reuse) a Razorpay order for one of the student's pending orders.

    Returns (payment, order). The amount always comes from the database.
    """
    try:
        # Lock the order row so two quick clicks can't create two Razorpay orders.
        order = (
            Order.query.filter_by(id=order_id, student_id=student_id)
            .with_for_update()
            .first()
        )
        if order is None:
            raise OrderError("ORDER_NOT_FOUND", "Order not found.", 404)

        if (
            order.order_status != OrderStatus.PENDING_PAYMENT
            or order.payment_status != PaymentStatus.PENDING
        ):
            raise OrderError("ORDER_NOT_PAYABLE", "This order cannot be paid for.", 409)

        if order.total_paise < MIN_AMOUNT_PAISE:
            raise OrderError(
                "AMOUNT_TOO_LOW",
                "Order total is below the minimum payable amount of ₹1.00.",
                400,
            )

        # Reuse the open Razorpay order so retries never create duplicates.
        existing = Payment.query.filter_by(
            order_id=order.id,
            status=PaymentRecordStatus.CREATED,
        ).first()
        if existing is not None:
            return existing, order

        client = get_razorpay_client()
        try:
            razorpay_order = client.order.create({
                "amount": order.total_paise,
                "currency": CURRENCY,
                "receipt": order.order_number,
                "payment_capture": 1,
            })
        except PROVIDER_ERRORS:
            raise OrderError(
                "PAYMENT_PROVIDER_ERROR",
                "Could not start payment. Please try again.",
                502,
            )

        payment = Payment(
            order_id=order.id,
            payment_provider="razorpay",
            provider_order_id=razorpay_order["id"],
            amount_paise=order.total_paise,
            currency=CURRENCY,
            status=PaymentRecordStatus.CREATED,
        )
        db.session.add(payment)
        db.session.commit()
        return payment, order

    except Exception:
        db.session.rollback()
        raise


def _record_attempt(order, payment, status, provider_payment_id, failure_reason=None):
    if provider_payment_id:
        already_logged = PaymentAttempt.query.filter_by(
            provider_payment_id=provider_payment_id,
            status=status,
        ).first()
        if already_logged is not None:
            return

    attempt_count = PaymentAttempt.query.filter_by(order_id=order.id).count()
    db.session.add(PaymentAttempt(
        order_id=order.id,
        provider_order_id=payment.provider_order_id,
        provider_payment_id=provider_payment_id,
        attempt_number=attempt_count + 1,
        status=status,
        failure_reason=failure_reason,
    ))


def _confirm_captured_payment(provider_order_id, provider_payment_id, amount_paise, currency):
    """Mark the order as paid. This is the only code path that does so.

    Safe to call more than once for the same payment. Returns the order.
    """
    try:
        payment = (
            Payment.query.filter_by(provider_order_id=provider_order_id)
            .with_for_update()
            .first()
        )
        if payment is None:
            raise OrderError("PAYMENT_NOT_FOUND", "Payment not found.", 404)

        order = (
            Order.query.filter_by(id=payment.order_id)
            .with_for_update()
            .first()
        )

        if amount_paise != payment.amount_paise or currency != payment.currency:
            raise OrderError(
                "PAYMENT_MISMATCH",
                "Payment amount or currency does not match the order.",
                400,
            )

        if payment.status == PaymentRecordStatus.PAID:
            if payment.provider_payment_id == provider_payment_id:
                # Already confirmed, for example when verify and the webhook both arrive.
                return order
            raise OrderError(
                "PAYMENT_CONFLICT",
                "This order already has a different successful payment.",
                409,
            )

        if order.order_status != OrderStatus.PENDING_PAYMENT:
            # Money was captured but the order can't be fulfilled. Needs a refund review.
            raise OrderError(
                "ORDER_NOT_PAYABLE",
                "Order is no longer awaiting payment. Flag this payment for refund.",
                409,
            )

        payment.status = PaymentRecordStatus.PAID
        payment.provider_payment_id = provider_payment_id
        payment.verified_at = utcnow()

        previous_status = order.order_status
        order.payment_status = PaymentStatus.PAID
        order.order_status = OrderStatus.RECEIVED

        db.session.add(OrderStatusHistory(
            order_id=order.id,
            previous_status=previous_status,
            new_status=OrderStatus.RECEIVED,
            changed_by=None,
            changed_at=utcnow(),
            notes="Payment confirmed",
        ))

        _record_attempt(order, payment, AttemptStatus.SUCCEEDED, provider_payment_id)

        db.session.commit()
        return order

    except Exception:
        db.session.rollback()
        raise


def verify_checkout(student_id, provider_order_id, provider_payment_id, signature):
    """Called by the browser after Razorpay Checkout succeeds.

    The browser's success message is not trusted. The signature is checked, then the
    payment is fetched from Razorpay and must show as captured with the right amount.
    """
    payment = Payment.query.filter_by(provider_order_id=provider_order_id).first()
    if payment is None:
        raise OrderError("PAYMENT_NOT_FOUND", "Payment not found.", 404)

    order = db.session.get(Order, payment.order_id)
    if order is None or order.student_id != student_id:
        # Same response for "not yours" and "doesn't exist".
        raise OrderError("PAYMENT_NOT_FOUND", "Payment not found.", 404)

    if not verify_checkout_signature(provider_order_id, provider_payment_id, signature):
        raise OrderError(
            "PAYMENT_VERIFICATION_FAILED",
            "Payment signature is invalid.",
            400,
        )

    client = get_razorpay_client()
    try:
        details = client.payment.fetch(provider_payment_id)
    except PROVIDER_ERRORS:
        raise OrderError(
            "PAYMENT_PROVIDER_ERROR",
            "Could not confirm the payment with Razorpay. Please try again.",
            502,
        )

    if details.get("order_id") != provider_order_id:
        raise OrderError("PAYMENT_MISMATCH", "Payment does not belong to this order.", 400)

    if details.get("status") != "captured":
        raise OrderError(
            "PAYMENT_NOT_CAPTURED",
            "Payment is not complete yet. Please wait a moment and try again.",
            409,
        )

    return _confirm_captured_payment(
        provider_order_id=provider_order_id,
        provider_payment_id=provider_payment_id,
        amount_paise=details.get("amount"),
        currency=details.get("currency"),
    )


def _payment_entity(payload):
    entity = ((payload or {}).get("payload") or {}).get("payment") or {}
    return entity.get("entity") or {}


def _handle_payment_captured(payload):
    entity = _payment_entity(payload)
    provider_order_id = entity.get("order_id")

    if not provider_order_id or not Payment.query.filter_by(provider_order_id=provider_order_id).first():
        return WebhookStatus.IGNORED

    _confirm_captured_payment(
        provider_order_id=provider_order_id,
        provider_payment_id=entity.get("id"),
        amount_paise=entity.get("amount"),
        currency=entity.get("currency"),
    )
    return WebhookStatus.PROCESSED


def _handle_payment_failed(payload):
    entity = _payment_entity(payload)
    provider_order_id = entity.get("order_id")
    if not provider_order_id:
        return WebhookStatus.IGNORED

    payment = Payment.query.filter_by(provider_order_id=provider_order_id).first()
    if payment is None or payment.status == PaymentRecordStatus.PAID:
        # Unknown payment, or a late failure after success. Nothing to change.
        return WebhookStatus.IGNORED

    order = db.session.get(Order, payment.order_id)
    reason = entity.get("error_description") or entity.get("error_reason") or "Payment failed"
    _record_attempt(
        order,
        payment,
        AttemptStatus.FAILED,
        entity.get("id"),
        failure_reason=str(reason)[:255],
    )
    # The order stays pending_payment, and the same Razorpay order can be retried.
    db.session.commit()
    return WebhookStatus.PROCESSED


WEBHOOK_HANDLERS = {
    "payment.captured": _handle_payment_captured,
    "payment.failed": _handle_payment_failed,
}


def process_webhook(event_id, event_type, raw_body, payload):
    """Store and apply one Razorpay webhook event.

    Returns 'processed', 'ignored', or 'duplicate'. Raises on failure so the
    route returns 500 and Razorpay retries delivery.
    """
    payload_hash = hashlib.sha256(raw_body).hexdigest()

    event = WebhookEvent.query.filter_by(provider_event_id=event_id).first()
    if event is None:
        event = WebhookEvent(
            provider_event_id=event_id,
            event_type=event_type,
            payload_hash=payload_hash,
            processing_status=WebhookStatus.RECEIVED,
            received_at=utcnow(),
        )
        db.session.add(event)
        try:
            db.session.commit()
        except IntegrityError:
            # A parallel delivery stored the same event first.
            db.session.rollback()
            event = WebhookEvent.query.filter_by(provider_event_id=event_id).first()

    if event.processing_status in (WebhookStatus.PROCESSED, WebhookStatus.IGNORED):
        return "duplicate"

    try:
        handler = WEBHOOK_HANDLERS.get(event_type)
        outcome = handler(payload) if handler else WebhookStatus.IGNORED

        event = WebhookEvent.query.filter_by(provider_event_id=event_id).first()
        event.processing_status = outcome
        event.processed_at = utcnow()
        db.session.commit()
        return outcome

    except Exception:
        db.session.rollback()
        event = WebhookEvent.query.filter_by(provider_event_id=event_id).first()
        if event is not None:
            event.processing_status = WebhookStatus.FAILED
            db.session.commit()
        raise
