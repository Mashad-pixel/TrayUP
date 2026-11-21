from dataclasses import dataclass, field

from app.models.menu import MenuItem
from app.services.errors import OrderError

MAX_LINE_QUANTITY = 20
MAX_ITEMS_PER_ORDER = 30


@dataclass
class PricedLine:
    menu_item_id: int
    item_name: str
    unit_price_paise: int
    quantity: int

    @property
    def line_total_paise(self):
        return self.unit_price_paise * self.quantity


@dataclass
class PricedOrder:
    lines: list = field(default_factory=list)
    subtotal_paise: int = 0
    discount_paise: int = 0
    tax_paise: int = 0
    total_paise: int = 0


def _parse_menu_item_id(value):
    # bool is a subclass of int in Python, so it is rejected explicitly
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise OrderError("INVALID_ITEM", "Each item needs a valid menu_item_id.")
    return value


def _parse_quantity(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise OrderError("INVALID_QUANTITY", "Quantity must be a whole number.")
    if value < 1 or value > MAX_LINE_QUANTITY:
        raise OrderError(
            "INVALID_QUANTITY",
            f"Quantity must be between 1 and {MAX_LINE_QUANTITY}.",
        )
    return value


def normalize_requested_items(raw_items):
    """Validate the request's item list and return {menu_item_id: quantity}.

    Only menu_item_id and quantity are read. Any price fields sent by the
    frontend are ignored on purpose.
    """
    if not isinstance(raw_items, list) or not raw_items:
        raise OrderError("EMPTY_ORDER", "Order must contain at least one item.")

    if len(raw_items) > MAX_ITEMS_PER_ORDER:
        raise OrderError(
            "TOO_MANY_ITEMS",
            f"An order can contain at most {MAX_ITEMS_PER_ORDER} items.",
        )

    requested = {}
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise OrderError("INVALID_ITEM", "Each item must be an object.")

        item_id = _parse_menu_item_id(raw.get("menu_item_id"))
        quantity = _parse_quantity(raw.get("quantity"))

        if item_id in requested:
            raise OrderError(
                "DUPLICATE_ITEM",
                "Each menu item may appear only once. Combine the quantities instead.",
            )
        requested[item_id] = quantity

    return requested


def price_order(requested):
    """Look up real prices from the database and build the order totals.

    `requested` is the {menu_item_id: quantity} dict from normalize_requested_items.
    """
    items = MenuItem.query.filter(MenuItem.id.in_(list(requested.keys()))).all()
    items_by_id = {item.id: item for item in items}

    lines = []
    for item_id, quantity in requested.items():
        item = items_by_id.get(item_id)

        if item is None:
            raise OrderError(
                "ITEM_NOT_FOUND",
                f"Menu item {item_id} does not exist.",
                404,
            )

        if not item.is_available:
            raise OrderError(
                "ITEM_UNAVAILABLE",
                f"'{item.name}' is not available right now.",
                409,
            )

        # Read-only check. Stock reservation with atomic updates belongs to the inventory service.
        if item.stock_quantity is not None and item.stock_quantity < quantity:
            raise OrderError(
                "INSUFFICIENT_STOCK",
                f"Only {item.stock_quantity} of '{item.name}' left.",
                409,
            )

        lines.append(
            PricedLine(
                menu_item_id=item.id,
                item_name=item.name,
                unit_price_paise=item.price_paise,
                quantity=quantity,
            )
        )

    subtotal = sum(line.line_total_paise for line in lines)

    # Discount and tax rules are not defined yet, so both stay at 0.
    discount = 0
    tax = 0
    total = subtotal - discount + tax

    return PricedOrder(
        lines=lines,
        subtotal_paise=subtotal,
        discount_paise=discount,
        tax_paise=tax,
        total_paise=total,
    )
