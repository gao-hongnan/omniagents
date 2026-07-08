# After the Pass — When the Map Outlives Planning

Read this only when the user has moved past planning. During an ordinary
pre-implementation pass it is dead weight.

The pass ends when the user holds a sharper prompt; the unknowns do not end with
it. Three later phases each reopen the same map-versus-territory gap — only now
the territory is the change itself, and the map belongs to whoever comes next: a
future you mid-build, a reviewer, a merger. Each phase has one move, and each
move is the pass pointed at a new pair.

## During the build — the deviation log

Implementation is where the map meets the territory for real. A surprise here —
an edge case that forces a departure from the plan — is an unknown unknown the
pass missed, surfacing late. Do not paper over it; log it.

Each entry records three things: what the plan assumed, what the code actually
revealed, and the conservative call you made to keep moving. Tag any entry that
needs the user's judgment rather than yours. The log is not bookkeeping; it is
the input to attempt #2. A deviation means the map was wrong in a small region,
so re-run the pass scoped to that region rather than improvising past it, and
fold what you learn back into the map.

## Before shipping — the buy-in doc

A reviewer inherits your unknowns. Their map is the PR description, the
territory is the diff, and the gap between them is everything they do not know
to ask about your change. Close it before they open the files.

Package the prototype, the spec, and the deviation log into one skimmable pitch.
Lead with a demo rather than prose — reacting beats imagining holds for
reviewers too. Pre-answer each likely objection with the evidence that settles
it: the file, the benchmark, the test. Name who signs off on what, so approval
is a decision and not a diffuse "looks fine to me".

## Before merging — the readiness quiz

Merging someone else's change, or your own long-lived branch, is the same
problem from the far side: you are about to own a territory whose map you did
not draw. A merge-readiness report states the mental model, the non-obvious
behaviors the change introduces, and what to watch after deploy — then ends in a
short quiz the merger must pass. A wrong answer is a blindspot; point it back at
the section that would have prevented it. Passing the quiz is the merge's
done-condition, the way the rewritten prompt is the pass's.

## Credits

These three moves are ported from the "after the walk" phase of
[dzhng's explore-unknowns](https://github.com/dzhng/skills/blob/main/skills/engineering/explore-unknowns/references/after-the-walk.md)
(MIT © 2026 David Zhang) and rewritten in the blindspot-pass idiom. The
map-versus-territory lens they extend comes from
[Thariq Shihipar](https://thariqs.github.io/html-effectiveness/unknowns/).
