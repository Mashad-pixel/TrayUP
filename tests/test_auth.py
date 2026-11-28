from app.extensions import db
from app.models.user import User
from tests.presence_helpers import presence_headers_for

STUDENT_EMAIL = "student@test.com"
STUDENT_MOBILE = "+919876500001"
STUDENT_PASSWORD = "StrongPass123!"


def login(client, mobile=STUDENT_MOBILE, password=STUDENT_PASSWORD):
    return client.post("/api/auth/login", json={"mobile": mobile, "password": password})


def test_login_success_starts_session(anon_client, student):
    response = login(anon_client)

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["email"] == STUDENT_EMAIL
    assert body["data"]["mobile_number"] == STUDENT_MOBILE
    assert "password_hash" not in body["data"]

    me = anon_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["data"]["role"] == "STUDENT"
    assert me.get_json()["data"]["mobile_number"] == STUDENT_MOBILE


def test_mobile_number_format_is_normalized(anon_client, student):
    response = login(anon_client, mobile=" +91 98765 00001 ")

    assert response.status_code == 200


def test_wrong_password_is_rejected(anon_client, student):
    response = login(anon_client, password="wrong-password")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_unknown_mobile_gives_same_error_as_wrong_password(anon_client, student):
    response = login(anon_client, mobile="+919876500002")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_inactive_user_cannot_login(anon_client, app):
    user = User(
        name="Old Account",
        email="old@test.com",
        mobile_number="+919876500003",
        role="STUDENT",
        is_active=False,
    )
    user.set_password(STUDENT_PASSWORD)
    db.session.add(user)
    db.session.commit()

    response = login(anon_client, mobile="+919876500003")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_missing_fields_are_rejected(anon_client, student):
    response = anon_client.post("/api/auth/login", json={"mobile": STUDENT_MOBILE})

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "MISSING_FIELDS"


def test_me_requires_login(anon_client):
    response = anon_client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "AUTH_REQUIRED"


def test_logout_ends_session(anon_client, student):
    login(anon_client)

    assert anon_client.post("/api/auth/logout").status_code == 200
    assert anon_client.get("/api/auth/me").status_code == 401


def test_real_login_can_create_order(anon_client, student, menu):
    login(anon_client)

    response = anon_client.post(
        "/api/orders",
        json={"items": [{"menu_item_id": menu["samosa"].id, "quantity": 2}]},
        headers={**presence_headers_for(anon_client), "Idempotency-Key": "real-login-test"},
    )

    assert response.status_code == 201
    assert response.get_json()["data"]["total_paise"] == 3000


def test_login_returns_csrf_token_for_next_requests(anon_client, student):
    response = anon_client.post(
        "/api/auth/login",
        json={"mobile": STUDENT_MOBILE, "password": "StrongPass123!"},
    )

    assert response.status_code == 200
    token = response.get_json()["data"]["csrf_token"]
    assert isinstance(token, str) and len(token) > 20



def test_registration_creates_mobile_only_student_and_ignores_requested_role(anon_client):
    response = anon_client.post(
        "/api/auth/register",
        json={
            "name": "New Student",
            "mobile": "9876500004",
            "password": "StrongPass123!",
            "role": "ADMIN",
        },
    )
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["role"] == "STUDENT"
    assert data["email"] is None
    assert data["mobile_number"] == "+919876500004"
    assert isinstance(data["csrf_token"], str)
    user = User.query.filter_by(mobile_number="+919876500004").one()
    assert user.mobile_number == "+919876500004"
    assert user.role == "STUDENT"
    assert user.check_password("StrongPass123!")
    assert anon_client.get("/api/auth/me").get_json()["data"]["role"] == "STUDENT"


def test_registration_rejects_weak_password(anon_client):
    response = anon_client.post(
        "/api/auth/register",
        json={
            "name": "New Student",
            "mobile": "9876500005",
            "password": "password",
        },
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_REGISTRATION"
    assert User.query.filter_by(mobile_number="+919876500005").count() == 0


def test_student_email_login_is_rejected(anon_client, student):
    response = anon_client.post(
        "/api/auth/login",
        json={"email": STUDENT_EMAIL, "password": STUDENT_PASSWORD},
    )

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_staff_can_still_login_with_email(anon_client, app):
    staff = User(name="Admin", email="admin@test.com", role="ADMIN", is_active=True)
    staff.set_password(STUDENT_PASSWORD)
    db.session.add(staff)
    db.session.commit()

    response = anon_client.post(
        "/api/auth/login",
        json={"email": staff.email, "password": STUDENT_PASSWORD},
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["role"] == "ADMIN"


def test_registration_requires_mobile_number(anon_client, student):
    response = anon_client.post(
        "/api/auth/register",
        json={
            "name": "New Student",
            "password": "StrongPass123!",
        },
    )

    assert response.status_code == 400
    assert User.query.count() == 1


def test_registration_rejects_duplicate_mobile_number(anon_client, student):
    response = anon_client.post(
        "/api/auth/register",
        json={
            "name": "Duplicate",
            "mobile": "9876500001",
            "password": "StrongPass123!",
        },
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "MOBILE_UNAVAILABLE"
