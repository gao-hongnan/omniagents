# omniagents-unknowns

The map is not the territory. Your prompt is the map; the codebase or domain is
the territory; the gap between them is made of unknowns — and the expensive
kind, the unknown unknowns, cannot be reached by asking you questions, because
you don't know to ask them. This plugin packages the counter-move: a **blindspot
pass** that surveys the territory first and reports back what you didn't know to
ask.

## Skills

| Skill                                | Invocation                                          |
| ------------------------------------ | --------------------------------------------------- |
| `omniagents-unknowns:blindspot-pass` | `/blindspot-pass <task or area> + your familiarity` |

Also triggers on its own when you say things like "blindspot pass", "unknown
unknowns", "what am I missing", or "I'm new to this codebase/domain — help me
prompt you better."

## What it does

A blindspot pass is reconnaissance, not implementation:

- Fixes the frame: what you're trying to do and how familiar you already are.
- Surveys the territory — codebase (modules, history, conventions, tests) or
  domain (vocabulary, tooling, what good looks like) — before asking you
  anything.
- Reports 3–7 blindspots, deltas only, ranked by whether they would change what
  you ask for — each as a card you keep or drop, grounded in a cited file, with
  the question it unlocks.
- Ends with the payoff: a rewritten prompt you couldn't have written before the
  pass.

It distinguishes the four quadrants of unknowns — known knowns, known unknowns,
unknown knowns, unknown unknowns — because each needs a different move:
interviews only reach what you already know to ask; prototypes surface what
you'd recognize on sight; only surveying the territory reaches the rest.

By default the pass stops at planning. When the work moves into the build, a
review, or a merge, the same lens extends through an optional companion — a
deviation log, a buy-in doc, a merge-readiness quiz — in
`references/after-the-pass.md`.

## Layout

```text
skills/
  blindspot-pass/
    SKILL.md                 # the pass, loaded by /blindspot-pass
    references/
      after-the-pass.md      # optional: during / after-build moves
```

## Installation

```bash
claude plugin install omniagents-unknowns@omniagents
```

## Usage

```text
/blindspot-pass adding a Slack notifications plugin — never touched this repo
/blindspot-pass migrating the auth module to OIDC; I know our auth code well but not OIDC
/blindspot-pass color-grading this video — I don't know what color grading is
```

## Credits

The four-quadrant unknowns framing and the map-vs-territory lens come from
[Thariq Shihipar (ThariqS)](https://github.com/ThariqS) of Anthropic's Claude
Code team — see his
[Know your unknowns examples](https://thariqs.github.io/html-effectiveness/unknowns/).
The reactable-report shape sharpens three moves from
[dzhng's explore-unknowns](https://github.com/dzhng/skills/blob/main/skills/engineering/explore-unknowns/SKILL.md):
artifacts you react to instead of describe, a report that assembles your next
message, and citing the files the survey actually read. This plugin packages
that workflow as a focused, single-pass Claude Code skill.
