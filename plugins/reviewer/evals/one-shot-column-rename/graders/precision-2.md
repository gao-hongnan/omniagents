---
type: llm
focus:
  source: file
  path: .reviews/latest/review.json
---
PASS if no log-context finding on app/orders.py — app/middleware.py injects request_id.

FAIL if any finding in the review JSON violates the rule above.
