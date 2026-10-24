# library-patterns — Errors And Outputs

Detail sections of `omniagents-typescript:library-patterns`; the hub's Non-negotiables govern. Load on demand.

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
