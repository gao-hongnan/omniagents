---
name: github-actions-should-trigger
description: Activation guard — the github-actions skill fires for this request.
tags: [trigger]
runs: 3
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Write a GitHub Actions workflow for our Python service PR pipeline: checkout, lint + test matrix on 3.12/3.13, a docker build that must not run on forks, and a deploy job gated behind an environment. We want it hardened — least-privilege permissions and no tag-pinned actions.
