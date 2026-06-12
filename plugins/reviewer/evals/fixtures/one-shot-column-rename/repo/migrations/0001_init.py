"""Initial schema."""


def up(conn) -> None:
    conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, status TEXT)")


def down(conn) -> None:
    conn.execute("DROP TABLE orders")
