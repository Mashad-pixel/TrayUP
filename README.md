# trayUP: Backend

Backend for trayUP, a QR-based online ordering and payment system for a college canteen. Students order from a menu, pay online, and collect food. Kitchen staff and admins manage orders.

## Status

**Implemented**

- Login, logout, and current-user endpoints (session-based, Flask-Login)
- Account creation from the command line (staff, admin, and student roles)
- Menu item model with prices in paise, availability, and optional stock
- Order creation with server-side pricing, idempotency keys, and price snapshots
- Database migration for users, menu items, orders, and order items
- 27 automated tests

**Not yet implemented**

- Razorpay payments (create order, verify, webhooks, refunds)
- Kitchen queue and status updates
- Collection QR generation and verification
- Inventory reservation
- Admin reports
- Menu management API
- Frontend pages

## Requirements

- Python 3.10 or newer (tested on Python 3.12 and 3.14)
- Windows PowerShell or any terminal

## Setup

From the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Open `.env` and set `SECRET_KEY` to a long random string. Never commit `.env`.

Create the database tables:

```powershell
flask --app run db upgrade
```

## Configuration

Settings come from `.env`. See `.env.example` for the full list.

| Variable | Purpose |
|---|---|
| `FLASK_CONFIG` | `development`, `testing`, or `production` |
| `SECRET_KEY` | Signs sessions. Must be random in production. |
| `DATABASE_URL` | Defaults to `sqlite:///canteen.db`, stored in `instance/` |
| `RATELIMIT_STORAGE_URI` | Defaults to `memory://`. Use Redis in production. |
| `ORDER_PAYMENT_EXPIRY_MINUTES` | Reserved for payments (default 10) |
| `COLLECTION_TOKEN_EXPIRY_MINUTES` | Reserved for collection QR (default 60) |
| `RAZORPAY_*` | Reserved for payments. Leave empty for now. |

## Create Accounts

There is no public signup. Create accounts from the command line. You will be asked for a password (at least 8 characters).

```powershell
flask --app run create-user --name "Test Student" --email student@test.com --role STUDENT
flask --app run create-user --name "Kitchen Staff" --email kitchen@trayup.test --role KITCHEN
flask --app run create-user --name "Admin" --email admin@trayup.test --role ADMIN
```

Emails are stored in lowercase. Duplicate emails are rejected.

## Add Menu Items

The admin menu screen is not built yet. Add items from the Flask shell:

```powershell
flask --app run shell
```

```python
from app.extensions import db
from app.models.menu import MenuItem
db.session.add(MenuItem(name="Samosa", category="Snacks", price_paise=1500, is_available=True))
db.session.commit()
exit()
```

Prices are integers in paise. `1500` means ₹15.00.

## Run the Server

```powershell
python run.py
```

The server runs at `http://127.0.0.1:5000`.

## Run Tests

```powershell
python -m pytest -v
```

Expected result: `27 passed`. Tests use an in-memory database and do not contact Razorpay.

## API

All responses use this format.

Success:

```json
{ "success": true, "message": "...", "data": { } }
```

Error:

```json
{ "success": false, "message": "...", "error": { "code": "..." } }
```

### Authentication

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/login` | None | Log in. Rate limit: 5 per minute per IP. |
| POST | `/api/auth/logout` | Logged in | End the session |
| GET | `/api/auth/me` | Logged in | Current user |

Login request:

```json
{ "email": "student@test.com", "password": "your-password" }
```

Login success (`200`):

```json
{
  "success": true,
  "message": "Logged in successfully",
  "data": { "id": 1, "name": "Test Student", "email": "student@test.com", "role": "STUDENT" }
}
```

Wrong email or password returns `401` with code `INVALID_CREDENTIALS`. The same response is used for unknown emails and disabled accounts, so attackers cannot tell which emails exist.

### Orders

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/orders` | Logged in as a student | Create an order. Rate limit: 10 per minute per IP. |

Headers:

- `Content-Type: application/json`
- `Idempotency-Key` (optional, up to 64 characters): send the same key when retrying, and you get back the original order instead of a duplicate.

Request:

```json
{
  "items": [
    { "menu_item_id": 1, "quantity": 2 },
    { "menu_item_id": 3, "quantity": 1 }
  ]
}
```

Only `menu_item_id` and `quantity` are read. Prices sent by the client are ignored. The server calculates every amount from the database.

Response codes:

| Status | Meaning |
|---|---|
| `201` | Order created. The response includes `tracking_token`, which is shown only once. |
| `200` | Retry with the same `Idempotency-Key`. Returns the original order without a token. |
| `400` | Invalid JSON, empty order, bad quantity, duplicate item, or bad idempotency key |
| `401` | Not logged in |
| `404` | Menu item does not exist |
| `409` | Item unavailable or not enough stock |
| `500` | Order could not be saved. Retry. |

Validation limits: 1 to 20 units per item, up to 30 different items per order.

Example success (`201`):

```json
{
  "success": true,
  "message": "Order created successfully",
  "data": {
    "id": 1,
    "order_number": "TU2611210001ABCD",
    "order_status": "pending_payment",
    "payment_status": "pending",
    "subtotal_paise": 3000,
    "discount_paise": 0,
    "tax_paise": 0,
    "total_paise": 3000,
    "items": [
      {
        "menu_item_id": 1,
        "item_name": "Samosa",
        "unit_price_paise": 1500,
        "quantity": 2,
        "line_total_paise": 3000
      }
    ],
    "created_at": "2026-11-21T09:00:00+00:00",
    "tracking_token": "random-token-shown-once"
  }
}
```

## Testing the API with Postman

1. Send `POST http://127.0.0.1:5000/api/auth/login` with the JSON body above. Postman keeps the session cookie.
2. Send `POST http://127.0.0.1:5000/api/orders` with a JSON body and an `Idempotency-Key` header.

## Project Structure

```
trayUP/
├── app/
│   ├── __init__.py          App factory, login handling, blueprint registration
│   ├── config.py            Settings for development, testing, production
│   ├── extensions.py        db, migrate, limiter, login_manager
│   ├── cli.py               create-user command
│   ├── models/
│   │   ├── user.py          Accounts and password hashing
│   │   ├── menu.py          Menu items (prices in paise)
│   │   ├── order.py         Orders and status constants
│   │   └── order_item.py    Order line items with price snapshots
│   ├── routes/
│   │   ├── auth.py          Login, logout, me
│   │   └── orders.py        Order creation
│   └── services/
│       ├── errors.py        OrderError for user-facing failures
│       ├── pricing_service.py  Validation and totals
│       └── order_service.py    Order creation and idempotency
├── migrations/              Database migrations (commit this folder)
├── tests/
│   ├── conftest.py          Test app, sample data, logged-in client
│   ├── test_auth.py
│   └── test_orders.py
├── .env.example
├── .gitignore
├── pytest.ini
├── requirements.txt
├── run.py
└── README.md
```

## Database Changes

Edit the models, then:

```powershell
flask --app run db migrate -m "describe the change"
flask --app run db upgrade
```

Review the generated file in `migrations/versions/` before upgrading. Commit the migration file with your code.

## Security Rules

- Never trust prices, totals, or payment status sent by the frontend.
- Store only hashes of tracking and collection tokens.
- Keep `.env`, database files, and API secrets out of Git.
- Students may only see their own orders.
- Unpaid orders must never reach the kitchen.
- A collection token must work exactly once.

## Team Notes

- Shared files (`app/__init__.py`, `app/config.py`, `app/extensions.py`, and the User and Menu models) should be reviewed by Nehal before changes are merged.
- Development branch: `backend-operations`. Open a pull request into `main`.

## Next Steps

1. Razorpay Test Mode: create order, verify signature, webhook (mocked in tests)
2. Kitchen queue and status transitions
3. Collection QR generation and single-use verification
4. Inventory reservation with atomic stock updates
5. Admin reports and refunds
