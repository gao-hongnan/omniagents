---
name: depth-pass
description: >-
  Use when the user wants a deeper version of a task rather than a bigger
  one: the same deliverable, done the way a top professional would do it.
  Also when they ask to deepen a prompt before work starts, or say an answer
  feels generic. Never answer a request for depth by making it longer or
  broader — load this skill first.
when_to_use: >-
  Trigger for "deeper, not bigger", "depth pass", "what would a top
  professional do here", "this feels surface-level", or "upgrade my prompt
  before I run it". Not for tasks simply wanted done; for unfamiliar
  territory, run blindspot-pass first.
argument-hint: "<the prompt or task to deepen>"
disable-model-invocation: false
user-invocable: true
model: inherit
---

# Depth Pass — A Deeper Version, Not a Bigger One

Most prompts arrive pre-digested. They name a deliverable and quietly inherit
the asker's picture of how the work gets done — usually a capable generalist's:
start from summaries, use the tools at hand, check by eye. Asked to do better,
a model's reflex is to do more: more sections, more features, more caveats.
That is a bigger version. A deeper version is the same deliverable produced
the way the best practitioner in the field produces it — from the underlying
material, with the field's own methods and instruments, against a check that
can say no.

A depth pass rewrites the prompt; it does not do the work. Four questions come
first:

1. What would a top professional in this field do here that the user is not
   asking for?
2. What is the rawest material they would start from, instead of what has
   already been digested?
3. Which specific methods and tools would they use?
4. What, other than the model or the user, would show the result is right?

Then the prompt is rewritten to ask for exactly that, and nothing more. The
deliverable is a prompt the user can send, edit, or hand to another agent —
one they could not have written before the pass.

## Deeper, not bigger

One rule governs the whole rewrite: depth changes how the deliverable is
produced and how anyone knows it is right. It does not change what is
delivered, or how much. Test every addition:

- **It changes the inputs, the method, or the check** — keep it. That is depth.
- **It adds a deliverable, a feature, an audience, or bulk the deliverable
  does not need** — cut it. If it is genuinely load-bearing, offer it as an
  option the user must opt into, `[optional, widens scope: …]`; never fold it
  in.

Reporting the evidence is not scope creep. A line naming the sources used and
what the check returned is how depth becomes visible, so the rewrite asks for
it. A one-page memo stays a one-page memo; it may take longer to write,
because its numbers now come from the raw data and tie out against something.
That cost is the point. The deeper prompt will usually have more words than
the original — words are not deliverables.

## The four questions

Each question invites a characteristic failure: a plausible, generic answer
that sounds like depth and changes nothing. The guidance below exists to block
those.

### 1. The moves the user is not asking for

Name the practitioner precisely. Not "an expert" or "a senior engineer" — the
role whose job this is when done at the highest level: a forensic accountant
closing the books, the SRE who carries this service's pager, a developmental
editor at a literary press, a biostatistician reviewing a trial. When a task
spans fields, pick the one whose judgment decides whether the result is good.
When the field is ambiguous, state your pick in one line and move on; the user
corrects it by reacting.

Then give two to four moves that professional would make here — routine to
them, invisible to an outsider, absent from the prompt. The strongest have a
name in the field: a pre-mortem, a variance analysis, a reverse outline, a
bisect, a sensitivity analysis, a reconciliation, a cold read. A move counts
only if doing it would change the work. "Be rigorous", "consider edge cases",
and "think holistically" are vocabulary, not moves — and so is role-play: "as
a senior engineer…" changes the words, not the method.

If the professional would question the premise itself — this is the wrong
problem — say so in one line and bracket it as the user's call. Do not swap
the task silently.

### 2. The rawest material

Every input sits on a digestion ladder: the thing itself, then records of it,
analyses of the records, summaries of the analyses, and someone's memory of a
summary. Each rung loses information and adds a framing, and an error made on
a lower rung is invisible from the rungs above it. Prompts and models both
default to the top: a dashboard, a blog post, a vendor's docs, the model's own
recall. The professional goes down.

| Digested | Raw |
| --- | --- |
| The dashboard figure | The event rows behind it |
| The docs, a blog post | The source code, the spec, the changelog |
| Press coverage of a study | The paper, its supplement, its data |
| The PM's synthesis | The customers' verbatim tickets and calls |
| "It feels slow" | A trace or profile of the slow path |
| The model's recall | The primary document the claim rests on |

Name the rawest material that is reachable for this user, and where it lives:
a path, an export, a query, an archive. If the rawest is out of reach, name it
anyway, then the best reachable proxy and what the proxy loses. In a
workspace, a few cheap reads (`ls`, `grep`, `git log`) to confirm the material
exists are worth it; cite what you saw and mark the rest "to locate". Never
invent a file, table, or dataset name — a fabricated specific sends the work
looking for a source that does not exist.

### 3. The methods and tools

Name the field's own techniques and instruments, each tied to the step it
serves: "find the commit that introduced it — `git bisect run ./repro.sh`";
"separate mix from rate — decompose churn by plan and cohort"; "find the hot
path — a flame graph under production-shaped load". A tool list with no step
attached is decoration. A method no practitioner would recognize by name, or a
command nobody would type, is usually a process word in disguise: "analyze",
"research", "review carefully", "apply best practices".

If the user lacks an instrument, name the cheapest adequate substitute rather
than silently downgrading the method. Name only tools you are sure exist, and
leave any flag you are unsure of to the tool's docs; a hallucinated option
sends the executor on a detour.

### 4. What, other than the model or the user, shows it is right

Both parties to the conversation are compromised judges. A model rates its
own output as correct more often than it is, and a user is inclined to accept
a confident, plausible answer. So neither counts — not "I double-checked", not
"re-read the draft", not "if you're happy with it", and not a second model's
opinion, which shares the first one's blind spots. The check has to be
something that can say no:

- **Executable** — a test that fails before the change and passes after; a
  type checker; a reproduction script.
- **Measured** — a benchmark or profile against a recorded baseline, under the
  same load.
- **Reconciled** — the same number computed a second, independent way, or tied
  out to an independent record: the bank statement, finance's reported figure.
- **Traced** — every claim followed back to the primary source it rests on.
- **Predicted** — a falsifiable prediction written down before looking: "if
  this diagnosis is right, X happens when we do Y".
- **Judged** — a qualified third party against a stated rubric: a domain
  reviewer, a target reader's cold read, a usability session with a real user.
- **Reality** — it runs on production data; the email gets replies; the dish
  gets cooked.

State what is checked, against what, and what result would count as failure —
and fix that before the work begins, so the work cannot redefine success.
Prefer the cheapest check that could actually fail; a check that cannot fail
is not a check. When no external check exists — pure taste, a eulogy — say so
plainly and name the nearest honest proxy rather than inventing rigor.

## The rewrite

Then rewrite the user's prompt to ask for exactly that. The deeper prompt:

- **Keeps the user's goal, deliverable, audience, constraints, and voice.** It
  is their prompt, deepened — not a new one.
- **Turns the four answers into instructions** — work as the named
  practitioner would; start from the named material, at its location; use the
  named methods at their steps; run the check and report its result with the
  deliverable.
- **Ends with one "Deliver …" line**, apart from the steps that produce it.
  The steps may grow; the deliverable may not, and that line is what the size
  test counts.
- **Stands alone.** A fresh agent with no access to this conversation could
  execute it.
- **Brackets the user's calls** instead of pre-deciding them:
  `[you decide: X vs Y — I'd pick X because …]`.
- **Passes the size test.** Count the deliverables in the original and in the
  "Deliver …" line. If the second number is larger, cut back.

## Output

Use this shape. Every slot is required (the one exception is the small-task
case under Calibration), and each is short — at most four bullets. The
analysis exists to justify the prompt; the prompt is the payoff.

````markdown
**Depth pass — <the task in a few words>**

**1. What a top <named practitioner> would do that you're not asking for**
- <move> — <why it changes the result>

**2. Rawest material**
- <raw source>, not <the digested version> — <where it lives, how to get it>

**3. Methods and tools**
- <step> → <method or tool>

**4. What shows it's right, other than you or me**
- <check> — fails if <result>

**Deeper prompt**

```text
<the rewritten prompt, ready to send>
```
````

Close with one line offering the next move: send it as written, edit it, or
say "go" to run it here. Do not start the work unprompted.

## Calibration

- **Small or already-deep tasks.** If the task is trivial — a rename, a typo —
  or the prompt already names its raw inputs, its methods, and an outside
  check, say so in one line and hand the prompt back with only the missing
  piece added — usually the check — in place of the full output. Do not
  manufacture depth.
- **Practitioners.** If the user evidently works in the field, skip what they
  plainly know and spend the words on raw material and the check — the two
  places experts cut corners under time pressure.
- **Unfamiliar territory.** When the user cannot yet state the task because
  the territory is new to them, there is nothing to deepen yet. Survey it
  first — with the `blindspot-pass` skill where it is installed — then deepen
  the prompt that survey produces.
- **No task given.** With no argument, deepen the most recent task in the
  conversation; if there is none, ask for it in one line.
- **Not copy-editing.** The pass deepens the work a prompt asks for, not its
  phrasing. Polishing wording, tone, or format is a different job.

## Common mistakes

| Mistake | Fix |
| --- | --- |
| Bigger, not deeper — new sections, features, deliverables | Same deliverable; change the inputs, methods, and check |
| "An expert", "a senior engineer" | Name the practitioner whose job this is at the top level |
| Vocabulary instead of moves — "rigorous", "holistic", "best practices" | Keep a move only if doing it changes the work |
| Digested material passed off as raw — a summary, a blog post, model recall | Go down the ladder; say where the raw thing lives |
| Tools listed without the step they serve | Tie each method to its step |
| Self-review, user approval, or another model as the check | An outside check that can fail, fixed before the work |
| A fabricated path, table, or dataset | Cite what you saw; mark the rest "to locate" |
| Pre-deciding the user's calls | `[you decide: X vs Y — I'd pick X]` |
| An essay before the prompt | At most four bullets per question |
| Doing the task | Stop at the deeper prompt; run it only when asked |

## Example

Illustrative, for shape and density — the moves always come from the task's
own field, not from this one.

Input: `/depth-pass speed up our /search endpoint, users say it's slow`

**Depth pass — speed up /search**

**1. What a top performance engineer would do that you're not asking for**

- Record a baseline (p50/p95/p99 under realistic load) before touching code;
  without one, "faster" cannot be shown.
- Profile first, then fix only the dominant cost.
- Agree a target with whoever owns the complaint, so "done" is a number.

**2. Rawest material**

- Production traces and slow-query logs for `/search`, not user reports — they
  name the slow segment.
- Query plans on production-sized data, not on a near-empty dev database where
  every plan looks fast.

**3. Methods and tools**

- Reproduce the load → k6 replaying a sample of real queries.
- Find the hot path → a flame graph (py-spy, pprof) and `EXPLAIN ANALYZE` on
  the slowest queries.

**4. What shows it's right, other than you or me**

- The same load test before and after — fails if p95 misses the target.
- 500 recorded queries return the same results, in the same order, before and
  after — fails on any difference.

**Deeper prompt**

```text
Make /search faster the way a performance engineer would. Before changing
code, record a baseline: replay a sample of real production queries with k6
against staging loaded with production-sized data, and note p50/p95/p99. Use
production traces and slow-query logs for /search to find the dominant
segment, profile that path with a flame graph, and run EXPLAIN ANALYZE on the
slowest queries. Fix only the dominant cost. Target: p95 under
[you decide: 300 ms — I'd confirm it with whoever owns the complaint] at
today's peak load. Done means the same load test meets the target and 500
recorded queries return identical results in identical order.

Deliver the change, with the before/after numbers and the comparison result.
```

Send it as written, edit it, or say "go" to run it here.

## Credits

The four questions are Felix Rieseberg's, from
[How to be more ambitious: A tutorial for humans with models](https://felixrieseberg.com/how-to-be-more-ambitious-a-tutorial-for-humans-with-models/)
(October 2026). Rieseberg, an engineering lead on Claude at Anthropic, sorts
ambition into four kinds — speed, altitude, depth, and range — and this prompt
is his depth move. Verbatim:

> I want a deeper version of this task, not a bigger one. Before rewriting it:
> (1) say what a top professional in this field would do here that I'm not
> asking for; (2) name the rawest material they would start from instead of
> what has already been digested for me; (3) name the specific methods and
> tools they would use; (4) say what, other than you or me, would show the
> result is right. Then rewrite my prompt to ask for exactly that.

This skill packages that prompt and adds a guard against the generic answer
each question invites: the size test, the named practitioner, the digestion
ladder, step-bound methods, and the catalogue of outside checks.
