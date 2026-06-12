"""Order reads on the hot path."""

import logging

from app.http_client import client

log = logging.getLogger(__name__)


def order_status(conn, order_id: int) -> str:
    row = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
    return row[0]


def notify_partner(order_id: int) -> None:
    resp = client.get(f"/partner/orders/{order_id}")
    if resp.status_code >= 400:
        log.error("partner sync failed for order %s", order_id)
