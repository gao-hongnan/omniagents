---
type: llm
focus:
  source: file
  path: .reviews/latest/review.json
---
PASS if no hardcoded-secret finding on TEST_TOKEN in tests/conftest.py.

FAIL if any finding in the review JSON violates the rule above.
