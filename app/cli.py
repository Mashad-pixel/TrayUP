import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models.user import User, UserRole
from app.services.order_service import expire_unpaid_orders
from app.security.account_rules import (
    is_valid_email,
    is_valid_name,
    normalize_email,
    normalize_mobile_number,
    password_problem,
)



@click.command("create-user")
@click.option("--name", required=True, help="Full name of the user.")
@click.option("--email", help="Account email; required for staff accounts.")
@click.option("--mobile", help="Student mobile number used for sign-in.")
@click.option(
    "--role",
    type=click.Choice([UserRole.ADMIN, UserRole.KITCHEN, UserRole.STUDENT], case_sensitive=False),
    default=UserRole.STUDENT,
    show_default=True,
    help="Account role.",
)
@click.password_option(help="Password (prompted twice).")
@with_appcontext
def create_user_command(name, email, mobile, role, password):
    name = name.strip()
    email = normalize_email(email) if email else None
    role = role.upper()
    mobile_number = normalize_mobile_number(mobile)

    if not is_valid_name(name):
        raise click.BadParameter("Enter a name with 1 to 100 characters.", param_hint="--name")
    if role != UserRole.STUDENT and not email:
        raise click.BadParameter("An email address is required for staff accounts.", param_hint="--email")
    if email and not is_valid_email(email):
        raise click.BadParameter("Enter a valid email address.", param_hint="--email")
    if role == UserRole.STUDENT and not mobile_number:
        raise click.BadParameter(
            "A valid mobile number is required for student accounts.",
            param_hint="--mobile",
        )
    if mobile is not None and not mobile_number:
        raise click.BadParameter("Enter a valid mobile number.", param_hint="--mobile")

    if not name:
        raise click.BadParameter("Name cannot be empty.", param_hint="--name")

    problem = password_problem(password)
    if problem:
        raise click.BadParameter(problem, param_hint="--password")

    if email and User.query.filter_by(email=email).first():
        raise click.ClickException(f"A user with email {email} already exists.")
    if mobile_number and User.query.filter_by(mobile_number=mobile_number).first():
        raise click.ClickException("An account with this mobile number already exists.")

    user = User(
        name=name,
        email=email,
        mobile_number=mobile_number,
        role=role,
        is_active=True,
    )
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    click.echo(f"Created {user.role} account (id {user.id}).")


@click.command("set-user-mobile")
@click.option("--email", required=True, help="Email of the student account to update.")
@click.option("--mobile", required=True, help="New mobile number used for sign-in.")
@with_appcontext
def set_user_mobile_command(email, mobile):
    email = normalize_email(email)
    mobile_number = normalize_mobile_number(mobile)
    if not is_valid_email(email):
        raise click.BadParameter("Enter a valid email address.", param_hint="--email")
    if not mobile_number:
        raise click.BadParameter("Enter a valid mobile number.", param_hint="--mobile")

    user = User.query.filter_by(email=email).first()
    if user is None or user.role != UserRole.STUDENT:
        raise click.ClickException("No student account was found for that email.")
    if User.query.filter(
        User.mobile_number == mobile_number,
        User.id != user.id,
    ).first():
        raise click.ClickException("An account with this mobile number already exists.")

    user.mobile_number = mobile_number
    db.session.commit()
    click.echo(f"Updated mobile sign-in for student account {user.id}.")


@click.command("expire-orders")
@with_appcontext
def expire_orders_command():
    """Cancel unpaid orders whose payment window has closed, and free their stock.

    Run this on a schedule (for example every minute) so stock is released even when
    no new orders are coming in.
    """
    count = expire_unpaid_orders()
    click.echo(f"Expired {count} unpaid order(s).")


@click.command("seed-demo")
@click.option("--student-mobile", required=True, help="Mobile number for the demo student.")
@with_appcontext
def seed_demo_command(student_mobile):
    """Seed sample users, canteen settings, and menu items for local testing."""
    from app.models.canteen import CanteenSettings
    from app.models.menu import MenuItem

    student_mobile = normalize_mobile_number(student_mobile)
    if not student_mobile:
        raise click.BadParameter("Enter a valid mobile number.", param_hint="--student-mobile")

    roles = [
        ("Demo Admin", "admin@trayup.internal", UserRole.ADMIN, "AdminPass123!", None),
        ("Demo Kitchen", "kitchen@trayup.internal", UserRole.KITCHEN, "KitchenPass123!", None),
        ("Demo Student", None, UserRole.STUDENT, "StudentPass123!", student_mobile),
    ]
    for name, email, role, pwd, mobile_number in roles:
        user = (
            User.query.filter_by(email=email).first()
            if email
            else User.query.filter_by(mobile_number=mobile_number).first()
        )
        if not user and role == UserRole.STUDENT:
            user = User.query.filter_by(email="student@trayup.internal").first()
        if not user:
            if mobile_number and User.query.filter_by(mobile_number=mobile_number).first():
                raise click.ClickException("An account with this mobile number already exists.")
            u = User(name=name, email=email, mobile_number=mobile_number, role=role, is_active=True)
            u.set_password(pwd)
            db.session.add(u)
            click.echo(f"Created {role} account")
        elif role == UserRole.STUDENT and not user.mobile_number:
            if User.query.filter_by(mobile_number=mobile_number).first():
                raise click.ClickException("An account with this mobile number already exists.")
            user.mobile_number = mobile_number

    settings = db.session.get(CanteenSettings, 1)
    if not settings:
        settings = CanteenSettings(
            id=1,
            is_accepting_orders=True,
            payment_provider="sandbox",
            merchant_display_name="Campus Canteen",
            upi_vpa="canteen@ybl",
            cash_enabled=True,
            cash_max_order_paise=20000,
        )
        db.session.add(settings)
        click.echo("Created default CanteenSettings")

    if MenuItem.query.count() == 0:
        demo_items = [
            MenuItem(name="Masala Dosa", category="Breakfast", price_paise=5000, is_available=True),
            MenuItem(name="Veg Burger", category="Fast Food", price_paise=6000, is_available=True, stock_quantity=20),
            MenuItem(name="Cold Coffee", category="Beverages", price_paise=4000, is_available=True),
            MenuItem(name="Samosa (2 pcs)", category="Snacks", price_paise=3000, is_available=True, stock_quantity=50),
        ]
        db.session.add_all(demo_items)
        click.echo("Added 4 demo menu items")

    db.session.commit()
    click.echo("Demo data seeded successfully.")


def register_cli(app):
    app.cli.add_command(create_user_command)
    app.cli.add_command(set_user_mobile_command)
    app.cli.add_command(expire_orders_command)
    app.cli.add_command(seed_demo_command)
