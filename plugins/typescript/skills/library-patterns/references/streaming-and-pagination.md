# library-patterns — Streaming And Pagination

Detail sections of `omniagents-typescript:library-patterns`; the hub's Non-negotiables govern. Load on demand.

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
