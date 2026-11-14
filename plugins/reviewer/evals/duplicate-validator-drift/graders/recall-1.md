---
type: regex
pattern: '"file"\s*:\s*"app/signup\.py"'
target:
  source: file
  path: .reviews/latest/review.json
---
Recall: a finding cites app/signup.py for clean_email duplicating validators.normalize_email.
