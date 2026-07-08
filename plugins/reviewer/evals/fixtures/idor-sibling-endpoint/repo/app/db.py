"""Report storage — every query is parameterized."""

import sqlite3

_conn = sqlite3.connect(":memory:", check_same_thread=False)
_conn.execute("CREATE TABLE reports (id INTEGER PRIMARY KEY, user_id INTEGER, body TEXT)")


def get_report(report_id: int) -> tuple[int, int, str] | None:
    return _conn.execute("SELECT id, user_id, body FROM reports WHERE id = ?", (report_id,)).fetchone()
