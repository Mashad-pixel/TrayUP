"""Canteen settings: persistent name/hours and the server-side order acceptance switch."""
from datetime import time

import pytest

from app.extensions import db
from app.models.canteen import CanteenSettings
from app.models.user import User, UserRole
from tests.session_helpers import issue_test_session


def _client_for_role(app, role, email):
    user = User(name=role.title(), email=email, role=role, is_active=True)
    user.set_password("StrongPass123!")
    db.session.add(user)
    db.session.commit()
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True
        session["sid"] = issue_test_session(user)
    return client


@pytest.fixture
def admin_client(app):
    return _client_for_role(app, UserRole.ADMIN, "admin-settings@test.com")


@pytest.fixture
def kitchen_client(app):
    return _client_for_role(app, UserRole.KITCHEN, "kitchen-settings@test.com")


def test_settings_default_when_no_row_exists(admin_client):
    response = admin_client.get("/api/admin/canteen/settings")
    assert response.status_code == 200
    settings = response.get_json()["settings"]
    assert settings["canteen_name"] == "TrayUP Canteen"
    assert settings["name"] == "TrayUP Canteen"
    assert settings["opens_at"] == "08:00"
    assert settings["closes_at"] == "18:00"
    assert settings["is_accepting_orders"] is True
    assert settings["closed_message"] is None


def test_admin_saves_name_and_hours_in_one_request(admin_client):
    response = admin_client.patch("/api/admin/canteen/settings", json={
        "canteen_name": "  Main Canteen  ", "opens_at": "08:30", "closes_at": "18:00",
    })
    assert response.status_code == 200
    settings = response.get_json()["settings"]
    assert settings["canteen_name"] == "Main Canteen"
    assert settings["opens_at"] == "08:30"
    assert settings["closes_at"] == "18:00"
    row = db.session.get(CanteenSettings, 1)
    assert (row.canteen_name, row.opens_at, row.closes_at) == ("Main Canteen", time(8, 30), time(18, 0))


def test_legacy_name_alias_is_supported(admin_client):
    response = admin_client.patch("/api/admin/canteen/settings", json={
        "name": "North Block", "opens_at": "08:00", "closes_at": "17:30",
    })
    assert response.status_code == 200
    assert response.get_json()["settings"]["canteen_name"] == "North Block"


def test_partial_detail_update_keeps_other_fields(admin_client):
    admin_client.patch("/api/admin/canteen/settings", json={
        "canteen_name": "Main Canteen", "opens_at": "08:00", "closes_at": "18:00",
    })
    response = admin_client.patch("/api/admin/canteen/settings", json={"canteen_name": "Annex"})
    settings = response.get_json()["settings"]
    assert settings["canteen_name"] == "Annex"
    assert (settings["opens_at"], settings["closes_at"]) == ("08:00", "18:00")


def test_partial_hour_update_keeps_the_other_hour(admin_client):
    response = admin_client.patch("/api/admin/canteen/settings", json={"opens_at": "09:00"})
    assert response.status_code == 200
    assert response.get_json()["settings"]["opens_at"] == "09:00"
    assert response.get_json()["settings"]["closes_at"] == "18:00"


@pytest.mark.parametrize("opens,closes", [("18:00", "08:00"), ("09:00", "09:00")])
def test_closing_time_must_be_after_opening_time(admin_client, opens, closes):
    response = admin_client.patch("/api/admin/canteen/settings", json={"opens_at": opens, "closes_at": closes})
    assert response.status_code == 400
    assert "closes_at" in response.get_json()["details"]


@pytest.mark.parametrize("value", ["8:00", "24:00", "12:60", "0800", "08:00:00", "08:00\n", 800, "ab:cd"])
def test_times_must_be_24_hour_hh_mm(admin_client, value):
    response = admin_client.patch("/api/admin/canteen/settings", json={"opens_at": value})
    assert response.status_code == 400
    assert "opens_at" in response.get_json()["details"]


@pytest.mark.parametrize("name", ["", "   ", 5, "x" * 121])
def test_name_is_validated(admin_client, name):
    response = admin_client.patch("/api/admin/canteen/settings", json={"canteen_name": name})
    assert response.status_code == 400
    assert "canteen_name" in response.get_json()["details"]


def test_unknown_settings_fields_are_refused(admin_client):
    response = admin_client.patch("/api/admin/canteen/settings", json={"theme": "dark"})
    assert response.status_code == 400
    assert "unknown_fields" in response.get_json()["details"]


def test_order_acceptance_and_closed_message_are_persistent(admin_client, anon_client):
    closed = admin_client.patch("/api/admin/canteen/settings", json={
        "is_accepting_orders": False, "closed_message": "Back at 2 PM",
    })
    assert closed.status_code == 200
    assert closed.get_json()["settings"]["closed_message"] == "Back at 2 PM"
    assert anon_client.get("/api/canteen/status").get_json()["message"] == "Back at 2 PM"

    reopened = admin_client.patch("/api/admin/canteen/status", json={"is_accepting_orders": True})
    assert reopened.status_code == 200
    assert admin_client.get("/api/admin/canteen/settings").get_json()["settings"]["closed_message"] is None


def test_public_status_shape_remains_minimal(anon_client):
    assert set(anon_client.get("/api/canteen/status").get_json()) == {"is_accepting_orders", "message"}


def test_kitchen_staff_cannot_read_or_change_settings(kitchen_client):
    assert kitchen_client.get("/api/admin/canteen/settings").status_code == 403
    assert kitchen_client.patch("/api/admin/canteen/settings", json={"canteen_name": "X"}).status_code == 403
