---
name: operability-review
description: >-
  Use when reviewing code for operability issues such as missing or noisy
  logging, absent metrics or tracing on new code paths, unreported errors,
  unbounded timeouts or retries, unsafe migrations, missing rollout/rollback
  paths, ungraceful shutdown, or config and secrets handling problems.
when_to_use: >-
  Trigger for operability review: silent failure, log without context, PII in
  logs, missing metric, missing trace span, swallowed error not reported,
  hardcoded timeout, retry without budget, migration locks table, no rollback
  path, feature flag missing, ungraceful shutdown, config drift, secret in
  config, health check gap.
disable-model-invocation: false
user-invocable: false
---

# Operability Review Checklist

Review whether the changed code can be operated: observed when healthy,
diagnosed when broken, rolled out safely, and rolled back cheaply. The
question is always "it is 3am and this code is misbehaving — what does the
on-call see, and what can they do?"

## When to Flag

- Flag a changed code path whose failure would be invisible, undiagnosable,
  or unrecoverable in production. If the path already inherits adequate
  observability from a caller or framework, do not duplicate it.
- This dimension usually only dispatches when the diff touches runtime
  source, config, infra, or migrations — calibrate to what actually ships.

## Observability

- New non-trivial code path with no log line, metric, or span on its
  failure branch — a silent failure mode
- Errors caught and handled without being counted or reported anywhere
- Log lines missing the identifiers needed to correlate (request id, job
  id, tenant) — "Error occurred" tells the on-call nothing
- PII, secrets, or full payloads in log output
- Log level misuse: expected conditions at ERROR (alert fatigue), real
  failures at DEBUG (invisible)
- New external call not covered by existing tracing/metrics middleware

## Resilience Budgets

- Outbound call with no timeout, or a single-number timeout where the
  caller's budget demands less
- Retry without a cap, without backoff+jitter, or on a non-idempotent
  operation without an idempotency key
- New failure mode with no degraded behavior decision: does the feature
  fail open or fail closed, and is that deliberate?
- Resource acquisition (connections, file handles, tasks) with no bound or
  no release on the error path
- Graceful shutdown: in-flight work on the changed path dropped or
  double-processed when the process receives SIGTERM

## Rollout and Rollback

- Behavior change shipped without a flag, config switch, or staged path
  when the blast radius is large
- Schema migration that locks a hot table, is irreversible, or is coupled
  to the code deploy such that rollback breaks (expand/contract violated)
- Data backfill with no resume/checkpoint on failure
- New config key with no default, or a default that differs between
  environments silently
- Version/protocol compatibility: old and new instances coexisting during
  deploy will disagree on the changed wire format, queue payload, or cache
  shape

## Config and Secrets

- Secrets read outside the established secret path (hardcoded, plain env
  literal in code, committed file)
- Config read at import time, freezing values before overrides apply
- Same knob duplicated in two places that will drift
- Health/readiness checks not updated for a new hard dependency

## Severity

Grade with the shared severity rubric and elevation rule from the preloaded
`review-contract` skill. Dimension calibration:

- An irreversible or rollback-breaking migration, or a silent failure mode
  on a critical path, is the BLOCKER case.
- A missing timeout/retry budget, unreported error path, or uncorrelatable
  log on a path that ships to production is IMPORTANT.
- Log-level tuning, extra context fields, and metric naming are SUGGESTION.
