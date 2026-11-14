---
name: github-actions-should-not-trigger
description: Activation guard — the github-actions skill does not fire for this request.
tags: [trigger]
runs: 3
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Write a production Dockerfile for our FastAPI service: uv two-phase build, non-root user, healthcheck, and a compose file for local dev. It currently runs as root off a python:3.13 image and pip-installs at container start.
