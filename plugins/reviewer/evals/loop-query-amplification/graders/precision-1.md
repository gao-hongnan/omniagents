---
type: llm
focus:
  source: file
  path: .reviews/latest/review.json
---
PASS if no performance finding on the sorted(PRIORITY_LEVELS) call in app/dashboard.py.

FAIL if any finding in the review JSON violates the rule above.
