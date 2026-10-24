# library-patterns — Construction And Retries

Detail sections of `omniagents-typescript:library-patterns`; the hub's Non-negotiables govern. Load on demand.

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
