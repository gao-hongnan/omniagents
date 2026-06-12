"""Request body shapes."""

from pydantic import BaseModel


class LoginForm(BaseModel):
    email: str
    password: str
