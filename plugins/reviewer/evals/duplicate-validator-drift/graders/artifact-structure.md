---
type: regex
pattern: '"verdict"\s*:'|"findings"\s*:'|"target"\s*:'
target:
  source: file
  path: .reviews/latest/review.json
---
