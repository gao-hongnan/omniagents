---
type: llm
focus:
  source: file
  path: .reviews/latest/review.json
---
PASS if no unbounded-cache finding on badge_for in app/summary.py (lru_cache maxsize=128).

FAIL if any finding in the review JSON violates the rule above.
