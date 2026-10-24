---
name: library-patterns
description: >-
  Use when writing or reviewing TypeScript that wraps a network service or
  authors a client SDK: client construction, per-request options, retry
  policy, idempotency keys, `APIError` hierarchies, zod-typed outputs,
  streaming with AbortController, cursor pagination, or telemetry hooks.
when_to_use: >-
  Trigger when designing an HTTP / SDK client, wrapping openai / anthropic /
  stripe SDKs, defining error classes, threading a `requestId`, streaming
  with cancellation, parsing output through Zod, or reviewing any module
  owning an outbound connection.
disable-model-invocation: false
user-invocable: true
allowed-tools: []
model: inherit
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/tsconfig*.json"
shell: bash
---

# TypeScript Library Patterns

This skill codifies the conventions that production-grade TypeScript client
libraries — [openai-node](https://github.com/openai/openai-node),
[anthropic-sdk-typescript](https://github.com/anthropics/anthropic-sdk-typescript),
[stripe-node](https://github.com/stripe/stripe-node), and
[zod](https://github.com/colinhacks/zod) — have converged on. It is project
policy for any TypeScript module that owns an outbound network connection or
wraps a third-party SDK. It specifies which shapes are accepted and which are
rejected when our code crosses a process boundary.

This skill cross-references rather than duplicates:

- Generic typing, branded types, discriminated unions, `Result` types →
  `typescript:typings`
- Public API documentation shape → `typescript:docstrings`

When this document says *"see `typescript:typings`"*, it means follow that
skill verbatim — do not restate its rules here.

## Non-negotiables

- A single typed client class owns the connection lifecycle. The client is
  constructed explicitly, threaded as a dependency, and (where applicable)
  closed deterministically. Module-globals that lazily construct clients are
  rejected.
- Timeouts are bounded. Unbounded fetch calls are rejected — every outbound
  request either uses the SDK's `timeout` option or wraps the call in
  `AbortSignal.timeout(ms)`.
- Retries are bounded, classified, and idempotency-keyed. The SDK
  `maxRetries` / `maxNetworkRetries` is set explicitly; retries on
  non-idempotent operations without an `idempotencyKey` are rejected.
- Errors form a single hierarchy. Caught errors are narrowed via
  `instanceof OpenAI.APIError` / `Anthropic.APIError` /
  `Stripe.errors.StripeError` — never via `err.code === 429` string checks
  or duck typing.
- Untrusted input is validated through Zod at the boundary; `z.infer<typeof
  Schema>` is the only acceptable way to derive its TypeScript type. See
  `typescript:typings` § *Zod at boundaries*.
- Streaming responses are consumed inside a single owning scope — either an
  awaited `for await (const event of stream)` loop, or a `stream.on(...)`
  registration tracked by an explicit cleanup. Leaving a stream listener
  unregistered after the parent scope returns is rejected.
- Cancellation flows through `AbortController` / `AbortSignal`. Cancelling
  by mutating a shared boolean is rejected — the SDK's `signal` option is
  the one true API.
- API keys are typed `Secret` (a branded `string`, see `typescript:typings`
  § *Branded types*) until the line that injects them into a header.
## Detail sections

The detail sections live in `references/` — load only what the task touches:

- [`construction-and-retries.md`](references/construction-and-retries.md) —
  client construction, per-request options, timeout granularity, retry
  policy with maxNetworkRetries
- [`errors-and-outputs.md`](references/errors-and-outputs.md) — `APIError`
  hierarchies, zod-typed structured outputs
- [`streaming-and-pagination.md`](references/streaming-and-pagination.md) —
  streaming with AbortController, cursor pagination, observability /
  requestId propagation, LLM tool-use parsing, anti-patterns

## References

Primary upstream sources for the patterns codified here:

- [openai-node](https://github.com/openai/openai-node) — `maxRetries`,
  `timeout`, `OpenAI.APIError` subclasses, `zodResponseFormat`,
  `zodTextFormat`, `chat.completions.parse`, `responses.parse`.
- [anthropic-sdk-typescript](https://github.com/anthropics/anthropic-sdk-typescript)
  — `MessageStream` event handlers, async iteration, `finalMessage`,
  `AbortController`, `betaZodTool`, `client.beta.messages.toolRunner`.
- [stripe-node](https://github.com/stripe/stripe-node) — `idempotencyKey`,
  `maxNetworkRetries`, `Stripe.errors.*` hierarchy, `apiVersion` pinning,
  `appInfo`, `telemetry`.
- [zod](https://github.com/colinhacks/zod) — `z.infer`, `z.input`,
  `z.output`, `z.discriminatedUnion`, `.brand<'...'>()`, `.parse` vs
  `.safeParse`, `.safeExtend` for refinement-preserving extension.
- [AWS Architecture Blog — exponential backoff and jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
  — canonical reference for the retry formula the SDKs implement.

Cross-references inside this repo:

- `typescript:typings` — branded types, discriminated unions, Zod at
  boundaries, `Result` shape, exhaustiveness checks.
- `typescript:docstrings` — TSDoc style for the client's public surface.
- `design-patterns:system` — retry, idempotency, circuit-breaker theory.

## Freshness

This skill is project policy distilled from the libraries above. Pinned
versions at authorship: `openai-node 6.1.0`, `@anthropic-ai/sdk` main,
`stripe-node 19.1.0`, `zod 4.0.1`.

When applying it to an unfamiliar API surface, version-specific behaviour,
a checker disagreement, or anything that may have moved since this was
written, verify against primary docs. Prefer Context7 MCP when available
(library IDs above resolve directly). If unavailable, restrict web search
to the upstream `github.com/<org>/<repo>/blob/main` and the official
documentation sites.
