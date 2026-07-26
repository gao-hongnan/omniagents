# Gates, CI, and pytest configuration

Scope: what runs where and under what verdict — coverage and mutation,
the G2 resource gates (memory, benchmarks), and the canonical
`pyproject.toml` the whole suite runs under. The tier definitions live in
the hub `SKILL.md`; the G3 eval tier in `references/evals.md`.

## Coverage and CI gates

- **Branch coverage on `src/`, with a ratcheted `fail_under`.** Coverage is
  a floor that catches untested modules, not a target — 100% line coverage
  with outcome-free assertions proves nothing (see the mutant framing in the
  hub's non-negotiables). Raise the floor as real coverage grows; never
  lower it to merge.
- **Mutation testing (mutmut) periodically on core logic** — it is the
  automated version of "name the mutant each test kills," and it grades the
  assertions coverage cannot.
- **CI runs the full strict stack**: type checkers over `tests/`, ruff over
  `tests/`, `pytest -n auto` with randomized order, warnings-as-errors, and
  the integration job gated on the `integration` marker. The seed printed
  by pytest-randomly goes in the failure report — an order-dependent
  failure without its seed is unreproducible. Same caveat as pytest-timeout:
  pytest-xdist 3.8.0 publishes no Python 3.14 classifier — verify it against
  the pinned interpreter before relying on `-n auto` in a 3.14+ project
  (checked 2026-07-26).

## Resource gates (G2)

Coverage and mutation grade *correctness*. Nothing above grades what a change
costs to run — and a refactor three call-layers down that turns a generator
into `list(...)` emits byte-identical output, so coverage, mutmut, and
hypothesis all stay green while memory goes O(1) → O(n). These gates live in
their own job because they are slower and, for timing, noisier than G1 admits.

- **Memory: assert a ceiling, not a number.** pytest-memray's
  `@pytest.mark.limit_memory("24 MB")` fails a test that allocates too much;
  `limit_leaks` fails on allocations still live at exit. Both see native
  growth (numpy, a Rust extension) that pure-Python instrumentation misses.
  Express the limit as a generous ceiling — a tight byte threshold breaks on
  the next allocator change, on musl vs glibc, or on arm64 vs x86_64. Linux
  and macOS only: **no Windows wheels**, so a mixed-platform matrix runs this
  on one leg and a Windows-inclusive project falls back to a `tracemalloc`
  snapshot delta. Pair `limit_leaks` with the cache-reset discipline in
  `references/determinism.md`, or a legitimately warmed pool reads as a leak.
- **Benchmarks: know whether your harness is actually running.**
  `pytest-benchmark` silently disables itself under pytest-xdist — the
  `-n auto` this skill mandates for G1 auto-triggers `--benchmark-disable`.
  A team that runs one command for everything therefore has benchmarks that
  have been no-ops for months, and a green pipeline asserting otherwise. Give
  benchmarks their own job, without `-n`.
- **Wall-clock gates need dedicated hardware; instruction counting does
  not.** pytest-benchmark's own FAQ attributes high variance to shared
  runners and prescribes bare metal — which most teams lack, which is why
  `--benchmark-compare-fail` on a shared runner becomes a gate that fails
  randomly and gets deleted. Instrumented counting (codspeed and kin) counts
  instructions on a simulated CPU instead of timing wall clock: stable across
  runners, at the price of a hosted dependency and a cost model that
  under-weights branch prediction and SIMD. Choose deliberately — measure
  locally with pytest-benchmark, *gate* with instruction counting, or do not
  gate at all. Do not pretend a noisy gate is a gate.
- **A resource gate that has never failed is not evidence of efficiency.**
  Land each one with a deliberately regressing spike, prove it goes red, then
  delete the spike — the same standard this skill sets for a bugfix's
  regression pin.

## Configuration reference

The canonical `pyproject.toml` baseline:

```toml
[tool.pytest]                          # native TOML types, pytest 9+
minversion = "9.0"
testpaths = ["tests"]
strict = true                          # umbrella; see the notes below
addopts = ["-ra", "--disable-socket"]
faulthandler_timeout = 120             # dump every thread's stack on a hang
faulthandler_exit_on_timeout = true    # pytest 9: and actually end the run
filterwarnings = [
    "error",
    # Each allowlist entry names its source and removal condition, e.g.:
    # "ignore:pkg_resources is deprecated:DeprecationWarning:vendor_sdk",
]
markers = [
    "integration: G2 — real infrastructure (testcontainers); separate CI job",
    "slow: exceeds the unit-test time budget",
    "eval: G3 — judged and nondeterministic; scheduled, never blocks a merge",
]

[tool.coverage.run]
source = ["src"]
branch = true

[tool.coverage.report]
fail_under = 90
show_missing = true
skip_covered = true
exclude_also = [
    "if TYPE_CHECKING:",
    "@overload",
    "raise NotImplementedError",
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = [
    "S101",     # assert is the mechanism of a test
    "PLR2004",  # literal expected values are the point of an assertion
]
```

Type-checker config includes `tests/` at the same strictness as `src/` — no
`disallow_untyped_defs = false` override for tests.

Four pytest 9 facts this baseline encodes:

- **`strict = true` is an umbrella that grows.** It currently enables
  `strict_config`, `strict_markers`, `strict_parametrization_ids`, and
  `strict_xfail`, and upstream states that future strictness options join it
  automatically — so enable it only against a pinned or locked pytest, which
  a lockfile-managed project already has. `xfail_strict = true` is redundant
  underneath it (`strict_xfail` is the same switch) and is dropped here.
- **Native TOML or INI-compat, never both.** `[tool.pytest]` carries real
  TOML types (`addopts` is a list, not a space-separated string);
  `[tool.pytest.ini_options]` is the pre-9 compatibility mode where every
  value is a string. With both tables present, pytest refuses to start: it
  exits with a usage error naming the offending file — "Cannot use both
  [tool.pytest] (native TOML types) and [tool.pytest.ini_options]
  (string-based INI format) simultaneously" — before collecting a single
  test (verified empirically against pytest 9.1.1, 2026-07-26). For a
  standalone file, `pytest.toml` / `.pytest.toml` with a `[pytest]` table is
  the equivalent.
- **The `PytestRemovedIn9Warning` escape hatch is gone.** The warning became
  an error by default in 9.0, and the features behind it are removed as of
  9.1 — the current stable line (9.1.1, checked 2026-07-26). A
  `filterwarnings` entry downgrading it back to a warning no longer rescues
  anything; code that still relied on those features is broken today, not
  facing a deadline.
- **`faulthandler_exit_on_timeout` is new in 9.0.** Previously a hung test
  dumped thread stacks and then kept hanging until CI's outer ceiling; now
  the run ends. A real deadlock becomes a stack trace instead of a
  ninety-minute job that times out with no diagnostic.

## Sources

- [Software Engineering at Google, ch. 11 "Testing Overview"](https://abseil.io/resources/swe-book/html/ch11.html)
- [Unit Testing ch. 1 excerpt (Vladimir Khorikov)](https://enterprisecraftsmanship.com/files/Unit-Testing-Chapter-1-Excerpt.pdf)
- [pytest configuration reference](https://docs.pytest.org/en/stable/reference/customize.html)
- [pytest good practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html)
- [coverage.py](https://coverage.readthedocs.io/)
- [mutmut](https://mutmut.readthedocs.io/en/latest/)
- [pytest-xdist](https://pytest-xdist.readthedocs.io/)
- [pytest-memray](https://pytest-memray.readthedocs.io/)
- [pytest-benchmark](https://pytest-benchmark.readthedocs.io/)
- [CodSpeed](https://codspeed.io/docs)

Freshness: verified against PyPI and current docs on 2026-07-26 — pytest
9.1.1 (the `strict` umbrella membership, native `[tool.pytest]` TOML,
`faulthandler_exit_on_timeout`; the both-tables error above was reproduced
empirically against this version), pytest-cov 7.1.0, pytest-xdist 3.8.0 (no
Python 3.14 classifier), pytest-timeout 2.4.0 (no Python 3.14 classifier;
pytest 9's `faulthandler_timeout` + `faulthandler_exit_on_timeout` now cover
the hang-kill case in core), mutmut 3.6.0 (new config examples must use the
3.x keys — `source_paths`, not `paths_to_mutate`; mutation runs need fork
support, so no native Windows runners). Checked and rejected the same day:
pytest-leaks (2019, requires a debug CPython build), pympler (no 3.13/3.14
classifiers), python-afl (2020, superseded by Atheris).
