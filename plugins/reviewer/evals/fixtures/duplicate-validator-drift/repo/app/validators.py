"""Canonical input normalization — one rule, one owner."""


def normalize_email(raw: str) -> str:
    """Lowercase, trim, and collapse plus-aliases — the one email rule."""
    email = raw.strip().lower()
    local, _, domain = email.partition("@")
    local = local.split("+", 1)[0]
    return f"{local}@{domain}"
