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

# Operability Review — Hunt Protocols

Judge whether the changed code can be **operated**: observed when healthy,
diagnosed when broken, rolled out safely, rolled back cheaply. The framing
question for every hunt: *it is 3am and this code is misbehaving — what does
the on-call see, and what can they do?* This dimension usually dispatches
only when the diff touches runtime source, config, infra, or migrations.

## Hunts

Execute every hunt whose `When` matches; skip the rest. Exemplars are
calibration anchors, never templates — do not copy their wording into
reports.

### Hunt: 3am Page Simulation

- **When**: a new failure branch, new external call, or new background work
  in runtime code.
- **Protocol**:
    1. Pick the changed path's most likely failure: downstream 500,
       timeout, malformed payload.
    2. Narrate the on-call story: what log/metric/span fires, at what
       level, carrying which identifiers (request id, job id, tenant)?
    3. Grep the handler for the signal — then Read the middleware,
       decorators, and base classes for **inherited** coverage before
       flagging.
    4. Ask whether the on-call can find *this* request from the line, or
       just "Error occurred".
- **Evidence bar**: the failure branch plus the absent or uncorrelatable
  signal, after checking inherited coverage.
- **Falsifiers**: a middleware or framework hook logs it with context
  (point at it); the platform captures it (crash loops, error trackers);
  the path is documented best-effort and counted elsewhere.
- **Exemplar**: IMPORTANT 83 — "new `except PublishError: return False` —
  no log, no counter, and the caller treats False as 'queued'; the first
  symptom is customers missing data days later." / **Noise twin**: a
  handler with no explicit log whose blueprint-level error handler logs
  with request context — inherited.

### Hunt: Timeout Budget Walk

- **When**: a new outbound call — HTTP, DB, queue, RPC.
- **Protocol**:
    1. Find the call's **effective** timeout: inline argument, client
       construction (Read it), or library default — often infinite.
    2. Walk up the callers to the entrypoint's budget: request deadline,
       job timeout, health-check interval.
    3. Sum the worst case along the path — nested timeouts (and retries)
       must fit inside the outer budget.
- **Evidence bar**: the call, its effective timeout or proven absence, and
  the budget it can blow.
- **Falsifiers**: the shared client sets it at construction (read the
  constructor, not just the call site); an infra-level bound exists and
  the team treats it as the contract.
- **Exemplar**: IMPORTANT 82 — "`urllib.request.urlopen(feed_url)` with no
  timeout on the request path — the default blocks forever; one slow
  vendor wedges every worker." / **Noise twin**: a call with no inline
  timeout through a client constructed once with `timeout=5`.

### Hunt: Retry Storm Trace

- **When**: new retry logic — a loop, a decorator, a library config.
- **Protocol**:
    1. Trace ten minutes of total downstream outage: is there a cap,
       backoff, jitter — or does every instance hammer in sync?
    2. Idempotency: is the retried operation safe to repeat, or keyed? A
       retried unkeyed write duplicates effects during recovery.
    3. Budget interaction: attempts × timeout must still fit the caller's
       deadline.
- **Evidence bar**: the retry config plus the storm or duplication
  scenario it admits.
- **Falsifiers**: the config caps attempts with exponential backoff and
  jitter (read it); the operation is idempotent by key.
- **Exemplar**: IMPORTANT 84 — "`while not ok: send()` — no cap, no
  backoff, and `send` is an unkeyed write: an outage turns every worker
  into a tight-loop hammer that double-sends on recovery." / **Noise
  twin**: three attempts with exponential jitter on an idempotent GET.

### Hunt: Mixed-Version Deploy Trace

- **When**: the diff changes a wire format, queue/event payload, cache
  entry shape, cross-service API, or DB schema that running code reads.
- **Protocol**:
    1. Set the scene every deploy creates: old and new instances running
       **concurrently**.
    2. Trace the four arrows: old-writes→new-reads, new-writes→old-reads,
       and both versions against the changed schema.
    3. Name who crashes, who misparses, who silently drops — then check
       for expand/contract staging, tolerant readers, versioned payloads.
- **Evidence bar**: the incompatible arrow, named — which instance, which
  payload, what failure.
- **Falsifiers**: the change is additive with defaults old readers
  ignore; deploy ordering is mechanically enforced, not hoped; payloads
  are versioned and both handlers exist.
- **Exemplar**: BLOCKER 87 — "queue payload field `kind` becomes an int
  enum; during rollout, old consumers receive int payloads from new
  producers and raise on parse — messages dead-letter for the whole
  deploy window." / **Noise twin**: a new optional field with a default
  that old consumers never read.

### Hunt: Rollback Rehearsal

- **When**: a migration, an irreversible data change, or a stateful
  behavior change.
- **Protocol**:
    1. Narrate the rollback at the worst moment (mid-deploy, an hour
       after): does a down path exist, and is it plausible?
    2. Run yesterday's code against today's database in your head — does
       it still work?
    3. Backfills: resumable from a checkpoint, or restart-from-zero?
       Destructive steps (drop, rename) staged behind a window in which
       nothing references the old shape?
- **Evidence bar**: the rollback step that fails or does not exist,
  named.
- **Falsifiers**: expand/contract staging — the destructive step lands in
  a later migration after code stops referencing; a written, plausible
  down migration; the data is scratch and droppable by design.
- **Exemplar**: BLOCKER 86 — "migration adds a NOT NULL column without a
  default in the same deploy as its writer — rolling back the code leaves
  inserts crashing, and there is no down migration." / **Noise twin**:
  dropping a column two releases after its last reader was removed.

### Hunt: Config Drift

- **When**: a new config key, env var, flag, or secret reference.
- **Protocol**:
    1. Check a default exists and is sane per environment — or that
       startup **fails loudly** when the key is missing. A silent
       fallback to the wrong default is the worst case.
    2. Grep the key across env files and manifests: defined everywhere it
       is read, under the same name?
    3. Secrets go through the established secret path; config read at
       import time freezes values before overrides apply; the same knob
       in two places will drift.
- **Evidence bar**: the key plus the environment or path where it is
  missing, silently defaulted, or duplicated.
- **Falsifiers**: the settings layer validates at startup (point at it);
  the default is explicit and documented; the duplicate is generated from
  one source.
- **Exemplar**: IMPORTANT 80 — "`os.getenv('PAYMENT_MODE', 'live')` — a
  missing var silently selects live mode in staging; fail loud or default
  safe." / **Noise twin**: a new key on a settings model that raises at
  boot when absent or malformed.

### Hunt: Shutdown Drain

- **When**: new background work, a consumer loop, or long-running request
  handling.
- **Protocol**:
    1. Trace SIGTERM arriving mid-operation: is in-flight work finished,
       checkpointed, or dropped?
    2. Ack discipline: acking before processing drops work on kill;
       acking after risks duplicates — which one is this, and is that
       deliberate?
    3. Does the worker stop pulling new work during the grace period, and
       does the grace period fit the longest task?
- **Evidence bar**: the kill moment plus what is lost or duplicated.
- **Falsifiers**: the framework drains by default (read the runner's
  lifecycle hooks); the handler is idempotent under at-least-once
  delivery and redelivery is the documented recovery.
- **Exemplar**: IMPORTANT 81 — "the consumer acks before processing; a
  SIGTERM mid-process loses the message permanently — ack after, or
  checkpoint." / **Noise twin**: an idempotent keyed handler under
  at-least-once delivery, with redelivery as the stated recovery path.

## Severity Anchors

Grade with the contract's Severity Rubric and elevation rule. In this
dimension:

- **BLOCKER**: an irreversible or rollback-breaking migration, a
  mixed-version crash lasting the rollout window, or a silent failure mode
  on a critical path.
- **IMPORTANT**: missing timeout or retry budget, an unreported error
  path, uncorrelatable logs, or a dangerous config default on a path that
  ships.
- **SUGGESTION**: log-level tuning, extra context fields, metric naming.

## Recall Sweep

After the hunts, sweep the diff once against these. Flag only what passes
the contract's Taste Test:

- Log-level misuse: expected conditions at ERROR (alert fatigue), real
  failures at DEBUG (invisible).
- PII, secrets, or full payloads in logs (exploit-grade exposure belongs
  to the security dimension).
- A new hard dependency absent from health/readiness checks.
- A new failure mode with no declared fail-open/fail-closed decision.
- A new external call outside the existing tracing/metrics middleware.
- A large-blast behavior change shipped without a flag or staged path.
- Resource acquisition without a bound, or without release on the error
  path.
