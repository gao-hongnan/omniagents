"""HTTP handlers."""

from app.models import User


def create_user(payload: dict[str, str]) -> User:
    return User(name=payload["name"], email_address=payload["email"])


def user_to_json(user: User) -> dict[str, str]:
    return {"name": user.name, "email": user.email_address}
