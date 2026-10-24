---
type: regex
pattern: '"file"\s*:\s*"app/paging\.py"|"file"\s*:\s*"tests/test_paging\.py"'
target:
  source: file
  path: .reviews/latest/review.json
---
Recall: a finding cites app/paging.py or tests/test_paging.py for the page_count fix lacking a regression test.
