"""Persistent, administrator-managed menu categories."""
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.menu import MenuItem
from app.models.menu_category import MenuCategory
from app.services.errors import OrderError, ServiceValidationError

NAME_MAX_LENGTH = 60
SORT_ORDER_MAX = 10_000
ALLOWED_FIELDS = frozenset({"name", "sort_order"})


def normalize_name(raw):
    return " ".join(raw.split())


def serialize_category(category, item_count):
    return {
        "id": category.id,
        "name": category.name,
        "sort_order": category.sort_order,
        "item_count": item_count,
        "created_at": category.created_at.isoformat() if category.created_at else None,
        "updated_at": category.updated_at.isoformat() if category.updated_at else None,
    }


def list_categories():
    counts = dict(
        db.session.query(MenuItem.category, func.count(MenuItem.id)).group_by(MenuItem.category).all()
    )
    rows = MenuCategory.query.order_by(MenuCategory.sort_order, MenuCategory.name, MenuCategory.id).all()
    return [serialize_category(row, counts.get(row.name, 0)) for row in rows]


def _validate(data, partial):
    errors, cleaned = {}, {}
    if not isinstance(data, dict):
        raise ServiceValidationError({"body": "Request body must be an object."}, "Category is invalid.")
    if partial and not data:
        raise ServiceValidationError({"body": "Provide at least one field to update."}, "Category is invalid.")
    unknown = sorted(set(data) - ALLOWED_FIELDS)
    if unknown:
        errors["unknown_fields"] = f"Unsupported fields: {', '.join(unknown)}."
    if "name" in data:
        value = data["name"]
        if not isinstance(value, str):
            errors["name"] = "Must be a string."
        else:
            name = normalize_name(value)
            if not name:
                errors["name"] = "Cannot be empty."
            elif len(name) > NAME_MAX_LENGTH:
                errors["name"] = f"Must be at most {NAME_MAX_LENGTH} characters."
            else:
                cleaned["name"] = name
    elif not partial:
        errors["name"] = "This field is required."
    if "sort_order" in data:
        value = data["sort_order"]
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= SORT_ORDER_MAX:
            cleaned["sort_order"] = value
        else:
            errors["sort_order"] = f"Must be a whole number from 0 to {SORT_ORDER_MAX}."
    if errors:
        raise ServiceValidationError(errors, "Category is invalid.")
    return cleaned


def _name_taken(name, exclude_id=None):
    query = MenuCategory.query.filter(func.lower(MenuCategory.name) == name.lower())
    if exclude_id is not None:
        query = query.filter(MenuCategory.id != exclude_id)
    return query.first() is not None


def create_category(data):
    cleaned = _validate(data, partial=False)
    cleaned.setdefault("sort_order", 0)
    if _name_taken(cleaned["name"]):
        raise OrderError("CATEGORY_NAME_TAKEN", "A category with this name already exists.", 409)
    category = MenuCategory(**cleaned)
    db.session.add(category)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise OrderError("CATEGORY_NAME_TAKEN", "A category with this name already exists.", 409) from exc
    return category


def update_category(category, data):
    cleaned = _validate(data, partial=True)
    new_name = cleaned.get("name")
    if new_name is not None and new_name != category.name:
        if _name_taken(new_name, exclude_id=category.id):
            raise OrderError("CATEGORY_NAME_TAKEN", "A category with this name already exists.", 409)
        MenuItem.query.filter(MenuItem.category == category.name).update(
            {MenuItem.category: new_name}, synchronize_session=False
        )
    for field, value in cleaned.items():
        setattr(category, field, value)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise OrderError("CATEGORY_NAME_TAKEN", "A category with this name already exists.", 409) from exc
    return category


def delete_category(category):
    count = MenuItem.query.filter_by(category=category.name).count()
    if count:
        raise OrderError("CATEGORY_IN_USE", f"{count} menu item(s) use this category. Move them first.", 409)
    db.session.delete(category)
    db.session.commit()


def category_exists(name):
    return MenuCategory.query.filter(func.lower(MenuCategory.name) == str(name).strip().lower()).first() is not None
