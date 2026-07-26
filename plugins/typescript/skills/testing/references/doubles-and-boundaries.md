# Test doubles and boundary control

Which double to reach for, where the mocking boundary sits, and why
dependency injection and MSW beat `vi.mock`. Timer and clock substitution
is covered in `references/determinism.md`; the config that auto-restores
mocks in `references/gates-and-ci.md`.

Name the double you are reaching for — the vocabulary disciplines the choice.
A **stub** returns canned answers; a **fake** is a working lightweight
implementation (in-memory repository, an MSW handler); a **spy** records calls
for later assertion; a **mock** is a spy with built-in expectations; a **dummy**
only fills a parameter slot. Prefer fakes and stubs; reserve mocks for the thin
interaction contracts where the call *is* the behavior. Reaching for a mock
where a fake would serve is how a suite ends up asserting on traffic instead of
outcomes.

- **Dependency injection beats module mocking.** When the subject accepts
  its collaborators (`fetchFn: typeof fetch`, a repository interface, a
  clock), tests pass typed fakes and `vi.mock` never enters the file. Do
  not use `vi.mock` when a parameter would do — module mocking is the
  patcher of last resort for boundaries you cannot inject.
- **Mock the network, not your HTTP client wrapper.** MSW intercepts at the
  request layer, so the subject's real serialization, URL building, and
  error mapping all execute. Mocking your own `apiClient` module skips the
  exact glue where bugs live. Handlers are defined once and overridden
  per-test:

```typescript
// src/testing/server.ts — the single home for request handlers
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { userFixture } from "./fixtures.js";

export const server = setupServer(
  http.get("https://api.example.test/users/:id", () =>
    HttpResponse.json(userFixture),
  ),
);

// vitest.setup.ts
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// In a test: override for the failure path
server.use(
  http.get("https://api.example.test/users/:id", () =>
    HttpResponse.json(null, { status: 503 }),
  ),
);
```

- **When `vi.mock` is unavoidable, it is typed and complete.** Use the
  factory form with `importOriginal` to keep unmocked exports real, and
  `vi.mocked()` to get typed access. Mirror the real module's surface —
  a partial hand-rolled mock hides structural assumptions and breaks
  silently when the subject reads a field you omitted.
- **Platform objects are constructed, not shape-faked.** A real
  `new Response(body, { status })` / `Response.json(payload)` keeps `.ok`,
  `.status`, and body semantics honest; a hand-rolled `{ ok: false }`
  object drifts from the fetch contract the day the subject reads a header.
- **Typed function mocks**: `vi.fn<typeof fetch>()`,
  `vi.fn<(name: string) => void>()` — an untyped `vi.fn()` lets the test
  feed the subject arguments production never could.
- **Only mock types you own.** Wrap the vendor SDK in a thin adapter that
  speaks your domain types; tests fake the adapter — an interface you can
  change — never the vendor's method signatures, which you cannot
  stabilize. One integration test verifies the adapter against the real
  service or its official emulator (`references/integration.md`).
- **Never mock the subject's own internals.** Spying on a private method of
  the class under test means the test exercises the spy. Extract the seam.

## Sources

- [Test Double (Martin Fowler)](https://martinfowler.com/bliki/TestDouble.html)
- [xUnit Test Patterns: Test Double (Gerard Meszaros)](http://xunitpatterns.com/Test%20Double.html)
- [Software Engineering at Google, ch. 13 "Test Doubles"](https://abseil.io/resources/swe-book/html/ch13.html)
- [When to Mock (Vladimir Khorikov)](https://enterprisecraftsmanship.com/posts/when-to-mock/)
- [The Merits of Mocking (Kent C. Dodds)](https://kentcdodds.com/blog/the-merits-of-mocking)
- [Mock Roles, not Objects (Freeman, Pryce, Mackinnon, Walnes)](http://jmock.org/oopsla2004.pdf)
- [MSW: Node.js integration](https://mswjs.io/docs/integrations/node)
- [MSW: setupServer listen options](https://mswjs.io/docs/api/setup-server/listen)

Freshness: verified 2026-07-26 — MSW 2.15.0 (`http.get` / `HttpResponse`,
`onUnhandledRequest` options current), Vitest 4.1.10 (`vi.mock` factory +
`importOriginal`, `vi.mocked` current).
