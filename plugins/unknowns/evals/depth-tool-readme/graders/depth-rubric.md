---
type: llm
---
Judge the response against every point; PASS only if all hold.

- PASS point: raw material comes from actually running the tool (real --help output, real sample input and output, real error messages)
- PASS point: the outside check runs the documented quickstart or examples in a clean environment, or by a fresh user, and fails on any divergence from the documented output

FAIL if any point above does not hold in the response.
