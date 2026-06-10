---
name: library-patterns
description: >-
  Use when writing or reviewing TypeScript that wraps a network service or
  authors a client SDK: client construction, per-request options, retry
  policy with maxNetworkRetries, idempotency keys, `APIError` hierarchies,
  structured outputs via `zodResponseFormat` / `zodTextFormat`, streaming
  with AbortController, cursor pagination, or telemetry hooks.
when_to_use: >-
  Trigger when designing an HTTP/SDK client, wrapping openai / anthropic /
  stripe SDKs, defining error classes, building Zod-typed config, threading
  a `requestId` through logs, implementing streaming with cancellation,
  parsing model output through Zod, or reviewing any module owning an
  outbound connection.
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

## Client Construction

The client is a typed object holding (a) credentials, (b) transport config,
(c) retry/timeout policy, and (d) telemetry tags. Build it once at process
startup; pass it through.

```typescript
import OpenAI from 'openai';
import { z } from 'zod';

const ClientConfigSchema = z.object({
  apiKey: z.string().min(1),
  baseURL: z.url().default('https://api.openai.com/v1'),
  maxRetries: z.number().int().min(0).max(5).default(2),
  timeoutMs: z.number().int().positive().default(60_000),
  appInfo: z
    .object({
      name: z.string(),
      version: z.string(),
      url: z.url().optional(),
    })
    .optional(),
});

type ClientConfig = z.infer<typeof ClientConfigSchema>;

export function makeClient(raw: unknown): OpenAI {
  const config = ClientConfigSchema.parse(raw);
  return new OpenAI({
    apiKey: config.apiKey,
    baseURL: config.baseURL,
    maxRetries: config.maxRetries,
    timeout: config.timeoutMs,
    defaultHeaders: config.appInfo
      ? {
          'User-Agent': `${config.appInfo.name}/${config.appInfo.version}`,
        }
      : undefined,
  });
}
```

Notes:

- The config is parsed once at startup. Storing the raw `unknown` and
  re-parsing per request is wasteful and lets invalid config survive to
  first use.
- `z.infer<typeof ClientConfigSchema>` is the only way to derive the TS
  type — never restate the shape as a `type ClientConfig = { ... }`.
- Stripe's `appInfo: { name, version, url }` is the canonical
  client-identification shape; OpenAI uses a `User-Agent` header directly.
  Pick whichever the SDK supports.

## Per-Request Overrides

Every SDK in scope supports a trailing `options` object that overrides
per-call. **Use it; do not fork the client.**

```typescript
// OpenAI — second-arg request options
await client.chat.completions.create(
  { model: 'gpt-4o', messages: [...] },
  { maxRetries: 0, timeout: 5_000 },
);

// Anthropic — same shape
await client.messages.create(
  { model: 'claude-sonnet-4-5-20250929', max_tokens: 128, messages: [...] },
  { maxRetries: 0, timeout: 5_000, signal: ctrl.signal },
);

// Stripe — second-arg options dict
await stripe.paymentIntents.create(
  { amount: 2000, currency: 'usd' },
  { idempotencyKey: id, maxNetworkRetries: 3, timeout: 5_000 },
);
```

Constructing a second `new OpenAI({...})` solely to set a different timeout
is rejected: it duplicates connection state and breaks pool sharing.

## Timeout Granularity

TypeScript SDKs default to a single `timeout` value (milliseconds). The
granular knobs that exist in `httpx` are not available; the discipline is
instead to bound *every* outbound call and to layer `AbortSignal.timeout(ms)`
where the SDK call itself wraps a longer logical operation.

```typescript
// SDK call — already bounded by client `timeout` / per-request `timeout`
await client.chat.completions.create({ ... });

// Custom fetch — wrap with AbortSignal.timeout
const response = await fetch(url, {
  signal: AbortSignal.timeout(10_000),
});

// Multi-step orchestration — single budget for the whole operation
async function fetchEnrichedItem(id: string): Promise<EnrichedItem> {
  const signal = AbortSignal.timeout(30_000);
  const base = await api.items.retrieve(id, { signal });
  const meta = await api.metadata.retrieve(base.metaId, { signal });
  return { ...base, meta };
}
```

`AbortSignal.timeout(ms)` is the right primitive — it integrates with
`fetch`, all four SDKs in scope, and any well-behaved async API. Do not
roll your own `setTimeout(() => abort(), ms)` unless you also need
`AbortSignal.any([...])` semantics.

## Retry Policy

Retries are bounded, exponential, and classified. The SDKs handle backoff
themselves when you set `maxRetries` / `maxNetworkRetries`; do not stack a
hand-rolled retry loop on top.

```typescript
const client = new OpenAI({ maxRetries: 2 }); // default

// Disable for a single non-idempotent call
await client.chat.completions.create(
  { ... },
  { maxRetries: 0 },
);

// Stripe — auto-generates idempotency keys when maxNetworkRetries > 0
const stripe = new Stripe(secret, { maxNetworkRetries: 2 });

// Per-mutation explicit key for safety
import { randomUUID } from 'node:crypto';

const idempotencyKey = randomUUID();
await stripe.paymentIntents.create(
  { amount: 2000, currency: 'usd' },
  { idempotencyKey },
);
```

Rules:

- **Cap retries explicitly.** SDK defaults (2 retries for OpenAI / Stripe,
  2 for Anthropic) are the right neighbourhood; do not raise without a
  reason.
- **Classification is the SDK's job.** All four SDKs in scope retry on
  network errors and 408 / 409 / 429 / 5xx. Do not paper over a 400 with a
  hand-rolled loop — a 400 means the request is wrong, not transiently
  failed.
- **Mutations need `idempotencyKey`.** Stripe auto-generates one when
  retries are enabled, but for cross-process retries (a worker queue, a
  webhook redelivery), pass an explicit key derived from the logical
  operation. See `design-patterns:system` § *Idempotency*.

## Error Hierarchy

Each SDK has a single base class; narrow with `instanceof`, never with
`err.status === 429` checks.

```typescript
import OpenAI from 'openai';

try {
  await client.chat.completions.create({ ... });
} catch (err) {
  if (err instanceof OpenAI.APIError) {
    logger.warn('openai.api_error', {
      status: err.status,        // HTTP status code
      name: err.name,             // e.g. 'RateLimitError'
      requestId: err.request_id,
      headers: err.headers,
      message: err.message,
    });
  }

  if (err instanceof OpenAI.RateLimitError) {
    // 429 — read `retry-after` header before re-issuing
  }
  if (err instanceof OpenAI.AuthenticationError) {
    // 401 — fail loud, do not retry
  }
  if (err instanceof OpenAI.BadRequestError) {
    // 400 — caller bug, surface to the user
  }
  throw err;
}
```

Anthropic and Stripe expose the same shape under different namespaces:

```typescript
import Anthropic from '@anthropic-ai/sdk';
import Stripe from 'stripe';

err instanceof Anthropic.APIError;      // base
err instanceof Anthropic.RateLimitError; // 429
err instanceof Anthropic.APIConnectionError; // network

err instanceof Stripe.errors.StripeError;     // base
err instanceof Stripe.errors.StripeCardError; // domain-specific
err instanceof Stripe.errors.StripeRateLimitError;
```

When wrapping multiple upstream services in one client, define a project
base error that **wraps** the upstream error rather than mimicking its
shape — preserving the original via a `cause` property keeps stack traces
honest:

```typescript
export class ServiceError extends Error {
  constructor(
    message: string,
    public readonly status: number | undefined,
    public readonly requestId: string | undefined,
    options?: { cause?: unknown },
  ) {
    super(message, options);
    this.name = 'ServiceError';
  }
}
```

Use `extends Error` with `options.cause` (ES2022+); do not roll your own
`originalError` field.

## Structured Outputs

When an upstream API supports typed output, route it through Zod via the
SDK's helper — never `JSON.parse` + manual validation.

```typescript
import OpenAI from 'openai';
import { zodResponseFormat } from 'openai/helpers/zod';
import { z } from 'zod';

const Step = z.object({
  explanation: z.string(),
  output: z.string(),
});

const MathResponse = z.object({
  steps: z.array(Step),
  final_answer: z.string(),
});

type MathResponse = z.infer<typeof MathResponse>;

const client = new OpenAI();
const completion = await client.chat.completions.parse({
  model: 'gpt-4o-2024-08-06',
  messages: [
    { role: 'system', content: 'You are a helpful math tutor.' },
    { role: 'user', content: 'solve 8x + 31 = 2' },
  ],
  response_format: zodResponseFormat(MathResponse, 'math_response'),
});

const message = completion.choices[0]?.message;
if (message?.parsed) {
  // message.parsed is fully typed as MathResponse
  for (const step of message.parsed.steps) { ... }
} else if (message?.refusal) {
  throw new ServiceError(`Model refused: ${message.refusal}`, undefined, undefined);
}
```

For the newer Responses API, use `zodTextFormat`:

```typescript
import { zodTextFormat } from 'openai/helpers/zod';

const rsp = await client.responses.parse({
  input: 'solve 8x + 31 = 2',
  model: 'gpt-4o-2024-08-06',
  text: { format: zodTextFormat(MathResponse, 'math_response') },
});

// rsp.output_parsed is typed as MathResponse | null
```

Rules:

- **Always check the refusal branch.** `message.parsed === undefined` does
  not imply a transport failure — the model refused.
- **Schema is the source of truth.** `type MathResponse = z.infer<typeof
  MathResponse>` is the only way to derive the type; never restate.
- **Discriminated unions parse cleanly.** Use `z.discriminatedUnion('kind',
  [...])` instead of `z.union([...])` when one field tags the variant —
  parser is O(1) instead of O(n) and the error message is precise. See
  `typescript:typings` § *Discriminated unions*.

## Streaming

Anthropic's `MessageStream` is the canonical shape: event-driven `.on()`
hooks, async iteration, and accumulators all on the same object. Pick one
consumption style per call site — don't mix.

```typescript
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic();

const stream = client.messages.stream({
  model: 'claude-sonnet-4-5-20250929',
  max_tokens: 1024,
  messages: [{ role: 'user', content: 'List the planets in order.' }],
});

// (A) Event-driven — register before reading
stream
  .on('text', (delta) => process.stdout.write(delta))
  .on('message', (msg) => logger.info('done', { usage: msg.usage }))
  .on('error', (err) => logger.error('stream.error', { err }));

// (B) Async iteration over typed events
for await (const event of stream) {
  if (
    event.type === 'content_block_delta'
    && event.delta.type === 'text_delta'
  ) {
    process.stdout.write(event.delta.text);
  }
}

// (C) Final-accumulator
const finalMessage = await stream.finalMessage();
const text = await stream.finalText();
```

Cancellation uses `AbortController`, not a side-channel flag:

```typescript
const ctrl = new AbortController();
setTimeout(() => ctrl.abort(), 2_000);

const stream = client.messages.stream(
  { model: 'claude-sonnet-4-5-20250929', max_tokens: 1000, messages: [...] },
  { signal: ctrl.signal },
);
```

Breaking from the `for await` loop also cleanly closes the stream:

```typescript
for await (const event of stream) {
  if (event.type === 'message_stop') break; // closes the connection
}
```

Rules:

- **Pick one consumption style per call.** Mixing `.on('text')` and `for
  await` consumes the same events twice and corrupts the accumulator.
- **Always cancel with `AbortController` / `AbortSignal`.** It is the
  language-level cancellation primitive; everything else is a workaround.
- **Treat the stream as one-shot.** Don't pass a stream out of the
  function that created it — its lifetime is tied to its consumer.

## Pagination

Use the SDK's auto-paging iterator. Each of openai-node / anthropic-sdk /
stripe-node implements `Symbol.asyncIterator` on list methods.

```typescript
// OpenAI — auto-pages
for await (const file of client.files.list()) {
  // file is fully typed
}

// Stripe — auto-pages; .autoPagingEach for callbacks
for await (const customer of stripe.customers.list({ limit: 100 })) {
  ...
}
```

Rules:

- **Auto-pagination, not manual cursor handling.** All three SDKs in scope
  expose `for await` — use it.
- **`limit` is a hint, not a cap.** The server may return fewer items;
  the iterator handles `has_more` for you.
- **Caller decides materialization.** A caller that wants the full list
  can `await Array.fromAsync(...)`. The wrapper does not eager-load.

## Observability

Three guarantees:

1. **Every request_id propagates.** Surface it via structured logging fields
   on every log line that mentions the upstream call.
2. **Errors are logged at the boundary that decides whether to continue,**
   never twice on the way up the stack.
3. **Secrets are redacted at the type level** — a `Secret` brand on the
   string makes it impossible to interpolate accidentally — and at runtime
   via the logger's redaction config.

```typescript
import { z } from 'zod';

declare const __brand: unique symbol;
export type Secret = string & { readonly [__brand]: 'Secret' };

export const SecretSchema = z.string().min(1).brand<'Secret'>();

function authHeader(token: Secret): Record<string, string> {
  // `token` is opaque outside this function; not interpolable in template strings
  return { Authorization: `Bearer ${token}` };
}
```

See `typescript:typings` § *Branded types* for the broader pattern.

For HTTP-level observability, the SDKs expose `defaultHeaders`,
`fetchOptions`, and (Stripe) `telemetry: true`. Wire them into your tracer:

```typescript
const stripe = new Stripe(secret, {
  telemetry: true,
  appInfo: {
    name: 'omniagents-billing',
    version: PACKAGE_VERSION,
    url: 'https://internal.example.com/billing',
  },
});
```

## Tool Use (LLM-specific)

Anthropic's `betaZodTool` is the canonical shape for typed tool
definitions. Combined with `toolRunner`, it removes the manual tool-call
loop entirely.

```typescript
import Anthropic from '@anthropic-ai/sdk';
import { betaZodTool } from '@anthropic-ai/sdk/helpers/beta/zod';
import { z } from 'zod';

const weatherTool = betaZodTool({
  name: 'get_weather',
  description: 'Get the current weather in a city.',
  inputSchema: z.object({
    location: z.string().describe('City and state, e.g. San Francisco, CA'),
    unit: z.enum(['celsius', 'fahrenheit']).default('fahrenheit'),
  }),
  run: async (input) => `The weather in ${input.location} is 22°C / 72°F`,
});

const finalMessage = await client.beta.messages.toolRunner({
  model: 'claude-sonnet-4-5-20250929',
  max_tokens: 1024,
  max_iterations: 10, // guard against infinite loops
  messages: [{ role: 'user', content: '...' }],
  tools: [weatherTool],
});
```

Rules:

- **Always bound `max_iterations`.** Without it, a misbehaving model can
  loop on tool calls indefinitely.
- **Tool input is Zod-validated end-to-end.** `input` inside `run` is typed
  as `z.infer<typeof inputSchema>` — no manual `JSON.parse` or casting.
- **Tool errors throw `ToolError`.** Caught by the runner and surfaced to
  the model as a tool result, not as a stream failure.

For OpenAI function tools, use `zodFunction({ name, description, parameters
})` from `openai/helpers/zod` — never hand-roll a JSON Schema for tool
parameters when Zod can describe them.

## Anti-Patterns

- **Module-globals that lazily construct clients.** Hides the lifecycle,
  shares state across tests, prevents typed dependency injection.
- **`new OpenAI({...})` per request.** Forks the connection pool; breaks
  retry / rate-limit telemetry. Use per-request `options` instead.
- **Hand-rolled retry loops on top of SDK retries.** Doubles the effective
  retry count; combined with `maxNetworkRetries: 2`, a wrapping
  `for (let i = 0; i < 3; i++)` produces 6 attempts.
- **`err.status === 429` checks instead of `instanceof RateLimitError`.**
  Loses type safety, breaks when the SDK adds new error subclasses.
- **`type Foo = { ... }` restating a Zod schema's shape.** Use
  `z.infer<typeof FooSchema>`; never duplicate.
- **`JSON.parse(content)` after a structured-output call.** The SDK already
  parsed it. Use `message.parsed` / `output_parsed`.
- **`fetch(url)` without a signal.** Every outbound `fetch` must have a
  timeout — `AbortSignal.timeout(ms)` is the answer.
- **Cancellation via a shared boolean.** Use `AbortController`; it is the
  one true API and propagates through every SDK in scope.
- **`stream.on('text', ...)` without `stream.on('error', ...)`.** A stream
  error then becomes an unhandled promise rejection.
- **Re-throwing as `Error` and losing `cause`.** `throw new ServiceError(msg,
  status, requestId, { cause: err })` — preserve the chain.

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
