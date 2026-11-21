from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.extensions import limiter
from app.services.errors import OrderError
from app.services.order_service import create_order

orders_bp = Blueprint("orders", __name__, url_prefix="/api/orders")


def success_response(message, data, status=200):
    return jsonify({"success": True, "message": message, "data": data}), status


def error_response(code, message, status):
    return (
        jsonify({"success": False, "message": message, "error": {"code": code}}),
        status,
    )


def serialize_order(order, raw_token=None):
    data = {
        "id": order.id,
        "order_number": order.order_number,
        "order_status": order.order_status,
        "payment_status": order.payment_status,
        "subtotal_paise": order.subtotal_paise,
        "discount_paise": order.discount_paise,
        "tax_paise": order.tax_paise,
        "total_paise": order.total_paise,
        "items": [
            {
                "menu_item_id": item.menu_item_id,
                "item_name": item.item_name_snapshot,
                "unit_price_paise": item.unit_price_snapshot_paise,
                "quantity": item.quantity,
                "line_total_paise": item.line_total_paise,
            }
            for item in order.items
        ],
        "created_at": order.created_at.isoformat(),
    }

    # The raw token is shown only on creation. It is never stored in plain text.
    if raw_token is not None:
        data["tracking_token"] = raw_token

    return data


@orders_bp.route("", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def create_order_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "Request body must be a JSON object.", 400)

    try:
        order, raw_token = create_order(
            student_id=current_user.id,
            raw_items=payload.get("items"),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
    except OrderError as exc:
        return error_response(exc.code, exc.message, exc.status)

    if raw_token is not None:
        return success_response(
            "Order created successfully",
            serialize_order(order, raw_token),
            201,
        )

    # Retried request with the same Idempotency-Key: return the original order.
    return success_response(
        "Existing order returned",
        serialize_order(order),
        200,
    )
