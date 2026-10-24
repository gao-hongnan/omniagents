---
name: depth-flaky-test
description: A four-part depth pass and a deeper prompt.
tags: [depth-pass]
runs: 3
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill]
---

/depth-pass fix the flaky test test_checkout_concurrency in tests/test_orders.py — it fails maybe 1 in 20 CI runs and everyone just hits re-run
