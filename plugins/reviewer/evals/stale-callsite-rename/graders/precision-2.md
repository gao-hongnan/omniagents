---
type: llm
focus:
  source: file
  path: .reviews/latest/review.json
---
PASS if no finding mentions the unused 'import os' in app/models.py.

FAIL if any finding in the review JSON violates the rule above.
