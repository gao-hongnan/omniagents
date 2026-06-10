"""Email notifications."""

from app.models import User


def send_welcome(user: User) -> str:
    body = f"Welcome, {user.name}!"
    return f"to={user.email_address}; body={body}"
