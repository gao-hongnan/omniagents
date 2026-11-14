---
type: llm
focus:
  source: file
  path: .reviews/latest/review.json
---
PASS if no missing-timeout finding on client.get/client.post in app/orders.py — app/http_client.py sets timeout at construction.

FAIL if any finding in the review JSON violates the rule above.
