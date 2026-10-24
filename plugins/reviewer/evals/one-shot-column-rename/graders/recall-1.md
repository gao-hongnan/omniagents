---
type: regex
pattern: '"file"\s*:\s*"migrations/0002_rename_status\.py"'
target:
  source: file
  path: .reviews/latest/review.json
---
Recall: a finding with severity BLOCKER or IMPORTANT cites migrations/0002_rename_status.py for the one-step rename / missing rollback.
