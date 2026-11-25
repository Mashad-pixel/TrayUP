import json

from flask import Blueprint, Response, current_app, request
from flask_login import current_user, login_required

from app.extensions import csrf, limiter
from app.models.user import UserRole
from app.security.permissions import roles_required
from app.responses import error_response, success_response
from app.services.errors import OrderError
from app.services.payment_service import (
    LATE_PAYMENT_CODE,
    LATE_PAYMENT_MESSAGE,
    complete_sandbox_payment,
    create_payment_order,
    get_available_payment_methods,
    get_order_upi_qr_svg,
    initiate_upi_order,
    process_phonepe_webhook,
    process_webhook,
    submit_upi_claim,
    verify_checkout,
    verify_webhook_signature,
)

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


@payments_bp.route("/methods", methods=["GET"])
@login_required
@roles_required(UserRole.STUDENT)
def payment_methods():
    order_id = request.args.get("order_id", type=int)
    methods = get_available_payment_methods(order_id=order_id, student_id=current_user.id)
    return success_response("Payment methods retrieved", methods)


@payments_bp.route("/upi/initiate", methods=["POST"])
@login_required
@roles_required(UserRole.STUDENT)
@limiter.limit("20 per minute")
def initiate_upi():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "Request body must be a JSON object.", 400)

    order_id = payload.get("order_id")
    if isinstance(order_id, bool) or not isinstance(order_id, int) or order_id < 1:
        return error_response("INVALID_ORDER_ID", "order_id must be a positive whole number.", 400)

    try:
        data = initiate_upi_order(order_id, current_user.id)
    except OrderError as exc:
        return _order_error(exc)

    return success_response("UPI payment initiated", data)


@payments_bp.route("/<int:order_id>/upi-qr.svg", methods=["GET"])
@login_required
@roles_required(UserRole.STUDENT)
def order_upi_qr_svg(order_id):
    try:
        svg_content = get_order_upi_qr_svg(order_id, current_user.id)
    except OrderError as exc:
        return _order_error(exc)

    return Response(svg_content, mimetype="image/svg+xml")


@payments_bp.route("/upi/submit-claim", methods=["POST"])
@login_required
@roles_required(UserRole.STUDENT)
@limiter.limit("20 per minute")
def submit_claim():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "Request body must be a JSON object.", 400)

    order_id = payload.get("order_id")
    if isinstance(order_id, bool) or not isinstance(order_id, int) or order_id < 1:
        return error_response("INVALID_ORDER_ID", "order_id must be a positive whole number.", 400)

    utr_number = payload.get("utr_number")
    try:
        order = submit_upi_claim(order_id, current_user.id, utr_number=utr_number)
    except OrderError as exc:
        return _order_error(exc)

    return success_response("Payment claim submitted. Awaiting staff confirmation.", {
        "order_id": order.id,
        "order_number": order.order_number,
        "order_status": order.order_status,
        "payment_status": order.payment_status,
        "utr_number": order.utr_number,
    })


@payments_bp.route("/sandbox/complete", methods=["POST"])
@login_required
@roles_required(UserRole.STUDENT)
@limiter.limit("30 per minute")
def complete_sandbox():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "Request body must be a JSON object.", 400)

    order_id = payload.get("order_id")
    if isinstance(order_id, bool) or not isinstance(order_id, int) or order_id < 1:
        return error_response("INVALID_ORDER_ID", "order_id must be a positive whole number.", 400)

    try:
        order, refund_required = complete_sandbox_payment(order_id, current_user.id)
    except OrderError as exc:
        return _order_error(exc)

    return success_response("Sandbox payment completed", {
        "order_id": order.id,
        "order_number": order.order_number,
        "order_status": order.order_status,
        "payment_status": order.payment_status,
        "refund_required": refund_required,
    })


@payments_bp.route("/webhook/phonepe", methods=["POST"])
@csrf.exempt
def phonepe_webhook():
    raw_body = request.get_data(cache=False)
    x_verify = request.headers.get("X-VERIFY", "").strip()
    if not x_verify:
        return error_response("MISSING_SIGNATURE", "X-VERIFY header is required.", 400)

    try:
        result = process_phonepe_webhook(raw_body, x_verify)
    except OrderError as exc:
        return _order_error(exc)
    except Exception:
        current_app.logger.exception("PhonePe webhook processing failed")
        return error_response("WEBHOOK_PROCESSING_FAILED", "Could not process PhonePe callback.", 500)

    return success_response("PhonePe callback processed", result)
