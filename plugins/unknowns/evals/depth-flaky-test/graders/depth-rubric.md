---
type: llm
---
Judge the response against every point; PASS only if all hold.

- PASS point: section 1 names a specific practitioner role, not just 'an expert' or 'a senior engineer'
- PASS point: raw material includes failure logs across many CI runs or a local reproduction of the failure
- PASS point: the outside check is a repeated-run count (hundreds or more consecutive passes, or a measured failure rate) rather than a single green run
- PASS point: the deeper prompt rules out masking the flake with a retry, a rerun plugin, or a sleep

FAIL if any point above does not hold in the response.
