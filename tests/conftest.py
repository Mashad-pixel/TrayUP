import pytest
from flask import g, has_app_context
from flask.testing import FlaskClient

from app import create_app
from app.extensions import db
from app.models.menu import MenuItem
from app.models.user import User
from presence_helpers import issue_test_presence_session


class IsolatedClient(FlaskClient):
    """Test client that clears Flask-Login's cached user before each request.

    Flask-Login caches the logged-in user in flask.g. Tests keep one app context open,
    so without this, a request from one logged-in client could reuse another client's user.
    """

    def open(self, *args, **kwargs):
        if has_app_context():
            g.pop("_login_user", None)
        return super().open(*args, **kwargs)


class PresenceAwareClient(IsolatedClient):
    """Test client that gives a logged-in student a fresh verified session for each order POST.

    Pricing, stock and payment tests are about their own rules, so they get a valid
    verification automatically. Real verification is covered in tests/test_presence.py. Set
    `auto_presence = False` on a client to test the verification rules directly.
    """

    auto_presence = True

    def post(self, *args, **kwargs):
        path = args[0] if args else kwargs.get("path", "")
        if self.auto_presence and path == "/api/orders":
            headers = dict(kwargs.get("headers") or {})
            if "X-Presence-Session" not in headers:
                with self.session_transaction() as sess:
                    user_id = sess.get("_user_id")
                if user_id is not None:
                    headers["X-Presence-Session"] = issue_test_presence_session(int(user_id))
                    kwargs["headers"] = headers
        return super().post(*args, **kwargs)


@pytest.fixture
def app():
    app = create_app("testing")
    app.test_client_class = PresenceAwareClient

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def student(app):
    user = User(
        name="Test Student",
        email="student@test.com",
        role="STUDENT",
        is_active=True,
    )
    user.set_password("StrongPass123!")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def menu(app):
    items = {
        "samosa": MenuItem(
            name="Samosa", category="Snacks", price_paise=1500,
            is_available=True, stock_quantity=None,
        ),
        "tea": MenuItem(
            name="Tea", category="Drinks", price_paise=1000,
            is_available=True, stock_quantity=None,
        ),
        "burger": MenuItem(
            name="Burger", category="Meals", price_paise=8000,
            is_available=False, stock_quantity=None,
        ),
        "paneer_roll": MenuItem(
            name="Paneer Roll", category="Meals", price_paise=6000,
            is_available=True, stock_quantity=2,
        ),
    }
    db.session.add_all(items.values())
    db.session.commit()
    return {key: item for key, item in items.items()}


@pytest.fixture
def client(app, student):
    """Test client logged in as the student.

    Sets the Flask-Login session key directly, so tests don't depend on the login route.
    """
    test_client = app.test_client()
    with test_client.session_transaction() as sess:
        sess["_user_id"] = str(student.id)
        sess["_fresh"] = True
    return test_client


@pytest.fixture
def anon_client(app):
    return app.test_client()


@pytest.fixture
def student_client(app, student):
    test_client = app.test_client()
    with test_client.session_transaction() as sess:
        sess["_user_id"] = str(student.id)
        sess["_fresh"] = True
    return test_client
