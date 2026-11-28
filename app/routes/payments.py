import json

from flask import Blueprint, current_app, make_response, request
from flask_login import current_user, login_required

from app.extensions import csrf, db, limiter
from app.models.user import UserRole
from app.security.permissions import roles_required
from app.responses import error_response, success_response
from app.services.errors import OrderError
from app.services.payment_service import (
    LATE_PAYMENT_CODE,
    LATE_PAYMENT_MESSAGE,
    create_payment_order,
    process_webhook,
    verify_checkout,
    verify_webhook_signature,
)
from app.services.upi_payment_service import (
    payment_methods,
    phonepe_webhook,
    start_upi_payment,
    submit_upi_claim,
    upi_qr_for_order,
)
from app.services.inventory_service import commit_reservations
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.order_status_history import OrderStatusHistory
from app.services.time_utils import utcnow

payments_bp = Blueprint("payments", __name__, url_prefix="/api/payments")


def _order_error(exc):
    return error_response(exc.code, exc.message, exc.status)


def _required_string(payload, key):
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


@payments_bp.route("/create-order", methods=["POST"])
@login_required
@roles_required(UserRole.STUDENT)
@limiter.limit("10 per minute")
def create_payment_order_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "Request body must be a JSON object.", 400)

    order_id = payload.get("order_id")
    if isinstance(order_id, bool) or not isinstance(order_id, int) or order_id < 1:
        return error_response("INVALID_ORDER_ID", "order_id must be a positive whole number.", 400)

    try:
        payment, order = create_payment_order(order_id, current_user.id)
    except OrderError as exc:
        return _order_error(exc)

    # The key_id is public (the browser needs it for Checkout). The key secret is never sent.
    return success_response("Payment order created", {
        "key_id": current_app.config.get("RAZORPAY_KEY_ID", ""),
        "razorpay_order_id": payment.provider_order_id,
        "amount_paise": payment.amount_paise,
        "currency": payment.currency,
        "order_id": order.id,
        "order_number": order.order_number,
    })


@payments_bp.get("/methods")
@login_required
@roles_required(UserRole.STUDENT)
def payment_methods_route():
    raw_order_id = request.args.get("order_id", "")
    try:
        order_id = int(raw_order_id)
        if order_id < 1:
            raise ValueError
        data = payment_methods(order_id, current_user.id)
    except ValueError:
        return error_response("INVALID_ORDER_ID", "order_id must be a positive whole number.", 400)
    except OrderError as exc:
        return _order_error(exc)
    return success_response("Payment methods retrieved", data)


@payments_bp.post("/upi/initiate")
@login_required
@roles_required(UserRole.STUDENT)
@limiter.limit("10 per minute")
def initiate_upi_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "Request body must be a JSON object.", 400)
    order_id = payload.get("order_id")
    if isinstance(order_id, bool) or not isinstance(order_id, int) or order_id < 1:
        return error_response("INVALID_ORDER_ID", "order_id must be a positive whole number.", 400)
    try:
        data = start_upi_payment(order_id, current_user.id)
    except OrderError as exc:
        return _order_error(exc)
    return success_response("UPI payment initiated", data)


@payments_bp.get("/<int:order_id>/upi-qr.svg")
@login_required
@roles_required(UserRole.STUDENT)
def upi_qr_route(order_id):
    try:
        svg = upi_qr_for_order(order_id, current_user.id)
    except OrderError as exc:
        return _order_error(exc)
    response = make_response(svg)
    response.mimetype = "image/svg+xml"
    response.headers["Cache-Control"] = "no-store"
    return response


@payments_bp.post("/upi/submit-claim")
@login_required
@roles_required(UserRole.STUDENT)
@limiter.limit("10 per minute")
def submit_upi_claim_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "Request body must be a JSON object.", 400)
    order_id = payload.get("order_id")
    if isinstance(order_id, bool) or not isinstance(order_id, int) or order_id < 1:
        return error_response("INVALID_ORDER_ID", "order_id must be a positive whole number.", 400)
    try:
        order = submit_upi_claim(order_id, current_user.id, payload.get("utr_number"))
    except OrderError as exc:
        return _order_error(exc)
    return success_response("Payment claim submitted", {
        "payment_status": order.payment_status,
        "utr_number": order.utr_number,
        "order_id": order.id,
    })


@payments_bp.post("/sandbox/complete")
@login_required
@roles_required(UserRole.STUDENT)
def complete_sandbox_payment_route():
    if not current_app.testing:
        return error_response("PAYMENT_METHOD_DISABLED", "Sandbox payments are not available.", 404)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "Request body must be a JSON object.", 400)
    order_id = payload.get("order_id")
    if isinstance(order_id, bool) or not isinstance(order_id, int) or order_id < 1:
        return error_response("INVALID_ORDER_ID", "order_id must be a positive whole number.", 400)
    order = Order.query.filter_by(id=order_id, student_id=current_user.id).with_for_update().first()
    if order is None:
        return error_response("ORDER_NOT_FOUND", "Order not found.", 404)
    if order.order_status != OrderStatus.PENDING_PAYMENT or order.payment_status != PaymentStatus.PENDING:
        return error_response("ORDER_NOT_PAYABLE", "This order is not waiting for payment.", 409)
    previous = order.order_status
    now = utcnow()
    commit_reservations(order.id)
    order.payment_status = PaymentStatus.PAID
    order.order_status = OrderStatus.RECEIVED
    db.session.add(OrderStatusHistory(
        order_id=order.id,
        previous_status=previous,
        new_status=OrderStatus.RECEIVED,
        changed_by=None,
        changed_at=now,
        notes="Sandbox payment completed",
    ))
    db.session.commit()
    return success_response("Sandbox payment completed", {
        "payment_status": order.payment_status,
        "order_status": order.order_status,
    })


@payments_bp.post("/webhook/phonepe")
@csrf.exempt
def phonepe_webhook_route():
    try:
        outcome = phonepe_webhook(
            request.get_data(cache=False),
            request.headers.get("X-VERIFY", ""),
        )
    except OrderError as exc:
        db.session.rollback()
        return _order_error(exc)
    return success_response("PhonePe webhook received", {"outcome": outcome})


@payments_bp.route("/verify", methods=["POST"])
@login_required
@roles_required(UserRole.STUDENT)
@limiter.limit("20 per minute")
def verify_payment_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "Request body must be a JSON object.", 400)

    razorpay_order_id = _required_string(payload, "razorpay_order_id")
    razorpay_payment_id = _required_string(payload, "razorpay_payment_id")
    razorpay_signature = _required_string(payload, "razorpay_signature")

    if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
        return error_response(
            "MISSING_FIELDS",
            "razorpay_order_id, razorpay_payment_id and razorpay_signature are required.",
            400,
        )

    try:
        order, refund_required = verify_checkout(
            order_id=razorpay_order_id,
            payment_id=razorpay_payment_id,
            signature=razorpay_signature,
            student_id=current_user.id,
        )
    except OrderError as exc:
        return _order_error(exc)

    if refund_required:
        return error_response(LATE_PAYMENT_CODE, LATE_PAYMENT_MESSAGE, 409)

    return success_response("Payment verified", {
        "order_id": order.id,
        "order_number": order.order_number,
        "order_status": order.order_status,
        "payment_status": order.payment_status,
    })


@payments_bp.route("/webhook", methods=["POST"])
@csrf.exempt
def razorpay_webhook():
    # Read the raw bytes first. The signature is calculated over exactly these bytes.
    raw_body = request.get_data(cache=False)
    signature = request.headers.get("X-Razorpay-Signature", "")
    event_id = request.headers.get("X-Razorpay-Event-Id", "").strip()

    try:
        signature_valid = verify_webhook_signature(raw_body, signature)
    except OrderError as exc:
        return _order_error(exc)

    if not signature_valid:
        return error_response("INVALID_SIGNATURE", "Webhook signature is invalid.", 400)

    if not event_id or len(event_id) > 100:
        return error_response("INVALID_EVENT_ID", "X-Razorpay-Event-Id header is missing or invalid.", 400)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return error_response("INVALID_JSON", "Webhook body is not valid JSON.", 400)

    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "Webhook body must be a JSON object.", 400)

    event_type = payload.get("event")
    if not isinstance(event_type, str) or not event_type:
        return error_response("INVALID_EVENT", "Webhook event type is missing.", 400)

    try:
        outcome = process_webhook(raw_body, signature, event_id, payload)
    except Exception as exc:
        # Do not log exception text or payload data; it can include provider/client details.
        # 500 makes Razorpay retry the delivery.
        current_app.logger.error(
            "Webhook processing failed for event %s (%s)",
            event_id,
            type(exc).__name__,
        )
        return error_response("WEBHOOK_PROCESSING_FAILED", "Could not process the event.", 500)

    return success_response("Webhook received", {"event_id": event_id, "outcome": outcome})
