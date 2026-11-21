import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models.user import User, UserRole

MIN_PASSWORD_LENGTH = 8


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
    email = email.strip().lower()
    role = role.upper()

    if not name:
        raise click.BadParameter("Name cannot be empty.", param_hint="--name")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise click.BadParameter(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
            param_hint="--password",
        )

    if User.query.filter_by(email=email).first():
        raise click.ClickException(f"A user with email {email} already exists.")

    user = User(name=name, email=email, role=role, is_active=True)
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    click.echo(f"Created {user.role} user {user.email} (id {user.id}).")


def register_cli(app):
    app.cli.add_command(create_user_command)
