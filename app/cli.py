import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models.user import User, UserRole
from app.services.order_service import expire_unpaid_orders
from app.security.account_rules import is_valid_email, is_valid_name, normalize_email, password_problem



@click.command("create-user")
@click.option("--name", required=True, help="Full name of the user.")
@click.option("--email", required=True, help="Login email. Stored in lowercase.")
@click.option(
    "--role",
    type=click.Choice([UserRole.ADMIN, UserRole.KITCHEN, UserRole.STUDENT], case_sensitive=False),
    default=UserRole.STUDENT,
    show_default=True,
    help="Account role.",
)
@click.password_option(help="Password (prompted twice).")
@with_appcontext
def create_user_command(name, email, role, password):
    name = name.strip()
    email = normalize_email(email)
    role = role.upper()

    if not is_valid_name(name):
        raise click.BadParameter("Enter a name with 1 to 100 characters.", param_hint="--name")
    if not is_valid_email(email):
        raise click.BadParameter("Enter a valid email address.", param_hint="--email")

    if not name:
        raise click.BadParameter("Name cannot be empty.", param_hint="--name")

    problem = password_problem(password)
    if problem:
        raise click.BadParameter(problem, param_hint="--password")

    if User.query.filter_by(email=email).first():
        raise click.ClickException(f"A user with email {email} already exists.")

    user = User(name=name, email=email, role=role, is_active=True)
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    click.echo(f"Created {user.role} user {user.email} (id {user.id}).")


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
@with_appcontext
def seed_demo_command():
    """Seed sample users, canteen settings, and menu items for local testing."""
    from app.models.canteen import CanteenSettings
    from app.models.menu import MenuItem

    roles = [
        ("Demo Admin", "admin@trayup.internal", UserRole.ADMIN, "AdminPass123!"),
        ("Demo Kitchen", "kitchen@trayup.internal", UserRole.KITCHEN, "KitchenPass123!"),
        ("Demo Student", "student@trayup.internal", UserRole.STUDENT, "StudentPass123!"),
    ]
    for name, email, role, pwd in roles:
        if not User.query.filter_by(email=email).first():
            u = User(name=name, email=email, role=role, is_active=True)
            u.set_password(pwd)
            db.session.add(u)
            click.echo(f"Created {role} {email}")

    settings = db.session.get(CanteenSettings, 1)
    if not settings:
        settings = CanteenSettings(
            id=1,
            is_accepting_orders=True,
            payment_provider="sandbox",
            merchant_display_name="Campus Canteen",
            upi_vpa="canteen@ybl",
            cash_enabled=False,
            cash_max_order_paise=20000,
        )
        db.session.add(settings)
        click.echo("Created default CanteenSettings")

    if MenuItem.query.count() == 0:
        from app.seed_data import DEMO_PRODUCTS

        demo_items = [
            MenuItem(
                id=item["id"],
                name=item["name"],
                category=item["category"],
                price_paise=item["price_paise"],
                description=item["description"],
                image_url=item["image_url"],
                is_available=True,
            )
            for item in DEMO_PRODUCTS
        ]
        db.session.add_all(demo_items)
        db.session.flush()

        if db.session.bind and db.session.bind.dialect.name == "postgresql":
            db.session.execute(
                db.text("SELECT setval(pg_get_serial_sequence('menu_items', 'id'), COALESCE(MAX(id), 1)) FROM menu_items;")
            )
        click.echo(f"Added {len(demo_items)} demo menu items")

    db.session.commit()
    click.echo("Demo data seeded successfully.")


def register_cli(app):
    app.cli.add_command(create_user_command)
    app.cli.add_command(expire_orders_command)
    app.cli.add_command(seed_demo_command)
