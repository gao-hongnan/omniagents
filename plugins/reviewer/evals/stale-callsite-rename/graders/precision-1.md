---
type: llm
focus:
  source: file
  path: .reviews/latest/review.json
---
PASS if no finding cites app/legacy.py unless its summary starts with [pre-existing].

FAIL if any finding in the review JSON violates the rule above.
