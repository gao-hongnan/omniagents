"""User domain model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    name: str
    email_address: str

    def display(self) -> str:
        return f"{self.name} <{self.email_address}>"
