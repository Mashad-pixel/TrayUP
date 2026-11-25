import base64
import hashlib
import json
import uuid

import pytest

from app.extensions import db
from app.models.canteen import CanteenSettings
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.payment import Payment, PaymentRecordStatus
from app.models.user import User, UserRole
from app.models.webhook_event import WebhookEvent, WebhookStatus
from app.services.order_service import create_order
from app.services.upi_service import (
    build_upi_intent_uri,
    decode_phonepe_callback,
    render_upi_qr_svg,
    verify_phonepe_signature,
)


def make_user(email, role, name="Test User"):
    user = User(name=name, email=email, role=role, is_active=True)
    user.set_password("StrongPass123!")
    db.session.add(user)
    db.session.commit()
    return user


def login_as(test_client, user):
    with test_client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True
    return test_client


def make_order(user, menu, quantity=1):
    order, _ = create_order(
        user.id,
        [{"menu_item_id": menu["samosa"].id, "quantity": quantity}],
    )
    return order


def make_phonepe_payload(order_number, amount_paise, utr="123456789012", success=True):
    inner = {
        "success": success,
        "code": "PAYMENT_SUCCESS" if success else "PAYMENT_ERROR",
        "message": "Payment Successful" if success else "Payment Failed",
        "data": {
            "merchantId": "PGTESTPAYUAT",
            "merchantTransactionId": f"phonepe_{order_number}",
            "transactionId": f"T{uuid.uuid4().hex[:12].upper()}",
            "amount": amount_paise,
            "state": "COMPLETED" if success else "FAILED",
            "responseCode": "SUCCESS" if success else "FAILED",
            "paymentInstrument": {
                "type": "UPI",
                "utr": utr,
            },
        },
    }
    encoded = base64.b64encode(json.dumps(inner).encode("utf-8")).decode("utf-8")
    outer = {"response": encoded}
    return json.dumps(outer).encode("utf-8"), encoded, inner["data"]["transactionId"]


def sign_phonepe(response_b64, salt_key="test_phonepe_salt_key_1234567890", salt_index="1"):
    h = hashlib.sha256((response_b64 + salt_key).encode("utf-8")).hexdigest()
    return f"{h}###{salt_index}"


# ==============================================================================
# Unit Tests for UPI & PhonePe Core Functions
# ==============================================================================

def test_build_upi_intent_uri_formatting():
    data = build_upi_intent_uri(
        vpa="canteen@ybl",
        merchant_name="TrayUP Canteen",
        amount_paise=1500,
        order_number="TU261125ABCD",
        note="Order TU261125ABCD",
    )
    assert "upi://pay?" in data["upi_uri"]
    assert "canteen%40ybl" in data["upi_uri"] or "canteen@ybl" in data["upi_uri"]
    assert "am=15.00" in data["upi_uri"]
    assert "cu=INR" in data["upi_uri"]
    assert "phonepe://pay?" in data["phonepe_uri"]
    assert "gpay://upi/pay?" in data["gpay_uri"]
    assert "paytmmp://pay?" in data["paytm_uri"]


def test_render_upi_qr_svg():
    upi_uri = "upi://pay?pa=canteen@ybl&pn=Canteen&am=15.00&cu=INR"
    svg = render_upi_qr_svg(upi_uri)
    assert "<svg" in svg
    assert "</svg>" in svg


def test_verify_phonepe_signature_and_decode():
    order_num = "TU1234"
    raw_bytes, b64_resp, txn_id = make_phonepe_payload(order_num, 1500)
    salt_key = "test_phonepe_salt_key_1234567890"
    valid_sig = sign_phonepe(b64_resp, salt_key, "1")

    assert verify_phonepe_signature(b64_resp, valid_sig, salt_key, "1") is True
    assert verify_phonepe_signature(b64_resp, "bad_sig###1", salt_key, "1") is False
    assert verify_phonepe_signature(b64_resp, valid_sig, salt_key, "2") is False

    decoded, _ = decode_phonepe_callback(raw_bytes, valid_sig, salt_key, "1")
    assert decoded["code"] == "PAYMENT_SUCCESS"
    assert decoded["data"]["amount"] == 1500


# ==============================================================================
# Payment Methods & Initiation Route Tests
# ==============================================================================

def test_get_payment_methods(app, student, menu, client):
    order = make_order(student, menu)
    response = client.get(f"/api/payments/methods?order_id={order.id}")
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert "payment_provider" in data
    assert "upi" in data
    assert "cash" in data
    assert "sandbox" in data


def test_initiate_upi_order(app, student, menu, client):
    order = make_order(student, menu)
    response = client.post("/api/payments/upi/initiate", json={"order_id": order.id})
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert "upi_uri" in data
    assert "phonepe_uri" in data
    assert data["order_id"] == order.id
    assert data["amount_paise"] == order.total_paise

    # Check Payment record was created
    payment = Payment.query.filter_by(order_id=order.id).first()
    assert payment is not None
    assert payment.status == PaymentRecordStatus.CREATED


def test_get_upi_qr_svg(app, student, menu, client):
    order = make_order(student, menu)
    response = client.get(f"/api/payments/{order.id}/upi-qr.svg")
    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert b"<svg" in response.data


# ==============================================================================
# Student Payment Claims & Cash Options
# ==============================================================================

def test_submit_upi_claim_with_valid_utr(app, student, menu, client):
    order = make_order(student, menu)
    client.post("/api/payments/upi/initiate", json={"order_id": order.id})

    utr = "412345678901"
    response = client.post("/api/payments/upi/submit-claim", json={
        "order_id": order.id,
        "utr_number": utr,
    })
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["payment_status"] == PaymentStatus.AWAITING_CONFIRMATION
    assert data["utr_number"] == utr

    reloaded = db.session.get(Order, order.id)
    assert reloaded.payment_status == PaymentStatus.AWAITING_CONFIRMATION
    assert reloaded.utr_number == utr


def test_submit_upi_claim_rejects_duplicate_utr(app, student, menu, client):
    order1 = make_order(student, menu)
    order2 = make_order(student, menu)
    utr = "998877665544"

    res1 = client.post("/api/payments/upi/submit-claim", json={"order_id": order1.id, "utr_number": utr})
    assert res1.status_code == 200

    res2 = client.post("/api/payments/upi/submit-claim", json={"order_id": order2.id, "utr_number": utr})
    assert res2.status_code == 409
    assert res2.get_json()["error"]["code"] == "DUPLICATE_UTR"


def test_submit_upi_claim_rejects_invalid_utr_format(app, student, menu, client):
    order = make_order(student, menu)
    response = client.post("/api/payments/upi/submit-claim", json={
        "order_id": order.id,
        "utr_number": "short",
    })
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_UTR"


def test_select_cash_payment_checks_canteen_setting(app, student, menu, client):
    # Enable cash
    settings = db.session.get(CanteenSettings, 1)
    if not settings:
        settings = CanteenSettings(id=1, cash_enabled=True, cash_max_order_paise=5000)
        db.session.add(settings)
    else:
        settings.cash_enabled = True
        settings.cash_max_order_paise = 5000
    db.session.commit()

    order = make_order(student, menu, quantity=2)  # 3000 paise <= 5000
    response = client.post("/api/payments/cash/select", json={"order_id": order.id})
    assert response.status_code == 200
    assert response.get_json()["data"]["payment_status"] == PaymentStatus.AWAITING_CONFIRMATION

    # Test cash limit exceeded
    big_order = make_order(student, menu, quantity=5)  # 7500 paise > 5000
    res_exceeded = client.post("/api/payments/cash/select", json={"order_id": big_order.id})
    assert res_exceeded.status_code == 400
    assert res_exceeded.get_json()["error"]["code"] == "CASH_LIMIT_EXCEEDED"


def test_select_cash_rejected_when_cash_disabled(app, student, menu, client):
    settings = db.session.get(CanteenSettings, 1)
    if settings:
        settings.cash_enabled = False
        db.session.commit()

    order = make_order(student, menu)
    response = client.post("/api/payments/cash/select", json={"order_id": order.id})
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "CASH_NOT_ENABLED"


# ==============================================================================
# Sandbox 1-Click Payment Simulation
# ==============================================================================

def test_sandbox_complete_payment(app, student, menu, client):
    order = make_order(student, menu)
    response = client.post("/api/payments/sandbox/complete", json={"order_id": order.id})
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["payment_status"] == PaymentStatus.PAID
    assert data["order_status"] == OrderStatus.RECEIVED

    reloaded = db.session.get(Order, order.id)
    assert reloaded.payment_status == PaymentStatus.PAID
    assert reloaded.order_status == OrderStatus.RECEIVED


# ==============================================================================
# Kitchen / Counter Confirmation & Rejection Tests
# ==============================================================================

def test_kitchen_pending_confirmation_and_confirm_payment(app, student, menu, client):
    kitchen_user = make_user("chef@test.com", UserRole.KITCHEN)
    kitchen_client = login_as(app.test_client(), kitchen_user)

    order = make_order(student, menu)
    client.post("/api/payments/upi/submit-claim", json={"order_id": order.id, "utr_number": "112233445566"})

    # Check order appears in pending confirmation queue
    queue_resp = kitchen_client.get("/api/kitchen/orders/pending-confirmation")
    assert queue_resp.status_code == 200
    orders = queue_resp.get_json()["data"]["orders"]
    assert any(o["id"] == order.id for o in orders)

    # Kitchen staff confirms payment
    confirm_resp = kitchen_client.post(
        f"/api/kitchen/orders/{order.id}/confirm-payment",
        json={"notes": "Soundbox announced payment received"},
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.get_json()["data"]["order"]["payment_status"] == PaymentStatus.PAID
    assert confirm_resp.get_json()["data"]["order"]["order_status"] == OrderStatus.RECEIVED

    reloaded = db.session.get(Order, order.id)
    assert reloaded.payment_status == PaymentStatus.PAID
    assert reloaded.order_status == OrderStatus.RECEIVED


def test_kitchen_reject_payment(app, student, menu, client):
    kitchen_user = make_user("chef_reject@test.com", UserRole.KITCHEN)
    kitchen_client = login_as(app.test_client(), kitchen_user)

    order = make_order(student, menu)
    client.post("/api/payments/upi/submit-claim", json={"order_id": order.id, "utr_number": "999999999999"})

    # Kitchen staff rejects payment
    reject_resp = kitchen_client.post(
        f"/api/kitchen/orders/{order.id}/reject-payment",
        json={"reason": "Payment not heard on soundbox"},
    )
    assert reject_resp.status_code == 200
    data = reject_resp.get_json()["data"]
    assert data["order_status"] == OrderStatus.CANCELLED
    assert data["payment_status"] == PaymentStatus.FAILED


# ==============================================================================
# PhonePe S2S Webhook Callback Tests
# ==============================================================================

def test_phonepe_webhook_success(app, student, menu):
    order = make_order(student, menu)
    raw_bytes, b64_resp, txn_id = make_phonepe_payload(order.order_number, order.total_paise, utr="445566778899")
    sig = sign_phonepe(b64_resp)

    test_client = app.test_client()
    response = test_client.post(
        "/api/payments/webhook/phonepe",
        data=raw_bytes,
        headers={"Content-Type": "application/json", "X-VERIFY": sig},
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["outcome"] == "payment_confirmed"

    reloaded = db.session.get(Order, order.id)
    assert reloaded.payment_status == PaymentStatus.PAID
    assert reloaded.order_status == OrderStatus.RECEIVED
    assert reloaded.utr_number == "445566778899"

    # Verify WebhookEvent stored
    event = WebhookEvent.query.filter_by(provider="phonepe", provider_event_id=txn_id).first()
    assert event is not None
    assert event.processing_status == WebhookStatus.PROCESSED

    # Verify duplicate is idempotent
    dup_resp = test_client.post(
        "/api/payments/webhook/phonepe",
        data=raw_bytes,
        headers={"Content-Type": "application/json", "X-VERIFY": sig},
    )
    assert dup_resp.status_code == 200
    assert dup_resp.get_json()["data"]["outcome"] == "already_processed"


def test_phonepe_webhook_rejects_bad_signature(app, student, menu):
    order = make_order(student, menu)
    raw_bytes, _, _ = make_phonepe_payload(order.order_number, order.total_paise)

    test_client = app.test_client()
    response = test_client.post(
        "/api/payments/webhook/phonepe",
        data=raw_bytes,
        headers={"Content-Type": "application/json", "X-VERIFY": "invalid_hash###1"},
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_SIGNATURE"


# ==============================================================================
# Admin Canteen Settings Routes
# ==============================================================================

def test_admin_canteen_settings_get_and_patch(app):
    admin_user = make_user("admin_settings@test.com", UserRole.ADMIN)
    admin_client = login_as(app.test_client(), admin_user)

    # GET
    res_get = admin_client.get("/api/admin/canteen/settings")
    assert res_get.status_code == 200
    data = res_get.get_json()
    assert "payment_provider" in data
    assert "cash_enabled" in data

    # PATCH
    update_payload = {
        "payment_provider": "phonepe",
        "merchant_display_name": "New Canteen Name",
        "upi_vpa": "newcanteen@okhdfcbank",
        "cash_enabled": True,
        "cash_max_order_paise": 25000,
    }
    res_patch = admin_client.patch("/api/admin/canteen/settings", json=update_payload)
    assert res_patch.status_code == 200
    updated = res_patch.get_json()
    assert updated["payment_provider"] == "phonepe"
    assert updated["merchant_display_name"] == "New Canteen Name"
    assert updated["upi_vpa"] == "newcanteen@okhdfcbank"
    assert updated["cash_enabled"] is True
    assert updated["cash_max_order_paise"] == 25000
