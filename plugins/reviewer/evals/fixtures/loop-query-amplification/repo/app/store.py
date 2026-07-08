"""Order lookups against the primary database."""

import sqlite3

_conn = sqlite3.connect(":memory:", check_same_thread=False)
_conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, total INTEGER)")


def fetch_orders(user_id: int) -> list[tuple[int, int]]:
    return _conn.execute("SELECT id, total FROM orders WHERE user_id = ?", (user_id,)).fetchall()


def fetch_orders_bulk(user_ids: list[int]) -> list[tuple[int, int, int]]:
    marks = ",".join("?" for _ in user_ids)
    return _conn.execute(
        f"SELECT user_id, id, total FROM orders WHERE user_id IN ({marks})",  # noqa: S608 — placeholders only
        user_ids,
    ).fetchall()
