from sqlalchemy import or_

from app.extensions import db
from app.models.menu import MenuItem

NAME_MAX_LENGTH = 120
CATEGORY_MAX_LENGTH = 60
DESCRIPTION_MAX_LENGTH = 500
IMAGE_URL_MAX_LENGTH = 500
IMAGE_URL_PREFIXES = ("https://", "http://", "/static/")
MAX_PRICE_PAISE = 1_000_000
MAX_STOCK_QUANTITY = 100_000
ALLOWED_FIELDS = frozenset({
    "name", "description", "category", "price_paise",
    "image_url", "is_available", "stock_quantity",
})


class MenuValidationError(ValueError):
    def __init__(self, errors):
        super().__init__("Menu item validation failed.")
        self.errors = errors


def _plain_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _text(field, value, max_length, errors, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str):
        errors[field] = "Must be a string."
        return None
    value = value.strip()
    if not value:
        if optional:
            return None
        errors[field] = "Cannot be empty."
        return None
    if len(value) > max_length:
        errors[field] = f"Must be at most {max_length} characters."
        return None
    return value


def validate_menu_payload(data, partial=False):
    if partial and not data:
        raise MenuValidationError({"body": "Provide at least one field to update."})

    errors = {}
    cleaned = {}
    unknown = sorted(set(data) - ALLOWED_FIELDS)
    if unknown:
        errors["unknown_fields"] = f"Unsupported fields: {', '.join(unknown)}."

    if "name" in data:
        cleaned["name"] = _text("name", data["name"], NAME_MAX_LENGTH, errors)
    elif not partial:
        errors["name"] = "This field is required."

    if "category" in data:
        cleaned["category"] = _text("category", data["category"], CATEGORY_MAX_LENGTH, errors)
    elif not partial:
        errors["category"] = "This field is required."

    if "description" in data:
        cleaned["description"] = _text("description", data["description"], DESCRIPTION_MAX_LENGTH, errors, optional=True)

    if "price_paise" in data:
        value = data["price_paise"]
        if _plain_int(value) and 0 <= value <= MAX_PRICE_PAISE:
            cleaned["price_paise"] = value
        else:
            errors["price_paise"] = f"Must be a whole number of paise from 0 to {MAX_PRICE_PAISE}."
    elif not partial:
        errors["price_paise"] = "This field is required."

    if "image_url" in data:
        value = _text("image_url", data["image_url"], IMAGE_URL_MAX_LENGTH, errors, optional=True)
        if value is not None and not value.startswith(IMAGE_URL_PREFIXES):
            errors["image_url"] = "Must start with https://, http://, or /static/."
        cleaned["image_url"] = value

    if "is_available" in data:
        value = data["is_available"]
        if isinstance(value, bool):
            cleaned["is_available"] = value
        else:
            errors["is_available"] = "Must be true or false."
    elif not partial:
        cleaned["is_available"] = True

    if "stock_quantity" in data:
        value = data["stock_quantity"]
        if value is None or (_plain_int(value) and 0 <= value <= MAX_STOCK_QUANTITY):
            cleaned["stock_quantity"] = value
        else:
            errors["stock_quantity"] = f"Must be empty or a whole number from 0 to {MAX_STOCK_QUANTITY}."

    if errors:
        raise MenuValidationError(errors)
    return cleaned


def serialize_menu_item(item):
    available = None
    if item.stock_quantity is not None:
        available = max(item.stock_quantity - item.reserved_quantity, 0)
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "category": item.category,
        "price_paise": item.price_paise,
        "image_url": item.image_url,
        "is_available": item.is_available,
        "stock_quantity": item.stock_quantity,
        "reserved_quantity": item.reserved_quantity,
        "available_quantity": available,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def serialize_public_menu_item(item):
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "category": item.category,
        "price_paise": item.price_paise,
        "image_url": item.image_url,
    }


def list_public_menu_items():
    return (
        MenuItem.query
        .filter(MenuItem.is_available.is_(True))
        .filter(or_(
            MenuItem.stock_quantity.is_(None),
            MenuItem.stock_quantity > MenuItem.reserved_quantity,
        ))
        .order_by(MenuItem.category, MenuItem.name, MenuItem.id)
        .all()
    )


def create_menu_item(data):
    cleaned = validate_menu_payload(data, partial=False)
    item = MenuItem(**cleaned)
    db.session.add(item)
    db.session.commit()
    return item


def update_menu_item(item, data):
    cleaned = validate_menu_payload(data, partial=True)
    if "stock_quantity" in cleaned:
        new_stock = cleaned["stock_quantity"]
        held = item.reserved_quantity or 0
        if new_stock is None and held:
            raise MenuValidationError({
                "stock_quantity": "Cannot disable stock tracking while units are reserved."
            })
        if new_stock is not None and new_stock < held:
            raise MenuValidationError({
                "stock_quantity": f"Cannot set stock below the {held} unit(s) already reserved."
            })
    for field, value in cleaned.items():
        setattr(item, field, value)
    db.session.commit()
    return item
