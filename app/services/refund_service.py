from datetime import timezone

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.order import Order, PaymentStatus
from app.models.payment import Payment, PaymentRecordStatus
from app.models.refund import Refund, RefundStatus
from app.services.errors import OrderError
from app.services.razorpay_client import PROVIDER_ERRORS, get_razorpay_client
from app.services.time_utils import utcnow


def _as_utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _sync_payment_status(payment):
    refunds = Refund.query.filter_by(payment_id=payment.id).all()
    processed = sum(r.amount_paise for r in refunds if r.status == RefundStatus.PROCESSED)
    pending = sum(r.amount_paise for r in refunds if r.status == RefundStatus.PENDING)
    remaining = payment.amount_paise - processed

    if processed and remaining <= 0:
        payment.status = PaymentRecordStatus.REFUNDED
        order_status = PaymentStatus.REFUNDED
    elif processed:
        payment.status = PaymentRecordStatus.PARTIALLY_REFUNDED
        order_status = PaymentStatus.PARTIALLY_REFUNDED
    elif pending:
        payment.status = PaymentRecordStatus.REFUND_REQUIRED
        order_status = PaymentStatus.PAID
    else:
        payment.status = PaymentRecordStatus.PAID
        order_status = PaymentStatus.PAID

    order = db.session.get(Order, payment.order_id)
    if order:
        order.payment_status = order_status


def request_refund(payment_id, admin_id, amount_paise, reason):
    """Request a full or partial refund. Status changes after Razorpay confirmation."""
    try:
        payment = Payment.query.filter_by(id=payment_id).with_for_update().first()
        if payment is None:
            raise OrderError("PAYMENT_NOT_FOUND", "Payment not found.", 404)

        order = db.session.get(Order, payment.order_id)
        if order is None:
            raise OrderError("ORDER_NOT_FOUND", "Order not found.", 404)

        if payment.status not in [PaymentRecordStatus.PAID, PaymentRecordStatus.REFUND_REQUIRED, PaymentRecordStatus.PARTIALLY_REFUNDED]:
            raise OrderError("PAYMENT_NOT_REFUNDABLE", "This payment cannot be refunded.", 409)

        amount = payment.amount_paise if amount_paise is None else amount_paise
        already = sum(
            r.amount_paise
            for r in Refund.query.filter_by(payment_id=payment.id).all()
            if r.status in [RefundStatus.PENDING, RefundStatus.PROCESSED]
        )
        if amount > payment.amount_paise - already:
            raise OrderError("REFUND_TOO_LARGE", "Refund exceeds the remaining captured amount.", 400)

        client = get_razorpay_client()
        try:
            result = client.payment.refund(
                payment.provider_payment_id,
                {"amount": amount, "notes": {"reason": reason}},
            )
        except PROVIDER_ERRORS as exc:
            raise OrderError("REFUND_PROVIDER_ERROR", "Razorpay could not accept the refund. Please retry.", 502) from exc

        now = utcnow()
        status = RefundStatus.PROCESSED if result.get("status") == "processed" else RefundStatus.PENDING
        refund = Refund(
            payment_id=payment.id,
            order_id=order.id,
            provider_refund_id=result["id"],
            amount_paise=amount,
            status=status,
            reason=reason,
            requested_by=admin_id,
            created_at=now,
            processed_at=now if status == RefundStatus.PROCESSED else None,
        )
        db.session.add(refund)
        db.session.flush()
        _sync_payment_status(payment)
        db.session.commit()
        return refund, payment, order

    except Exception:
        db.session.rollback()
        raise


def _refund_by_provider_id(provider_refund_id):
    return Refund.query.filter_by(provider_refund_id=provider_refund_id).with_for_update().first()


def _update_refund(refund, status):
    if refund.status == status:
        return
    if refund.status == RefundStatus.PROCESSED:
        return  # Never reverse a confirmed refund if an older failure event arrives later.
    refund.status = status
    refund.processed_at = utcnow() if status == RefundStatus.PROCESSED else None

    payment = db.session.get(Payment, refund.payment_id)
    if payment:
        _sync_payment_status(payment)


def handle_refund_processed_event(entity):
    provider_refund_id = entity.get("id")
    refund = _refund_by_provider_id(provider_refund_id)
    if refund is None:
        # The webhook may beat our request transaction. Raising asks Razorpay to retry later.
        raise OrderError("REFUND_NOT_FOUND", "Refund record is not available yet. Retry webhook.", 404)
    _update_refund(refund, RefundStatus.PROCESSED)


def handle_refund_failed_event(entity):
    provider_refund_id = entity.get("id")
    refund = _refund_by_provider_id(provider_refund_id)
    if refund is None:
        raise OrderError("REFUND_NOT_FOUND", "Refund record is not available yet. Retry webhook.", 404)
    _update_refund(refund, RefundStatus.FAILED)


def reconcile_refund_status(payment_id):
    """Read-only summary useful for an admin's reconciliation screen."""
    payment = Payment.query.filter_by(id=payment_id).first()
    if payment is None:
        raise OrderError("PAYMENT_NOT_FOUND", "Payment not found.", 404)
    refunds = Refund.query.filter_by(payment_id=payment_id).all()
    return {
        "payment_id": payment.id,
        "payment_status": payment.status,
        "captured_paise": payment.amount_paise,
        "refunded_paise": sum(r.amount_paise for r in refunds if r.status == RefundStatus.PROCESSED),
        "pending_refund_paise": sum(r.amount_paise for r in refunds if r.status == RefundStatus.PENDING),
        "remaining_paise": payment.amount_paise - sum(
            r.amount_paise for r in refunds if r.status == RefundStatus.PROCESSED
        ),
    }
