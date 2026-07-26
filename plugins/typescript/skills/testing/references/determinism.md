# Determinism: timers, async, and ambient state

Everything that makes a test pass on one machine and fail on another: fake
timers, async assertion ordering, and the ambient state (env, globals,
filesystem, module singletons) a hermetic test must not touch. The doubles
vocabulary is in `references/doubles-and-boundaries.md`; the config keys
that restore stubs are in `references/gates-and-ci.md`.

## Timers and async

- **Fake timers are scoped to what the subject uses**:
  `vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] })`. The
  default `toFake` already excludes `nextTick` and `queueMicrotask` —
  opting into faking them can wedge `fetch`/undici body reads mid-test, so
  leave them out: fake the clock, not the event loop. Note the minimal
  list above also leaves `Date` un-faked — add `"Date"` to `toFake` when
  the test relies on `vi.setSystemTime`.
- **Injected clock first, `vi.setSystemTime` second.** An injected
  `now: () => Date` (or clock parameter) is the designed seam: the test
  passes a fixed function and no global gets patched. `vi.setSystemTime`
  is for subjects that read the global `Date` and cannot be reshaped — it
  requires `"Date"` in `toFake` and stays scoped to the file that needs it.
- **Attach rejection expectations before advancing time.** The canonical
  shape for "it retries, then gives up":

```typescript
it("gives up after three 5xx responses and reports the last status", async () => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  const fetchFn = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(new Response(null, { status: 500 }))
    .mockResolvedValueOnce(new Response(null, { status: 502 }))
    .mockResolvedValueOnce(new Response(null, { status: 503 }));

  const promise = fetchUser(fetchFn, "https://api.test", "u-1");
  // Attached now, so the eventual rejection is handled the moment it fires:
  const rejection = expect(promise).rejects.toThrowError(
    "user fetch failed after 3 attempts: status=503",
  );

  await vi.runAllTimersAsync();
  await rejection;

  expect(fetchFn).toHaveBeenCalledTimes(3);
  expect(vi.getTimerCount()).toBe(0);
});
```

- **Kill schedule mutants with boundary advances.** For backoff/debounce
  contracts, advance to one tick before the deadline and assert nothing
  fired, then one tick more and assert it did — `runAllTimersAsync` alone
  passes under a fixed-delay mutant.
- **Assert nothing leaks past the test**: `expect(vi.getTimerCount()).
  toBe(0)` after the final settle; a timer that outlives its test fails a
  different test later.
- **Genuinely-async conditions use `vi.waitFor` with a deadline** (or
  Testing Library's `findBy*`), never a real `setTimeout` pause. A raw
  sleep is the canonical flake: green on your machine, red on loaded CI.

## Hermeticity and ambient state

A hermetic test reads and writes nothing outside its own scope — ambient state
is the undeclared axis that makes a test pass locally and fail in CI.

- **Environment via `vi.stubEnv`, restored by config.** With `unstubEnvs:
  true` set, stub exactly the vars a test needs; reading the runner's ambient
  `process.env` is a CI failure on a clean box. Stub to `undefined` to prove
  the default branch, too.
- **Globals via `vi.stubGlobal`, never raw assignment.** Patch `fetch`,
  `crypto`, `Date`, or `window` properties through `vi.stubGlobal` so
  `unstubGlobals: true` restores them; a hand-assigned `globalThis.fetch = …`
  leaks into the next test.
- **Filesystem into an OS temp dir, never the repo.** Disk-touching tests use
  `fs.mkdtemp` under `os.tmpdir()` and clean up in teardown; a checked-in path
  the test also writes couples tests and leaks across pool workers.
- **Module singletons reset at a seam you own.** Module-level caches,
  registries, and clients retain state between tests in a worker. Export a
  `reset()` and call it in teardown rather than reaching for
  `vi.resetModules()` — reloading the graph desynchronizes already-imported
  references and is a blunt instrument.
- **`vi.hoisted` for values a `vi.mock` factory closes over.** `vi.mock` is
  hoisted above the imports, so a factory referencing a top-level `const`
  throws "cannot access before initialization." Declare shared spies with
  `const { spy } = vi.hoisted(() => ({ spy: vi.fn() }))`. This is the most
  common Vitest mocking footgun in a large suite.

## Sources

- [Software Engineering at Google, ch. 11 "Testing Overview"](https://abseil.io/resources/swe-book/html/ch11.html)
- [Just Say No to More End-to-End Tests (Google Testing Blog)](https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html)
- [xUnit Test Patterns: Erratic Test (Gerard Meszaros)](http://xunitpatterns.com/Erratic%20Test.html)
- [Vitest: fakeTimers.toFake config](https://vitest.dev/config/#faketimers-tofake)
- [Vitest 4 migration guide](https://vitest.dev/guide/migration.html)

Freshness: verified 2026-07-26 — Vitest 4.1.10 (default `toFake` excludes
`nextTick` and `queueMicrotask`; `toFake`/`toNotFake` mutually exclusive;
`nextTick` unsupported under `--pool=forks`).
