import hashlib
import hmac

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.order_status_history import OrderStatusHistory
from app.models.payment import Payment, PaymentRecordStatus
from app.models.payment_attempt import AttemptStatus, PaymentAttempt
from app.models.webhook_event import WebhookEvent, WebhookStatus
from app.services.errors import OrderError
from app.services.inventory_service import commit_reservations
from app.services.order_service import expire_order, payment_window_closed
from app.services.razorpay_client import PROVIDER_ERRORS, get_razorpay_client
from app.services.refund_service import handle_refund_failed_event, handle_refund_processed_event
from app.services.time_utils import utcnow

CURRENCY = "INR"

# Razorpay rejects charges below ₹1.00 (100 paise).
MIN_AMOUNT_PAISE = 100

# Raised when money is captured after the order stopped waiting for payment. The payment
# is recorded as REFUND_REQUIRED and an admin refunds it. The order is not fulfilled.
LATE_PAYMENT_CODE = "ORDER_NOT_PAYABLE_REFUND_REQUIRED"
LATE_PAYMENT_MESSAGE = "Payment was received after this order expired, so it will be refunded."


def _hmac_signature(secret, message):
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_checkout_signature(order_id, payment_id, signature):
    secret = current_app.config["RAZORPAY_KEY_SECRET"]
    expected = _hmac_signature(secret, f"{order_id}|{payment_id}")
    return hmac.compare_digest(expected, signature or "")


def verify_webhook_signature(raw_body, signature):
    secret = current_app.config["RAZORPAY_WEBHOOK_SECRET"]
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def _record_attempt(payment_id, outcome, provider_payment_id=None, error_code=None, message=None):
    payment = db.session.get(Payment, payment_id)
    if payment is None:
        return
    attempt_number = (
        PaymentAttempt.query.filter_by(order_id=payment.order_id).count() + 1
    )
    db.session.add(PaymentAttempt(
        order_id=payment.order_id,
        provider_order_id=payment.provider_order_id,
        attempt_number=attempt_number,
        status=outcome,
        provider_payment_id=provider_payment_id,
        failure_reason=message or error_code,
    ))


def _confirm_captured_payment(
    payment=None,
    provider_payment_id=None,
    amount_paise=None,
    currency=None,
    provider_order_id=None,
):
    """Confirm a captured payment. Idempotent for the same provider payment ID."""
    if payment is None:
        payment = Payment.query.filter_by(provider_order_id=provider_order_id).first()
        if payment is None:
            raise OrderError("PAYMENT_NOT_FOUND", "Payment not found.", 404)
    if amount_paise != payment.amount_paise or currency != payment.currency:
        raise OrderError("PAYMENT_MISMATCH", "Captured amount or currency does not match the order.", 409)

    if payment.status == PaymentRecordStatus.PAID:
        if payment.provider_payment_id == provider_payment_id:
            return payment, False
        raise OrderError("PAYMENT_CONFLICT", "A different payment already paid this order.", 409)

    order = Order.query.filter_by(id=payment.order_id).with_for_update().first()
    if order is None:
        payment.status = PaymentRecordStatus.REFUND_REQUIRED
        payment.provider_payment_id = provider_payment_id
        db.session.commit()
        return payment, True

    # The payment window may have elapsed before the scheduled expiry job ran.
    if order.order_status == OrderStatus.PENDING_PAYMENT and payment_window_closed(order):
        expire_order(order)
        db.session.flush()

    payable = (
        order.order_status == OrderStatus.PENDING_PAYMENT
        and order.payment_status == PaymentStatus.PENDING
    )
    if not payable:
        payment.status = PaymentRecordStatus.REFUND_REQUIRED
        payment.provider_payment_id = provider_payment_id
        _record_attempt(
            payment.id,
            AttemptStatus.REFUND_REQUIRED,
            provider_payment_id=provider_payment_id,
            error_code=LATE_PAYMENT_CODE,
            message=LATE_PAYMENT_MESSAGE,
        )
        db.session.commit()
        return payment, True

    # Verify the stock hold exists and convert it to a sale in the same transaction.
    commit_reservations(order.id)

    now = utcnow()
    payment.status = PaymentRecordStatus.PAID
    payment.provider_payment_id = provider_payment_id
    payment.verified_at = now

    order.payment_status = PaymentStatus.PAID
    order.order_status = OrderStatus.RECEIVED
    order.updated_at = now

    db.session.add(OrderStatusHistory(
        order_id=order.id,
        previous_status=OrderStatus.PENDING_PAYMENT,
        new_status=OrderStatus.RECEIVED,
        changed_by=None,  # Payment webhook/system event
        changed_at=now,
        notes="Payment captured and verified",
    ))

    _record_attempt(payment.id, AttemptStatus.SUCCESS, provider_payment_id=provider_payment_id)
    db.session.commit()
    return payment, False


def create_payment_order(internal_order_id, student_id):
    """Create (or return) a Razorpay order for one of the student's pending orders."""
    order = Order.query.filter_by(id=internal_order_id, student_id=student_id).with_for_update().first()
    if order is None:
        raise OrderError("ORDER_NOT_FOUND", "Order not found.", 404)

    if order.order_status != OrderStatus.PENDING_PAYMENT or order.payment_status != PaymentStatus.PENDING:
        raise OrderError("ORDER_NOT_PAYABLE", "This order is not waiting for payment.", 409)
    if payment_window_closed(order):
        expire_order(order)
        db.session.commit()
        raise OrderError("ORDER_EXPIRED", "This order's payment window has expired. Place a new order.", 409)

    if order.total_paise < MIN_AMOUNT_PAISE:
        raise OrderError("AMOUNT_TOO_SMALL", "The minimum payment amount is ₹1.00.", 400)

    existing = Payment.query.filter_by(order_id=order.id, status=PaymentRecordStatus.CREATED).first()
    if existing:
        return existing, order

    client = get_razorpay_client()
    try:
        provider_order = client.order.create({
            "amount": order.total_paise,
            "currency": CURRENCY,
            "receipt": order.order_number,
        })
    except PROVIDER_ERRORS as exc:
        raise OrderError("PAYMENT_PROVIDER_ERROR", "Could not start payment. Please try again.", 502) from exc

    payment = Payment(
        order_id=order.id,
        provider_order_id=provider_order["id"],
        amount_paise=order.total_paise,
        currency=CURRENCY,
        status=PaymentRecordStatus.CREATED,
    )
    db.session.add(payment)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        # A concurrent payment creation may have committed first.
        existing = Payment.query.filter_by(order_id=order.id, status=PaymentRecordStatus.CREATED).first()
        if existing:
            return existing, order
        raise OrderError("PAYMENT_CREATE_FAILED", "Could not record payment. Please retry.", 500) from exc
    return payment, order


def verify_checkout(order_id, payment_id, signature, student_id):
    payment = Payment.query.join(Order).filter(
        Payment.provider_order_id == order_id,
        Order.student_id == student_id,
    ).first()
    if payment is None:
        raise OrderError("PAYMENT_NOT_FOUND", "Payment not found.", 404)

    if not verify_checkout_signature(order_id, payment_id, signature):
        _record_attempt(payment.id, AttemptStatus.SIGNATURE_FAILED, provider_payment_id=payment_id)
        db.session.commit()
        raise OrderError("INVALID_SIGNATURE", "Payment verification failed.", 400)

    client = get_razorpay_client()
    try:
        details = client.payment.fetch(payment_id)
    except PROVIDER_ERRORS as exc:
        raise OrderError("PAYMENT_PROVIDER_ERROR", "Could not verify payment yet. Please retry.", 502) from exc

    if details.get("order_id") != order_id:
        raise OrderError("PAYMENT_MISMATCH", "This payment belongs to a different order.", 409)
    if details.get("status") != "captured":
        raise OrderError("PAYMENT_NOT_CAPTURED", "Payment is not captured yet.", 409)

    return _confirm_captured_payment(
        payment,
        provider_payment_id=payment_id,
        amount_paise=details.get("amount"),
        currency=details.get("currency"),
    )


def _handle_payment_captured(entity):
    order_id = entity.get("order_id")
    provider_payment_id = entity.get("id")
    amount = entity.get("amount")
    currency = entity.get("currency")

    payment = Payment.query.filter_by(provider_order_id=order_id).first()
    if payment is None:
        # Unknown captured payment. Keep the event failed so Razorpay retries and it can be reconciled.
        raise OrderError("PAYMENT_NOT_FOUND", "No internal payment matches this Razorpay order.", 404)

    return _confirm_captured_payment(payment, provider_payment_id, amount, currency)


def _event_entity(payload):
    return payload.get("payload", {}).get("payment", {}).get("entity", {})


def _refund_entity(payload):
    return payload.get("payload", {}).get("refund", {}).get("entity", {})


def process_webhook(raw_body, signature, event_id, payload):
    """Verify and process one Razorpay webhook. Duplicate event IDs are no-ops."""
    if not verify_webhook_signature(raw_body, signature):
        raise OrderError("INVALID_WEBHOOK_SIGNATURE", "Webhook signature is invalid.", 400)
    if not event_id:
        raise OrderError("MISSING_EVENT_ID", "Razorpay event ID is required.", 400)

    existing = WebhookEvent.query.filter_by(provider_event_id=event_id).first()
    if existing and existing.processing_status == WebhookStatus.PROCESSED:
        return False

    event_type = payload.get("event", "")
    event = existing or WebhookEvent(
        provider_event_id=event_id,
        event_type=event_type,
        payload_hash=hashlib.sha256(raw_body).hexdigest(),
        processing_status=WebhookStatus.RECEIVED,
    )
    event.processing_status = WebhookStatus.RECEIVED
    event.last_error = None
    db.session.add(event)
    db.session.flush()

    try:
        if event_type == "payment.captured":
            _handle_payment_captured(_event_entity(payload))
        elif event_type == "payment.failed":
            entity = _event_entity(payload)
            payment = Payment.query.filter_by(provider_order_id=entity.get("order_id")).first()
            # A late failure must not reverse a successful capture or refund-required payment.
            if payment and payment.status == PaymentRecordStatus.CREATED:
                _record_attempt(
                    payment.id,
                    AttemptStatus.FAILED,
                    provider_payment_id=entity.get("id"),
                    error_code=entity.get("error_code"),
                    message=entity.get("error_description"),
                )
        elif event_type == "refund.processed":
            handle_refund_processed_event(_refund_entity(payload))
        elif event_type == "refund.failed":
            handle_refund_failed_event(_refund_entity(payload))
        # Unknown event types are recorded and acknowledged. Subscribe only to the events needed.

        event.processing_status = WebhookStatus.PROCESSED
        event.processed_at = utcnow()
        db.session.commit()
        return True

    except Exception as exc:
        db.session.rollback()
        # Preserve a failed event so Razorpay can retry it (or an operator can inspect it).
        failed = WebhookEvent.query.filter_by(provider_event_id=event_id).first()
        if failed:
            failed.processing_status = WebhookStatus.FAILED
            failed.last_error = str(exc)[:500]
            db.session.commit()
        else:
            failed = WebhookEvent(
                provider_event_id=event_id,
                event_type=event_type,
                payload_hash=hashlib.sha256(raw_body).hexdigest(),
                processing_status=WebhookStatus.FAILED,
                last_error=str(exc)[:500],
            )
            db.session.add(failed)
            db.session.commit()
        raise
