import json
import os

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models.menu import MenuItem
from app.models.menu_category import MenuCategory
from app.models.user import User, UserRole
from app.services.order_service import (
    DEFAULT_EXPIRY_BATCH_SIZE,
    MAX_EXPIRY_BATCH_SIZE,
    expire_unpaid_orders,
    expiry_status,
)
from app.services.menu_service import MenuValidationError, create_menu_item, validate_menu_payload
from app.services.category_service import create_category
from app.services.session_service import prune_sessions, revoke_user_sessions
from app.services.time_utils import utcnow
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
@click.option(
    "--check",
    is_flag=True,
    help="Report overdue orders without expiring anything. Exits 1 if the sweep has stalled.",
)
@click.option(
    "--batch-size",
    type=click.IntRange(1, MAX_EXPIRY_BATCH_SIZE),
    default=DEFAULT_EXPIRY_BATCH_SIZE,
    show_default=True,
    help="Orders expired per database transaction.",
)
@with_appcontext
def expire_orders_command(check, batch_size):
    """Cancel unpaid orders whose payment window has closed, and free their stock.

    Run this on a schedule (for example every minute) so stock is released even when
    no new orders are coming in. Use --check from monitoring to see whether it is keeping up.
    """
    if check:
        status = expiry_status()
        click.echo(f"Overdue unpaid orders: {status['overdue_orders']}")
        if status["oldest_overdue_minutes"] is not None:
            click.echo(f"Oldest is {status['oldest_overdue_minutes']:.1f} minute(s) past its payment window.")
        if status["stalled"]:
            click.echo("STALLED: overdue orders are not being expired. Check the scheduled job.")
            raise SystemExit(1)
        return

    count = expire_unpaid_orders(batch_size=batch_size)
    click.echo(f"Expired {count} unpaid order(s).")


def _user_by_email(email):
    user = User.query.filter_by(email=normalize_email(email)).first()
    if user is None:
        raise click.ClickException("No user has that email address.")
    return user


@click.command("reset-mfa")
@click.option("--email", required=True, help="Account whose authenticator must be re-enrolled.")
@with_appcontext
def reset_mfa_command(email):
    """Remove an account's two-factor setup (for a lost phone) and end its sessions.

    The account must enroll again at its next sign-in.
    """
    user = _user_by_email(email)
    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_last_step = None
    user.mfa_failed_attempts = 0
    user.mfa_locked_until = None
    db.session.commit()
    revoked = revoke_user_sessions(user.id)
    click.echo(f"Reset two-factor authentication for {user.email}. Revoked {revoked} session(s).")


@click.command("revoke-sessions")
@click.option("--email", required=True, help="Account whose live sessions should end immediately.")
@with_appcontext
def revoke_sessions_command(email):
    user = _user_by_email(email)
    revoked = revoke_user_sessions(user.id)
    click.echo(f"Revoked {revoked} session(s) for {user.email}.")


@click.command("prune-sessions")
@with_appcontext
def prune_sessions_command():
    """Delete expired and revoked session rows. Run this on a schedule."""
    removed = prune_sessions()
    click.echo(f"Removed {removed} finished session(s).")


SEED_MENU_PATH = os.path.join(os.path.dirname(__file__), "data", "menu_seed.json")


@click.command("seed-menu")
@with_appcontext
def seed_menu_command():
    """Load the starter menu into an empty database. Does nothing if any menu item exists.

    Every entry goes through the same validation as the admin API, and all entries are
    checked before any are written.
    """
    if MenuItem.query.first() is not None:
        click.echo("The menu already has items. Nothing was loaded.")
        return

    with open(SEED_MENU_PATH, encoding="utf-8") as handle:
        entries = json.load(handle)

    for index, entry in enumerate(entries, start=1):
        try:
            validate_menu_payload(entry)
        except MenuValidationError as exc:
            raise click.ClickException(
                f"Seed entry {index} ({entry.get('name')!r}) is invalid: {exc.errors}"
            )

    categories = {}
    for entry in entries:
        category_name = entry["category"]
        if category_name not in categories:
            category = MenuCategory.query.filter_by(name=category_name).first()
            if category is None:
                category = create_category({"name": category_name})
            categories[category_name] = category
    for entry in entries:
        create_menu_item(entry)
    click.echo(f"Loaded {len(entries)} menu items.")


@click.command("setup-admin")
@click.option("--email", required=True, help="Administrator sign-in email.")
@click.option("--name", default="Administrator", show_default=True, help="Administrator name.")
@with_appcontext
def setup_admin_command(email, name):
    """Create the first administrator account interactively."""
    email = normalize_email(email)
    name = " ".join(name.split())
    if not is_valid_email(email):
        raise click.ClickException("Enter a valid email address.")
    if not is_valid_name(name):
        raise click.ClickException("Enter a name with 1 to 100 characters.")
    if User.query.filter_by(role=UserRole.ADMIN).first() is not None:
        raise click.ClickException("An administrator already exists.")
    if User.query.filter_by(email=email).first() is not None:
        raise click.ClickException("A user with that email already exists.")

    password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
    problem = password_problem(password)
    if problem:
        raise click.ClickException(problem)
    user = User(name=name, email=email, role=UserRole.ADMIN, is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f"Created administrator {user.email}.")


@click.command("reset-admin-credentials")
@click.option("--current-email", required=True, help="Current administrator email.")
@click.option("--new-email", help="New sign-in email. Defaults to the current email.")
@with_appcontext
def reset_admin_credentials_command(current_email, new_email):
    """Change an administrator's email/password and revoke existing sessions."""
    user = User.query.filter_by(email=normalize_email(current_email)).first()
    if user is None:
        raise click.ClickException("No user has that email address.")
    if user.role != UserRole.ADMIN:
        raise click.ClickException("That user is not an administrator.")

    normalized_email = normalize_email(new_email) if new_email else user.email
    if not is_valid_email(normalized_email):
        raise click.ClickException("Enter a valid email address.")
    duplicate = User.query.filter(User.email == normalized_email, User.id != user.id).first()
    if duplicate is not None:
        raise click.ClickException("A user with that email already exists.")

    password = click.prompt("New password", hide_input=True, confirmation_prompt=True)
    problem = password_problem(password)
    if problem:
        raise click.ClickException(problem)

    user.email = normalized_email
    user.set_password(password)
    user.password_changed_at = utcnow()
    db.session.commit()
    revoked = revoke_user_sessions(user.id)
    click.echo(f"Updated administrator credentials. Revoked {revoked} session(s).")


def register_cli(app):
    app.cli.add_command(seed_menu_command)
    app.cli.add_command(create_user_command)
    app.cli.add_command(expire_orders_command)
    app.cli.add_command(reset_mfa_command)
    app.cli.add_command(revoke_sessions_command)
    app.cli.add_command(prune_sessions_command)
    app.cli.add_command(setup_admin_command)
    app.cli.add_command(reset_admin_credentials_command)
