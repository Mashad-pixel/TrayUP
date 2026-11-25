from flask import current_app

from app.extensions import db
from app.models.canteen import CanteenSettings
from app.services.errors import ServiceValidationError

SINGLETON_ID = 1
CLOSED_MESSAGE_MAX_LENGTH = 200
ALLOWED_FIELDS = frozenset({"is_accepting_orders", "closed_message"})
SETTINGS_ALLOWED_FIELDS = frozenset({
    "is_accepting_orders",
    "closed_message",
    "payment_provider",
    "merchant_display_name",
    "upi_vpa",
    "cash_enabled",
    "cash_max_order_paise",
})
VALID_PAYMENT_PROVIDERS = frozenset({"sandbox", "phonepe", "razorpay"})


def get_canteen_settings():
    """Retrieve full canteen settings including payment and cash configuration."""
    settings = db.session.get(CanteenSettings, SINGLETON_ID)
    if settings is None:
        settings = CanteenSettings(
            id=SINGLETON_ID,
            is_accepting_orders=True,
            closed_message=None,
            payment_provider=current_app.config.get("PAYMENT_DEFAULT_PROVIDER", "sandbox"),
            merchant_display_name=current_app.config.get("CANTEEN_MERCHANT_NAME", "TrayUP Canteen"),
            upi_vpa=current_app.config.get("CANTEEN_UPI_VPA") or None,
            cash_enabled=False,
            cash_max_order_paise=15000,
        )
        db.session.add(settings)
        db.session.commit()

    return {
        "is_accepting_orders": settings.is_accepting_orders,
        "closed_message": settings.closed_message,
        "payment_provider": settings.payment_provider,
        "merchant_display_name": settings.merchant_display_name,
        "upi_vpa": settings.upi_vpa,
        "cash_enabled": settings.cash_enabled,
        "cash_max_order_paise": settings.cash_max_order_paise,
        "sandbox_enabled": current_app.config.get("PAYMENT_SANDBOX_ENABLED", False),
    }


def update_canteen_settings(data):
    """Update general and payment configuration for the canteen."""
    errors = {}
    unknown = sorted(set(data) - SETTINGS_ALLOWED_FIELDS)
    if unknown:
        errors["unknown_fields"] = f"Unsupported fields: {', '.join(unknown)}."

    if "is_accepting_orders" in data and not isinstance(data["is_accepting_orders"], bool):
        errors["is_accepting_orders"] = "Must be true or false."

    if "closed_message" in data:
        msg = data["closed_message"]
        if msg is not None and not isinstance(msg, str):
            errors["closed_message"] = "Must be a string."
        elif isinstance(msg, str) and len(msg.strip()) > CLOSED_MESSAGE_MAX_LENGTH:
            errors["closed_message"] = f"Must be at most {CLOSED_MESSAGE_MAX_LENGTH} characters."

    if "payment_provider" in data:
        prov = str(data["payment_provider"]).lower().strip()
        if prov not in VALID_PAYMENT_PROVIDERS:
            errors["payment_provider"] = f"Must be one of: {', '.join(sorted(VALID_PAYMENT_PROVIDERS))}."

    if "merchant_display_name" in data:
        name = data["merchant_display_name"]
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
            errors["merchant_display_name"] = "Must be a string between 1 and 100 characters."

    if "upi_vpa" in data:
        vpa = data["upi_vpa"]
        if vpa is not None:
            if not isinstance(vpa, str) or "@" not in vpa or len(vpa.strip()) > 100:
                errors["upi_vpa"] = "Must be a valid UPI VPA containing '@' or null."

    if "cash_enabled" in data and not isinstance(data["cash_enabled"], bool):
        errors["cash_enabled"] = "Must be true or false."

    if "cash_max_order_paise" in data:
        val = data["cash_max_order_paise"]
        if not isinstance(val, int) or val < 0:
            errors["cash_max_order_paise"] = "Must be a non-negative integer in paise."

    if errors:
        raise ServiceValidationError(errors, "Canteen settings update is invalid.")

    settings = db.session.get(CanteenSettings, SINGLETON_ID)
    if settings is None:
        settings = CanteenSettings(id=SINGLETON_ID)
        db.session.add(settings)

    if "is_accepting_orders" in data:
        settings.is_accepting_orders = data["is_accepting_orders"]
    if "closed_message" in data:
        msg = data["closed_message"]
        settings.closed_message = msg.strip() if isinstance(msg, str) and msg.strip() else None
    if "payment_provider" in data:
        settings.payment_provider = str(data["payment_provider"]).lower().strip()
    if "merchant_display_name" in data:
        settings.merchant_display_name = str(data["merchant_display_name"]).strip()
    if "upi_vpa" in data:
        vpa = data["upi_vpa"]
        settings.upi_vpa = str(vpa).strip() if isinstance(vpa, str) and vpa.strip() else None
    if "cash_enabled" in data:
        settings.cash_enabled = data["cash_enabled"]
    if "cash_max_order_paise" in data:
        settings.cash_max_order_paise = data["cash_max_order_paise"]

    db.session.commit()
    return get_canteen_settings()


def get_status():
    """The canteen is open unless an admin has explicitly closed it."""
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

    if "is_accepting_orders" not in data:
        errors["is_accepting_orders"] = "This field is required."
    elif not isinstance(data["is_accepting_orders"], bool):
        errors["is_accepting_orders"] = "Must be true or false."

    message = data.get("closed_message")
    if message is not None and not isinstance(message, str):
        errors["closed_message"] = "Must be a string."
    elif isinstance(message, str) and len(message.strip()) > CLOSED_MESSAGE_MAX_LENGTH:
        errors["closed_message"] = f"Must be at most {CLOSED_MESSAGE_MAX_LENGTH} characters."

    if errors:
        raise ServiceValidationError(errors, "Canteen status update is invalid.")

    is_open = data["is_accepting_orders"]
    cleaned_message = message.strip() if isinstance(message, str) and message.strip() else None

    settings = db.session.get(CanteenSettings, SINGLETON_ID)
    if settings is None:
        settings = CanteenSettings(id=SINGLETON_ID)
        db.session.add(settings)
    settings.is_accepting_orders = is_open
    settings.closed_message = None if is_open else cleaned_message
    db.session.commit()
    return get_status()
