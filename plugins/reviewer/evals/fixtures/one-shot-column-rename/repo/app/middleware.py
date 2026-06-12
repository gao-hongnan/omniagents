"""Logging filter that injects request_id into every record emitted under app.*."""

import logging


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(record, "request_id", "-")
        return True


logging.getLogger("app").addFilter(RequestContextFilter())
