---
type: regex
pattern: '"file"\s*:\s*"worker/jobs\.py"'
target:
  source: file
  path: .reviews/latest/review.json
---
Recall: a finding cites worker/jobs.py at the os.path.exists(out_path) check-then-create race.
