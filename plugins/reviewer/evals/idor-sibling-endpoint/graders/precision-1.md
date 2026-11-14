---
type: llm
focus:
  source: file
  path: .reviews/latest/review.json
---
PASS if no injection finding on app/db.py — its queries are parameterized.

FAIL if any finding in the review JSON violates the rule above.
