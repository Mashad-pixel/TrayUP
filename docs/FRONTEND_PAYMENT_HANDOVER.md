# TrayUP Payment System — Frontend & Teammate Handover Guide

> **Branch:** `feature/phonepe-payments`  
> **Backend Status:** 100% complete, 229 tests passing.  
> **Target Audience:** Frontend engineers, Kitchen display app maintainers, Admin dashboard maintainers.

---

## 1. Quick Setup for Teammates

Before running the server locally on this branch, perform the following two commands in your environment:

```bash
# 1. Install updated dependencies (added pure-Python qrcode library)
pip install -r requirements.txt

# 2. Apply database migrations (adds payment_provider, upi_vpa, cash settings, and utr_number)
flask --app run.py db upgrade

# 3. (Optional) Seed demo menu items and demo student/kitchen/admin accounts
flask --app run.py seed-demo
```

### Environment Variables (.env)
The system works out-of-the-box with **Sandbox & Soundbox enabled**. If configuring PhonePe or UPI VPA:
```env
PAYMENT_DEFAULT_PROVIDER=sandbox    # "sandbox", "phonepe", or "razorpay"
PAYMENT_SANDBOX_ENABLED=true       # true allows 1-click test payments in dev
CANTEEN_UPI_VPA=canteen@ybl         # Canteen's UPI ID for QR code generation
CANTEEN_MERCHANT_NAME="Campus Canteen"
PHONEPE_MERCHANT_ID=PGTESTPAYUAT   # PhonePe UAT test merchant ID
PHONEPE_SALT_KEY=test_phonepe_salt_key_1234567890
PHONEPE_SALT_INDEX=1
```

---

## 2. Architecture & Payment Options Overview

The backend supports 3 payment options tailored for college canteens:

```
                  ┌── [Option 1: PhonePe / UPI Apps] ── Direct Deep Link / Intent
                  │
[Student Checkout]├── [Option 2: Counter QR & Soundbox] ── Student scans QR -> Submits Claim (UTR) -> Staff confirms
                  │
                  └── [Option 3: Test Store Sandbox] ── 1-Click instant test payment (Dev/Test only)
```

---

## 3. Frontend Endpoints Contract

### A. Get Available Payment Options
Returns payment methods currently active based on Canteen Settings.

- **URL:** `GET /api/payments/methods`
- **Auth:** Student (`@login_required`)
- **Response `200 OK`:**
```json
{
  "success": true,
  "message": "Payment methods retrieved",
  "data": {
    "payment_provider": "sandbox",
    "merchant_display_name": "Campus Canteen",
    "upi": {
      "enabled": true,
      "vpa": "canteen@ybl"
    },
    "sandbox": {
      "enabled": true
    }
  }
}
```

---

### B. Initiate UPI Payment (Deep Links)
Generates standard NPCI intent URIs and deep links for specific UPI applications.

- **URL:** `POST /api/payments/upi/initiate`
- **Auth:** Student (`@login_required`)
- **Request Body:**
```json
{
  "order_id": 14
}
```
- **Response `200 OK`:**
```json
{
  "success": true,
  "message": "UPI payment initiated",
  "data": {
    "order_id": 14,
    "payment_id": 9,
    "amount_paise": 5000,
    "amount_inr": "50.00",
    "order_number": "TU261125A1B2",
    "upi_uri": "upi://pay?pa=canteen%40ybl&pn=Campus+Canteen&am=50.00&cu=INR&tr=TU261125A1B2&tn=Order+TU261125A1B2",
    "phonepe_uri": "phonepe://pay?pa=canteen%40ybl&pn=Campus+Canteen&am=50.00&cu=INR&tr=TU261125A1B2&tn=Order+TU261125A1B2",
    "gpay_uri": "gpay://upi/pay?pa=canteen%40ybl&pn=Campus+Canteen&am=50.00&cu=INR&tr=TU261125A1B2&tn=Order+TU261125A1B2",
    "paytm_uri": "paytmmp://pay?pa=canteen%40ybl&pn=Campus+Canteen&am=50.00&cu=INR&tr=TU261125A1B2&tn=Order+TU261125A1B2",
    "qr_svg_url": "/api/payments/14/upi-qr.svg"
  }
}
```
- **Frontend Usage:**
  - On mobile: Add buttons for `"Open PhonePe"`, `"Open GPay"`, or `"Open Any UPI App"` using the corresponding URI schemes.
  - On desktop/kiosk: Render the QR code image via `<img src="/api/payments/14/upi-qr.svg" alt="Scan to Pay" />`.

---

### C. Live SVG QR Code Image
Direct vector QR code for the order.

- **URL:** `GET /api/payments/<order_id>/upi-qr.svg`
- **Auth:** Student (`@login_required`)
- **Headers:** `Content-Type: image/svg+xml`
- **Usage:** Point any `<img>` tag or React/Vue SVG loader directly to this endpoint.

---

### D. Submit Payment Claim (Soundbox / UPI)
When a student scans the counter QR or pays via UPI and clicks "I have paid":

- **URL:** `POST /api/payments/upi/submit-claim`
- **Auth:** Student (`@login_required`)
- **Request Body:**
```json
{
  "order_id": 14,
  "utr_number": "412345678901"
}
```
*(Note: `utr_number` is optional or recommended. Must be 12 alphanumeric chars if passed).*
- **Response `200 OK`:**
```json
{
  "success": true,
  "message": "Payment claim submitted. Awaiting staff confirmation.",
  "data": {
    "order_id": 14,
    "order_number": "TU261125A1B2",
    "order_status": "pending_payment",
    "payment_status": "awaiting_confirmation",
    "utr_number": "412345678901"
  }
}
```
- **Error Responses:**
  - `400 INVALID_UTR`: `"UTR number must be exactly 12 alphanumeric characters."`
  - `409 DUPLICATE_UTR`: `"This UTR number has already been submitted for another order."`

---

### E. Complete Sandbox Payment (Dev / Testing)
Instant 1-click test simulation for developers and testers.

- **URL:** `POST /api/payments/sandbox/complete`
- **Auth:** Student (`@login_required`)
- **Request Body:**
```json
{
  "order_id": 14
}
```
- **Response `200 OK`:**
```json
{
  "success": true,
  "message": "Sandbox payment completed",
  "data": {
    "order_id": 14,
    "order_number": "TU261125A1B2",
    "order_status": "received",
    "payment_status": "paid",
    "refund_required": false
  }
}
```

---

## 4. Kitchen / Counter Staff Screen Endpoints

### A. List Orders Awaiting Confirmation
Returns all orders waiting for staff confirmation (Soundbox announcements or cash received).

- **URL:** `GET /api/kitchen/orders/pending-confirmation`
- **Auth:** Kitchen or Admin (`@login_required`)
- **Response `200 OK`:**
```json
{
  "success": true,
  "message": "Orders awaiting payment confirmation retrieved",
  "data": {
    "orders": [
      {
        "id": 14,
        "order_number": "TU261125A1B2",
        "order_status": "pending_payment",
        "payment_status": "awaiting_confirmation",
        "payment_method": "upi_soundbox",
        "utr_number": "412345678901",
        "total_paise": 5000,
        "items": [
          {
            "item_name": "Veg Burger",
            "quantity": 1,
            "unit_price_paise": 5000,
            "line_total_paise": 5000
          }
        ],
        "created_at": "2026-11-25T14:20:00Z"
      }
    ],
    "count": 1,
    "limit": 100
  }
}
```

### B. Confirm Payment
Staff clicks **"Confirm"** upon hearing the Soundbox chime or taking cash.

- **URL:** `POST /api/kitchen/orders/<order_id>/confirm-payment`
- **Auth:** Kitchen or Admin
- **Request Body (optional):**
```json
{
  "notes": "Payment heard on Paytm/PhonePe soundbox"
}
```
- **Response `200 OK`:**
```json
{
  "success": true,
  "message": "Payment confirmed successfully",
  "data": {
    "order": {
      "id": 14,
      "order_status": "received",
      "payment_status": "paid"
    },
    "refund_required": false
  }
}
```

### C. Reject Payment
Staff clicks **"Reject"** if the student walked away or payment was not received.

- **URL:** `POST /api/kitchen/orders/<order_id>/reject-payment`
- **Auth:** Kitchen or Admin
- **Request Body (optional):**
```json
{
  "reason": "Payment not received"
}
```
- **Response `200 OK`:**
```json
{
  "success": true,
  "message": "Payment rejected and order cancelled",
  "data": {
    "id": 14,
    "order_status": "cancelled",
    "payment_status": "failed"
  }
}
```

---

## 5. Admin Settings Configuration

Admins can configure the canteen's payment behavior dynamically.

- **URL:** `GET /api/admin/canteen/settings`
- **URL:** `PATCH /api/admin/canteen/settings`
- **Auth:** Admin
- **PATCH Request Body:**
```json
{
  "payment_provider": "phonepe",
  "merchant_display_name": "Campus Canteen",
  "upi_vpa": "canteen@ybl",
  "cash_enabled": true,
  "cash_max_order_paise": 20000
}
```
- **Response `200 OK`:**
```json
{
  "is_accepting_orders": true,
  "closed_message": null,
  "payment_provider": "phonepe",
  "merchant_display_name": "Campus Canteen",
  "upi_vpa": "canteen@ybl",
  "cash_enabled": true,
  "cash_max_order_paise": 20000,
  "sandbox_enabled": true
}
```

---

## 6. Recommended Student UI States

```
[Student in Checkout]
  │
  ├── Select "UPI / QR"
  │     ├── Mobile: Show "Pay via PhonePe / GPay" (triggers deep links)
  │     ├── Desktop: Show rendered SVG QR code (/api/payments/<id>/upi-qr.svg)
  │     └── After user switches back: Input for "Enter 12-digit UTR (optional)" + "I Have Paid" button
  │           └── Calls: POST /api/payments/upi/submit-claim
  │                 └── Screen enters: "Waiting for Canteen Soundbox Confirmation..."
  │
  └── (Dev Only) "Instant Sandbox Pay"
        └── Click "Simulate 1-Click Pay"
              └── Calls: POST /api/payments/sandbox/complete
                    └── Screen immediately enters: "Order Received (#TUXXXX)"
```
