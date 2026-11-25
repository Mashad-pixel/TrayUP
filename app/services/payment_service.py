import hashlib
import hmac
import re

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.canteen import CanteenSettings
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.order_status_history import OrderStatusHistory
from app.models.payment import Payment, PaymentRecordStatus
from app.models.payment_attempt import AttemptStatus, PaymentAttempt
from app.models.webhook_event import WebhookEvent, WebhookStatus
from app.services.canteen_service import get_canteen_settings
from app.services.errors import OrderError
from app.services.inventory_service import commit_reservations, release_reservations
from app.services.order_service import expire_order, payment_window_closed
from app.services.razorpay_client import PROVIDER_ERRORS, get_razorpay_client
from app.services.refund_service import handle_refund_failed_event, handle_refund_processed_event
from app.services.time_utils import utcnow
from app.services.firebase_service import sync_order_to_firebase
from app.services.upi_service import (
    build_upi_intent_uri,
    decode_phonepe_callback,
    render_upi_qr_svg,
)

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
    if not secret:
        raise OrderError("PAYMENTS_NOT_CONFIGURED", "Online payments are not configured on this server.", 503)
    expected = _hmac_signature(secret, f"{order_id}|{payment_id}")
    return _signature_matches(expected, signature)


def _signature_matches(expected, received):
    # compare_digest raises TypeError on non-ASCII text, which would turn bad input into a 500.
    if not isinstance(received, str) or not received.isascii():
        return False
    return hmac.compare_digest(expected, received)


def verify_webhook_signature(raw_body, signature):
    secret = current_app.config["RAZORPAY_WEBHOOK_SECRET"]
    if not secret:
        raise OrderError("WEBHOOKS_NOT_CONFIGURED", "Webhook processing is not configured on this server.", 503)
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return _signature_matches(expected, signature)


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
    confirmed_by=None,
    notes=None,
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
        committed_order = db.session.get(Order, payment.order_id)
        if committed_order is not None:
            sync_order_to_firebase(committed_order)
        return payment, True

    # The payment window may have elapsed before the scheduled expiry job ran.
    # Orders already marked awaiting_confirmation (e.g., student at counter) are not expired here.
    if (
        order.order_status == OrderStatus.PENDING_PAYMENT
        and order.payment_status == PaymentStatus.PENDING
        and payment_window_closed(order)
    ):
        expire_order(order)
        db.session.flush()

    payable = (
        order.order_status == OrderStatus.PENDING_PAYMENT
        and order.payment_status in (PaymentStatus.PENDING, PaymentStatus.AWAITING_CONFIRMATION)
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
        changed_by=confirmed_by,
        changed_at=now,
        notes=notes or "Payment captured and verified",
    ))

    _record_attempt(payment.id, AttemptStatus.SUCCESS, provider_payment_id=provider_payment_id)
    db.session.commit()
    committed_order = db.session.get(Order, order.id)
    if committed_order is not None:
        sync_order_to_firebase(committed_order)
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

    payment, refund_required = _confirm_captured_payment(
        payment,
        provider_payment_id=payment_id,
        amount_paise=details.get("amount"),
        currency=details.get("currency"),
    )
    order = db.session.get(Order, payment.order_id)
    return order, refund_required


def _handle_payment_captured(entity):
    order_id = entity.get("order_id")
    provider_payment_id = entity.get("id")

    payment = Payment.query.filter_by(provider_order_id=order_id).first() if order_id else None
    if payment is None:
        # A capture for an order this system never created. Acknowledge it so Razorpay
        # stops retrying. The payment is logged for manual review.
        current_app.logger.warning(
            "Captured Razorpay payment %s has no internal order; ignored.", provider_payment_id
        )
        return "ignored"

    _confirm_captured_payment(
        payment,
        provider_payment_id,
        entity.get("amount"),
        entity.get("currency"),
    )
    return "processed"


def _handle_payment_failed(entity):
    order_id = entity.get("order_id")
    payment = Payment.query.filter_by(provider_order_id=order_id).first() if order_id else None
    if payment is None:
        return "ignored"

    # A late failure must not reverse a successful capture or refund-required payment.
    if payment.status != PaymentRecordStatus.CREATED:
        return "ignored"

    _record_attempt(
        payment.id,
        AttemptStatus.FAILED,
        provider_payment_id=entity.get("id"),
        error_code=entity.get("error_code"),
        message=entity.get("error_description"),
    )
    return "processed"


def _event_entity(payload):
    return ((payload or {}).get("payload") or {}).get("payment", {}).get("entity") or {}


def _refund_entity(payload):
    return ((payload or {}).get("payload") or {}).get("refund", {}).get("entity") or {}


def _dispatch_webhook(event_type, payload):
    """Apply one event. Returns 'processed' or 'ignored'. Raises when a retry is needed."""
    if event_type == "payment.captured":
        return _handle_payment_captured(_event_entity(payload))
    if event_type == "payment.failed":
        return _handle_payment_failed(_event_entity(payload))
    if event_type == "refund.processed":
        return handle_refund_processed_event(_refund_entity(payload))
    if event_type == "refund.failed":
        return handle_refund_failed_event(_refund_entity(payload))
    # Unknown event types are recorded and acknowledged. Subscribe only to the events needed.
    return "ignored"


def process_webhook(raw_body, signature, event_id, payload):
    """Verify and process one Razorpay webhook.

    Returns 'processed', 'ignored', or 'duplicate'. Raises on failure, so the route
    returns 500 and Razorpay retries the delivery.
    """
    if not verify_webhook_signature(raw_body, signature):
        raise OrderError("INVALID_WEBHOOK_SIGNATURE", "Webhook signature is invalid.", 400)
    if not event_id:
        raise OrderError("MISSING_EVENT_ID", "Razorpay event ID is required.", 400)

    existing = WebhookEvent.query.filter_by(provider_event_id=event_id).first()
    if existing and existing.processing_status in (WebhookStatus.PROCESSED, WebhookStatus.IGNORED):
        return "duplicate"

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
        outcome = _dispatch_webhook(event_type, payload)
        event.processing_status = outcome
        event.processed_at = utcnow()
        db.session.commit()
        return outcome

    except Exception as exc:
        db.session.rollback()
        # Keep a failed record so Razorpay can retry it, and so an operator can inspect it.
        failed = WebhookEvent.query.filter_by(provider_event_id=event_id).first()
        if failed:
            failed.processing_status = WebhookStatus.FAILED
            failed.last_error = (exc.code if isinstance(exc, OrderError) else type(exc).__name__)[:100]
        else:
            failed = WebhookEvent(
                provider_event_id=event_id,
                event_type=event_type,
                payload_hash=hashlib.sha256(raw_body).hexdigest(),
                processing_status=WebhookStatus.FAILED,
                last_error=(exc.code if isinstance(exc, OrderError) else type(exc).__name__)[:100],
            )
            db.session.add(failed)
        db.session.commit()
        raise


def get_available_payment_methods(order_id=None, student_id=None):
    """Return available payment methods and eligibility for the active canteen configuration."""
    settings = get_canteen_settings()
    order = None
    if order_id is not None:
        query = Order.query.filter_by(id=order_id)
        if student_id is not None:
            query = query.filter_by(student_id=student_id)
        order = query.first()

    cash_max_paise = settings.get("cash_max_order_paise", 15000)
    cash_eligible = False
    if settings.get("cash_enabled"):
        if order is None:
            cash_eligible = True
        else:
            cash_eligible = order.total_paise <= cash_max_paise

    return {
        "payment_provider": settings.get("payment_provider", "sandbox"),
        "merchant_display_name": settings.get("merchant_display_name", "TrayUP Canteen"),
        "upi": {
            "enabled": bool(settings.get("upi_vpa")),
            "vpa": settings.get("upi_vpa"),
        },
        "cash": {
            "enabled": settings.get("cash_enabled", False),
            "max_order_paise": cash_max_paise,
            "eligible_for_order": cash_eligible,
        },
        "sandbox": {
            "enabled": settings.get("sandbox_enabled", False),
        },
    }


def initiate_upi_order(internal_order_id, student_id):
    """Initiate UPI payment for an order and generate UPI intent links."""
    order = Order.query.filter_by(id=internal_order_id, student_id=student_id).with_for_update().first()
    if order is None:
        raise OrderError("ORDER_NOT_FOUND", "Order not found.", 404)

    if order.order_status != OrderStatus.PENDING_PAYMENT or order.payment_status not in (
        PaymentStatus.PENDING,
        PaymentStatus.AWAITING_CONFIRMATION,
    ):
        raise OrderError("ORDER_NOT_PAYABLE", "This order is not waiting for payment.", 409)

    if payment_window_closed(order):
        expire_order(order)
        db.session.commit()
        raise OrderError("ORDER_EXPIRED", "This order's payment window has expired. Place a new order.", 409)

    settings = get_canteen_settings()
    vpa = settings.get("upi_vpa") or current_app.config.get("CANTEEN_UPI_VPA")
    if not vpa:
        raise OrderError("UPI_NOT_CONFIGURED", "UPI payments are not configured on this canteen.", 503)
    merchant_name = settings.get("merchant_display_name") or current_app.config.get("CANTEEN_MERCHANT_NAME", "TrayUP Canteen")

    provider = "phonepe" if settings.get("payment_provider") == "phonepe" else "upi_soundbox"
    provider_order_id = f"upi_{order.order_number}"

    payment = Payment.query.filter_by(order_id=order.id).first()
    if payment is None:
        payment = Payment(
            order_id=order.id,
            payment_provider=provider,
            provider_order_id=provider_order_id,
            amount_paise=order.total_paise,
            currency=CURRENCY,
            status=PaymentRecordStatus.CREATED,
        )
        db.session.add(payment)
        db.session.commit()
    elif payment.status == PaymentRecordStatus.PAID:
        raise OrderError("ORDER_ALREADY_PAID", "This order has already been paid.", 409)

    intent_data = build_upi_intent_uri(
        vpa=vpa,
        merchant_name=merchant_name,
        amount_paise=order.total_paise,
        order_number=order.order_number,
        note=f"Order {order.order_number}",
    )
    intent_data["order_id"] = order.id
    intent_data["payment_id"] = payment.id
    intent_data["qr_svg_url"] = f"/api/payments/{order.id}/upi-qr.svg"
    return intent_data


def get_order_upi_qr_svg(internal_order_id, student_id=None):
    """Generate pure SVG QR code for an order's UPI payment intent."""
    query = Order.query.filter_by(id=internal_order_id)
    if student_id is not None:
        query = query.filter_by(student_id=student_id)
    order = query.first()
    if order is None:
        raise OrderError("ORDER_NOT_FOUND", "Order not found.", 404)

    settings = get_canteen_settings()
    vpa = settings.get("upi_vpa") or current_app.config.get("CANTEEN_UPI_VPA")
    if not vpa:
        raise OrderError("UPI_NOT_CONFIGURED", "UPI payments are not configured on this canteen.", 503)
    merchant_name = settings.get("merchant_display_name") or current_app.config.get("CANTEEN_MERCHANT_NAME", "TrayUP Canteen")

    intent_data = build_upi_intent_uri(
        vpa=vpa,
        merchant_name=merchant_name,
        amount_paise=order.total_paise,
        order_number=order.order_number,
    )
    return render_upi_qr_svg(intent_data["upi_uri"])


def submit_upi_claim(internal_order_id, student_id, utr_number=None):
    """Student submits payment claim with optional 12-digit UPI UTR."""
    order = Order.query.filter_by(id=internal_order_id, student_id=student_id).with_for_update().first()
    if order is None:
        raise OrderError("ORDER_NOT_FOUND", "Order not found.", 404)

    if order.order_status != OrderStatus.PENDING_PAYMENT or order.payment_status not in (
        PaymentStatus.PENDING,
        PaymentStatus.AWAITING_CONFIRMATION,
    ):
        raise OrderError("ORDER_NOT_PAYABLE", "This order is not waiting for payment.", 409)

    cleaned_utr = None
    if utr_number is not None:
        cleaned_utr = str(utr_number).strip()
        if not re.match(r"^[0-9A-Za-z]{12}$", cleaned_utr):
            raise OrderError("INVALID_UTR", "UTR number must be exactly 12 alphanumeric characters.", 400)

        duplicate = Order.query.filter(Order.utr_number == cleaned_utr, Order.id != order.id).first()
        if duplicate is not None:
            raise OrderError("DUPLICATE_UTR", "This UTR number has already been submitted for another order.", 409)

    order.payment_status = PaymentStatus.AWAITING_CONFIRMATION
    order.payment_method = "upi_soundbox"
    if cleaned_utr:
        order.utr_number = cleaned_utr

    payment = Payment.query.filter_by(order_id=order.id).first()
    if payment is None:
        payment = Payment(
            order_id=order.id,
            payment_provider="upi_soundbox",
            provider_order_id=f"upi_{order.order_number}",
            amount_paise=order.total_paise,
            currency=CURRENCY,
            status=PaymentRecordStatus.AWAITING_CONFIRMATION,
            utr_number=cleaned_utr,
        )
        db.session.add(payment)
    else:
        payment.status = PaymentRecordStatus.AWAITING_CONFIRMATION
        if cleaned_utr:
            payment.utr_number = cleaned_utr

    now = utcnow()
    db.session.add(OrderStatusHistory(
        order_id=order.id,
        previous_status=OrderStatus.PENDING_PAYMENT,
        new_status=OrderStatus.PENDING_PAYMENT,
        changed_by=student_id,
        changed_at=now,
        notes=f"UPI payment claim submitted (UTR: {cleaned_utr or 'None'})",
    ))
    db.session.commit()
    sync_order_to_firebase(order)
    return order


def select_cash_payment(internal_order_id, student_id):
    """Student chooses cash payment at counter."""
    order = Order.query.filter_by(id=internal_order_id, student_id=student_id).with_for_update().first()
    if order is None:
        raise OrderError("ORDER_NOT_FOUND", "Order not found.", 404)

    if order.order_status != OrderStatus.PENDING_PAYMENT or order.payment_status != PaymentStatus.PENDING:
        raise OrderError("ORDER_NOT_PAYABLE", "This order is not waiting for payment.", 409)

    settings = get_canteen_settings()
    if not settings.get("cash_enabled"):
        raise OrderError("CASH_NOT_ENABLED", "Cash payments are currently disabled by the canteen.", 403)

    cash_max_paise = settings.get("cash_max_order_paise", 15000)
    if order.total_paise > cash_max_paise:
        raise OrderError(
            "CASH_LIMIT_EXCEEDED",
            f"Cash payments are limited to maximum ₹{cash_max_paise / 100:.2f}.",
            400,
        )

    order.payment_status = PaymentStatus.AWAITING_CONFIRMATION
    order.payment_method = "cash"

    payment = Payment.query.filter_by(order_id=order.id).first()
    if payment is None:
        payment = Payment(
            order_id=order.id,
            payment_provider="cash",
            provider_order_id=f"cash_{order.order_number}",
            amount_paise=order.total_paise,
            currency=CURRENCY,
            status=PaymentRecordStatus.AWAITING_CONFIRMATION,
        )
        db.session.add(payment)
    else:
        payment.payment_provider = "cash"
        payment.status = PaymentRecordStatus.AWAITING_CONFIRMATION

    now = utcnow()
    db.session.add(OrderStatusHistory(
        order_id=order.id,
        previous_status=OrderStatus.PENDING_PAYMENT,
        new_status=OrderStatus.PENDING_PAYMENT,
        changed_by=student_id,
        changed_at=now,
        notes="Cash at counter selected",
    ))
    db.session.commit()
    sync_order_to_firebase(order)
    return order


def complete_sandbox_payment(internal_order_id, student_id):
    """Simulate 1-click test payment in development or testing environments."""
    if not current_app.config.get("PAYMENT_SANDBOX_ENABLED", False):
        raise OrderError("SANDBOX_DISABLED", "Payment sandbox is disabled in this environment.", 403)

    order = Order.query.filter_by(id=internal_order_id, student_id=student_id).with_for_update().first()
    if order is None:
        raise OrderError("ORDER_NOT_FOUND", "Order not found.", 404)

    if order.order_status != OrderStatus.PENDING_PAYMENT or order.payment_status not in (
        PaymentStatus.PENDING,
        PaymentStatus.AWAITING_CONFIRMATION,
    ):
        raise OrderError("ORDER_NOT_PAYABLE", "This order is not waiting for payment.", 409)

    order.payment_method = "sandbox"
    payment = Payment.query.filter_by(order_id=order.id).first()
    if payment is None:
        payment = Payment(
            order_id=order.id,
            payment_provider="sandbox",
            provider_order_id=f"sandbox_{order.order_number}",
            amount_paise=order.total_paise,
            currency=CURRENCY,
            status=PaymentRecordStatus.CREATED,
        )
        db.session.add(payment)
        db.session.flush()

    payment, refund_required = _confirm_captured_payment(
        payment=payment,
        provider_payment_id=f"sandbox_pay_{order.order_number}",
        amount_paise=order.total_paise,
        currency=CURRENCY,
        notes="Simulated payment completed via test sandbox",
    )
    return order, refund_required


def confirm_manual_payment(internal_order_id, staff_user_id, notes=None):
    """Kitchen or Admin staff confirms a payment upon Soundbox alert or cash receipt."""
    order = Order.query.filter_by(id=internal_order_id).with_for_update().first()
    if order is None:
        raise OrderError("ORDER_NOT_FOUND", "Order not found.", 404)

    if order.order_status != OrderStatus.PENDING_PAYMENT or order.payment_status not in (
        PaymentStatus.PENDING,
        PaymentStatus.AWAITING_CONFIRMATION,
    ):
        raise OrderError("ORDER_NOT_PAYABLE", "This order is not waiting for payment confirmation.", 409)

    payment = Payment.query.filter_by(order_id=order.id).first()
    if payment is None:
        provider = order.payment_method or "upi_soundbox"
        payment = Payment(
            order_id=order.id,
            payment_provider=provider,
            provider_order_id=f"manual_{order.order_number}",
            amount_paise=order.total_paise,
            currency=CURRENCY,
            status=PaymentRecordStatus.AWAITING_CONFIRMATION,
            utr_number=order.utr_number,
        )
        db.session.add(payment)
        db.session.flush()

    payment, refund_required = _confirm_captured_payment(
        payment=payment,
        provider_payment_id=f"staff_{staff_user_id}_{order.order_number}",
        amount_paise=order.total_paise,
        currency=CURRENCY,
        confirmed_by=staff_user_id,
        notes=notes or "Payment confirmed by staff at counter",
    )
    return order, refund_required


def reject_manual_payment(internal_order_id, staff_user_id, reason=None):
    """Kitchen or Admin staff rejects a payment claim and cancels order / releases stock."""
    order = Order.query.filter_by(id=internal_order_id).with_for_update().first()
    if order is None:
        raise OrderError("ORDER_NOT_FOUND", "Order not found.", 404)

    if order.order_status != OrderStatus.PENDING_PAYMENT:
        raise OrderError("ORDER_NOT_CANCELLABLE", "Only pending orders can be rejected.", 409)

    order.order_status = OrderStatus.CANCELLED
    order.payment_status = PaymentStatus.FAILED
    release_reservations(order.id)

    payment = Payment.query.filter_by(order_id=order.id).first()
    if payment is not None:
        payment.status = "failed"

    now = utcnow()
    db.session.add(OrderStatusHistory(
        order_id=order.id,
        previous_status=OrderStatus.PENDING_PAYMENT,
        new_status=OrderStatus.CANCELLED,
        changed_by=staff_user_id,
        changed_at=now,
        notes=f"Payment rejected by staff: {reason or 'Unverified/Unpaid'}",
    ))
    db.session.commit()
    sync_order_to_firebase(order)
    return order


def process_phonepe_webhook(raw_body_bytes, x_verify_header):
    """Process a server-to-server webhook callback from PhonePe."""
    salt_key = current_app.config.get("PHONEPE_SALT_KEY", "")
    salt_index = current_app.config.get("PHONEPE_SALT_INDEX", "1")
    if not salt_key:
        raise OrderError("PHONEPE_NOT_CONFIGURED", "PhonePe secrets are not configured on this server.", 503)

    callback_dict, response_b64 = decode_phonepe_callback(
        raw_body_bytes=raw_body_bytes,
        x_verify_header=x_verify_header,
        salt_key=salt_key,
        salt_index=salt_index,
    )

    data = callback_dict.get("data", {})
    code = callback_dict.get("code")
    merchant_txn = str(data.get("merchantTransactionId", "")).strip()
    txn_id = str(data.get("transactionId") or merchant_txn).strip()

    if not txn_id:
        raise OrderError("INVALID_PAYLOAD", "Missing transaction identifier in PhonePe callback.", 400)

    # Idempotency check via WebhookEvent
    existing = WebhookEvent.query.filter_by(provider="phonepe", provider_event_id=txn_id).first()
    if existing and existing.processing_status == WebhookStatus.PROCESSED:
        return {"event_id": txn_id, "outcome": "already_processed"}

    event = existing or WebhookEvent(
        provider="phonepe",
        provider_event_id=txn_id,
        event_type=code or "PAYMENT_CALLBACK",
        payload_hash=hashlib.sha256(raw_body_bytes).hexdigest(),
        processing_status=WebhookStatus.RECEIVED,
    )
    db.session.add(event)
    db.session.flush()

    # Match order
    clean_num = merchant_txn.replace("phonepe_", "").replace("upi_", "").strip()
    order = Order.query.filter(
        (Order.order_number == merchant_txn) | (Order.order_number == clean_num)
    ).with_for_update().first()

    if order is None:
        event.processing_status = WebhookStatus.IGNORED
        event.processed_at = utcnow()
        db.session.commit()
        return {"event_id": txn_id, "outcome": "ignored_unknown_order"}

    if code == "PAYMENT_SUCCESS" and data.get("state") == "COMPLETED":
        payment = Payment.query.filter_by(order_id=order.id).first()
        if payment is None:
            payment = Payment(
                order_id=order.id,
                payment_provider="phonepe",
                provider_order_id=f"phonepe_{order.order_number}",
                amount_paise=order.total_paise,
                currency=CURRENCY,
                status=PaymentRecordStatus.CREATED,
            )
            db.session.add(payment)
            db.session.flush()

        payment_instrument = data.get("paymentInstrument") or {}
        utr = payment_instrument.get("utr")
        if utr:
            payment.utr_number = str(utr).strip()
            order.utr_number = str(utr).strip()

        order.payment_method = "phonepe"
        payment, refund_required = _confirm_captured_payment(
            payment=payment,
            provider_payment_id=txn_id,
            amount_paise=data.get("amount", order.total_paise),
            currency=CURRENCY,
            notes="PhonePe S2S verified callback",
        )
        event.processing_status = WebhookStatus.PROCESSED
        event.processed_at = utcnow()
        db.session.commit()
        return {"event_id": txn_id, "outcome": "payment_confirmed", "refund_required": refund_required}
    else:
        # Failure or cancellation
        event.processing_status = WebhookStatus.PROCESSED
        event.processed_at = utcnow()
        db.session.commit()
        return {"event_id": txn_id, "outcome": "payment_failed"}
