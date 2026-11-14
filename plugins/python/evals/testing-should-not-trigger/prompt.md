---
name: testing-should-not-trigger
description: Activation guard — the testing skill does not fire for this request.
tags: [trigger]
runs: 3
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

This function's callers keep confusing megabytes with bytes. Give it precise type hints — a NewType for Megabytes, Literal for the unit parameter — and adjust the signature:

```python
def cache_size(unit, value):
    return value * 1024 * 1024 if unit == 'mb' else value
```
