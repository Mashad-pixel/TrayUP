import hashlib
import secrets
import re

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.canteen import CanteenSettings
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.order_status_history import OrderStatusHistory
from app.models.payment import Payment, PaymentRecordStatus
from app.models.webhook_event import WebhookEvent, WebhookStatus
from app.services.errors import OrderError
from app.services.inventory_service import commit_reservations, release_reservations
from app.services.time_utils import utcnow
from app.services.upi_service import build_upi_intent_uri, decode_phonepe_callback

_UTR_PATTERN = re.compile(r"^\d{12}$")


def _settings():
    row = db.session.get(CanteenSettings, 1)
    return {
        "payment_provider": row.payment_provider if row else "sandbox",
        "merchant_display_name": row.merchant_display_name if row else "TrayUP Canteen",
        "upi_vpa": (row.upi_vpa if row else None) or current_app.config.get("UPI_VPA", ""),
        "cash_enabled": row.cash_enabled if row else False,
        "cash_max_order_paise": row.cash_max_order_paise if row else 15000,
    }


def available_payment_methods():
    settings = _settings()
    return {
        **settings,
        "upi": True,
        "sandbox": current_app.testing or current_app.config.get("PAYMENT_SANDBOX_ENABLED", False),
    }


def payment_methods(order_id, student_id):
    order = Order.query.filter_by(id=order_id, student_id=student_id).first()
    if order is None:
        raise OrderError("ORDER_NOT_FOUND", "Order not found.", 404)
    settings = _settings()
    return {
        **settings,
        "upi": True,
        "sandbox": current_app.testing,
    }


def start_upi_payment(order_id, student_id):
    order = Order.query.filter_by(id=order_id, student_id=student_id).with_for_update().first()
    if order is None:
        raise OrderError("ORDER_NOT_FOUND", "Order not found.", 404)
    if order.order_status != OrderStatus.PENDING_PAYMENT or order.payment_status != PaymentStatus.PENDING:
        raise OrderError("ORDER_NOT_PAYABLE", "This order is not waiting for payment.", 409)

    settings = _settings()
    vpa = settings["upi_vpa"]
    if not vpa:
        raise OrderError("PAYMENTS_NOT_CONFIGURED", "UPI payments are not configured.", 503)
    payment = Payment.query.filter_by(order_id=order.id, status=PaymentRecordStatus.CREATED).first()
    if payment is None:
        payment = Payment(
            order_id=order.id,
            payment_provider="upi",
            provider_order_id="upi_" + secrets.token_urlsafe(24),
            amount_paise=order.total_paise,
            currency="INR",
            status=PaymentRecordStatus.CREATED,
        )
        db.session.add(payment)
        db.session.commit()

    links = build_upi_intent_uri(
        vpa=vpa,
        merchant_name=settings["merchant_display_name"],
        amount_paise=order.total_paise,
        order_number=order.order_number,
    )
    return {
        **links,
        "order_id": order.id,
        "payment_id": payment.id,
        "payment_provider": settings["payment_provider"],
    }


def upi_qr_for_order(order_id, student_id):
    from app.services.upi_service import render_upi_qr_svg

    data = start_upi_payment(order_id, student_id)
    return render_upi_qr_svg(data["upi_uri"])


def submit_upi_claim(order_id, student_id, raw_utr):
    if not isinstance(raw_utr, str):
        raise OrderError("INVALID_UTR", "Enter a valid 12-digit UTR number.", 400)
    utr = raw_utr.strip()
    if not _UTR_PATTERN.fullmatch(utr):
        raise OrderError("INVALID_UTR", "Enter a valid 12-digit UTR number.", 400)
    if Order.query.filter(Order.utr_number == utr).first() is not None:
        raise OrderError("DUPLICATE_UTR", "That UTR number has already been submitted.", 409)

    order = Order.query.filter_by(id=order_id, student_id=student_id).with_for_update().first()
    if order is None:
        raise OrderError("ORDER_NOT_FOUND", "Order not found.", 404)
    if order.order_status != OrderStatus.PENDING_PAYMENT or order.payment_status != PaymentStatus.PENDING:
        raise OrderError("ORDER_NOT_PAYABLE", "This order is not waiting for payment.", 409)

    payment = Payment.query.filter_by(order_id=order.id, status=PaymentRecordStatus.CREATED).first()
    if payment is None:
        payment = Payment(
            order_id=order.id,
            payment_provider="upi",
            provider_order_id="upi_" + secrets.token_urlsafe(24),
            amount_paise=order.total_paise,
            currency="INR",
            status=PaymentRecordStatus.CREATED,
        )
        db.session.add(payment)
    order.utr_number = utr
    order.payment_method = "upi"
    order.payment_status = PaymentStatus.AWAITING_CONFIRMATION
    payment.utr_number = utr
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise OrderError("DUPLICATE_UTR", "That UTR number has already been submitted.", 409) from exc
    return order


def confirm_upi_payment(order_id, staff_id, notes=""):
    order = Order.query.filter_by(id=order_id).with_for_update().first()
    if order is None:
        raise OrderError("ORDER_NOT_FOUND", "Order not found.", 404)
    if order.payment_status != PaymentStatus.AWAITING_CONFIRMATION:
        raise OrderError("PAYMENT_NOT_AWAITING_CONFIRMATION", "No UPI payment is awaiting confirmation.", 409)
    now = utcnow()
    commit_reservations(order.id)
    previous = order.order_status
    order.payment_status = PaymentStatus.PAID
    order.order_status = OrderStatus.RECEIVED
    payment = Payment.query.filter_by(order_id=order.id).order_by(Payment.created_at.desc()).first()
    if payment is not None:
        payment.status = PaymentRecordStatus.PAID
        payment.verified_at = now
    db.session.add(OrderStatusHistory(
        order_id=order.id,
        previous_status=previous,
        new_status=OrderStatus.RECEIVED,
        changed_by=staff_id,
        changed_at=now,
        notes=notes or "UPI payment confirmed by staff",
    ))
    db.session.commit()
    return order


def reject_upi_payment(order_id, staff_id, reason):
    order = Order.query.filter_by(id=order_id).with_for_update().first()
    if order is None:
        raise OrderError("ORDER_NOT_FOUND", "Order not found.", 404)
    if order.payment_status != PaymentStatus.AWAITING_CONFIRMATION:
        raise OrderError("PAYMENT_NOT_AWAITING_CONFIRMATION", "No UPI payment is awaiting confirmation.", 409)
    now = utcnow()
    previous = order.order_status
    order.payment_status = PaymentStatus.FAILED
    order.order_status = OrderStatus.CANCELLED
    release_reservations(order.id)
    payment = Payment.query.filter_by(order_id=order.id).order_by(Payment.created_at.desc()).first()
    if payment is not None:
        payment.status = PaymentRecordStatus.FAILED
    db.session.add(OrderStatusHistory(
        order_id=order.id,
        previous_status=previous,
        new_status=OrderStatus.CANCELLED,
        changed_by=staff_id,
        changed_at=now,
        notes=reason or "UPI payment rejected by staff",
    ))
    db.session.commit()
    return order


def phonepe_webhook(raw_body, signature):
    config = current_app.config
    payload, _ = decode_phonepe_callback(
        raw_body,
        signature,
        config.get("PHONEPE_SALT_KEY", ""),
        config.get("PHONEPE_SALT_INDEX", "1"),
    )
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise OrderError("INVALID_DECODED_DATA", "PhonePe callback data is invalid.", 400)
    event_id = data.get("transactionId")
    merchant_transaction_id = data.get("merchantTransactionId")
    if not isinstance(event_id, str) or not event_id or not isinstance(merchant_transaction_id, str):
        raise OrderError("INVALID_DECODED_DATA", "PhonePe transaction details are missing.", 400)

    existing = WebhookEvent.query.filter_by(provider="phonepe", provider_event_id=event_id).first()
    if existing is not None and existing.processing_status == WebhookStatus.PROCESSED:
        return "already_processed"

    order_number = merchant_transaction_id.removeprefix("phonepe_")
    order = Order.query.filter_by(order_number=order_number).with_for_update().first()
    event = WebhookEvent(
        provider="phonepe",
        provider_event_id=event_id,
        event_type=str(payload.get("code", "unknown")),
        payload_hash=hashlib.sha256(raw_body).hexdigest(),
        processing_status=WebhookStatus.RECEIVED,
    )
    db.session.add(event)
    if order is None:
        event.processing_status = WebhookStatus.IGNORED
        db.session.commit()
        return "ignored"

    if data.get("amount") != order.total_paise:
        raise OrderError("PAYMENT_MISMATCH", "PhonePe amount does not match the order.", 409)
    if payload.get("success") is not True:
        event.processing_status = WebhookStatus.IGNORED
        db.session.commit()
        return "payment_failed"

    utr = (data.get("paymentInstrument") or {}).get("utr")
    if isinstance(utr, str) and _UTR_PATTERN.fullmatch(utr):
        order.utr_number = utr
    previous = order.order_status
    order.payment_method = "phonepe"
    order.payment_status = PaymentStatus.PAID
    order.order_status = OrderStatus.RECEIVED
    commit_reservations(order.id)
    db.session.add(OrderStatusHistory(
        order_id=order.id,
        previous_status=previous,
        new_status=OrderStatus.RECEIVED,
        changed_by=None,
        changed_at=utcnow(),
        notes="PhonePe payment confirmed",
    ))
    event.processing_status = WebhookStatus.PROCESSED
    event.processed_at = utcnow()
    db.session.commit()
    return "payment_confirmed"
