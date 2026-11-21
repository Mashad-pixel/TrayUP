import pytest

from app import create_app
from app.extensions import db
from app.models.menu import MenuItem
from app.models.user import User


@pytest.fixture
def app():
    app = create_app("testing")

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
