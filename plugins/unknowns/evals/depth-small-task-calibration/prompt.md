---
name: depth-small-task-calibration
description: Calibration: the task is trivial.
tags: [depth-pass]
runs: 3
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill]
---

/depth-pass rename the variable tmp to retry_count in src/net/client.py
