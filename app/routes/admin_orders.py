from flask import Blueprint, request
from flask_login import login_required

from app.models.user import UserRole
from app.responses import error_response, success_response
from app.security.permissions import roles_required
from app.services.errors import OrderError
from app.services.order_query_service import (
    get_order_for_admin,
    get_status_history,
    get_students_for_orders,
    list_orders_for_admin,
    pagination_info,
    parse_pagination,
    validate_order_status,
    validate_payment_status,
)
from app.services.order_serializer import (
    serialize_order_for_admin,
    serialize_status_history,
)

admin_orders_bp = Blueprint("admin_orders", __name__, url_prefix="/api/admin/orders")


def _order_error(exc):
    return error_response(exc.code, exc.message, exc.status)


@admin_orders_bp.route("", methods=["GET"])
@login_required
@roles_required(UserRole.ADMIN)
def list_all_orders():
    try:
        page, per_page = parse_pagination(request.args)
        order_status = validate_order_status(request.args.get("order_status"))
        payment_status = validate_payment_status(request.args.get("payment_status"))
    except OrderError as exc:
        return _order_error(exc)

    pagination = list_orders_for_admin(
        page,
        per_page,
        order_status=order_status,
        payment_status=payment_status,
    )
    students = get_students_for_orders(pagination.items)

    return success_response("Orders retrieved", {
        "orders": [
            serialize_order_for_admin(order, students.get(order.student_id))
            for order in pagination.items
        ],
        "pagination": pagination_info(pagination),
    })


@admin_orders_bp.route("/<int:order_id>", methods=["GET"])
@login_required
@roles_required(UserRole.ADMIN)
def get_any_order(order_id):
    order = get_order_for_admin(order_id)
    if order is None:
        return error_response("ORDER_NOT_FOUND", "Order not found.", 404)

    students = get_students_for_orders([order])
    data = serialize_order_for_admin(order, students.get(order.student_id))
    data["status_history"] = serialize_status_history(get_status_history(order.id))

    return success_response("Order retrieved", data)
