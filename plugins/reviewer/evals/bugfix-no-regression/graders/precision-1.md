---
type: llm
focus:
  source: file
  path: .reviews/latest/review.json
---
PASS if no finding flags tests/test_paging.py's parametrized page_slice coverage as weak or missing.

FAIL if any finding in the review JSON violates the rule above.
