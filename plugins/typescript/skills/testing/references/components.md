# Component tests (Testing Library)

Component tests assert the accessible contract a user (and a screen reader)
gets, through Testing Library in the jsdom project — and this file draws
the boundary with Playwright's component testing. Timer and async waiting
rules are in `references/determinism.md`; MSW for component-level network
in `references/doubles-and-boundaries.md`.

- **Query by role first** — `getByRole("button", { name: /save/i })` —
  then label/text; `data-testid` is the documented last resort. Role
  queries test the accessible contract users and screen readers get;
  `container.querySelector` pins DOM structure and class names that
  refactors legitimately change.
- **`userEvent.setup()` over `fireEvent`** — user-event dispatches the full
  event sequence (pointer, focus, keyboard) a real user triggers.
- **Async UI through `findBy*` / `waitFor` with specific assertions** —
  waiting for "the mutation finished" is asserting on implementation;
  wait for the visible outcome (`await screen.findByText(/saved/i)`).
- **Assert accessible outcomes, not internals**: jest-dom matchers
  (`toBeVisible`, `toBeDisabled`, `toHaveAccessibleName`) over class-name
  and prop inspection.
- **Accessibility is a tested contract, not a review afterthought.** Beyond
  role queries, run `vitest-axe` on rendered output —
  `expect(await axe(container)).toHaveNoViolations()` — so an unlabeled
  control or an invalid-ARIA regression fails the unit suite instead of an
  audit months later.

## When a real browser is required: Playwright CT

Playwright 1.62 ships first-class
[component testing](https://playwright.dev/docs/test-components) in plain
`@playwright/test`: a stories-and-galleries model in which a component test
is a regular Playwright end-to-end test that runs against a small story
gallery page served by your own dev server, using the built-in `mount()`
fixture (typed props via `mount<typeof WithTitle>(...)`, `update(props)`,
`unmount()`). It replaces the experimental
`@playwright/experimental-ct-react` / `-vue` packages.

This skill still prefers Testing Library in the jsdom project for component
tests: it is faster (no browser or dev server in the loop), hermetic inside
the Vitest worker, and it enforces the role-first query discipline above —
the accessible contract, not the DOM tree. Reach for Playwright CT when the
behavior under test genuinely requires a real browser — real layout and
scrolling, native dialogs, clipboard, cross-origin navigation — and keep
those suites in the Playwright config, outside the Vitest projects.

## Sources

- [Testing Library: guiding principles](https://testing-library.com/docs/guiding-principles/)
- [Testing Library: query priority](https://testing-library.com/docs/queries/about/#priority)
- [Testing Library: user-event setup](https://testing-library.com/docs/user-event/setup/)
- [Testing Implementation Details (Kent C. Dodds)](https://kentcdodds.com/blog/testing-implementation-details)
- [vitest-axe (chaance)](https://github.com/chaance/vitest-axe)
- [Playwright: component testing](https://playwright.dev/docs/test-components)
- [Playwright: release notes](https://playwright.dev/docs/release-notes)

Freshness: verified 2026-07-26 — @testing-library/react 16.3.2,
@testing-library/dom 10.4.1 (query-priority ladder current),
@testing-library/user-event 14.6.1, @playwright/test 1.62.0 (first-class
component testing; experimental CT packages superseded), vitest-axe 0.1.0
(registry checked 2026-07-26: latest stable dates from 2022, a 1.0.0-pre.5
tag from 2025-01, not deprecated — slow-moving but alive).
