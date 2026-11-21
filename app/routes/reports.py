from datetime import date

from flask import Blueprint, request
from flask_login import login_required

from app.models.user import UserRole
from app.responses import error_response, success_response
from app.security.permissions import roles_required
from app.services.errors import OrderError
from app.services.report_service import (
    report_categories,
    report_overview,
    report_orders,
    report_peak_hours,
    report_popular_items,
    report_sales,
)

reports_bp = Blueprint("reports", __name__, url_prefix="/api/admin/reports")


def _parse_dates():
    try:
        start = date.fromisoformat(request.args["from"]) if "from" in request.args else None
        end = date.fromisoformat(request.args["to"]) if "to" in request.args else None
    except (ValueError, TypeError) as exc:
        raise OrderError("INVALID_DATE", "Dates must be YYYY-MM-DD.", 400) from exc

    if (start is None) != (end is None):
        raise OrderError("INVALID_DATE_RANGE", "Provide both 'from' and 'to'.", 400)

    if start and end:
        if end < start or (end - start).days > 365:
            raise OrderError("INVALID_DATE_RANGE", "Date range must be ordered and at most 366 days.", 400)

    return start, end


def _run_report(fn, *args):
    try:
        start, end = _parse_dates()
        result = fn(start, end, *args)
    except OrderError as exc:
        return error_response(exc.code, exc.message, exc.status)
    return success_response("Report retrieved", result)


@reports_bp.get("/overview")
@login_required
@roles_required(UserRole.ADMIN)
def overview():
    return _run_report(report_overview)


@reports_bp.get("/sales")
@login_required
@roles_required(UserRole.ADMIN)
def sales():
    return _run_report(report_sales)


@reports_bp.get("/popular-items")
@login_required
@roles_required(UserRole.ADMIN)
def popular_items():
    try:
        limit = int(request.args.get("limit", "10"))
        if not 1 <= limit <= 50:
            raise ValueError
    except (TypeError, ValueError):
        return error_response("INVALID_PAGINATION", "'limit' must be between 1 and 50.", 400)
    return _run_report(report_popular_items, limit)


@reports_bp.get("/categories")
@login_required
@roles_required(UserRole.ADMIN)
def categories():
    return _run_report(report_categories)


@reports_bp.get("/peak-hours")
@login_required
@roles_required(UserRole.ADMIN)
def peak_hours():
    return _run_report(report_peak_hours)


@reports_bp.get("/orders")
@login_required
@roles_required(UserRole.ADMIN)
def orders():
    return _run_report(report_orders)
