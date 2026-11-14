---
name: typings-should-not-trigger
description: Activation guard — the typings skill does not fire for this request.
tags: [trigger]
runs: 3
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Our pytest suite has a test that fails about 1 run in 10 with 'assertion on response.json()["total"] == 3' — everything else passes. How should I structure fixture scope and isolation so state stops leaking between this test and the others? Show me the pytest-idiomatic fix.
