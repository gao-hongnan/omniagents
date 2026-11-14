---
name: testing-should-trigger
description: Activation guard — the testing skill fires for this request.
tags: [trigger]
runs: 3
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Review this pytest test for determinism problems — it hits a live HTTP endpoint, uses time.sleep to wait for a background job, and depends on test ordering (a previous test creates the row it reads). Rewrite it to be hermetic and order-independent, and name the mutant each assertion kills:

```python
def test_export_ready(client, row_from_previous_test):
    time.sleep(2)
    r = client.get(f"/export/{row_from_previous_test.id}")
    assert r.status_code == 200
```
