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
the questions exist. A blindspot pass surveys the territory first, then reports
the delta between the user's map and what is actually there, while acting on it
is still cheap. The unknown that costs minutes to close before code is written
costs three PRs to close after.

A pass is reconnaissance, not implementation. It changes no files. Its
deliverable is not a solution but a better prompt — one the user could not have
written before the pass.

## Three rules that hold at every step

When a procedure below competes with speed or convenience, these win.

- **Deltas, not a tour.** Report only what the user's map does not already
  cover and what would change their ask. A blindspot report that reads like
  onboarding docs has failed.
- **Reacting beats imagining.** Never ask the user to describe what they want
  when you can hand them something concrete to react to. A named variant, a
  sample, a rewritten prompt — reaction extracts knowledge the user holds but
  cannot summon on demand.
- **Evidence or it did not happen.** Every claim about the territory cites the
  file, line, or source you actually read. Never invent a specific; a
  fabricated function name or line number destroys the authority of the whole
  report. A labeled gap is honest, a confident fabrication is not.

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
until the survey is done, with two exceptions. The first is the frame (below).
The second is any finding material enough to change a decision already in
flight — disclose that the moment you have it, then file it under its quadrant.
Holding a load-bearing finding back for its scheduled turn is not discipline; it
is withholding.

## The pass

**1. Fix the frame.** You need the task and the user's familiarity — and
familiarity has two axes users routinely conflate: territory-side (this
codebase, this module) and domain-side (the technique, tool, or service
involved). "I'm new to this repo" says nothing about whether they also know the
Slack API, or what color grading is. If either axis is unstated, ask one
question to pin both, then stop asking.

**2. Survey the territory, and cite as you read.** Codebase variant: the
relevant modules, the git history of that area, local conventions, tests,
tooling and scripts, docs — using whatever structural tools exist (knowledge
graph, grep, git log). Domain variant: model knowledge plus current docs or the
web. Go breadth-first; deepen only where something looks load-bearing for this
task. Record the file, line, or source behind each finding as you meet it — a
claim you cannot cite does not reach the report. State the coverage plainly
("the sweep read the N files this task touches; it did not read the migration
history") so the user knows the survey's edges.

**3. Hunt in the standard lairs.** Unknown unknowns cluster in predictable
places. Check each against the user's map; keep only deltas.

| Lair | What hides there |
| --- | --- |
| Vocabulary | Terms of art the user isn't using — without the word, they cannot ask the question |
| History | Prior or abandoned attempts, migrations mid-flight, why the code is weird — and why an attempt died is usually the landmine |
| Invariants | What must not break: implicit contracts, ordering, idempotency |
| Conventions | How this territory already does X — deviating is expensive |
| Quality bar | What good looks like here; does the user know how good this can be? |
| Potholes | Known failure modes, flaky areas, load-bearing hacks |
| Blast radius | What else this touches that the user hasn't mentioned |
| Wrong problem | Signs the task should be reframed entirely |

**4. Write the report** — the contract below.

## The report

The report is a thing to react to, not a lecture to read. It has five slots, in
this order. Every slot is REQUIRED (a slot can be one line, but it cannot be
silently absent). Two properties hold across all of them: every territory claim
carries its citation, and the report as a whole assembles the user's next
message — it ends with a prompt they can send, not a question they must answer
from a blank line.

1. **The frame.** One or two lines: the user's map restated, their familiarity
   on both axes, and the survey's coverage and edges. This is what the rest is
   a delta against.

2. **Reframes first.** If the survey suggests the task itself is misframed —
   the wrong problem, a better intervention point, an existing thing that
   already does this — say so before anything else. The biggest possible
   blindspot is solving the wrong problem well.

3. **Ranked blindspot cards, 3–7.** Deltas only, ranked by "would this change
   what you ask for"; drop trivia that wouldn't. Each card has four parts:
   - **The miss** — the thing the user didn't know to ask. Where they lack the
     term of art, teach the word inline; vocabulary is what turns an unknown
     unknown into an askable one.
   - **Why it bites here** — anchored to a citation (file and line, a commit, a
     doc), not a generic worry.
   - **The question it unlocks** — phrased verbatim, ready to ask. Where the
     answer is genuinely the user's call, pair the question with your
     recommendation; do not silently pre-decide it.
   - **A one-token reaction** — keep or drop, so the user reshapes the report
     without writing prose.

4. **Recognize-on-sight items.** Suspected unknown knowns — taste, format,
   tone, layout, UX feel. Do not ask about these; asking gets confabulated
   answers. Name them, then show 2–4 concrete variants to react to. This is the
   one slot where the medium may leave text: if the reaction needs something to
   look at — a mock, a sample render, a layout — build it as a self-contained
   HTML artifact (inline CSS and JS, no external requests, plausible fake data
   over lorem ipsum, light theme). If the reaction is a decision, keep it in
   text. "Reacting beats imagining" is not "always render"; it is "match the
   medium to what the user must react to".

5. **"Now ask me like this:"** — the rewritten prompt, assembled from the cards
   above, ready to send. Every kept blindspot has become either a resolved
   constraint in the prompt or a bracketed decision
   (`[you decide: X vs Y — I recommend X]`); nothing the user kept is left
   implicit. This is the payoff: a prompt the user could not have written
   before the pass. A pass that ends without one has surveyed but not helped.

## Calibration

- **Depth follows the frame.** Expert-in-area: skip the mental model, hunt
  history and potholes only. Domain-novice: vocabulary and quality bar first —
  teach enough that they can direct the work, not more.
- **Medium follows the reaction.** A decision, a constraint, or a ranked list
  is text, read inline and reacted to by typing. Taste, layout, and tone want a
  rendered artifact, reacted to by looking. Defaulting everything to HTML
  buries a prompt-shaped deliverable in a browser tab; defaulting everything to
  text asks the user to imagine what they should be seeing.
- **The pass is re-runnable.** A surprise during implementation — an edge case
  that forces a deviation — means the map was wrong in a smaller region.
  Re-run the pass scoped to that region before improvising.

## Common mistakes

| Mistake | Fix |
| --- | --- |
| A codebase tour | Report deltas against the user's stated map, nothing else |
| Interviewing before surveying | Questions only reach known unknowns; survey first |
| An uncited territory claim | Cite the file, line, or source — or cut the claim |
| A fabricated specific | A labeled gap beats a confident invention; never invent a name or number |
| Conclusions without questions | Every blindspot ends in the question it unlocks |
| Pre-deciding the user's calls | Unlocked question plus recommendation, not a silent choice |
| Asking about taste | Offer variants to react to instead |
| HTML for a decision | Render only what must be looked at; keep decisions in text |
| A report that doesn't assemble | End with the rewritten prompt, built from the kept cards |
| Unbounded lists | 3–7 items, ranked by decision impact |
| Ending with "let me know" | End with the rewritten prompt |

## After the pass

The pass is pre-implementation reconnaissance; its job ends when the user holds
a sharper prompt. When the work moves past planning — into the build, a review,
or a merge — the same map-versus-territory gap reopens around the change itself.
Those moves (a deviation log, a buy-in doc, a merge-readiness quiz) live in
[references/after-the-pass.md](references/after-the-pass.md); read it only when
the user has left planning.

## Credits

The four-quadrant unknowns framing, the map-versus-territory lens, and the
"reacting beats imagining" principle come from
[Thariq Shihipar (ThariqS)](https://github.com/ThariqS) of Anthropic's Claude
Code team — see his
[Know your unknowns examples](https://thariqs.github.io/html-effectiveness/unknowns/).
This pass also sharpens three ideas from
[dzhng's explore-unknowns](https://github.com/dzhng/skills/blob/main/skills/engineering/explore-unknowns/SKILL.md),
which packages the same source as a five-stage quadrant walk: the reactable
artifact as the medium rather than an afterthought, the report that assembles
the user's next message, and the rule that every territory claim cites a file
actually read. Where that skill walks all four quadrants in order, this one
deepens the single quadrant the other moves cannot reach.
