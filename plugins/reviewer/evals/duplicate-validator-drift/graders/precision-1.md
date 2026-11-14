---
type: llm
focus:
  source: file
  path: .reviews/latest/review.json
---
PASS if no premature-abstraction or unnecessary-indirection finding on the SignupForm dataclass.

FAIL if any finding in the review JSON violates the rule above.
