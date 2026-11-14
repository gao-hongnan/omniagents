---
type: regex
pattern: '"file"\s*:\s*"app/dashboard\.py"'
target:
  source: file
  path: .reviews/latest/review.json
---
Recall: a finding cites app/dashboard.py for the per-member fetch_orders query in the loop.
