"""Cursor-free pagination helpers."""


def page_slice(items: list[str], page: int, size: int) -> list[str]:
    """Return the 1-indexed page of items."""
    start = (page - 1) * size
    return items[start : start + size]


def page_count(total: int, size: int) -> int:
    return total // size
