from app.extensions import db
from app.models.canteen import CanteenSettings
from app.services.errors import ServiceValidationError

SINGLETON_ID = 1
CLOSED_MESSAGE_MAX_LENGTH = 200
ALLOWED_FIELDS = frozenset({"is_accepting_orders", "closed_message"})


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
