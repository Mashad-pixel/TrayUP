import re
from datetime import time

from app.extensions import db
from app.models.canteen import CanteenSettings
from app.services.errors import ServiceValidationError

SINGLETON_ID = 1
CLOSED_MESSAGE_MAX_LENGTH = 200
ALLOWED_FIELDS = frozenset({"is_accepting_orders", "closed_message"})
NAME_MAX_LENGTH_DETAILS = 120
HOURS_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
DETAIL_FIELDS = frozenset({
    "canteen_name", "name", "opens_at", "closes_at", "is_accepting_orders", "closed_message",
    "payment_provider", "merchant_display_name", "upi_vpa", "cash_enabled", "cash_max_order_paise",
})
DEFAULT_NAME = "TrayUP Canteen"
DEFAULT_OPENS = time(8, 0)
DEFAULT_CLOSES = time(18, 0)


def get_status():
    settings = db.session.get(CanteenSettings, SINGLETON_ID)
    if settings is None or settings.is_accepting_orders:
        return {"is_accepting_orders": True, "message": None}
    return {"is_accepting_orders": False, "message": settings.closed_message}


def is_accepting_orders():
    return get_status()["is_accepting_orders"]


def update_status(data):
    errors = {}
    unknown = sorted(set(data) - ALLOWED_FIELDS)
    if unknown:
        errors["unknown_fields"] = f"Unsupported fields: {', '.join(unknown)}."
    if "is_accepting_orders" not in data or not isinstance(data.get("is_accepting_orders"), bool):
        errors["is_accepting_orders"] = "This field is required and must be true or false."
    message = data.get("closed_message")
    if message is not None and not isinstance(message, str):
        errors["closed_message"] = "Must be a string."
    elif isinstance(message, str) and len(message.strip()) > CLOSED_MESSAGE_MAX_LENGTH:
        errors["closed_message"] = f"Must be at most {CLOSED_MESSAGE_MAX_LENGTH} characters."
    if errors:
        raise ServiceValidationError(errors, "Canteen status update is invalid.")
    settings = db.session.get(CanteenSettings, SINGLETON_ID)
    if settings is None:
        settings = CanteenSettings(id=SINGLETON_ID)
        db.session.add(settings)
    settings.is_accepting_orders = data["is_accepting_orders"]
    cleaned = message.strip() if isinstance(message, str) and message.strip() else None
    settings.closed_message = None if settings.is_accepting_orders else cleaned
    db.session.commit()
    return get_status()


def _format_time(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value[:5]
    return value.strftime("%H:%M")


def _parse_hours(raw, field, errors):
    if not isinstance(raw, str) or not HOURS_PATTERN.fullmatch(raw):
        errors[field] = "Must be a time in 24-hour HH:MM format."
        return None
    hour, minute = (int(part) for part in raw.split(":"))
    return time(hour, minute)


def get_settings():
    settings = db.session.get(CanteenSettings, SINGLETON_ID)
    return {
        **get_status(),
        "closed_message": settings.closed_message if settings else None,
        "canteen_name": settings.canteen_name if settings else DEFAULT_NAME,
        "name": settings.canteen_name if settings else DEFAULT_NAME,
        "opens_at": _format_time(settings.opens_at) if settings else "08:00",
        "closes_at": _format_time(settings.closes_at) if settings else "18:00",
        "payment_provider": settings.payment_provider if settings else "sandbox",
        "merchant_display_name": settings.merchant_display_name if settings else DEFAULT_NAME,
        "upi_vpa": settings.upi_vpa if settings else None,
        "cash_enabled": settings.cash_enabled if settings else False,
        "cash_max_order_paise": settings.cash_max_order_paise if settings else 15000,
    }


def update_details(data):
    errors = {}
    if not isinstance(data, dict):
        raise ServiceValidationError({"body": "Request body must be an object."}, "Canteen details are invalid.")
    unknown = sorted(set(data) - DETAIL_FIELDS)
    if unknown:
        errors["unknown_fields"] = f"Unsupported fields: {', '.join(unknown)}."
    if not data:
        errors["body"] = "Provide at least one canteen setting to update."
    current = db.session.get(CanteenSettings, SINGLETON_ID)
    name = current.canteen_name if current else DEFAULT_NAME
    opens = current.opens_at if current else DEFAULT_OPENS
    closes = current.closes_at if current else DEFAULT_CLOSES
    if isinstance(opens, str):
        opens = _parse_hours(opens[:5], "opens_at", {}) or DEFAULT_OPENS
    if isinstance(closes, str):
        closes = _parse_hours(closes[:5], "closes_at", {}) or DEFAULT_CLOSES
    if "name" in data and "canteen_name" in data and data["name"] != data["canteen_name"]:
        errors["canteen_name"] = "Provide either name or canteen_name, not conflicting values."
    if "canteen_name" in data or "name" in data:
        raw = data.get("canteen_name", data.get("name"))
        cleaned = " ".join(raw.split()) if isinstance(raw, str) else ""
        if not cleaned:
            errors["canteen_name"] = "Must be a name of at least one character."
        elif len(cleaned) > NAME_MAX_LENGTH_DETAILS:
            errors["canteen_name"] = f"Must be at most {NAME_MAX_LENGTH_DETAILS} characters."
        else:
            name = cleaned
    if "opens_at" in data:
        parsed = _parse_hours(data["opens_at"], "opens_at", errors)
        if parsed is not None:
            opens = parsed
    if "closes_at" in data:
        parsed = _parse_hours(data["closes_at"], "closes_at", errors)
        if parsed is not None:
            closes = parsed
    if not errors and opens >= closes:
        errors["closes_at"] = "Closing time must be after opening time."
    accepting = current.is_accepting_orders if current else True
    closed_message = current.closed_message if current else None
    if "is_accepting_orders" in data:
        if not isinstance(data["is_accepting_orders"], bool):
            errors["is_accepting_orders"] = "Must be true or false."
        else:
            accepting = data["is_accepting_orders"]
    if "closed_message" in data:
        raw_message = data["closed_message"]
        if raw_message is not None and not isinstance(raw_message, str):
            errors["closed_message"] = "Must be a string."
        elif isinstance(raw_message, str) and len(raw_message.strip()) > CLOSED_MESSAGE_MAX_LENGTH:
            errors["closed_message"] = f"Must be at most {CLOSED_MESSAGE_MAX_LENGTH} characters."
        else:
            closed_message = raw_message.strip() if isinstance(raw_message, str) and raw_message.strip() else None
    if accepting:
        closed_message = None

    payment_provider = current.payment_provider if current else "sandbox"
    if "payment_provider" in data:
        value = data["payment_provider"]
        if value not in {"sandbox", "upi", "phonepe"}:
            errors["payment_provider"] = "Choose sandbox, upi or phonepe."
        else:
            payment_provider = value
    merchant_display_name = current.merchant_display_name if current else DEFAULT_NAME
    if "merchant_display_name" in data:
        value = data["merchant_display_name"]
        cleaned = " ".join(value.split()) if isinstance(value, str) else ""
        if not cleaned:
            errors["merchant_display_name"] = "Must be a non-empty name."
        elif len(cleaned) > 100:
            errors["merchant_display_name"] = "Must be at most 100 characters."
        else:
            merchant_display_name = cleaned
    upi_vpa = current.upi_vpa if current else None
    if "upi_vpa" in data:
        value = data["upi_vpa"]
        if value is not None and (
            not isinstance(value, str) or not value.strip() or "@" not in value or len(value) > 100
        ):
            errors["upi_vpa"] = "Enter a valid UPI address."
        else:
            upi_vpa = value.strip() if isinstance(value, str) else None
    cash_enabled = current.cash_enabled if current else False
    if "cash_enabled" in data:
        if not isinstance(data["cash_enabled"], bool):
            errors["cash_enabled"] = "Must be true or false."
        else:
            cash_enabled = data["cash_enabled"]
    cash_max_order_paise = current.cash_max_order_paise if current else 15000
    if "cash_max_order_paise" in data:
        value = data["cash_max_order_paise"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            errors["cash_max_order_paise"] = "Must be a non-negative whole number of paise."
        else:
            cash_max_order_paise = value
    if errors:
        raise ServiceValidationError(errors, "Canteen details are invalid.")
    if current is None:
        current = CanteenSettings(id=SINGLETON_ID)
        db.session.add(current)
    current.canteen_name, current.opens_at, current.closes_at = name, opens, closes
    current.is_accepting_orders = accepting
    current.closed_message = closed_message
    current.payment_provider = payment_provider
    current.merchant_display_name = merchant_display_name
    current.upi_vpa = upi_vpa
    current.cash_enabled = cash_enabled
    current.cash_max_order_paise = cash_max_order_paise
    db.session.commit()
    return get_settings()
