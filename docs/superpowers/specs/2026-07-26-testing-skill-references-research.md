# Testing-skill references restructure — source dossier

Compiled 2026-07-26. This dossier grounds the hub-and-spoke restructure of
`plugins/python/skills/testing/SKILL.md` (981 lines) and
`plugins/typescript/skills/testing/SKILL.md` (513 lines). Every rule that
survives into the restructured skills must be traceable either to an entry in
this dossier or to already-verified content in the existing SKILL.md files.

Method: five parallel research agents compiled the sections below on 2026-07-26.
Essay and book sources were fetched live (WebFetch/curl) with quote fragments
recorded verbatim; book claims are cited to chapters verified against publisher
tables of contents, author-published excerpt PDFs, or the Mock Roles OOPSLA
paper read in full. Tooling versions come from PyPI/npm registry JSON checked
the same day; doc patterns from official docs and Context7. Both existing
SKILL.md files were read in full and audited against current docs; every
contradiction found is listed with a line number.

Contents:

1. Fowler cluster (test shapes, doubles, unit tests)
2. Google testing canon (SWE book ch11-14 + Google Testing Blog)
3. Books (Khorikov, Meszaros, GOOS, Beck, Feathers), Dodds essays, PBT strategy
4. Python tooling ground truth (16 packages)
5. TypeScript tooling ground truth (10 packages)
6. Cross-cluster adjudications
7. Consolidated fix list (changes Phase 3 must make)
8. Phase 2 file map (the restructure plan)

## Dossier section: Fowler cluster (testing shapes, doubles, unit tests)

Compiled 2026-07-26. Sources fetched live; all five URLs resolve.

### Test Pyramid (Martin Fowler, bliki)

-   URL: https://martinfowler.com/bliki/TestPyramid.html
-   Type: essay
-   Claims:
    1. The pyramid is a portfolio-balancing heuristic: keep many more low-level
       unit tests than high-level broad-stack tests running through a GUI —
       evidence: "a way of thinking about how different kinds of automated tests
       should be used to create a balanced portfolio."
    2. GUI/end-to-end tests earn their small share because they are brittle,
       expensive to write, and slow to run, with non-determinism that "can
       undermine trust" — evidence: "Problems with UI Testing" section.
    3. A failing high-level test signals two defects at once — the bug itself
       and a missing/incorrect unit test — so "before fixing a bug exposed by a
       high level test, you should replicate the bug with a unit test" —
       evidence: "second line of test defense."
    4. The inverted pyramid (test suites dominated by GUI tests) is the
       ice-cream cone anti-pattern — evidence: ice-cream cone reference.
    5. The pyramid's premise carries an explicit caveat: it assumes broad-stack
       tests are expensive and brittle, "While this is usually true, there are
       exceptions" — evidence: closing caveat; concept credited to Mike Cohn
       (_Succeeding with Agile_, 2009).
-   Tensions: The 2021 test-shapes article partially walks this back — Fowler
    there treats the pyramid-vs-honeycomb fight as largely a terminology dispute
    and (via Searls) calls shape ratios "a distraction"; Vocke keeps the pyramid
    but softens it to two rules of thumb rather than fixed proportions.

### Test Double (Martin Fowler, bliki)

-   URL: https://martinfowler.com/bliki/TestDouble.html
-   Type: essay
-   Claims:
    1. "Test Double" is Gerard Meszaros's generic term for "any case where you
       replace a production object for testing purposes" — evidence: opening
       definition, credited to Meszaros.
    2. Dummies "are passed around but never actually used. Usually they are just
       used to fill parameter lists"; fakes "have working implementations, but
       usually take some shortcut which makes them not suitable for production"
       (e.g. InMemoryTestDatabase) — evidence: numbered taxonomy.
    3. Stubs "provide canned answers to calls made during the test, usually not
       responding at all to anything outside what's programmed in for the test";
       spies "are stubs that also record some information based on how they were
       called" (e.g. an email service counting messages sent) — evidence:
       numbered taxonomy.
    4. Mocks alone carry behavior verification: they are "pre-programmed with
       expectations which form a specification of the calls they are expected to
       receive," can throw on unexpected calls, and "are checked during
       verification to ensure they got all the calls they were expecting" —
       evidence: mock definition; Fowler points to "Mocks Aren't Stubs" for the
       deeper distinction.
-   Tensions: none direct, but the vocabulary is loose in practice — Vocke uses
    "mocks and stubs" almost interchangeably for solitary-test substitutes,
    whereas this entry reserves "mock" for expectation-verifying doubles.

### Unit Test (Martin Fowler, bliki)

-   URL: https://martinfowler.com/bliki/UnitTest.html
-   Type: essay
-   Claims:
    1. Unit tests share three traits: they are "low-level, focusing on a small
       part of the software system," written by programmers with their normal
       tools, and "significantly faster than other kinds of tests" — evidence:
       opening common-elements list.
    2. "Unit" is deliberately situational: "the team decides what makes sense to
       be a unit for the purposes of their understanding of the system and its
       testing" — a class, a function, a cluster of "closely related classes,"
       or a subset of methods — evidence: variable-notion-of-unit section.
    3. Solitary tests (Jay Fields's term) isolate the unit with test doubles for
       all collaborators; sociable tests exercise real collaborators while still
       testing "the behavior of a single unit," assuming "everything other than
       that unit is working correctly" — evidence: sociable/solitary section.
    4. The split maps to schools: mockists prefer solitary, classicists sociable
       — but even classical testers reach for doubles "when there's an awkward
       collaboration" — evidence: same section.
    5. Speed underwrites self-testing code: the compile suite runs constantly
       during development, and the commit suite ("all the unit tests" plus some
       broader ones) should finish "in no more than ten minutes" — evidence:
       compile/commit-suite section.
-   Tensions: Claim 3 quietly undermines TestPyramid's clean unit/integration
    layering — a sociable unit test exercises multiple real objects yet still
    counts as a unit test, which is exactly the ambiguity the 2021 article makes
    explicit.

### On the Diverse And Fantastical Shapes of Testing (Martin Fowler)

-   URL: https://martinfowler.com/articles/2021-test-shapes.html
-   Type: essay
-   Claims:
    1. The pyramid-vs-honeycomb/trophy argument is about "the amount of effort
       we should expend on various types of tests, in particular the balance
       between unit and broader tests" — evidence: framing of the competing
       shape diagrams.
    2. The fight is largely semantic: "unit test" has meant
       isolated-before-integration testing (waterfall era) versus Kent Beck's XP
       sense of "tests written by developers as part of their day-to-day work" —
       one expert claimed "24 different definitions of unit test" — evidence:
       terminology-history section.
    3. The substantive axis under the shapes is sociable vs solitary, not unit
       vs integration: honeycomb critics "specifically target excessive
       mocking," while pyramid advocates typically accept both styles —
       evidence: sociable/solitary analysis.
    4. Fowler's conclusion, via Justin Searls: "People love debating what
       percentage of which type of tests to write, but it's a distraction.
       Nearly zero teams write expressive tests that establish clear boundaries,
       run quickly & reliably, and only fail for useful reasons" — evidence:
       closing quote; test quality outranks shape.
-   Tensions: Directly relativizes the TestPyramid bliki — the shape itself
    matters less than whether names like "unit"/"integration" are even shared;
    recasts Vocke's pyramid layers as one vocabulary among several rather than
    the canonical one.

### The Practical Test Pyramid (Ham Vocke, on martinfowler.com)

-   URL: https://martinfowler.com/articles/practical-test-pyramid.html
-   Type: essay
-   Claims:
    1. Vocke reduces the pyramid to two rules of thumb: "Write _lots_ of small
       and fast _unit tests_... _some_ more coarse-grained tests and _very few_
       high-level tests," and "The more high-level you get the fewer tests you
       should have" — evidence: two-rules section.
    2. Unit tests target the public interface and observable behavior — "Test
       for observable behaviour instead," "Don't reflect your internal code
       structure within your unit tests" — and skip trivial code: "You **don't
       test trivial code**... simple _getters_ or _setters_" — evidence:
       what-to-test section.
    3. On doubles he is pragmatic rather than doctrinaire: solitary means "all
       collaborators... should be substituted with _mocks_ or _stubs_," but his
       own rule is "If it becomes awkward to use real collaborators I will use
       mocks and stubs generously"; a private method that begs for testing means
       "the class I'm testing is already too complex" — split the class instead
       — evidence: sociable/solitary and private-methods sections.
    4. Integration tests are narrow — "test the integration of your application
       with all the parts that live outside of your application," one
       integration point at a time (real local database, doubles for remote
       services) — and duplication is managed by pushing tests down: "If a
       higher-level test spots an error and there's no lower-level test failing,
       you need to write a lower-level test" — evidence: integration and
       duplication sections.
    5. Consumer-driven contract tests replace broad end-to-end coverage across
       team boundaries — "The consuming team writes automated tests with all
       consumer expectations... The providing team runs the CDC tests
       continuously and keeps them green" — and test code deserves
       production-grade care: "Test code is as important as production code...
       _'this is only test code'_ is not a valid excuse," tempered by
       "Duplication is okay, if it improves readability" — evidence: CDC and
       test-code-quality sections.
-   Tensions: Uses "mock" loosely against TestDouble's strict
    expectation-verifying sense; keeps the pyramid shape the 2021 article
    de-emphasizes, but his awkwardness-driven doubling rule is effectively
    Fowler's classicist position from UnitTest; his narrow "integration test" is
    one of the competing definitions the 2021 article says cause the whole shape
    debate.

### Cluster tensions

1. **Shape vs vocabulary.** TestPyramid (and Vocke) prescribe a shape — many
   unit, few end-to-end. The 2021 test-shapes article argues the shape debate is
   confounded because "unit" and "integration" lack shared meaning (up to "24
   different definitions"), and via Searls demotes ratio arguments to "a
   distraction" next to test quality. The pyramid is thus refined from a rule
   into one vocabulary's heuristic.
2. **Sociable/solitary cuts across unit/integration.** UnitTest establishes that
   a sociable test with real collaborators is still a unit test; the 2021
   article says the real disagreement behind honeycomb-vs-pyramid is
   sociable-vs-solitary, not layer ratios. This dissolves the pyramid's
   implication that "touches more than one object" means "integration test."
3. **Strict vs loose double vocabulary.** TestDouble reserves "mock" for doubles
   with pre-programmed, verified expectations (dummy/fake/stub/spy being
   distinct). Vocke — and common usage — say "mocks and stubs" generically for
   any substitute. A reference layout citing both must pick one register and
   flag the other.
4. **Pyramid dogma vs Vocke's pragmatism.** The bliki pyramid warns against
   inversion (ice-cream cone) as an anti-pattern; Vocke softens ratios to rules
   of thumb, licenses "generous" doubling only when real collaborators get
   awkward (the classicist test from UnitTest), and adds mechanisms the bare
   pyramid lacks: narrow integration tests, CDC contract tests as the cross-team
   alternative to broad E2E, and push-tests-down duplication management.
5. **Agreement backbone.** All five converge on: fast feedback is the point of
   low-level tests; high-level tests are a second, thinner line of defense;
   behavior over implementation structure; and (Vocke, explicitly) test code
   merits production-grade care — the claims a restructuring can treat as
   uncontested.

## Dossier section: Google testing canon (SWE book + Google Testing Blog)

Compiled 2026-07-26. Extraction only — no restructuring advice.

### Software Engineering at Google, ch. 11 "Testing Overview"

-   URL: https://abseil.io/resources/swe-book/html/ch11.html
-   Type: book-chapter
-   Claims:
    1. Test sizes are defined by resource constraints, not scope: small tests
       "must run in a single process" (often "a single thread") and "aren't
       allowed to sleep, perform I/O operations, or make any other blocking
       calls" — no network, no disk — evidence: "small tests aren't allowed to
       access the network or disk"
    2. Medium tests "can span multiple processes, use threads, and can make
       blocking calls, including network calls, to localhost" but nothing beyond
       localhost; large tests "remove the localhost restriction," allowing the
       test and system under test to "span across multiple machines" — evidence:
       "aren't allowed to make network calls to any system other than localhost"
    3. Size and scope are "interrelated but distinct concepts": size is about
       resource consumption/hermeticity, scope about "the specific code paths we
       are verifying"; the distinction exists because "the most important
       qualities we want from our test suite are speed and determinism,
       regardless of the scope" — evidence: "Size and scope are interrelated but
       distinct concepts"
    4. Google's recommended mix is roughly "80% of our tests being narrow-scoped
       unit tests... 15% medium-scoped integration tests... and 5% end-to-end
       tests"; anti-patterns are the "ice cream cone" (many e2e, few unit —
       "slow, unreliable") and the "hourglass" (many unit and e2e, few
       integration) — evidence: the 80/15/5 passage and the anti-pattern
       descriptions
    5. Brittle tests "over-specify expected outcomes or rely on extensive and
       complicated boilerplate" and "can fail even when unrelated changes are
       made"; flakiness has a hard ceiling — "as you approach 1% flakiness, the
       tests begin to lose value" (Google's own rate hovers ~0.15%) — evidence:
       "as you approach 1% flakiness, the tests begin to lose value"
    6. Coverage is a floor, not a goal: "Code coverage only measures that a line
       was invoked, not what happened as a result," and the Beyoncé Rule sets
       the actual bar — "If you liked it, then you shoulda put a test on it" —
       evidence: the Beyoncé Rule statement
-   Tensions: recommends 80/15/5 where the 2015 blog post suggests 70/20/10; the
    chapter frames the pyramid in size terms (small/medium/large), the blog in
    colloquial scope terms (unit/integration/e2e).

### Software Engineering at Google, ch. 12 "Unit Testing"

-   URL: https://abseil.io/resources/swe-book/html/ch12.html
-   Type: book-chapter
-   Claims:
    1. A brittle test is "one that fails in the face of an unrelated change to
       production code that does not introduce any real bugs," and "the ideal
       test is unchanging: after it's written, it never needs to change unless
       the requirements of the system under test change" — evidence: "the ideal
       test is unchanging"
    2. Test via public APIs: "write tests that invoke the system being tested in
       the same way its users would; that is, make calls against its public API
       rather than its implementation details" — such tests are "more realistic
       and less brittle" — evidence: "make calls against its public API rather
       than its implementation details"
    3. Prefer state testing to interaction testing: "you should care only what
       the result is," and interaction tests checking specific method calls "are
       more brittle than state tests" — evidence: "are more brittle than state
       tests"
    4. Test code should be DAMP — "Descriptive And Meaningful Phrases" — where
       "DAMP is not a replacement for DRY; it is complementary to it," and "a
       little bit of duplication is OK in tests so long as that duplication
       makes the test simpler and clearer" — evidence: "DAMP is not a
       replacement for DRY; it is complementary to it"
    5. Structure tests as given/when/then and keep them narrow: "Each test
       should cover only a single behavior, and the vast majority of unit tests
       require only one 'when' and one 'then' block"; prefer helper methods with
       defaults over setup methods that hide "important details in a separate
       initialization method" — evidence: "cover only a single behavior"
-   Tensions: the "ideal test is unchanging" absolutism is softened by the ToT
    "Test Behavior, Not Implementation" post, which allows that "test setup may
    need to change if the implementation changes" and that implementation-detail
    tests are sometimes wanted.

### Software Engineering at Google, ch. 13 "Test Doubles"

-   URL: https://abseil.io/resources/swe-book/html/ch13.html
-   Type: book-chapter
-   Claims:
    1. First choice is realism: "Our first choice for tests is to use the real
       implementations of the system under test's dependencies," because "tests
       have higher fidelity when they execute code as it will be executed in
       production"; a real implementation is preferred "if it is fast,
       deterministic, and has simple dependencies" — evidence: "Our first choice
       for tests is to use the real implementations"
    2. Fakes are the preferred double when a real implementation isn't feasible:
       a fake is "a lightweight implementation of an API that behaves similar to
       the real implementation but isn't suitable for production; for example,
       an in-memory database" — evidence: "the best option is often to use a
       fake in its place"
    3. Fakes carry a fidelity contract and an owner: "For any given input to an
       API, a fake should return the same output and perform the same state
       changes of its corresponding real implementation"; "the team that owns
       the real implementation should write and maintain a fake," and "a fake
       must have its own tests" — evidence: the fidelity and ownership passages
    4. Stubbing is dangerous at scale: it "leaks implementation details of your
       code into your test," makes tests unclear and brittle, and "there is no
       way to ensure the function being stubbed behaves like the real
       implementation" — evidence: "Stubbing leaks implementation details of
       your code into your test"
    5. Interaction testing is a last resort: "it can't tell you that the system
       under test is working properly; it can only validate that certain
       functions are called as expected"; use it only when state testing is
       impossible or call counts/order matter, and "prefer to perform
       interaction testing only for state-changing functions" (e.g.,
       sendEmail(), saveRecord()), never for non-state-changing queries —
       evidence: "it can only validate that certain functions are called as
       expected"
    6. Over-mocked tests are mocked as "change-detector tests" — tests that
       "fail in response to any change to the production code, even if the
       behavior of the system under test remains unchanged" — evidence:
       "change-detector tests"
-   Tensions: none within the cluster; refines the ToT state-vs-interaction post
    by adding the state-changing-functions-only rule and the fake-ownership
    discipline.

### Software Engineering at Google, ch. 14 "Larger Testing"

-   URL: https://abseil.io/resources/swe-book/html/ch14.html
-   Type: book-chapter
-   Claims:
    1. Larger tests exist to close fidelity gaps — fidelity being "the property
       by which a test is reflective of the real behavior of the system under
       test" — that unit tests structurally cannot cover — evidence: the
       fidelity definition
    2. The enumerated gaps: unfaithful doubles ("mocks become stale" and the
       double and "the doubled thing do not agree"), configuration issues (a bad
       untested "network configuration push" caused "a global Google outage back
       in 2013"), load-related issues invisible without real traffic volumes,
       and unanticipated/emergent behaviors — "unit tests are limited by the
       imagination of the engineer writing them" — evidence: "unit tests are
       limited by the imagination of the engineer writing them"
    3. Unit tests deliberately "eliminate the chaos of real dependencies,
       network, and data" — a vacuum that hides defects which only emerge in
       integrated systems — evidence: the vacuum/chaos-elimination passage
    4. Larger tests trade away the small-test virtues: "they may be slow"
       (default timeouts of "15 minutes or 1 hour"), "they may be nonhermetic,"
       "they may be nondeterministic," and they create ownership problems
       because "a larger test spans multiple units and thus can span multiple
       owners" — evidence: "Our large tests have a default timeout of 15 minutes
       or 1 hour"
    5. Every large test follows one skeleton: "obtain a system under test,"
       "seed necessary test data," "perform actions using the system under
       test," "verify behaviors"; the overall strategy should still keep "the
       vast majority of written tests" as unit tests and derive larger tests
       from identified system risks — evidence: the four-phase structure
-   Tensions: none — explicitly complements ch11-13 by defining what the 15%/5%
    tiers are for rather than arguing for more of them.

### Just Say No to More End-to-End Tests (Google Testing Blog, Mike Wacker, 2015)

-   URL:
    https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html
-   Type: blog
-   Claims:
    1. The pyramid split: "As a good first guess, Google often suggests a
       70/20/10 split: 70% unit tests, 20% integration tests, and 10% end-to-end
       tests. The exact mix will be different for each team, but in general, it
       should retain that pyramid shape." — evidence: verbatim from the "Testing
       Pyramid" section
    2. "A failing test does not directly benefit the user... A bug fix directly
       benefits the user" — so a testing strategy must be judged by "how it
       enables developers to fix (and even prevent) bugs," not just how it finds
       them — evidence: "A failing test does not directly benefit the user"
    3. The ideal feedback loop has three properties: "It's fast... It's
       reliable... It isolates failures" — flaky tests "are often ignored, even
       when they find real product issues," and without isolation a bug "could
       be anywhere" in millions of lines — evidence: the "Building the Right
       Feedback Loop" section
    4. Unit tests win on all three: "one tenth of a second is considered slow
       for unit tests"; hermetic practices "will remove flakiness entirely"; "if
       a unit test fails, you only need to search that small unit under test to
       find the bug" — evidence: "one tenth of a second is considered slow for
       unit tests"
    5. Integration tests, not e2e tests, are the answer to "do units work
       together": "An integration test takes a small group of units, often two
       units, and tests their behavior as a whole"; "why write an end-to-end
       test when you can write a much smaller, more focused integration test
       that will detect the same bug?"; the anti-patterns are the "inverted
       pyramid/ice cream cone" and the "hourglass" — evidence: "you only need to
       think a little larger"
-   Tensions: 70/20/10 vs the book's 80/15/5 (the post itself pre-empts this:
    "the exact mix will be different for each team"); the post's composite
    sketch treats e2e mostly as a liability, while ch14 gives larger tests a
    positive charter (fidelity gaps); the post lists "mocking" among needed
    unit-test skills, whereas ch13 demotes mocking below real implementations
    and fakes.

### Testing on the Toilet: Test Behavior, Not Implementation (Google Testing Blog, Andrew Trenk, 2013-08-05)

-   URL:
    https://testing.googleblog.com/2013/08/testing-on-toilet-test-behavior-not.html
-   Type: blog
-   Claims:
    1. "In most cases, tests should focus on testing your code's public API, and
       your code's implementation details shouldn't need to be exposed to
       tests." — evidence: verbatim, Calculator/AdderFactory example
    2. Behavior tests survive refactors: after swapping the add-operator
       implementation for an AdderFactory, "none of the existing tests should
       need to change since you only changed the code's implementation, but its
       user-facing behavior didn't change" — evidence: the Calculator refactor
       example
    3. Implementation-independent tests are "easier to maintain" and "easier to
       understand since they basically act as code samples that show all the
       different ways your class's methods can be used" — evidence: verbatim
    4. The rule is scoped, not absolute: "There are many cases where you do want
       to test implementation details (e.g. you want to ensure that your
       implementation reads from a cache instead of from a datastore), but this
       should be less common" — evidence: verbatim
    5. Setup is exempt from the unchanging ideal: "test setup may need to change
       if the implementation changes... but the actual test itself typically
       shouldn't need to change if the code's user-facing behavior doesn't
       change" — evidence: verbatim
-   Tensions: claim 4 (cache-vs-datastore exception) is broader than ch13's
    narrowed rule that interaction testing should target state-changing
    functions only; claim 5 refines ch12's "ideal test is unchanging" by carving
    out setup.

### Testing on the Toilet: Testing State vs. Testing Interactions (Google Testing Blog, Andrew Trenk, 2013-03-22)

-   URL:
    https://testing.googleblog.com/2013/03/testing-on-toilet-testing-state-vs.html
-   Type: blog
-   Claims:
    1. Definitions: "Testing state means you're verifying that the code under
       test returns the right results"; "Testing interactions means you're
       verifying that the code under test calls certain methods properly" —
       evidence: verbatim definitions
    2. Interaction tests can pass while the code is broken: the mockQuicksort
       test "may result in good code coverage, but it doesn't tell you whether
       sorting works properly, only that quicksort.sort() was called... in most
       cases, you want to test state, not interactions" — evidence: "you want to
       test state, not interactions"
    3. Interaction testing is warranted only "when correctness doesn't just
       depend on what the code's output is, but also how the output is
       determined" (e.g., quicksort must be used because another algorithm
       "would run too slowly") — evidence: verbatim
    4. Concrete interaction-test cases: call count/order matters for "side
       effects (e.g. you only want one email to be sent), latency (e.g. you only
       want a certain number of disk reads to occur) or multithreading issues
       (e.g. your code will deadlock if it calls some methods in the wrong
       order)" — evidence: verbatim
    5. UI layering is a sanctioned interaction-testing case: with MVC/MVP, "in
       tests for your controller/presenter, you only care that a certain method
       of the view was called, not what was actually rendered" — evidence:
       verbatim
-   Tensions: the MVC/MVP view-call case (claim 5) verifies calls to a
    non-state-changing render surface, sitting uneasily beside ch13's "prefer to
    perform interaction testing only for state-changing functions"; otherwise
    this post is the seed ch12/ch13 later systematized.

### Cluster tensions

1. Size vs scope: ch11 insists test "size" (small/medium/large) is a
   resource/hermeticity contract — process/thread confinement, no
   sleeping/blocking, localhost-only vs multi-machine network — that is
   "interrelated but distinct" from scope, whereas the 2015 blog post and the
   colloquial pyramid conflate the axes into unit/integration/e2e by scope. The
   book's 80/15/5 is phrased over scopes ("narrow-scoped unit... medium-scoped
   integration... end-to-end") even while its size taxonomy is resource-based,
   so the two axes must be tracked separately when citing either.
2. The mix numbers disagree: 70/20/10 (2015 blog) vs ~80/15/5 (book, 2020). Both
   sources hedge that the mix is a starting guess per team; the invariant both
   defend is the pyramid shape plus the ice-cream-cone and hourglass
   anti-patterns, not the digits.
3. Attitude toward larger tests: the 2015 post argues down ("just say no to MORE
   e2e tests" — a smaller integration test usually detects the same bug), while
   ch14 argues a positive, non-overlapping charter for larger tests: fidelity
   gaps unit tests structurally cannot cover (stale/unfaithful doubles, untested
   deployment configuration, load, emergent behavior outside the unit-test
   "vacuum"). Read together: cap the count per the blog, justify each survivor
   by a named fidelity risk per ch14.
4. Doubles hierarchy hardened over time: the 2015 post names "mocking" a core
   unit-testing skill; ch13 (later) demotes it — real implementation first (when
   fast, deterministic, simple deps), fake second (with fidelity contract,
   owner, and its own tests), stubbing sparingly, interaction verification last
   resort and only for state-changing functions. The ToT posts (2013) already
   contain the seed ("test state, not interactions") but permit broader
   interaction-testing cases (cache-read verification, MVC/MVP view calls) than
   ch13's narrowed rule.
5. The "unchanging test" ideal (ch12) is an asymptote, not a law: the Test
   Behavior ToT post exempts test setup from it and concedes legitimate
   implementation-detail tests exist; ch11's brittleness/flakiness data (value
   lost near 1% flake rate) supplies the operational reason the ideal is worth
   approaching.

## Source dossier — testing-standards restructure (books, Dodds essays, PBT strategy)

Compiled 2026-07-26. Book text is not directly fetchable; book claims are cited
to chapters verified against the publisher's table of contents or
author-published excerpts, with fetchable supporting URLs where they exist.
Quote fragments from fetchable sources are verbatim as retrieved on 2026-07-26.

### Group A — Books

### Unit Testing: Principles, Practices, and Patterns (Vladimir Khorikov, Manning, 2020)

-   URL: book — claims cited to chapters (ToC verified via author's excerpt PDF
    at
    https://enterprisecraftsmanship.com/files/Unit-Testing-Chapter-1-Excerpt.pdf);
    supporting URLs:
    https://enterprisecraftsmanship.com/posts/styles-of-unit-testing/ and
    https://enterprisecraftsmanship.com/posts/when-to-mock/
-   Type: book
-   Claims:
    1. The goal of unit testing is economic, not moral: "The goal is to enable
       sustainable growth of the software project," and both tests and
       production code are costs — "Code is a liability, not an asset" —
       evidence: ch. 1 excerpt PDF, sections 1.2 and the "Production code vs.
       test code" sidebar.
    2. Coverage numbers must never be targets: "coverage metrics are a good
       negative indicator, but a bad positive one," and "targeting a specific
       coverage number creates a perverse incentive that goes against the goal
       of unit testing" — evidence: ch. 1 excerpt PDF, section 1.3.4 "Aiming at
       a particular coverage number".
    3. A good unit test has four pillars — protection against regressions,
       resistance to refactoring, fast feedback, and maintainability — the first
       two are in intrinsic tension (test accuracy), and since no test maxes all
       four, resistance to refactoring is the non-negotiable one — evidence: ch.
       4 ("The four pillars of a good unit test": 4.1 "The first pillar:
       Protection against regressions" p. 68, "The second pillar: Resistance to
       refactoring" p. 69; 4.2 "The intrinsic connection between the first two
       attributes"; 4.3 "Fast feedback and maintainability"; 4.4 "In search of
       an ideal test").
    4. Classical (Detroit) school beats the London school: the London school
       "advocates for replacing all mutable dependencies (collaborators) with
       mocks," which "results in fragile tests — tests that couple to
       implementation details"; the classical school substitutes only
       shared/out-of-process dependencies — evidence: ch. 2 ("The classical and
       London schools of unit testing") and ch. 5.4 ("The classical vs. London
       schools, revisited"); quote from
       https://enterprisecraftsmanship.com/posts/when-to-mock/.
    5. Mock ONLY unmanaged out-of-process dependencies: "Only unmanaged
       dependencies should be replaced with mocks. Use real instances of managed
       dependencies in tests" — managed deps (e.g. the application's own
       database) are implementation details, unmanaged deps (SMTP, message bus,
       third-party APIs) are externally observable contracts requiring backward
       compatibility; corollaries: "Mocks are for integration tests only" and
       "Only mock types that you own" — evidence: ch. 8.2 ("Which out-of-process
       dependencies to test directly", p. 190) and ch. 9.2 ("Mocking best
       practices", pp. 225–227); quotes from
       https://enterprisecraftsmanship.com/posts/when-to-mock/.
    6. Styles of unit testing rank output-based > state-based >
       communication-based, because output-based has "the lowest chance of
       producing false positives" and inputs/outputs "tend to change less
       frequently during refactorings," while communication-based verification
       "introduces coupling between the tests and the SUT's implementation
       details" — evidence: ch. 6 ("Styles of unit testing", 6.1–6.2); quotes
       from https://enterprisecraftsmanship.com/posts/styles-of-unit-testing/.
-   Tensions: Head-on with Freeman & Pryce/GOOS — Khorikov ranks their signature
    style (communication-based verification of collaborations) worst and calls
    London-style tests fragile, while GOOS calls intra-system mocking its core
    design tool. Partially with Dodds on layer emphasis: Khorikov keeps a
    unit-test-centric pyramid focused on the domain model, Dodds's trophy makes
    integration the biggest layer — though both agree mocks trade away
    confidence and coverage targets are harmful. Agrees with GOOS on "only mock
    types you own" (Khorikov adopts it in ch. 9.2).

### xUnit Test Patterns: Refactoring Test Code (Gerard Meszaros, Addison-Wesley, 2007)

-   URL: book — claims cited to the pattern/smell chapters; supporting URL
    (author's own pattern site, HTTP-only): http://xunitpatterns.com/
    (per-pattern pages: /Four%20Phase%20Test.html, /Test%20Double.html,
    /Fragile%20Test.html, /Obscure%20Test.html, /Erratic%20Test.html,
    /Test%20Code%20Duplication.html, /Fresh%20Fixture.html,
    /Shared%20Fixture.html)
-   Type: book
-   Claims:
    1. The Four-Phase Test is the canonical test shape: "The four parts are
       fixture setup, exercise SUT, result verification and fixture teardown,"
       structured so "the test reader [is] able to quickly determine what
       behavior the test is verifying" — evidence: Four-Phase Test page (book p.
       358).
    2. Fresh vs shared fixture is "a key test automation decision": a Fresh
       Fixture means "Each test constructs its own brand-new test fixture for
       its own private use," which "prevents Erratic Tests"; a Shared Fixture
       ("we reuse the same instance of the test fixture across many tests") buys
       speed at the cost of inter-test coupling, with Immutable Shared Fixture
       as the recommended middle step — evidence: Fresh Fixture page (book
       p. 311) and Shared Fixture page (book p. 317).
    3. The book codifies the test-smell vocabulary: Fragile Test ("a test fails
       to compile or run when the SUT is changed in ways that do not affect the
       part the test is exercising"), Obscure Test ("it is difficult to
       understand the test at a glance", caused by Mystery Guest, Eager Test,
       Irrelevant Information), Erratic Test ("sometimes they pass and sometimes
       they fail"), and Test Code Duplication ("the same test code is repeated
       many times") — evidence: smell pages (book pp. 239, 186, 228, 213).
    4. Fragile Tests have four root-cause "sensitivities" — Interface
       Sensitivity, Behavior Sensitivity, Data Sensitivity, and Context
       Sensitivity — a diagnostic taxonomy for why passing tests start failing —
       evidence: Fragile Test page ("the 'four sensitivities' of automated
       tests"; named causes listed as "Cause: Interface Sensitivity" etc.).
    5. The test-double taxonomy originates here: Test Double ("we replace a
       component on which the SUT depends with a 'test-specific equivalent'")
       with variations Test Stub, Test Spy, Mock Object, Fake Object, and Dummy
       Object, "classified based on how/why we use the Test Double" — evidence:
       Test Double page (book p. 522); this is the taxonomy Fowler's "Mocks
       Aren't Stubs" and Khorikov ch. 5.1 both build on.
-   Tensions: Test Code Duplication as a named smell sits in tension with
    Dodds's "Avoid Nesting"/AHA stance ("prefer duplication over the wrong
    abstraction") — Meszaros pushes toward extraction (Test Utility Method,
    Creation Method), Dodds toward inline self-containment; they converge,
    however, on Fresh Fixture/self-contained tests and on Erratic Test as the
    price of shared state. Neutral in the classical-vs-London fight: the
    taxonomy serves both camps.

### Growing Object-Oriented Software, Guided by Tests (Steve Freeman & Nat Pryce, Addison-Wesley, 2009)

-   URL: book — claims cited to chapters; supporting URLs:
    http://www.growing-object-oriented-software.com/ (book site; HTTPS cert
    broken, fetch over HTTP) and the precursor paper "Mock Roles, not Objects"
    (Freeman, Pryce, Mackinnon, Walnes, OOPSLA 2004):
    http://jmock.org/oopsla2004.pdf
-   Type: book
-   Claims:
    1. Development is outside-in, starting from a walking skeleton: begin every
       project by building "an implementation of the thinnest possible slice of
       real functionality that we can automatically build, deploy, and test
       end-to-end," then grow features acceptance-test-first from the outside in
       — evidence: ch. 4 "Kick-Starting the Test-Driven Cycle" (walking
       skeleton), ch. 1 & ch. 10 (outside-in TDD cycle); book site: "let tests
       guide your development and 'grow' software".
    2. Mocks are a design tool for interface discovery, not an isolation
       convenience: "Mock Objects is misnamed. It is really a technique for
       identifying types in a system based on the roles that objects play," and
       "the most important benefit of Mock Objects is what we originally called
       'interface discovery'" — evidence: Mock Roles, not Objects §1 (verbatim);
       book site: "using Mock Objects to discover and then describe
       relationships between objects".
    3. Need-driven development: "TDD with Mock Objects guides interface design
       by the services that an object requires, not just those it provides. This
       process results in a system of narrow interfaces each of which defines a
       role in an interaction between objects" — evidence: Mock Roles, not
       Objects §2.1.
    4. "Listen to your tests": difficulty writing a test is feedback about the
       design, not about the test — tests that are hard to set up or
       over-complicated indicate weak structure ("mock-based tests quickly
       become too complicated when the system design is weak. The use of mock
       objects amplifies problems such as tight coupling... it is better to use
       this as a motivator for improving the design") — evidence: book ch. 20
       "Listening to the Tests"; quote from Mock Roles, not Objects §4.
    5. Only mock types you own: "programmers should only write mocks for types
       that they can change... Programmers should not write mocks for fixed
       types, such as those defined by the runtime or external libraries.
       Instead they should write thin wrappers to implement the application
       abstractions in terms of the underlying infrastructure" — evidence: Mock
       Roles, not Objects §4.1; book ch. 8 "Building on Third-Party Code".
    6. Explicit anti-boundary position: to the claim "Mock Objects should only
       be used at the boundaries of the system," the authors reply "We believe
       the opposite, that Mock Objects are most useful when used to drive the
       design of the code under test... within the system where the interfaces
       can be changed" — evidence: Mock Roles, not Objects §5.2.
-   Tensions: Claim 6 is the direct antithesis of Khorikov's
    mock-only-unmanaged-out-of-process rule and of Dodds's "Testing
    Implementation Details" (interaction expectations on internal collaborators
    are exactly what Dodds calls implementation details; GOOS answers that role
    interfaces are the design, not a detail). Common ground with both: "only
    mock types you own," and Mock Roles §4.4 concedes the fragility risk — tests
    "have been over-specified to check features that are an artefact of the
    implementation, not an expression of some requirement," with the fix "a
    specification should be as precise as possible, but not more precise."

### Test-Driven Development: By Example (Kent Beck, Addison-Wesley, 2002)

-   URL: book — claims cited to chapters; supporting URL (author's own
    restatement, 2023): https://newsletter.kentbeck.com/p/canon-tdd (redirect
    target of tidyfirst.substack.com/p/canon-tdd)
-   Type: book
-   Claims:
    1. TDD is driven by two rules — write new code only if an automated test has
       failed, and eliminate duplication — producing the red/green/refactor
       rhythm: "Red—write a little test that doesn't work... Green—make the test
       work quickly, committing whatever sins necessary... Refactor—eliminate
       all of the duplication created in merely getting the test to work" —
       evidence: Preface.
    2. The goal is "clean code that works" — courage through rapid, concrete
       feedback rather than up-front design certainty — evidence: Preface
       (crediting Ron Jeffries's phrase).
    3. Isolated Test: tests must not affect one another — run in any order, no
       shared leftover state — which pushes toward small, decoupled, highly
       cohesive objects — evidence: ch. 25 "Test-Driven Development Patterns,"
       pattern "Isolated Test."
    4. Test List: before starting, "write a list of the test scenarios you want
       to cover," then "turn exactly one item on the list into an actual,
       concrete, runnable test," and loop "until the list is empty" — the list
       absorbs new cases discovered mid-implementation instead of derailing the
       current step — evidence: ch. 25, pattern "Test List"; verbatim quotes
       from Canon TDD.
    5. Canon TDD's success criteria are behavioral confidence, not coverage:
       done means "Everything that used to work still works. The new behavior
       works as expected. The system is ready for the next change. The
       programmer & their colleagues feel confident in the above points"; and
       Beck disclaims dogma — "What follows is NOT how _you_ should _do_ TDD" —
       evidence: Canon TDD (verbatim).
-   Tensions: Beck's fine-grained, unit-first workflow is the historical root of
    the pyramid-era unit emphasis Dodds's trophy pushes against — but note
    Beck's "isolated" means tests isolated from each other, not the SUT isolated
    by mocks; Beck's own practice is classical (real collaborators, minimal
    doubles), so he is not the London school despite London describing itself as
    TDD. Khorikov explicitly builds on Beck's classical school. Canon TDD's
    "test scenarios" list is example-based enumeration, which Hillel Wayne's PBT
    essays argue systematically misses intersection edge cases.

### Working Effectively with Legacy Code (Michael Feathers, Prentice Hall, 2004)

-   URL: book — claims cited to chapters; supporting URL (publisher excerpt of
    the seam chapter):
    https://www.informit.com/articles/article.aspx?p=359417&seqNum=2
-   Type: book
-   Claims:
    1. Legacy code is defined by tests, not age: "To me, legacy code is simply
       code without tests" — code without tests cannot be changed with verified
       safety regardless of how well it is written — evidence: Preface (widely
       reproduced verbatim; confirmed via multiple secondary sources including
       the InformIT excerpt series).
    2. Two ways to change software: "Edit and Pray" vs "Cover and Modify" — the
       book's program is converting the former into the latter by getting tests
       in place before changing behavior — evidence: ch. 1 "Changing Software."
    3. A seam is the unit of testability: "a seam is a place where you can alter
       behavior in your program without editing in that place," and every seam
       has an enabling point where you choose which behavior runs — evidence:
       ch. 4 "The Seam Model" (InformIT excerpt).
    4. Seams come in types — preprocessing seams, link seams, and object seams —
       and "object seams are the most useful seams available in object-oriented
       languages"; dependency-breaking techniques exist to create them without
       yet having tests — evidence: ch. 4 "The Seam Model" (seam-type taxonomy),
       Part III dependency-breaking catalog (ch. 25).
    5. Characterization tests pin actual behavior, not intended behavior: a
       characterization test is "a test that characterizes the actual behavior
       of a piece of code" — you write an assertion you know is wrong, let the
       failure tell you what the code really does, then lock that in as the
       baseline for safe refactoring — evidence: ch. 13 "I Need to Make a
       Change, but I Don't Know What Tests to Write."
-   Tensions: Characterization tests intentionally protect current behavior
    including bugs, which inverts every other source's assumption that tests
    encode desired behavior — this is a deliberate, transitional stance for
    legacy contexts, not a disagreement about end-state. Feathers' seam-enabling
    design changes create test-only structure, which brushes against Dodds's
    "test user" critique (tests as a third user the code must serve); Feathers
    accepts that cost explicitly as the price of getting legacy code under test.
    Seam substitution frequently fakes managed in-process dependencies, which
    Khorikov tolerates only as a legacy on-ramp, not steady state.

### Group B — Kent C. Dodds essays (kentcdodds.com)

### Write tests. Not too many. Mostly integration.

-   URL: https://kentcdodds.com/blog/write-tests
-   Type: essay
-   Claims:
    1. The title is Guillermo Rauch's 2016 tweet, adopted as a complete testing
       strategy in three clauses — evidence: essay opening, "Write tests. Not
       too many. Mostly integration." (Rauch tweet, Dec 2016).
    2. Coverage has diminishing returns: "you get diminishing returns on your
       tests as the coverage increases much beyond 70%," and chasing 100% forces
       testing "things that really don't need to be tested" — evidence: "Not too
       many" section.
    3. Confidence rises with test level: as you climb from unit toward E2E "the
       confidence quotient of each form of testing increases," while speed and
       cheapness fall — evidence: "confidence coefficient" discussion.
    4. Integration is the sweet spot: "Integration tests strike a great balance
       on the trade-offs between confidence and speed/expense" — the essay's
       core prescription for where most effort goes — evidence: "Mostly
       integration" section.
-   Tensions: Directly against the classic test pyramid's unit-heavy allocation
    (Beck-era practice, Cohn's pyramid, and Khorikov's domain-model-focused unit
    emphasis). Aligned with Khorikov on coverage targets being harmful (Khorikov
    ch. 1.3.4 makes the same negative-indicator argument).

### Testing Implementation Details

-   URL: https://kentcdodds.com/blog/testing-implementation-details
-   Type: essay
-   Claims:
    1. Implementation-detail tests fail in both directions: "Tests which test
       implementation details can give you a false negative when you refactor
       your code" (breaks without a bug) and a false positive when "we didn't
       get a test failure, but we should have!" (passes despite a bug) —
       evidence: the two named failure modes, verbatim.
    2. Definition: "Implementation details are things which users of your code
       will not typically use, see, or even know about" — evidence: verbatim.
    3. Code has two users — end users and developer users — and testing
       internals invents a third: "we create a third user our application code
       needs to consider: the tests!" — evidence: "test user" section, verbatim.
    4. The remedy is Testing Library's guiding principle, quoted as the essay's
       north star: "The more your tests resemble the way your software is used,
       the more confidence they can give you." — evidence: verbatim; this line
       is Testing Library's own stated guiding principle at
       https://testing-library.com/docs/guiding-principles/ (confirmed verbatim
       there).
-   Tensions: This essay is the frontend-flavored restatement of Khorikov's
    resistance-to-refactoring pillar (false negative/false positive framing
    matches Khorikov ch. 4–5 almost one-to-one) — the two agree against
    GOOS-style interaction verification of internals. GOOS would reply that a
    collaborator's role interface is part of the public design contract, not an
    internal detail.

### Avoid Nesting when you're Testing

-   URL: https://kentcdodds.com/blog/avoid-nesting-when-youre-testing
-   Type: essay
-   Claims:
    1. Nested describe/beforeEach with mutable variables is the main readability
       hazard: "Tracing through the code to keep track of the variables and
       their values over time is the number one reason I strongly recommend
       against nested tests" — evidence: verbatim.
    2. Tests should be self-contained: inline setup so "the entire test is
       self-contained" and readable without scanning the file for reassignments
       — evidence: Login-component example, verbatim.
    3. Reuse via plain functions, not hooks: for shared setup "we have functions
       for that" — beforeEach earns its keep only for guaranteed cleanup (e.g.
       shutting down a server), not for code reuse — evidence: "functions over
       hooks" and cleanup-exception sections.
    4. AHA applied to tests: "prefer duplication over the wrong abstraction and
       optimize for change first" — tolerate repetition rather than premature
       test abstractions — evidence: verbatim (AHA Programming principle).
-   Tensions: Pulls against Meszaros's Test Code Duplication smell and
    utility-method extraction patterns — Dodds treats extraction itself as the
    risk, Meszaros treats duplication as the risk. Strongly agrees with
    Meszaros's Fresh Fixture/Obscure Test analysis (Dodds's
    mutable-shared-variable complaint is Meszaros's Erratic Test/Obscure Test in
    vitest clothing). Also agrees with Khorikov, who calls high coupling between
    tests an anti-pattern (ch. 3.3).

### The Merits of Mocking

-   URL: https://kentcdodds.com/blog/the-merits-of-mocking
-   Type: essay
-   Claims:
    1. The cost of a mock is stated as a law: "Mocking severs the real-world
       connection between what you're testing and what you're mocking" — every
       mock trades confidence for practicality — evidence: verbatim.
    2. Mock where reality is unaffordable: charging real credit cards in
       checkout tests is the canonical justified mock — evidence:
       payment-provider example.
    3. Speed alone never justifies mocking: "trading confidence for a minute or
       two faster test suite is a bad trade" — evidence: verbatim.
    4. Default posture is minimal doubles: keep most production code real, mock
       network calls and animations in UI tests, reserve mocks for "genuinely
       impractical scenarios" — evidence: selective-mocking discussion.
-   Tensions: Operationally identical to Khorikov's rule — Dodds's justified
    mocks (payment provider, network) are exactly Khorikov's unmanaged
    out-of-process dependencies — arrived at from a confidence argument rather
    than a contracts argument. Both stand against GOOS's use of mocks between
    internal roles. No tension with Meszaros, who defines the double taxonomy
    without prescribing frequency.

### Static vs Unit vs Integration vs E2E Testing for Frontend Apps (the Testing Trophy)

-   URL: https://kentcdodds.com/blog/static-vs-unit-vs-integration-vs-e2e-tests
-   Type: essay
-   Claims:
    1. The Testing Trophy has four layers with distinct jobs — Static ("Catch
       typos and type errors as you write the code"), Unit ("Verify that
       individual, isolated parts work as expected"), Integration ("Verify that
       several units work together in harmony"), E2E ("A helper robot that
       behaves like a user to click around the app") — evidence: verbatim layer
       definitions.
    2. Layer size prescribes effort: "The size of these forms of testing on the
       trophy is relative to the amount of focus you should give them when
       testing your applications" — integration is the biggest band — evidence:
       verbatim.
    3. Three trade-off axes govern placement — cost, speed, and "how well your
       tests resemble the way your software is used" — climbing the trophy buys
       confidence with money and time — evidence: trade-offs section.
    4. The organizing principle is again "The more your tests resemble the way
       your software is used, the more confidence they can give you" (Testing
       Library's stated guiding principle; see
       https://testing-library.com/docs/guiding-principles/) — evidence:
       verbatim.
    5. Every layer has a blind spot (static can't verify logic, unit can't
       verify integration, integration can't verify backend contracts, E2E runs
       outside production), so the layers are complements, not substitutes —
       evidence: capability-boundaries discussion.
-   Tensions: The trophy is an explicit revision of the unit-heavy pyramid: it
    demotes unit tests and promotes a static-analysis base the pyramid never
    had. Against Beck-era unit emphasis and Khorikov's pyramid-with-unit-focus;
    partially reconciled by Khorikov's own concession that classical "units" are
    units of behavior (often several classes), which converges toward what Dodds
    calls integration.

### Group C — Property-based testing strategy

### Finding Property Tests (Hillel Wayne)

-   URL: https://www.hillelwayne.com/post/contract-examples/
-   Type: essay
-   Claims:
    1. Example-based tests structurally miss intersection bugs: the buggy `mode`
       implementation fails only when "the mode of a list must be a falsy value
       like 0 or `[]` _and_ the last value of the list must be something else" —
       an input class no reasonable example list would include — evidence:
       verbatim, mode-bug worked example.
    2. The adoption bottleneck of PBT is named precisely: "The problem with PBT,
       though, is that it can be hard to find good properties" — evidence:
       verbatim.
    3. Types are not properties: annotating `mode` correctly "doesn't actually
       find the error. The problem isn't the type, it's that we got the wrong
       result" — evidence: verbatim.
    4. Properties come in strengths — partial "sanity check" contracts ("it will
       catch _some_ incorrect outputs, it won't catch them all") up to full
       definitional contracts ("Why not just use the definition itself?" —
       assert `all(l.count(m) >= l.count(x) for x in l)`) — and partial
       properties are still worth writing — evidence: verbatim, escalation from
       sanity check to definition.
-   Tensions: Aims squarely at the example-first canon (Beck's Test List,
    Dodds's user-resembling examples): enumerated scenarios cannot cover
    input-space intersections. Complements rather than contradicts — Wayne
    positions PBT as an addition, and the "hard to find good properties"
    concession is the limit the example-based camp escapes.

### Metamorphic Testing (Hillel Wayne)

-   URL: https://www.hillelwayne.com/post/metamorphic-testing/
-   Type: essay
-   Claims:
    1. Metamorphic relations relate transformed inputs to outputs: "if we have
       `x` and `f(x)`, we can make some transformation on `x` to get `x2` and
       `f(x2)`" whose outputs must relate predictably — evidence: verbatim.
    2. This defeats the oracle problem: for a speech-to-text system, "if a given
       soundclip transcribes to output `out`, then we should _still_ get output
       `out` if we Double the volume, or Raise the pitch" — "At no point do we
       need to check what `out` is. This is really, really big." — evidence:
       verbatim.
    3. MT and PBT are complementary halves of one strategy: "MT research is more
       focused on determining what we actually want to test" while "PBT research
       focuses on how we effectively generate and shrink inputs" — evidence:
       verbatim.
-   Tensions: None with the PBT cluster; against the assumption implicit in all
    Group A/B sources that a test can state its expected output — metamorphic
    properties verify systems where no oracle exists, a case the four-phase/AAA
    verify-step model does not cover.

### Property Testing with Complex Inputs (Hillel Wayne)

-   URL: https://www.hillelwayne.com/post/property-testing-complex-inputs/
-   Type: essay
-   Claims:
    1. PBT's second hard problem is generation, not just properties: "Often
       we're working with data that has lots of preconditions and we want to
       generate inputs that satisfy the preconditions," a problem "neglected by
       most PBT literature, which focuses on the finding properties side" —
       evidence: verbatim.
    2. Filtering is a trap at scale: with `assume`/`filter` "we are still
       generating bad inputs - we're just throwing it away" — construct valid
       inputs instead of rejecting invalid ones — evidence: verbatim.
    3. There is a tool ladder: "Hypothesis can infer a lot using `from_type`. If
       most random inputs are valid... then `assume` and `filter` are simple and
       effective," but interdependent data needs composite strategies because
       "We can't link strategies to each other" with plain builders — evidence:
       verbatim.
    4. (Companion critique, same author) Preconditions weaken what a property
       proves: "any assumption added makes a property weaker" and "more
       assumptions means more likely to go wrong" — supporting URL:
       https://buttondown.com/hillelwayne/archive/assumptions-weaken-properties/
       — evidence: verbatim.
-   Tensions: The generator-cost claims are the honest counterweight to PBT
    advocacy — the effort curve of building constructive generators is the same
    maintainability cost Khorikov's fourth pillar and Dodds's "not too many"
    would charge against any test; none of the Group A/B sources model this cost
    because they assume hand-written inputs.

### Hypothesis Testing with Oracle Functions (Hillel Wayne)

-   URL: https://www.hillelwayne.com/post/hypothesis-oracles/
-   Type: essay
-   Claims:
    1. An oracle is the cheapest property: to test a new sort "we just need to
       check that the output of the function matches the output of a sorting
       function! In this case, `sorted` is an _oracle_" — evidence: verbatim.
    2. The prime oracle use case is refactoring: "one use case for an oracle is
       when you refactor an existing function: you want to clean up or optimize
       something you're confident is correct" — the old implementation tests the
       new one — evidence: verbatim.
    3. Slow-but-obviously-right implementations are legitimate oracles:
       "Sometimes there's a solution to a problem that we know for sure works
       but is too slow/memory-intensive/etc for production code" — evidence:
       verbatim.
    4. Oracles can be partial (correct on a restricted domain: "Since we know
       it's correct for certain lists, our final function must match its output
       for those lists") or reversed (generate the answer, derive the question)
       — evidence: verbatim.
-   Tensions: The refactoring-oracle pattern is PBT's implementation of
    Feathers' characterization testing (pin current behavior, change with a
    safety net) and directly serves Khorikov's resistance-to-refactoring pillar
    — a rare point where all three clusters agree.

### Hypothesis documentation (strategic guidance)

-   URL: https://hypothesis.readthedocs.io/en/latest/ (front page; stateful:
    /en/latest/stateful.html; settings: /en/latest/tutorial/settings.html and
    the settings API reference)
-   Type: official-docs
-   Claims:
    1. What PBT is for, in the project's own words: you "write tests which
       should pass for all inputs in whatever range you describe, and let
       Hypothesis randomly choose which of those inputs to check - including
       edge cases you might not have thought about" — evidence: docs front page,
       verbatim.
    2. Stateful/rule-based testing generates programs, not just data: a
       `RuleBasedStateMachine` "takes values drawn from strategies and passes
       them to a user defined test function," where rules "can be chained
       together - a single test run may involve multiple rule invocations, which
       may interact in various ways" — evidence: stateful.html, verbatim.
    3. Bundles carry state between rules ("a named collection of generated
       values that can be reused by other operations in the test... allowing
       data to flow from one rule to another") and `invariant()` marks checks
       "to be run after every step"; failures shrink to "a very short program
       that will demonstrate the problem" — evidence: stateful.html, verbatim.
    4. The docs' own scoping advice: stateful machinery is not the default —
       "For simpler cases though, you might not need them at all - a standard
       test with @given might be enough" — evidence: stateful.html, verbatim.
    5. Settings profiles are the sanctioned CI-vs-dev mechanism: "You can
       configure test behavior across your test suite using a settings profile"
       via `settings.register_profile()` in `conftest.py`, selected by
       environment variable (`HYPOTHESIS_PROFILE`) or `--hypothesis-profile`;
       `max_examples` (default: "stop after generating 100 test cases") is the
       rigor/speed dial; a built-in "ci" profile sets `derandomize=True`,
       `deadline=None`, `database=None`, `print_blob=True` — evidence:
       tutorial/settings.html verbatim plus the settings API reference (built-in
       profiles).
-   Tensions: `derandomize=True` for CI is a deliberate trade of bug-finding
    power for reproducibility — the docs institutionalize the
    fast-feedback/protection-against-regressions tension Khorikov's pillars
    describe. Stateful testing's deliberately interleaved operations invert
    Meszaros's Fresh Fixture instinct (no interaction between test steps);
    Hypothesis makes the interaction safe by owning generation, shrinking, and
    replay. Random generation is also maximally unlike "the way your software is
    used," cutting against Dodds's resemblance principle — PBT buys edge-case
    discovery at the cost of realism.

### Cluster tensions

**Classical vs London (Khorikov vs Freeman & Pryce), adjudicated.** This is a
genuine, symmetric disagreement, not a misreading. GOOS says mocks earn their
keep _inside_ the system: "Mock Objects is misnamed. It is really a technique
for identifying types... based on the roles that objects play," and — answering
the boundary objection explicitly — "We believe the opposite, that Mock Objects
are most useful when used to drive the design of the code under test" (Mock
Roles §5.2). Khorikov says precisely the inverse: communication-based
verification ranks last of the three styles because it "introduces coupling
between the tests and the SUT's implementation details"; mocks belong only at
unmanaged out-of-process boundaries, and "Mocks are for integration tests only"
(ch. 9.2). The crux is what counts as contract: for GOOS, the role interfaces an
object _requires_ are the design itself, discovered through the mocks; for
Khorikov, anything not externally observable is an implementation detail that
refactoring must be free to change. The disagreement narrows on three shared
commitments both sides state in print: (a) only mock types you own (Mock Roles
§4.1; Khorikov ch. 9.2 adopts it verbatim); (b) over-specified interaction tests
are a failure mode (Mock Roles §4.4: tests "over-specified to check features
that are an artefact of the implementation"; Khorikov's entire
resistance-to-refactoring pillar); (c) test pain is design feedback (GOOS ch.
20; Khorikov's "good negative indicator" litmus). What remains irreducible is
temporal: GOOS uses mocks _during_ design, when interfaces are still fluid and
the mock is the cheapest way to sketch them; Khorikov evaluates tests _after_
design, when surviving refactoring is the measure of worth. A dossier consumer
should record that the London style is load-bearing only while its premise holds
— that the discovered role interfaces stabilize into honored contracts — and
that Khorikov, Dodds ("Testing Implementation Details"), and Meszaros's Fragile
Test/Behavior Sensitivity all document what happens when that premise fails.

**Trophy vs pyramid (Dodds vs Beck-era unit emphasis), adjudicated.** Dodds's
trophy makes integration the largest investment ("Integration tests strike a
great balance on the trade-offs between confidence and speed/expense") and adds
a static-analysis base, explicitly revising the unit-heavy pyramid tradition
descending from Beck's fine-grained programmer tests. Two findings blunt the
apparent contradiction. First, Beck's "unit" discipline is about test
_independence_ (Isolated Test: tests must not affect each other), not about
isolating the SUT behind doubles — Beck is classical, and Canon TDD refuses
prescription outright ("What follows is NOT how _you_ should _do_ TDD"). Second,
Khorikov shows the two vocabularies measure different things: a classical "unit
test" covers a unit of _behavior_, possibly many classes with real collaborators
— which is materially what Dodds calls an integration test in a frontend
context, where Testing Library renders real component trees against a real DOM.
The remaining genuine disagreement is empirical and stack-dependent: which layer
maximizes confidence per unit cost. Dodds's answer (integration) is calibrated
to modern frontend tooling, where multi-unit tests are nearly as fast as unit
tests and user-resembling by construction; Khorikov's answer (unit tests on the
domain model, integration tests over managed dependencies) is calibrated to
enterprise backends with heavy out-of-process edges. Both reject the same
failure modes — coverage-number targets, mock-everything isolation,
E2E-everything — so the tension resolves to a sizing heuristic conditioned on
the cost curve of the stack, not a contradiction of principle. All parties'
shared metric is Khorikov's economics: maximum confidence per unit of
maintenance cost; the trophy and pyramid are competing empirical claims about
where that maximum sits.

## Dossier section: Python testing tooling — ground truth as of 2026-07-26

Scope: current stable versions (PyPI JSON), doc-recommended patterns for the
major packages, and contradictions against
`/Users/gaohn/gaohn/packages/omniagents/plugins/python/skills/testing/SKILL.md`
(981 lines, read in full on 2026-07-26). Line numbers refer to that file.

Verification method: `https://pypi.org/pypi/<pkg>/json` via WebFetch for every
version; official docs via WebFetch + Context7 (`/websites/pytest_en_stable`,
`/websites/hypothesis_readthedocs_io_en`) for patterns. Pattern bullets for
minor packages are canonical README/docs usage, version-checked only.

### pytest

-   Current stable: 9.1.1 (evidence: https://pypi.org/pypi/pytest/json, checked
    2026-07-26)
-   Python support: >=3.10 (classifiers 3.10–3.15)
-   Docs-recommended patterns:
    -   `strict = true` umbrella confirmed: pytest's own option help reads
        "Enables all strictness options, currently: strict_config,
        strict_markers, strict_xfail, strict_parametrization_ids"; individual
        options explicitly set take precedence, and future strictness options
        join automatically — docs recommend it "only for pinned pytest
        versions". https://docs.pytest.org/en/stable/reference/reference.html
        and https://docs.pytest.org/en/stable/explanation/goodpractices.html
    -   `strict_xfail` "was previously named `xfail_strict`" (reference docs);
        skipping.html still accepts both spellings.
        https://docs.pytest.org/en/stable/how-to/skipping.html
    -   Native `[tool.pytest]` TOML table "supported since pytest 9.0" (native
        TOML types); `[tool.pytest.ini_options]` remains the INI-compat mode
        (since 6.0). `pytest.toml` / hidden `.pytest.toml` with a `[pytest]`
        table: "Added in version 9.0", and "pytest.toml files take precedence
        over other files, even when empty".
        https://docs.pytest.org/en/stable/reference/customize.html
    -   `subtests` fixture: "Added in version 9.0", "originally implemented as a
        separate plugin in pytest-subtests, but since 9.0 has been merged into
        the core", and "This feature is experimental. Its behavior, particularly
        how failures are reported, may evolve" — plus a `verbosity_subtests`
        config option exists.
        https://docs.pytest.org/en/stable/how-to/subtests.html
    -   `faulthandler_exit_on_timeout` (default false): passes `exit=True` to
        `faulthandler.dump_traceback_later()` so a deadlocked run ends instead
        of hanging; listed under 9.0 new features in the changelog.
        https://docs.pytest.org/en/stable/reference/reference.html
-   Deprecated/renamed since ~2024:
    -   `xfail_strict` → `strict_xfail` (old name still accepted).
    -   `--strict` CLI flag repurposed: now enables the `strict` umbrella mode.
    -   `PytestRemovedIn9Warning`-gated features: errors by default in 9.0,
        **removed in 9.1 — which has now shipped** (current stable is 9.1.1).
-   Contradictions with SKILL.md:
    -   SKILL.md:798–801 — the skill frames the 9.1 removals as a _future_
        migration deadline ("the features behind it are removed in 9.1. The
        `filterwarnings` entry ... stops working at 9.1 — that is a migration
        deadline"). pytest 9.1.1 is the current stable, so the deadline has
        passed: the escape hatch is already gone and the paragraph should be
        present-tense ("removed as of 9.1") or dropped. Evidence:
        https://pypi.org/pypi/pytest/json +
        https://docs.pytest.org/en/stable/changelog.html
    -   SKILL.md:794–797 — "pytest errors when both tables are present"
        ([tool.pytest] + [tool.pytest.ini_options]): **not confirmed, not
        contradicted** — the customize.html page fetched does not state the
        both-tables behavior. Verify against a live pytest before restating as
        fact. https://docs.pytest.org/en/stable/reference/customize.html
    -   Everything else checked is accurate: strict umbrella membership
        (SKILL.md:107–111, 785–791), xfail_strict redundancy (SKILL.md:791),
        subtests-in-core + experimental caveat (SKILL.md:500–508),
        faulthandler_exit_on_timeout new in 9.0 (SKILL.md:802–805), native-TOML
        claims (SKILL.md:742, 792–797 first half).

### pytest-asyncio

-   Current stable: 1.4.0 (evidence: https://pypi.org/pypi/pytest-asyncio/json,
    checked 2026-07-26)
-   Python support: >=3.10 (classifiers 3.10–3.14)
-   Docs-recommended patterns:
    -   `asyncio_mode`: default `strict` (explicit `@pytest.mark.asyncio` +
        `@pytest_asyncio.fixture`); docs call auto mode "the simplest test and
        fixture configuration and is the recommended default", with strict mode
        preferred when multiple async libraries coexist.
        https://pytest-asyncio.readthedocs.io/en/latest/concepts.html
    -   `asyncio_default_fixture_loop_scope`: unset is deprecated/warned; docs
        advise setting it explicitly — future versions default it to `function`.
        `asyncio_default_test_loop_scope` defaults to `function`.
        https://pytest-asyncio.readthedocs.io/en/latest/reference/configuration.html
    -   Per-test/per-fixture loop sharing via `loop_scope` kwarg
        (`@pytest.mark.asyncio(loop_scope="module")`); docs: "It's highly
        recommended for neighboring tests to use the same event loop scope."
        https://pytest-asyncio.readthedocs.io/en/latest/concepts.html
    -   `asyncio_debug` option enables asyncio debug mode for the event loop.
        https://pytest-asyncio.readthedocs.io/en/latest/reference/configuration.html
-   Deprecated/renamed since ~2024: the v0.x `event_loop` fixture override
    mechanism was removed in the 1.0 line (loop scoping replaced it); unset
    `asyncio_default_fixture_loop_scope` emits a deprecation warning.
-   Contradictions with SKILL.md: none found — SKILL.md:478–480 ("pin the loop
    scope deliberately in config rather than relying on plugin defaults that
    shift between majors") matches the documented deprecation posture, and
    SKILL.md:874–876 (asyncio vs anyio, don't enable both auto modes) is
    consistent.

### pytest-randomly

-   Current stable: 4.1.0 (evidence: https://pypi.org/pypi/pytest-randomly/json,
    checked 2026-07-26)
-   Python support: >=3.10 (classifiers 3.10–3.14)
-   Docs-recommended patterns (version check only):
    -   Installed = active; prints `Using --randomly-seed=...` so failures
        reproduce with `-p randomly --randomly-seed=<n>`.
        https://github.com/pytest-dev/pytest-randomly
    -   Also reseeds `random`, and (if installed) numpy/faker/factory-boy per
        test. https://github.com/pytest-dev/pytest-randomly
-   Deprecated/renamed since ~2024: none found (4.x dropped older Pythons only).
-   Contradictions with SKILL.md: none found (SKILL.md:120–123, 653–655
    consistent).

### pytest-cov

-   Current stable: 7.1.0 (evidence: https://pypi.org/pypi/pytest-cov/json,
    checked 2026-07-26)
-   Python support: >=3.9 (classifiers 3.9–3.14)
-   Docs-recommended patterns (version check only):
    -   `--cov=src --cov-branch --cov-report=term-missing`, config delegated to
        `[tool.coverage.*]`; xdist-aware combining is built in.
        https://pytest-cov.readthedocs.io/
-   Deprecated/renamed since ~2024: pytest-cov 6→7 raised floors (newer
    coverage.py required); no flag renames found.
-   Contradictions with SKILL.md: none found (skill configures coverage.py
    directly at SKILL.md:760–772, which is compatible).

### pytest-timeout

-   Current stable: 2.4.0 (evidence: https://pypi.org/pypi/pytest-timeout/json,
    checked 2026-07-26)
-   Python support: >=3.7 (classifiers 3.7–3.13; **no 3.14 classifier**)
-   Docs-recommended patterns (version check only):
    -   `timeout = N` ini / `@pytest.mark.timeout(N)`; signal vs thread methods.
        https://pypi.org/project/pytest-timeout/
-   Deprecated/renamed since ~2024: none found.
-   Contradictions with SKILL.md: none found — SKILL.md:977 ("publishes no
    Python 3.14 classifier — verify before adding it to a 3.14+ project") is
    **confirmed still true** at 2.4.0. Note pytest 9's own
    `faulthandler_timeout` + `faulthandler_exit_on_timeout` (SKILL.md:747–748)
    now covers the hang-kill use case in core, which weakens the case for the
    plugin.

### pytest-xdist

-   Current stable: 3.8.0 (evidence: https://pypi.org/pypi/pytest-xdist/json,
    checked 2026-07-26)
-   Python support: >=3.9 (classifiers 3.9–3.13; **no 3.14 classifier**)
-   Docs-recommended patterns (version check only):
    -   `pytest -n auto`; `--dist` modes (`load`, `loadscope`, `loadgroup`,
        `worksteal`); per-worker resources keyed on `worker_id` fixture /
        `PYTEST_XDIST_WORKER`. https://pytest-xdist.readthedocs.io/
-   Deprecated/renamed since ~2024: none found.
-   Contradictions with SKILL.md: SKILL.md:121–122 and 653 mandate
    `pytest -n auto` in a declared "Python 3.14+" baseline (SKILL.md:49) with no
    classifier caveat, while the skill gives pytest-timeout exactly that caveat
    at SKILL.md:977 — inconsistent standard: pytest-xdist 3.8.0 likewise
    publishes no 3.14 classifier (evidence:
    https://pypi.org/pypi/pytest-xdist/json). Either both get the caveat or
    neither does.

### hypothesis

-   Current stable: 6.161.5 (evidence: https://pypi.org/pypi/hypothesis/json,
    checked 2026-07-26)
-   Python support: >=3.10 (classifiers 3.10–3.14)
-   Docs-recommended patterns:
    -   Profiles via `settings.register_profile(...)` /
        `settings.load_profile(...)`, selected by
        `pytest --hypothesis-profile <name>` or a `HYPOTHESIS_PROFILE` env var.
        https://hypothesis.readthedocs.io/en/latest/ (tutorial/settings)
    -   **Built-in profiles ship with the library**: a "default" profile
        (max_examples=100, deadline=200ms, stateful_step_count=50) and a "ci"
        profile (parent=default, `derandomize=True`, `deadline=None`,
        `database=None`, `print_blob=True`, suppress `HealthCheck.too_slow`)
        that is **auto-loaded when a CI environment is detected**
        (`if is_in_ci(): settings.load_profile("ci")`).
        https://hypothesis.readthedocs.io/en/latest/_modules/hypothesis/_settings.html
    -   Extending the built-in ci profile is the documented move:
        `settings.register_profile("ci", settings.get_profile("ci"), max_examples=1000)`.
        https://hypothesis.readthedocs.io/en/latest/_modules/hypothesis/_settings.html
    -   `@example` pins alongside `@given` for regression counterexamples.
        https://hypothesis.readthedocs.io/
    -   Stateful: `RuleBasedStateMachine` + `@rule` / `@invariant` / `Bundle`,
        exposed to the runner as `TestTrees = DatabaseComparison.TestCase`;
        `stateful_step_count` trades program length vs number of runs.
        https://hypothesis.readthedocs.io/en/latest/stateful.html
-   Deprecated/renamed since ~2024: none found affecting the skill's surface
    (profiles, @example, stateful API all stable).
-   Contradictions with SKILL.md: SKILL.md:529–530 — "Register hypothesis
    profiles (`dev` small/fast, `ci` more examples, explicit `deadline`) so
    local runs stay quick and CI stays thorough" is behind current behavior on
    two points: (1) Hypothesis now auto-detects CI and auto-loads its built-in
    `ci` profile, so a hand-registered `ci` profile silently overrides/interacts
    with a built-in one — worth stating; (2) the built-in ci profile
    deliberately sets `deadline=None` (deadlines off in CI because shared
    runners are noisy), so "explicit `deadline`" in CI runs against upstream's
    own recommendation; explicit deadlines make sense in the dev profile, not
    ci. Evidence:
    https://hypothesis.readthedocs.io/en/latest/_modules/hypothesis/_settings.html

### time-machine

-   Current stable: 3.2.0 (evidence: https://pypi.org/pypi/time-machine/json,
    checked 2026-07-26)
-   Python support: >=3.10 (classifiers 3.10–3.14)
-   Docs-recommended patterns (version check only):
    -   `time_machine.travel(dest, tick=False)` as decorator/context manager;
        pytest `time_machine` fixture (`time_machine.move_to(...)`).
        https://github.com/adamchainz/time-machine
-   Deprecated/renamed since ~2024: 3.0 dropped Python <3.10; API stable.
-   Contradictions with SKILL.md: none found (SKILL.md:50–51, 366–369, 855–857
    consistent; `tick=False` is current API).

### freezegun

-   Current stable: 1.5.5 (evidence: https://pypi.org/pypi/freezegun/json,
    checked 2026-07-26)
-   Python support: >=3.8 (classifiers 3.8–3.13; no 3.14 classifier)
-   Docs-recommended patterns (version check only):
    -   `@freeze_time("2026-01-01")` decorator/context manager; `tick=True`,
        `auto_tick_seconds`. https://github.com/spulec/freezegun
-   Deprecated/renamed since ~2024: none found; slower C-level coverage than
    time-machine (freezegun patches at the Python level).
-   Contradictions with SKILL.md: none found — the skill never mentions
    freezegun and standardizes on time-machine (SKILL.md:50–51); freezegun's
    missing 3.14 classifier supports that choice for a 3.14+ baseline.

### testcontainers (Python)

-   Current stable: 4.15.0 (evidence: https://pypi.org/pypi/testcontainers/json,
    checked 2026-07-26)
-   Python support: >=3.10 (classifiers 3.10–3.14)
-   Docs-recommended patterns:
    -   Context-manager lifecycle is canonical:
        `with PostgresContainer("postgres:16") as postgres:` — cleanup on scope
        exit, plus Ryuk reaper as backstop (`TESTCONTAINERS_RYUK_DISABLED`
        etc.). https://testcontainers-python.readthedocs.io/en/latest/
    -   `get_connection_url()` returns a SQLAlchemy-compatible URL;
        `driver=None` for psycopg v3.
        https://testcontainers-python.readthedocs.io/en/latest/
    -   Per-module extras installs: `pip install testcontainers[postgres]`;
        **database drivers are no longer bundled dependencies** — the project
        must declare its own (psycopg2/psycopg).
        https://testcontainers-python.readthedocs.io/en/latest/
    -   Session-scoped pytest fixture wrapping the context manager (the skill's
        SKILL.md:582–597 example is the documented shape).
-   Deprecated/renamed since ~2024: 4.x dropped bundled DB driver deps (declare
    your own).
-   Contradictions with SKILL.md: none found — the SKILL.md:582–597 fixture
    matches current docs. Minor completeness note: the example presumes a
    psycopg2-style driver is installed; with psycopg v3,
    `get_connection_url(driver=None)` is the documented form
    (https://testcontainers-python.readthedocs.io/en/latest/).

### respx

-   Current stable: 0.23.1 (evidence: https://pypi.org/pypi/respx/json, checked
    2026-07-26)
-   Python support: >=3.8 (classifiers 3.8–3.14)
-   Docs-recommended patterns:
    -   Activate via `@respx.mock` decorator, `with respx.mock:` context
        manager, or the `respx_mock` pytest fixture (configured with
        `@pytest.mark.respx(...)`). https://lundberg.github.io/respx/guide/
    -   Routes:
        `respx.get("https://example.org/").mock(return_value=httpx.Response(200))`;
        lower-level `respx.route()` with pattern lookups/regex.
        https://lundberg.github.io/respx/guide/
    -   Error simulation: `.mock(side_effect=httpx.ConnectError)`.
        https://lundberg.github.io/respx/guide/
    -   Assertions: `route.called`, `route.call_count`, router-level
        `assert_all_called` / `assert_all_mocked`.
        https://lundberg.github.io/respx/guide/
    -   Selective real traffic: `respx.route(host="localhost").pass_through()`.
        https://lundberg.github.io/respx/guide/
-   Deprecated/renamed since ~2024: none found.
-   Contradictions with SKILL.md: none found (SKILL.md:610–614, 858–860
    MockTransport-vs-respx decision rule consistent with current respx docs).

### responses

-   Current stable: 0.26.2 (evidence: https://pypi.org/pypi/responses/json,
    checked 2026-07-26)
-   Python support: >=3.8 (classifiers 3.8–3.13); requires requests >=2.30
-   Docs-recommended patterns (version check only):
    -   `@responses.activate` + `responses.add(...)` / `responses.get(...)`;
        `RequestsMock` context manager; for the `requests` library only.
        https://github.com/getsentry/responses
-   Deprecated/renamed since ~2024: none found.
-   Contradictions with SKILL.md: none found — the skill is httpx-first and
    never recommends responses; keep it as the requests-stack counterpart only.

### schemathesis

-   Current stable: 4.24.3 (evidence: https://pypi.org/pypi/schemathesis/json,
    checked 2026-07-26)
-   Python support: >=3.10 (classifiers 3.10–3.14)
-   Docs-recommended patterns:
    -   v4 namespaced loaders: `schemathesis.openapi.from_url` / `from_path` /
        `from_asgi` / `from_wsgi` / `from_dict`; pytest-fixture loading via
        `schemathesis.pytest.from_fixture`.
        https://schemathesis.readthedocs.io/en/stable/migration/
    -   pytest integration: `@schema.parametrize()` with
        `case.call_and_validate()` (Pytest Tutorial).
        https://schemathesis.readthedocs.io/en/stable/
    -   CLI: `schemathesis run https://example.schemathesis.io/openapi.json`.
        https://schemathesis.readthedocs.io/en/stable/
    -   CLI renames: `--hypothesis-max-examples` → `--max-examples`;
        `--data-generation-methods` → `--mode`.
        https://schemathesis.readthedocs.io/en/stable/migration/
    -   API renames/removals: `DataGenerationMethod` → `GenerationMode`,
        `schemathesis.target` → `schemathesis.metric`; `add_case` /
        `process_call_kwargs` hooks and aiohttp support removed.
        https://schemathesis.readthedocs.io/en/stable/migration/
-   Deprecated/renamed since ~2024: the entire v3 API surface (see renames
    above) — v4 is a breaking release with a dedicated migration guide.
-   Contradictions with SKILL.md: none found — the skill names schemathesis only
    at concept level (SKILL.md:620–623, 946–948) with no v3 API references. If
    the restructure adds code examples, they must use the v4 namespaced loaders
    above.

### mutmut

-   Current stable: 3.6.0 (evidence: https://pypi.org/pypi/mutmut/json, checked
    2026-07-26)
-   Python support: >=3.10 (classifiers 3.10–3.14)
-   Docs-recommended patterns:
    -   Config in `pyproject.toml` `[tool.mutmut]` with array values:
        `source_paths = ["src/"]`,
        `pytest_add_cli_args_test_selection = ["tests/"]` (setup.cfg `[mutmut]`
        also accepted). https://mutmut.readthedocs.io/en/latest/
    -   CLI: `mutmut run` (drives pytest), `mutmut results`, `mutmut show`,
        `mutmut browse` (interactive TUI with retest), `mutmut apply <mutant>`
        (only on committed code). https://mutmut.readthedocs.io/en/latest/
    -   State lives in a `mutants/` directory — runs are resumable; delete the
        directory to force a full restart.
        https://mutmut.readthedocs.io/en/latest/
    -   Requires fork support: "if you want to run on windows, you must run
        inside WSL". https://mutmut.readthedocs.io/en/latest/
    -   3.x mutates only code inside functions; docs point to mutmut 2's
        different execution model for module-level code.
        https://mutmut.readthedocs.io/en/latest/
-   Deprecated/renamed since ~2024: mutmut 2.x execution model and its config
    keys (e.g. `paths_to_mutate`, `runner`) superseded by 3.x (`source_paths`,
    built-in pytest driving, `mutants/` copy-and-trampoline model).
-   Contradictions with SKILL.md: none found — the skill references mutmut only
    at concept level (SKILL.md:648–650). If the restructure adds config/CLI
    examples, they must use the 3.x keys (`source_paths`, not 2.x
    `paths_to_mutate`), and a G2 mutation job cannot run on native Windows
    runners.

### pact-python

-   Current stable: 3.4.0 (evidence: https://pypi.org/pypi/pact-python/json,
    checked 2026-07-26)
-   Python support: >=3.10 (classifiers 3.10–3.14, "3 :: Only")
-   Docs-recommended patterns (version check only):
    -   v3 is the Rust-FFI-based rewrite (Pact specification v3/v4 support);
        consumer tests build interactions on a `Pact` object and replay them
        against the mock provider; provider verification via the Verifier
        against a broker. https://pact-foundation.github.io/pact-python/ and
        https://docs.pact.io/implementation_guides/python
-   Deprecated/renamed since ~2024: the pre-3.0
    (`pact.Consumer`/Ruby-CLI-backed) API is superseded by the pact-python 3.x
    FFI API — code samples from the 2.x era do not carry forward.
-   Contradictions with SKILL.md: none found — the skill names Pact only at
    concept level (SKILL.md:617–623, 946–948). Any added examples must target
    the 3.x API.

### stamina

-   Current stable: 26.1.0 (evidence: https://pypi.org/pypi/stamina/json,
    checked 2026-07-26)
-   Python support: >=3.10 (classifiers 3.10–3.14)
-   Docs-recommended patterns:
    -   `stamina.set_testing(True)` — testing mode: drops backoff entirely and
        caps attempts at 1 by default; `stamina.set_testing(True, attempts=2)`
        to raise the cap. https://stamina.hynek.me/en/stable/testing.html
    -   Global deactivation: `stamina.set_active(False)`; docs' canonical pytest
        pattern is an autouse session fixture calling it — exactly the shape the
        skill prescribes. https://stamina.hynek.me/en/stable/testing.html
    -   Testing mode recommended for iterator-based `stamina.retry_context()`
        call sites where deactivation alone does not shortcut the loop.
        https://stamina.hynek.me/en/stable/testing.html
-   Deprecated/renamed since ~2024: none found (CalVer; testing API stable).
-   Contradictions with SKILL.md: none found — SKILL.md:394–398 (`set_testing()`
    caps attempts and drops backoff sleep; autouse `stamina.set_active(False)`
    for non-retry tests) matches current docs verbatim.

### Summary of contradictions

| SKILL.md line | Package      | Finding                                                                                                                                                                                                                                                                                 | Evidence                                                                            |
| ------------- | ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| 798–801       | pytest       | `PytestRemovedIn9Warning` removals framed as a future 9.1 deadline; pytest 9.1.1 is current stable — the removal has shipped, the `filterwarnings` escape hatch is already dead. Rewrite in present tense.                                                                              | https://pypi.org/pypi/pytest/json, https://docs.pytest.org/en/stable/changelog.html |
| 794–797       | pytest       | "pytest errors when both tables are present" is asserted but not confirmed by the current customize docs — unverified claim, not contradicted; verify before restating.                                                                                                                 | https://docs.pytest.org/en/stable/reference/customize.html                          |
| 121–122, 653  | pytest-xdist | Skill mandates `-n auto` under a Python 3.14+ baseline with no caveat, yet flags pytest-timeout for lacking a 3.14 classifier (line 977); pytest-xdist 3.8.0 also publishes no 3.14 classifier — apply the caveat consistently or drop it.                                              | https://pypi.org/pypi/pytest-xdist/json                                             |
| 529–530       | hypothesis   | "Register profiles (… `ci` more examples, explicit `deadline`)" ignores that Hypothesis now ships and **auto-loads** a built-in `ci` profile in CI, and that profile sets `deadline=None` — upstream's CI recommendation is deadlines _off_, the opposite of "explicit deadline" in CI. | https://hypothesis.readthedocs.io/en/latest/_modules/hypothesis/_settings.html      |

Confirmed-accurate freshness claims worth keeping: SKILL.md:977 (pytest-timeout
still has no 3.14 classifier at 2.4.0 — verified true on 2026-07-26);
SKILL.md:107–111 and 784–805 pytest 9 facts (strict umbrella membership,
strict_xfail rename, native TOML, faulthandler_exit_on_timeout) all verified
against current pytest docs; SKILL.md:394–398 stamina helpers verified verbatim
against current stamina docs.

## Dossier section: TypeScript testing tooling — ground truth (checked 2026-07-26)

Scope: current stable versions + currently-recommended patterns for the packages
the `plugins/typescript/skills/testing/SKILL.md` skill depends on, and every
place that skill contradicts current docs. Skill file audited:
`/Users/gaohn/gaohn/packages/omniagents/plugins/typescript/skills/testing/SKILL.md`
(513 lines).

### vitest

-   Current stable: 4.1.10 (evidence: https://registry.npmjs.org/vitest/latest,
    checked 2026-07-26)
-   Node/peer support: Node `^20.0.0 || ^22.0.0 || >=24.0.0`; peer
    `vite ^6.0.0 || ^7.0.0 || ^8.0.0`; optional peers include
    `@vitest/coverage-v8`, `@vitest/browser-playwright`
-   Docs-recommended patterns:
    -   Config via `defineConfig` from `vitest/config` with options under
        `test`; multi-environment layout via `test.projects` (the `workspace`
        option was renamed to `projects` in Vitest 3.2 and removed in 4) —
        https://vitest.dev/guide/migration.html
    -   Coverage: `coverage.all` and `coverage.extensions` removed in v4; when
        `coverage.include` is unset, "coverage report will include only files
        that were loaded during test run" —
        https://vitest.dev/guide/migration.html
    -   Mock hygiene config: `restoreMocks` runs `vi.restoreAllMocks()` before
        each test, `mockReset` runs `vi.resetAllMocks()`, `clearMocks` runs
        `vi.clearAllMocks()`; in v4 `vi.restoreAllMocks` "no longer resets the
        state of spies and only restores spies created manually with `vi.spyOn`"
        — https://vitest.dev/guide/migration.html
    -   Fake timers: `vi.useFakeTimers()` by default "fakes everything globally
        available except `nextTick` and `queueMicrotask`"; scope with
        `fakeTimers.toFake`/`toNotFake` (mutually exclusive); `nextTick`
        unsupported under `--pool=forks` —
        https://vitest.dev/config/#faketimers-tofake
    -   Type testing: `*.test-d.ts` files run under the `--typecheck` flag using
        `expectTypeOf` / `assertType`; internally invokes `tsc --noEmit` —
        https://vitest.dev/guide/testing-types.html
    -   `allowOnly` defaults to `!process.env.CI`, so `.only` fails in CI by
        default — https://vitest.dev/config/#allowonly
-   Deprecated/renamed since ~2024:
    -   `test.workspace` → `test.projects` (renamed 3.2, removed in 4) —
        https://vitest.dev/guide/migration.html
    -   `coverage.all`, `coverage.extensions`, `coverage.ignoreEmptyLines`
        removed in v4 — https://vitest.dev/guide/migration.html
    -   `poolOptions` removed (options hoisted to top level);
        `maxThreads`/`maxForks` → `maxWorkers` —
        https://vitest.dev/guide/migration.html
    -   `vi.restoreAllMocks` behavior narrowed in v4 to `vi.spyOn`-created spies
        only — https://vitest.dev/guide/migration.html
-   Contradictions with SKILL.md:
    -   SKILL.md:72–76 — skill presents `restoreMocks: true` (+
        `unstubEnvs`/`unstubGlobals`) as the complete config-level mock-hygiene
        story ("a manual `afterEach(() => vi.restoreAllMocks())` … is the
        version of this that one file forgets"). In Vitest 4, `restoreAllMocks`
        (and therefore `restoreMocks: true`) only restores `vi.spyOn` spies and
        no longer resets mock state — `vi.fn()` call history and
        `mockResolvedValueOnce` queues leak between tests unless
        `clearMocks`/`mockReset` is also set.
        https://vitest.dev/guide/migration.html
    -   SKILL.md:111 (and 501) — skill calls `projects` "the Vitest 4
        replacement for `workspace`"; docs say the rename happened in Vitest 3.2
        (v4 only removed the old name). Minor precision issue.
        https://vitest.dev/guide/migration.html
    -   SKILL.md:195–198 — skill justifies
        `toFake: ["setTimeout", "clearTimeout"]` with "Faking microtasks or
        `queueMicrotask` wholesale can wedge `fetch`/undici body reads",
        implying the default fakes microtasks. Docs: the default already
        excludes `nextTick` and `queueMicrotask`; faking them is opt-in only.
        (Scoping `toFake` remains a legitimate choice, but the stated hazard
        misstates the default; note the skill's minimal list also leaves `Date`
        un-faked, which its own `vi.setSystemTime` guidance elsewhere assumes.)
        https://vitest.dev/config/#faketimers-tofake

### @testing-library/react

-   Current stable: 16.3.2 (evidence:
    https://registry.npmjs.org/@testing-library/react/latest, checked
    2026-07-26)
-   Node/peer support: Node >=18; peers `@testing-library/dom ^10.0.0`, `react`
    / `react-dom` `^18.0.0 || ^19.0.0`
-   Docs-recommended patterns:
    -   Guiding principle: "The more your tests resemble the way your software
        is used, the more confidence they can give you"; test DOM nodes, not
        component instances —
        https://testing-library.com/docs/guiding-principles/
    -   Query priority: accessible-to-everyone first (`getByRole` →
        `getByLabelText` → `getByPlaceholderText` → `getByText` →
        `getByDisplayValue`), then semantic (`getByAltText`, `getByTitle`), then
        `getByTestId` as last resort —
        https://testing-library.com/docs/queries/about/#priority
    -   `data-testid` "only recommended for cases where you can't match by role
        or text" — https://testing-library.com/docs/queries/about/#priority
-   Deprecated/renamed since ~2024: RTL 16 (2024) moved `@testing-library/dom`
    from a direct dependency to a required peer dependency —
    https://github.com/testing-library/react-testing-library/releases/tag/v16.0.0
-   Contradictions with SKILL.md: none found

### @testing-library/dom

-   Current stable: 10.4.1 (evidence:
    https://registry.npmjs.org/@testing-library/dom/latest, checked 2026-07-26)
-   Node/peer support: Node >=18
-   Docs-recommended patterns:
    -   Same query-priority ladder as above (this package defines it) —
        https://testing-library.com/docs/queries/about/#priority
    -   Async UI via `findBy*` (getBy + waitFor) rather than manual polling —
        https://testing-library.com/docs/dom-testing-library/api-async/
-   Deprecated/renamed since ~2024: none found
-   Contradictions with SKILL.md: none found

### @testing-library/user-event

-   Current stable: 14.6.1 (evidence:
    https://registry.npmjs.org/@testing-library/user-event/latest, checked
    2026-07-26)
-   Node/peer support: Node >=12, npm >=6; peer `@testing-library/dom >=7.21.4`
-   Docs-recommended patterns:
    -   `userEvent.setup()` before interaction; the returned instance's methods
        dispatch full realistic event sequences —
        https://testing-library.com/docs/user-event/setup/
    -   Preferred over `fireEvent` because it simulates complete user
        interactions (pointer, focus, keyboard), not single synthetic events —
        https://testing-library.com/docs/user-event/intro/
-   Deprecated/renamed since ~2024: none found (v14 API unchanged since 2022)
-   Contradictions with SKILL.md: none found

### msw

-   Current stable: 2.15.0 (evidence: https://registry.npmjs.org/msw/latest,
    checked 2026-07-26)
-   Node/peer support: Node >=18; optional peer `typescript >= 4.8.x`
-   Docs-recommended patterns:
    -   Handlers: `http.get('/users/:id', resolver)` from `"msw"`; resolver
        receives `{ request, params, cookies, requestId }`; respond with
        `HttpResponse.json(...)`; query params never go in the path predicate —
        https://mswjs.io/docs/http/intercepting-requests/
    -   Node integration: `setupServer` from `"msw/node"`; lifecycle
        `beforeAll(() => server.listen())`,
        `afterEach(() => server.resetHandlers())`,
        `afterAll(() => server.close())` —
        https://mswjs.io/docs/integrations/node
    -   `server.listen({ onUnhandledRequest })` accepts `"warn"` (default) |
        `"error"` | `"bypass"` | callback —
        https://mswjs.io/docs/api/setup-server/listen
    -   Per-test overrides via `server.use(...)` reset by `resetHandlers()` —
        https://mswjs.io/docs/integrations/node
-   Deprecated/renamed since ~2024: none found in the ~2024+ window (the
    `rest.get` → `http.get` / `HttpResponse` rename was the 1.x→2.0 break, Oct
    2023 — https://mswjs.io/docs/migrations/1.x-to-2.x/)
-   Contradictions with SKILL.md: none found (skill's
    `onUnhandledRequest: "error"` is a deliberate tightening of the `"warn"`
    default, and its handler/lifecycle code at SKILL.md:152–176 matches current
    API)

### fast-check

-   Current stable: 4.9.0 (evidence:
    https://registry.npmjs.org/fast-check/latest, checked 2026-07-26)
-   Node/peer support: Node >=12.17.0
-   Docs-recommended patterns:
    -   `fc.assert(fc.property(...arbitraries, predicate))` for sync,
        `fc.asyncProperty` for async; runner shrinks failures and reports the
        seed for reproduction; test-runner agnostic —
        https://fast-check.dev/docs/introduction/getting-started/
    -   Predicates may return boolean or use assertions (`expect`) directly —
        https://fast-check.dev/docs/introduction/getting-started/
    -   Model-based testing: `fc.commands` + `fc.modelRun` (with `asyncModelRun`
        / `scheduledModelRun` variants) over `ICommand` implementations remains
        the current API, no deprecation —
        https://fast-check.dev/docs/advanced/model-based-testing/
-   Deprecated/renamed since ~2024: fast-check 4 (2025) is the current major;
    long-deprecated 3.x arbitraries/aliases were dropped at the 4.0 boundary —
    https://fast-check.dev/docs/migration-guide/from-3.x-to-4.x/
-   Contradictions with SKILL.md: none found (skill's
    `fc.assert`/`fc.property`/`fc.integer({min,max})` example at
    SKILL.md:300–310 and `fc.commands` reference at 315–318 match current API)

### expect-type

-   Current stable: 1.4.0 (evidence:
    https://registry.npmjs.org/expect-type/latest, checked 2026-07-26)
-   Node/peer support: Node >=12.0.0
-   Docs-recommended patterns:
    -   `expectTypeOf` fluent API (`.toEqualTypeOf<...>()`, `.returns`,
        `.parameter(n)`, `.toBeFunction()`); Vitest re-exports it for
        `*.test-d.ts` files run under `--typecheck` —
        https://vitest.dev/guide/testing-types.html
    -   `assertType` plus `@ts-expect-error` for negative cases —
        https://vitest.dev/guide/testing-types.html
-   Deprecated/renamed since ~2024: none found (1.0 stabilized late 2024; API
    stable since)
-   Contradictions with SKILL.md: none found

### @playwright/test

-   Current stable: 1.62.0 (evidence:
    https://registry.npmjs.org/@playwright/test/latest, checked 2026-07-26)
-   Node/peer support: Node >=20
-   Docs-recommended patterns:
    -   Component testing is now first-class in plain `@playwright/test`
        (v1.62): a "stories and galleries" model where "A component test is a
        regular Playwright end-to-end test that runs against a small story
        gallery page served by your own dev server", using the built-in
        `mount()` fixture (`await mount('components/Button/Primary')`, typed
        props via `mount<typeof WithTitle>(...)`, `update(props)` / `unmount()`)
        — https://playwright.dev/docs/test-components
    -   The guide "replaces the experimental `@playwright/experimental-ct-react`
        and `@playwright/experimental-ct-vue` packages"; a migration guide from
        those packages is provided — https://playwright.dev/docs/test-components
    -   E2E boundary: Playwright frames component tests as a variant of its e2e
        tests (real browser, your own dev server) rather than a separate
        runner/config dialect — https://playwright.dev/docs/test-components
    -   1.62 release notes confirm: "Component testing moves to a stories and
        galleries model", plus AbortSignal support and WebP screenshots —
        https://playwright.dev/docs/release-notes
-   Deprecated/renamed since ~2024: `@playwright/experimental-ct-react` /
    `@playwright/experimental-ct-vue` superseded by the built-in
    stories/galleries model in 1.62 —
    https://playwright.dev/docs/test-components
-   Contradictions with SKILL.md:
    -   SKILL.md:57–58 (and 481–483) — skill declares "Browser end-to-end suites
        (Playwright) are out of scope; this skill covers unit, component, and
        service-level integration tests", i.e. Playwright = e2e-only and
        component testing belongs exclusively to Testing Library/jsdom under
        Vitest. Playwright 1.62 now ships stable, first-class component testing
        inside `@playwright/test` (no experimental package), so the skill's
        scope partition ("component tests are ours, Playwright is only e2e") no
        longer matches how Playwright draws its own boundary. The restructure
        must either acknowledge Playwright CT and state why the skill still
        prefers Testing Library, or redraw the boundary.
        https://playwright.dev/docs/test-components

### @stryker-mutator/core

-   Current stable: 9.6.1 (evidence:
    https://registry.npmjs.org/@stryker-mutator/core/latest, checked 2026-07-26)
-   Node/peer support: Node >=20.0.0
-   Docs-recommended patterns:
    -   Config file (`stryker.config.json` / `.js` / `.mjs`) or CLI;
        `testRunner` defaults to `'command'`; a dedicated Vitest runner exists:
        `@stryker-mutator/vitest-runner` 9.6.1 (peer `vitest >=2.0.0`) —
        https://stryker-mutator.io/docs/stryker-js/configuration/ and
        https://registry.npmjs.org/@stryker-mutator/vitest-runner/latest
    -   `mutate` defaults guess production files under `{src,lib}` while
        excluding `*.spec`/`*.test`/`__tests__` —
        https://stryker-mutator.io/docs/stryker-js/configuration/
    -   `thresholds: { high: 80, low: 60, break: null }` recommended defaults —
        https://stryker-mutator.io/docs/stryker-js/configuration/
    -   `"incremental": true` stores results to speed up subsequent runs;
        `plugins` defaults to `['@stryker-mutator/*']` —
        https://stryker-mutator.io/docs/stryker-js/configuration/
-   Deprecated/renamed since ~2024: none found
-   Contradictions with SKILL.md: none found (the skill invokes mutation-kill
    _reasoning_ — SKILL.md:96–97, "the mutant it fails to kill" — but names no
    Stryker tooling, flags, or config; nothing to contradict)

### testcontainers

-   Current stable: 12.0.4 (evidence:
    https://registry.npmjs.org/testcontainers/latest, checked 2026-07-26)
-   Node/peer support: no `engines` field published
-   Docs-recommended patterns:
    -   Lifecycle:
        `const container = await new GenericContainer("alpine").withExposedPorts(80).start()`;
        connect via `container.getHost()` + `container.getMappedPort(80)`
        (random host ports to avoid conflicts); teardown with
        `await container.stop()` —
        https://node.testcontainers.org/features/containers/
    -   Wait strategies gate readiness before `start()` resolves —
        https://node.testcontainers.org/features/wait-strategies/
    -   Preconfigured module packages (`@testcontainers/postgresql`,
        `@testcontainers/mongodb`, …) over hand-rolled `GenericContainer` setups
        — https://node.testcontainers.org/features/containers/
    -   Container reuse across tests via `.withReuse()` (gated by
        `TESTCONTAINERS_REUSE_ENABLE`) —
        https://node.testcontainers.org/features/containers/
-   Deprecated/renamed since ~2024: none found (the `@testcontainers/*`
    per-module split has been the shape since v10, 2023)
-   Contradictions with SKILL.md: none found (skill's globalSetup-once /
    per-worker-isolation guidance at SKILL.md:322–327 is policy layered on top
    of, not in conflict with, the documented lifecycle)

### Summary of contradictions

| SKILL.md line(s) | Skill claim                                                                                                                                  | Current docs                                                                                                                                                                                                   | URL                                          |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| 72–76            | `restoreMocks: true` (+ unstub options) is the complete config-level mock hygiene; manual `restoreAllMocks` is the inferior duplicate        | Vitest 4: `vi.restoreAllMocks` (hence `restoreMocks: true`) only restores `vi.spyOn` spies and no longer resets mock state — `vi.fn()` history/one-shot impls leak unless `clearMocks`/`mockReset` is also set | https://vitest.dev/guide/migration.html      |
| 111 (also 501)   | `projects` is "the Vitest 4 replacement for `workspace`"                                                                                     | `workspace` was renamed to `projects` in Vitest 3.2; Vitest 4 only removed the old name                                                                                                                        | https://vitest.dev/guide/migration.html      |
| 195–198          | Scoped `toFake` needed because "faking microtasks or `queueMicrotask` wholesale can wedge `fetch`/undici" — implies default fakes microtasks | Default `fakeTimers.toFake` already excludes `nextTick` and `queueMicrotask`; faking them is opt-in only                                                                                                       | https://vitest.dev/config/#faketimers-tofake |
| 57–58, 481–483   | Playwright is e2e-only; component testing belongs to this skill via Testing Library/jsdom                                                    | Playwright 1.62 ships first-class component testing in plain `@playwright/test` (stories/galleries model, built-in `mount()` fixture), replacing the experimental CT packages                                  | https://playwright.dev/docs/test-components  |

## Cross-cluster adjudications

### Pyramid vs trophy vs test sizes: two orthogonal axes, one economic dial

The three famous taxonomies are not three answers to one question; they are
answers to two different questions plus a sizing heuristic.

-   **Scope** (what code paths a test verifies) is the axis the pyramid and the
    trophy argue over: unit vs integration vs e2e.
-   **Size** (what resources a test may consume) is Google's axis: small tests
    are single-process with no sleep/I-O/network, medium may touch localhost,
    large may span machines — and ch11 states explicitly that size and scope are
    "interrelated but distinct concepts" (Google §ch11).
-   The remaining fight — how much to invest per level — is an economic dial,
    not a law. The digits disagree even within one organization (80/15/5 in the
    SWE book vs 70/20/10 in the 2015 blog, both self-hedged), Vocke softens the
    pyramid to two rules of thumb, Fowler's 2021 article shows "unit" has no
    shared definition ("24 different definitions"), and Searls's line — ratio
    debates are "a distraction" next to test quality — is quoted approvingly by
    Fowler himself. Khorikov supplies the shared metric all parties actually
    optimize: maximum confidence per unit of maintenance cost. Where that
    maximum sits is stack-dependent: Dodds's integration-heavy trophy is
    calibrated to frontend tooling where multi-unit tests are cheap and
    user-resembling by construction; Khorikov's unit-heavy allocation is
    calibrated to enterprise backends with expensive out-of-process edges.

**Consequences for the restructure.** (a) The existing gate tiers are the size
axis: G1 maps to small (hermetic, in-process), G2 to medium/large
(resource-gated), G3 to subjects outside Google's taxonomy but anticipated by
ch14's fidelity gaps. The hub should state this mapping once. (b) The
`references/` split uses BOTH axes: level files (`unit.md`, `integration.md`)
carry the scope axis; concern files carry techniques that the canon itself keeps
level-agnostic — Google puts doubles in their own chapter (ch13) rather than
inside unit testing (ch12), and Meszaros's fixture and smell patterns apply at
every level. Forcing concerns under level directories would either duplicate
them or orphan them. (c) No ratio digits anywhere in the skills: encode the
shape (fast hermetic tests dominate; each larger test justified by a named
fidelity risk per ch14) and never a percentage.

### Classical vs London: side with the classical/Google consensus, mine GOOS

Four independent sources converge on the same operational rule: Google ch13
(real implementation first, fake second, stub sparingly, interaction
verification last and only for state-changing calls), Khorikov ("only unmanaged
dependencies should be replaced with mocks"; "mocks are for integration tests
only"), Dodds ("mocking severs the real-world connection"; justified mocks are
payment providers and network), and Fowler's classicist position (doubles only
"when there's an awkward collaboration"). GOOS is the genuine dissent — "We
believe the opposite" to boundary-only mocking — but its position is
load-bearing only while role interfaces discovered via mocks stabilize into
honored contracts, and its own §4.4 concedes the over-specification failure
mode. The existing skills already sit on the consensus side (never patch the
subject's internals; fake collaborators at boundaries), so the restructure keeps
that stance and mines GOOS for the two claims everyone accepts: only mock types
you own, and test pain is design feedback.

### Double vocabulary: strict Meszaros register

The skills use the strict register — dummy, fake, stub, spy, mock, where only
mocks verify expectations (Fowler TestDouble; Meszaros p. 522; Google ch13 uses
the same distinctions). Where common usage says "mock" loosely (Vocke, most
tooling docs), the reference files may note the looseness once but never adopt
it.

### Test-code duplication: DAMP, with extraction only for infrastructure

Meszaros names Test Code Duplication a smell and pushes extraction; Dodds pushes
inline self-containment ("prefer duplication over the wrong abstraction");
Google ch12 resolves the tension: DAMP is complementary to DRY — "a little bit
of duplication is OK in tests so long as that duplication makes the test simpler
and clearer". Adjudication: extract data construction (factories, builders —
Meszaros's Creation Method) and guaranteed cleanup; inline the story of the test
(arrange-act-assert visible in the test body). This is what the existing skills
already do; the reference files cite it.

### Property-based testing: a complement with named costs

PBT attacks what example enumeration structurally misses (intersection edge
cases — Wayne's mode bug), oracles implement Feathers-style characterization for
refactors, and metamorphic relations handle no-oracle subjects. Its costs are
equally documented: good properties are hard to find, constructive generators
are expensive, and random inputs are maximally UNLIKE real usage — the
deliberate inverse of the Dodds/Testing Library resemblance principle.
`property-based.md` presents both halves; PBT never replaces the example suite.

## Consolidated fix list (Phase 3 MUST apply these)

Python (`plugins/python/skills/testing/SKILL.md` line numbers):

| ID  | Lines        | Fix                                                                                                                                                                                                                             |
| --- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P1  | 798-801      | pytest 9.1 has shipped (9.1.1 current): rewrite the `PytestRemovedIn9Warning` passage in present tense; the `filterwarnings` escape hatch is gone.                                                                              |
| P2  | 794-797      | "pytest errors when both tables are present" is unverified by current docs. Verify empirically against live pytest 9.1 before restating; otherwise soften or drop.                                                              |
| P3  | 121-122, 653 | pytest-xdist 3.8.0 publishes no Python 3.14 classifier, same as pytest-timeout (flagged at line 977). Apply the classifier caveat consistently to both or drop it for both.                                                     |
| P4  | 529-530      | Hypothesis now ships a built-in `ci` profile auto-loaded in CI with `deadline=None`. Rewrite profile guidance: extend the built-in `ci` profile rather than hand-registering one; explicit deadlines belong in `dev`, not `ci`. |

TypeScript (`plugins/typescript/skills/testing/SKILL.md` line numbers):

| ID  | Lines          | Fix                                                                                                                                                                                                                 |
| --- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T1  | 72-76 + config | Vitest 4 narrowed `restoreMocks` to `vi.spyOn` spies; `vi.fn()` history and one-shot impls leak without `clearMocks`/`mockReset`. State the pairing wherever mock hygiene config appears.                           |
| T2  | 111, 501       | `workspace` was renamed to `projects` in Vitest 3.2; v4 only removed the old name. Correct the attribution.                                                                                                         |
| T3  | 195-198        | Default `fakeTimers.toFake` already excludes `nextTick`/`queueMicrotask`. Keep scoped `toFake` as a choice but fix the stated hazard; note the minimal list leaves `Date` un-faked, which `vi.setSystemTime` needs. |
| T4  | 57-58, 481-483 | Playwright 1.62 ships first-class component testing (`mount()` fixture, stories/galleries). Redraw the boundary: acknowledge Playwright CT exists and state why this skill still prefers Testing Library/jsdom.     |

New code examples, if any are added, must target: schemathesis 4 namespaced
loaders, mutmut 3.x config keys (`source_paths`), pact-python 3.x FFI API,
psycopg-v3 `get_connection_url(driver=None)` where relevant, MSW 2.x
`http.get`/`HttpResponse`.

## Phase 2 file map

### Shape

Each skill becomes a hub `SKILL.md` (target under 250 lines, hard cap 300:
scope + gate tiers + non-negotiables + a routing table keyed by
symptom/question + traps + when-in-doubt + what-this-is-NOT + freshness) plus a
`references/` folder. Frontmatter stays byte-identical (trigger wording
unchanged). Moved prose is preserved verbatim except where the fix list above
mandates a change or light stitching is needed at file seams. Every
`references/*.md` ends with a `## Sources` section citing the dossier entries it
draws on (title + URL) and a re-dated freshness note stating what was verified
on 2026-07-26. No `@`-links anywhere.

### Python: section-to-destination map

| Current section (lines)                  | Destination                                    |
| ---------------------------------------- | ---------------------------------------------- |
| Preamble (40-69)                         | hub (condensed)                                |
| Gate tiers (70-95)                       | hub                                            |
| Non-negotiables (96-140)                 | hub (apply P3)                                 |
| Suite architecture (141-166)             | hub (condensed) + `unit.md` (detail)           |
| Typed fixtures and factories (167-285)   | `fixtures-and-factories.md`                    |
| Test data (286-302)                      | `fixtures-and-factories.md`                    |
| Boundary control (303-363)               | `doubles-and-boundaries.md`                    |
| Time, sleep, and randomness (364-381)    | `determinism.md`                               |
| Resilience patterns under test (382-414) | `resilience.md`                                |
| Hermeticity and ambient state (415-463)  | `determinism.md`                               |
| Async tests (464-481)                    | `determinism.md`                               |
| Parametrize and property-based (482-536) | `unit.md` (parametrize) + `property-based.md`  |
| Type-level tests (537-564)               | `unit.md`                                      |
| Integration tests (565-624)              | `integration.md`                               |
| Assertions and snapshots (625-641)       | `unit.md`                                      |
| Coverage and CI gates (642-656)          | `gates-and-ci.md`                              |
| Resource gates G2 (657-695)              | `gates-and-ci.md`                              |
| Nondeterministic subjects G3 (696-736)   | `evals.md`                                     |
| Configuration reference (737-806)        | `gates-and-ci.md` (apply P1, P2)               |
| Traps reviewers should catch (807-843)   | hub                                            |
| When in doubt (844-883)                  | hub (condensed)                                |
| What this skill is NOT (884-915)         | hub                                            |
| Freshness (916-981)                      | hub (re-dated) + per-file freshness notes (P4) |

### TypeScript: section-to-destination map

| Current section (lines)                 | Destination                            |
| --------------------------------------- | -------------------------------------- |
| Preamble (30-59)                        | hub (apply T4 at 57-58)                |
| Non-negotiables (60-103)                | hub (apply T1)                         |
| Suite architecture (104-129)            | hub (condensed) + `unit.md` (apply T2) |
| Boundary control (130-192)              | `doubles-and-boundaries.md`            |
| Timers and async (193-235)              | `determinism.md` (apply T3)            |
| Hermeticity and ambient state (236-262) | `determinism.md`                       |
| Component tests (263-283)               | `components.md` (apply T4)             |
| Type-level tests (284-294)              | `unit.md`                              |
| Property-based tests (295-319)          | `property-based.md`                    |
| Integration tests (320-340)             | `integration.md`                       |
| Assertions and snapshots (341-363)      | `unit.md`                              |
| Coverage and CI gates (364-375)         | `gates-and-ci.md`                      |
| Configuration reference (376-424)       | `gates-and-ci.md` (apply T1)           |
| Traps reviewers should catch (425-446)  | hub                                    |
| When in doubt (447-472)                 | hub (condensed)                        |
| What this skill is NOT (473-490)        | hub (apply T4 at 481-483)              |
| Freshness (491-513)                     | hub (re-dated; apply T2 at 501)        |

### Parallel structure and justified deltas

Shared files in both skills: `unit.md`, `integration.md`,
`doubles-and-boundaries.md`, `determinism.md`, `property-based.md`,
`gates-and-ci.md`.

Deltas, each justified by existing verified content rather than invented:

-   Python-only `fixtures-and-factories.md`: pytest has a fixture system; the TS
    skill's setup guidance is function-based (Dodds: reuse via plain functions,
    hooks only for guaranteed cleanup) and small enough to live in `unit.md`.
-   Python-only `resilience.md` and `evals.md`: the TS skill has no verified
    resilience or G3/evals content; inventing it is out of scope for a
    restructure.
-   TypeScript-only `components.md`: Testing Library component testing has no
    Python counterpart; absorbs the T4 boundary redraw.
-   No `e2e.md` in either skill: neither has verified e2e content beyond drawing
    the Playwright boundary; a router note covers it until content earns a file.

### Level-vs-concern justification (from the adjudications)

Levels and concerns are different axes (Google ch11: size and scope
"interrelated but distinct"; the gate tiers already encode the size axis).
Concern files exist because the canon treats those techniques as level-agnostic
chapters — doubles (Google ch13, Meszaros, Khorikov ch. 8-9), fixtures
(Meszaros), determinism/hermeticity (Google ch11 small-test constraints), PBT
(Wayne, Hypothesis docs) — and because routing fails without them: "how do I
test retry with jittered backoff" has no home in a pure level hierarchy but
routes cleanly to `resilience.md`.

### Pre-registered Phase 4 retrieval questions

Python (question, expected route): retry with jittered backoff →
`resilience.md`; freeze time in an async test → `determinism.md`; real Postgres
or mock the repository → `integration.md` + `doubles-and-boundaries.md`; where
do factories live → `fixtures-and-factories.md`; chase 100% coverage / what runs
in CI → `gates-and-ci.md`; test an LLM-backed function → `evals.md`; Hypothesis
vs parametrize → `property-based.md`; patch my service's internal helper →
`doubles-and-boundaries.md`.

TypeScript: should this vitest suite mock the repository layer →
`doubles-and-boundaries.md`; fake timers wedge fetch → `determinism.md`;
`getByTestId` everywhere → `components.md`; Playwright CT vs Testing Library →
`components.md`; mock state leaks despite `restoreMocks` → hub non-negotiables +
`gates-and-ci.md`; when to reach for fast-check → `property-based.md`.
