---
type: regex
pattern: '"file"\s*:\s*"app/routes\.py"'
target:
  source: file
  path: .reviews/latest/review.json
---
Recall: a finding with severity BLOCKER or IMPORTANT cites app/routes.py for remove_report's missing ownership check.
