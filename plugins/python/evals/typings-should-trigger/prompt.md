---
name: typings-should-trigger
description: Activation guard — the typings skill fires for this request.
tags: [trigger]
runs: 3
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Here is a Python function from our billing service — the parameters and return type are untyped and callers keep passing the wrong things. Tighten its type hints to production standard (closed sets as Literal, no bare dict/str soup, precise generics) and explain each choice briefly:

```python
def find_invoices(customer, status, since, limit=None):
    ...
```
