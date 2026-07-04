---
name: blindspot-pass
description: >-
  Use when the user is entering unfamiliar territory — a new area of the
  codebase, a new domain, tool, or problem space — or is about to scope
  substantial work in one, and the gap between what they asked for and what
  the territory actually demands is likely to be large. Also use when the
  user asks what they are missing, says they don't know what good looks like,
  or wants help prompting better before delegating work.
when_to_use: >-
  Trigger for "blindspot pass", "unknown unknowns", "what am I missing",
  "what don't I know", "what would you ask that I haven't", "I'm new to this
  codebase / module / domain / tool", "I don't know what good looks like
  here", "help me prompt you better", "teach me X so I can direct the work",
  or before planning work in an area the user has never touched.
argument-hint: "<task or area, plus how familiar you are with it>"
disable-model-invocation: false
user-invocable: true
model: inherit
---

# Blindspot Pass — Finding Unknown Unknowns

The user's prompt is a map. The codebase or domain is the territory. The gap
between them is made of unknowns, and the expensive kind — unknown unknowns —
cannot be reached by asking the user questions, because the user does not know
the questions exist. A blindspot pass surveys the territory first, then
reports back the delta between the user's map and what is actually there,
while acting on it is still cheap.

A pass is reconnaissance, not implementation. It changes no files. Its
deliverable is a better prompt, not a solution.

## The four quadrants

Every unknown falls into one of four quadrants, and each quadrant has a
different elicitation move. Using the wrong move is the core failure: an
interview, however thorough, only ever reaches the second quadrant.

| Quadrant | Test | Move |
| --- | --- | --- |
| Known knowns | It is written in the prompt | None — honor it |
| Known unknowns | The user can already ask the question | Interview: collect, answer, or park |
| Unknown knowns | The user would recognize it on sight but never thought to write it down | Show, don't ask: offer 2–4 concrete variants |
| Unknown unknowns | The user does not know the question exists | Survey the territory — this pass |

Exploration therefore precedes questions. Ask the user nothing substantive
until the survey is done, with one exception: the frame.

## The pass

**1. Fix the frame.** You need the task and the user's familiarity — and
familiarity has two axes users routinely conflate: territory-side (this
codebase, this module) and domain-side (the technique, tool, or service
involved). "I'm new to this repo" says nothing about whether they also know
the Slack API, or what color grading is. If either axis is unstated, ask one
question to pin both, then stop asking.

**2. Survey the territory.** Codebase variant: the relevant modules, the git
history of that area, local conventions, tests, tooling and scripts, docs —
using whatever structural tools exist (knowledge graph, grep, git log).
Domain variant: model knowledge plus current docs or web. Go breadth-first;
deepen only where something looks load-bearing for this task.

**3. Hunt in the standard lairs.** Unknown unknowns cluster in predictable
places. Check each against the user's map; keep only deltas.

| Lair | What hides there |
| --- | --- |
| Vocabulary | Terms of art the user isn't using — without the word, they cannot ask the question |
| History | Prior or abandoned attempts, migrations mid-flight, why the code is weird |
| Invariants | What must not break: implicit contracts, ordering, idempotency |
| Conventions | How this territory already does X — deviating is expensive |
| Quality bar | What good looks like here; does the user know how good this can be? |
| Potholes | Known failure modes, flaky areas, load-bearing hacks |
| Blast radius | What else this touches that the user hasn't mentioned |
| Wrong problem | Signs the task should be reframed entirely |

**4. Write the report** — the contract below.

## The report contract

The report has five slots, in this order. Every slot is REQUIRED (a slot can
be one line, but it cannot be silently absent).

1. **The frame.** One or two lines: the user's map restated, and their
   familiarity on both axes. This is what the rest is a delta against.

2. **Reframes first.** If the survey suggests the task itself is misframed —
   the wrong problem, a better intervention point, an existing thing that
   already does this — say so before anything else. The biggest possible
   blindspot is solving the wrong problem well.

3. **Ranked blindspots, 3–7.** Deltas only, ranked by "would this change
   what you ask for"; drop trivia that wouldn't. Each item has three parts:
   the thing the user didn't know to ask, why it matters here, and **the
   question it unlocks** — phrased verbatim, ready to ask. Where the answer
   is genuinely the user's call, give the unlocked question plus your
   recommendation; do not silently pre-decide it. Where the user lacks a
   term of art, teach the word inline — vocabulary is what turns an unknown
   unknown into an askable one.

4. **Recognize-on-sight items.** Suspected unknown knowns — taste,
   format, tone, layout, UX feel. Do not ask about these; asking gets
   confabulated answers. Name them and offer to show 2–4 concrete variants
   (a mock, a sample message, a stub API) so the user can react instead.

5. **"Now ask me like this:"** — the rewritten prompt, ready to send, with
   brackets only around the decisions that are genuinely the user's. This is
   the payoff: a prompt the user could not have written before the pass. A
   pass that ends without one has surveyed but not helped.

## Calibration

- Depth follows the frame. Expert-in-area: skip the mental model, hunt
  history and potholes only. Domain-novice: vocabulary and quality bar
  first — teach enough that they can direct the work, not more.
- Deltas, not a tour. Anything the user's map already covers, or that
  wouldn't change their ask, is cut. A blindspot report that reads like
  onboarding docs has failed.
- The pass is re-runnable. A surprise during implementation — an edge case
  that forces a deviation — means the map was wrong in a smaller region.
  Re-run the pass scoped to that region before improvising.

## Common mistakes

| Mistake | Fix |
| --- | --- |
| A codebase tour | Report deltas against the user's stated map, nothing else |
| Interviewing before surveying | Questions only reach known unknowns; survey first |
| Conclusions without questions | Every blindspot ends in the question it unlocks |
| Pre-deciding the user's calls | Unlocked question + recommendation, not a silent choice |
| Asking about taste | Offer variants to react to instead |
| Unbounded lists | 3–7 items, ranked by decision impact |
| Ending with "let me know" | End with the rewritten prompt |
