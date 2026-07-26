# Nondeterministic subjects: harness tests vs evals (G3)

Scope: LLM-backed and other nondeterministic subjects — separating the
harness code that is ordinary G1 testing in disguise from the judged
remainder, which runs as scheduled evals that never block a merge.

Begin with the subtraction, because most of what gets called "testing an LLM
app" is already covered by this skill and belongs on G1.

- **The harness is ordinary code and gets ordinary tests.** Prompt assembly,
  tool-schema generation, dispatch, retry and backoff, response parsing,
  structured-output validation, and streaming-chunk accumulation are all
  deterministic. The OpenAI and Anthropic SDKs are `httpx`-based, so the
  `MockTransport` / respx patterns in `references/doubles-and-boundaries.md`
  fake them with no live call, no spend, and no new vocabulary. Three
  mutants worth naming: a `ValidationError` retry path that has never once
  executed until the first malformed production response; a tool schema
  nobody asserted, so a parameter rename breaks the model-facing contract
  while every test stays green; and chunk-boundary handling that works
  whenever chunking happens to align and corrupts output when it does not.
- **Only output *quality* scoring is genuinely new — and it cannot block a
  merge.** Hallucination, faithfulness, relevance, and tone are scored by a
  judge model carrying documented position, verbosity, and self-enhancement
  biases; identical inputs legitimately produce different scores. deepeval
  runs these inside pytest (`assert_test`, dataset parametrization), which is
  precisely the trap: it *looks* like a unit test, so teams apply
  green-to-merge to a noisy instrument and then mute it when it flickers.
- **This does not contradict the no-retry rule — it is why the tiers
  exist.** On G1 a flake is a defect in the test or the code and rerunning is
  banned. On G3 the variance belongs to the instrument, so the answer is
  statistical rather than a rerun: score a sample, report mean and interval,
  gate on a band, and calibrate the judge against human labels before
  trusting it. Treating one greedy-decoded score as a boolean is the actual
  error.
- **Run evals path-gated or scheduled, against a versioned golden set.**
  Trigger on changes to prompts, models, or tool definitions rather than
  every commit; keep the dataset in version control like a migration and
  refresh it from production traces. Watch three drifts: prompt drift, model
  drift (the vendor moves the model behind a pinned name), and dataset drift
  (the golden set stops resembling real traffic).
- **A muted eval is a silent quality regression, not CI noise.** If a judged
  check is too noisy to read, fix the instrument — more samples, a coarser
  band, binary pass/fail instead of a Likert scale — or delete it. Leaving it
  red and ignored is the failure mode this tier exists to prevent.

## Sources

- [Software Engineering at Google, ch. 11 "Testing Overview"](https://abseil.io/resources/swe-book/html/ch11.html)
- [Software Engineering at Google, ch. 14 "Larger Testing"](https://abseil.io/resources/swe-book/html/ch14.html)
- [deepeval](https://deepeval.com/docs)

Freshness: pytest 9.1.1 verified 2026-07-26 — the harness-test patterns
above run on it. deepeval was not part of the 2026-07-26 version audit;
check its docs before wiring it to anything.
