---
name: technical-writing
description: >-
  Use when writing, rewriting, or reviewing technical prose that instructs or
  informs: docs pages, READMEs, tutorials, how-to guides, runbooks, reference
  pages, explanations, PR descriptions, commit messages, changelogs, or release
  notes. A layered standard: Diátaxis modes, Google developer style, ASD-STE100
  rules, and Global English syntax.
when_to_use: >-
  Trigger for "document this", "write the README", "make this clearer", "tighten
  this up", "review this doc", "write the PR description", "commit message",
  "release notes", "runbook", "Diátaxis", or prose that reads machine-written.
  Do not draft or review documentation without loading this skill first.
  Persuasive memos and RFC arguments go to measured-persuasion. Markdown syntax
  goes to markdown-conventions.
argument-hint: "[write|review] <doc, diff, or topic>"
disable-model-invocation: false
user-invocable: true
allowed-tools:
  - "Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/lint_prose.py *)"
model: inherit
---

# Technical writing

Write so a tired engineer understands on the first read. Apply all four layers.

Three rules sit above the layers:

- **Cut every word that does no work.** If the sentence survives without a word,
  the word goes. "In order to" is "to". "It is important to note that" is
  nothing.
- **Use the short, everyday word.** "Use", not "utilize". "Help", not
  "facilitate". "Do", not "perform". Use a long word only when it says something
  the short one can't.
- **When a rule makes a sentence worse, fix the sentence another way or leave it
  alone.** A sentence that follows every rule and sounds like a machine wrote it
  has failed.

The codebase is the word list. Write the real symbol, file, flag, or command
name in code font. Don't use a synonym or a description of it: write "set
`retry_budget`", not "set the retry allowance".

Don't invent jargon. Use the words a developer would say out loud: "move",
"delete", "a budget that only decreases", not "evacuate", "ratchet", or
"endgame". A named pattern is fine when the doc says what it means the first
time. Terms of art are not metaphors, so "cache", "thread", and "handshake"
stay. When you meet a new offender, propose it and its plain replacement in your
reply as an addition to `references/slop-patterns.md`. Don't edit this skill's
files during a writing task.

## Know where this skill stops

This skill governs prose that instructs or informs. Neighbor skills own the
rest:

- `measured-persuasion` owns documents that ask the reader to decide, such as a
  proposal, a strategy memo, or the case for an RFC. It owns their argument and
  voice. This skill still governs the background, design detail, and rollout
  steps around that argument.
- `markdown-conventions` owns Markdown syntax: fences, tables, list markers, and
  link forms.
- The repo's ADR template owns when to write an ADR and which sections it has.
  If the repo has none and the `documentation-and-adrs` skill is present, that
  skill owns both.
- The `docstrings` skills own the structure of API docs inside code. This skill
  governs their sentences.
- Product UI strings are not documentation. Use your product's copy guidelines
  for those.

When two rules collide, the earlier item in this list wins:

1. The repo's own style guide or prose-linter config, such as `STYLE.md`,
   `CONTRIBUTING.md`, or `.vale.ini`.
2. Exact strings. Quote code, commands, UI labels, error messages, and log lines
   exactly as the product prints them, even when they break these rules.
3. The mode's rules. A tutorial says "we" even though the sentence rules say
   "you".
4. Clarity over brevity. Words that prevent a misread do work, so they stay.

Edit only what the user asked you to edit. Apply the standard to the text that
you write and to the text that the user asked you to fix. Leave the rest, and
name its problems in your reply when they matter.

## Vary the rhythm

A doc can obey every layer and still read machine-written: every sentence
clipped short, no view anywhere, nothing specific.

- Mix sentence lengths on purpose. Short sentences land a point. Longer ones
  carry a fact with its condition or consequence. "Longer" means up to about 25
  words, not 40.
- One thought per sentence does not mean one length per sentence. Split the
  sentence that carries two thoughts. Keep the long sentence that carries one.
- Have a view where the mode allows it. Explanation weighs trade-offs, so say
  what you make of them instead of listing pros and cons. Reference stays dry.
- Be specific over sterile. Not "schema changes can cause issues" but "a column
  rename fails the build".

## Pick the mode first (Diátaxis)

One document, one mode. Two questions pick it. The first: does the content
inform action (doing) or understanding (thinking)? The second: does it serve
learning or work? Diátaxis calls this pair of questions its compass.

- Action + learning: **tutorial**.
- Action + work: **how-to**.
- Understanding + work: **reference**.
- Understanding + learning: **explanation**.

Use the compass on a whole document or on one sentence. A sentence that answers
a different question from its document belongs in another document.

**Tutorial: learning by doing.** The learner's success is your job, not theirs.

- Open with what the learner builds, never with "you will learn".
- Make every step produce a visible result, early and often.
- Show what the learner sees next: the expected output, the prompt change, the
  log line.
- Cut explanation to one clause and a link.
- Stay concrete, and offer one path with no choices.
- Write as "we", in commands: "First, do x. Now, do y."

**How-to: steps to a goal.** Solve a problem that a person has, not an operation
that the machine can perform.

- Assume competence and skip teaching.
- Give action only: no digressions, no background, no completeness for its own
  sake. Link those instead.
- Allow forks and judgment: "If you want x, do y."
- End with a step that shows the task worked.
- Name the guide by the task, as a verb phrase: "How to calibrate the radar
  array" or "Calibrate the radar array", not "Radar array calibration". Use one
  form across a doc set.

**Reference: facts for lookup.** Only describe. No procedures, no persuasion, no
opinion.

- State constraints and warnings here: "Don't set `b` unless `c` is set."
- Be dry, complete, and sure. State facts, options, defaults, limits, and errors
  with no hedging.
- Give each entry a short usage example.
- Mirror the structure of the thing described, so readers can move between the
  code and the docs.
- Put material where readers expect it. Generate it from code where possible.

**Explanation: understanding and why.** One bounded topic, readable away from
the product.

- Write each title so that "About..." fits in front of it.
- Anchor on a real why question.
- Give context: design decisions, history, constraints, alternatives.
- Take a position. Opinion belongs here and nowhere else.

Don't mix modes: no reference tables inside a tutorial, no tutorial hand-holding
inside reference, no arguing inside a how-to. Split and link instead. For each
mode's skeleton, the signs that another mode leaked in, and a map from common
doc types to modes, read `references/modes.md`.

## Write sentences to the reader (Google developer style)

- Talk to the reader as "you", in the present tense. Use "will" only for events
  that happen later.
- Say who does what: "the compiler checks", not "is checked". Use the passive
  only when the actor is unknown or beside the point.
- Write instructions as commands: "Click **Submit**." State requirements with
  "must". Avoid "should", which reads as both advice and a rule.
- Put the goal, condition, or location before the action: "To delete the
  document, click **Delete**." "In the console, open **Logs**."
- State the action first and its result second, in the same paragraph: "Click
  **Run**. The results table appears."
- Start an optional step with "Optional:".
- Put the common case first. Exceptions after.
- Sound like a knowledgeable friend. No buzzwords, no figurative language, no
  "please" in instructions, and never "simply", "just", "easy", or "quickly" in
  a procedure. If it were simple, the reader would not be here.
- Don't pre-announce ("we will soon support..."), and don't start consecutive
  sentences with the same phrase. Avoid "currently", "new", and "latest",
  because they go stale.
- Link with words that say where the link goes: the page title or a short
  description. Never "click here". Prefer a sentence of context on the page over
  a link off it.
- Headings carry the point, not the bare topic ("Pick the mode first", not
  "Modes"). Use sentence case. A task heading is a bare verb phrase ("Create an
  instance"). A concept heading is a noun phrase. One h1 per page, no skipped
  levels, and no links in headings.
- Use numbered lists for sequences and bullets for everything else. Introduce a
  list with a complete sentence. Keep items parallel. A single item is not a
  list.
- Code goes in code font. UI elements go in bold. Use serial commas. Drop "etc."
  and say up front that a list is partial.
- Write dates that read one way everywhere: "2026-10-23" or "October 23, 2026",
  never "10/23/26". Give every time a time zone.
- Prefer inclusive, literal terms: "allowlist", "primary" and "replica",
  "placeholder". A real command or branch name keeps its name in code font. The
  swaps are in `references/word-list.md`.

## Make statements load one at a time (STE rules)

- Write one instruction per sentence, and one thought per sentence everywhere
  else.
- Split instructions longer than about 20 words and other sentences longer than
  about 25.
- Keep each paragraph to one topic and at most six sentences.
- Put a warning before the step it guards, never after it. Open the warning with
  the command or the condition: "Back up the database first. `migrate --apply`
  drops every table that it can't convert."
- Keep "the" and "a": "Remove backup file" reads two ways. "Remove the backup
  file" reads one.
- Give each word one meaning and one job, then keep it. If "check" means
  inspect, don't also use it for restrain.
- Pick one word per action and keep it: "start", not "start" here and "initiate"
  there.
- Write procedures as direct commands, never as narration and never in the
  passive: "Install the component", not "the component must be installed".
- Avoid "-ing" words where you can: "Before you deploy, configure the firewall",
  not "Configuring the firewall is required before deploying".
- Use a vertical list when a sentence would carry three or more conditions or
  steps.

## Leave no sentence open to two readings (Global English)

- Keep words like "only" and "not" next to the word they change: "only fails on
  growth" and "fails only on growth" say different things.
- Break up long noun strings. Put at most two nouns in front of a noun: "the
  proto import budget check script" becomes "the script that checks the
  proto-import budget".
- Make every "it", "they", and "this" point at one obvious thing. Put a noun
  after "this" ("this setting"), and repeat the noun when in doubt. Never use
  "this" or "which" to point at a whole clause.
- Don't drop verbs: "Phase 1 moves the converters and Phase 2 the runtime"
  leaves Phase 2 without one. Give it one.
- Keep the small words that show structure, such as "that" in "Ensure that the
  switch is off". Never trade clarity for word count.
- Repeat the article in a series when it prevents a misread: "the client and the
  host", not "the client and host", when they are two things.
- Say which parts "and" or "or" joins when a sentence can group two ways.
  "Both...and", "either...or", and "if...then" are free disambiguators.
- Pick the connective with one meaning: "because", not "since" or "as". "After",
  not "once". "Although", not "while", for a contrast.
- Prefer one verb to a phrasal verb: "uses", not "makes use of". When you need a
  phrasal verb, keep it whole: "set up the server", not "set the server up".
- Use periods, not semicolons. Replace an em dash with a new sentence or a
  colon.
- Make text in parentheses a full grammatical unit or its own sentence. Never
  form plurals with "(s)".
- No slashes: write "a, b, or both" instead of "a/b" or "and/or". Paths and URLs
  keep theirs.
- Call each thing by one name, everywhere. A doc that says "the gate", "the
  ratchet", and "the budget check" for one thing teaches three things. Don't
  churn what didn't change.
- Skip idioms, colloquialisms, jokes, Latin abbreviations, and metaphors.

## Prove every fact the doc states

A wrong command costs the reader more than a clumsy sentence. Before the doc
ships, run these checks:

- Run every command you document when it is safe to run: read-only, local, or in
  a scratch environment. For a destructive or production command, check the
  syntax against `--help` or the source, and say in your reply that you didn't
  run it.
- Paste real output, trimmed. Never invent output. Mark values that change
  between runs, such as IDs and timestamps, as placeholders.
- Check every path, flag, default, and version against the code at `HEAD`.
- Make every count or tree claim true at the commit that lands it, and include
  the command that regenerates it.
- Format code samples the way the repo's formatter would, and make them complete
  enough to copy and run.
- Write real paths. Mark each placeholder the way the repo does, such as
  `<project-id>`, and say what goes there.

## Write commits and PR descriptions as briefings

Commit messages, PR descriptions, and changelog entries are writing too. Every
layer except Diátaxis applies to them. Follow the repo's convention first: read
`git log --oneline -20` and the PR template, if there is one.

- Write the commit subject as an imperative summary of 50 characters or fewer,
  with no period. It completes "If applied, this commit will...".
- Wrap the commit body at 72 columns. State the problem in the present tense,
  then why this change solves it. Leave the how to the diff.
- Make the PR description a briefing that a reviewer can read in under a minute.
  Say what changed and why, then how you verified it, then any risk or rollout
  step.
- Don't narrate your process, list the files the diff already shows, or paste
  logs, SHA lists, transcripts, or metric tables. Summarize the result in a
  sentence and link the rest.
- Name the evidence: "`pytest tests/api` passed, 212 tests", not "all tests
  pass".
- Update the description when review changes the PR.

Templates, before-and-after examples, and changelog rules are in
`references/commits-and-prs.md`.

## Strip the machine-writing tells

Read the draft once more for the tells that mark text as machine-written, and
remove them. The full catalog is `references/slop-patterns.md`. The common tells
are these:

- AI vocabulary: "delve", "robust", "seamless", "leverage", "crucial",
  "landscape".
- Filler that announces instead of saying: "It's worth noting that", "In this
  section, we will discuss".
- Hedge stacks: "may potentially", "could possibly". Use one specific hedge or
  none.
- Assistant talk: "Great question", "I hope this helps", "Let me know if you
  have questions". It never belongs in a doc, a PR, or a commit.
- Padding: a list of three where one item is true, and a "not only X but also Y"
  frame around a single point.
- Decoration: bold scattered through sentences, emoji in headings, and a heading
  over every second paragraph.

## Write a doc

1. Name the reader and the one task or question the doc serves. If you can't say
   it in one sentence, fix that first.
2. Pick the mode. If the request spans two modes, write two docs and link them.
3. List the nouns that the doc depends on. Give each one name, taken from the
   code.
4. Draft in the mode's skeleton from `references/modes.md`.
5. Prove the facts: run the commands and check the paths.
6. Revise in layer order: mode, headings, sentences, then words and tells.
7. Run the repo's prose linter if it has one, such as `vale`. Then run the
   bundled checker on each file:

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/lint_prose.py <file>...
   ```

   The `scripts` directory sits next to this file. Fix every error. Treat a
   warning as a question: fix it unless the fix makes the sentence worse.

## Review a doc

1. Read the whole doc before you mark anything.
2. Open the report with one sentence that names the question the doc answers and
   its mode. Then say what already works, and keep it. A review that replaces
   the author's voice with yours has failed.
3. Check in this order: mode and structure, facts, headings, sentences, then
   words and tells. A structural fix can delete the sentences that a later pass
   would polish.
4. Run the checker from step 7 of "Write a doc". Treat each hit as a lead, not a
   verdict.
5. Report each finding in this shape. List the findings that make the doc wrong
   first, the findings that cause a misread second, and style last.

   ```text
   <file>:<line>  <wrong | misread | style>  <rule>
   Quote:   "<the text as written>"
   Rewrite: "<your version>"
   ```

6. Rewrite only when asked. Otherwise, offer to apply the fixes.

## Apply the layers to one paragraph

Before:

<!-- lint-prose off -->

> Configuration of the proto import ratchet budget script parameters is
> performed via budget.json. Note that it's important to remember that running
> with --write, which updates the committed budget to reflect the current count,
> should only be done when lowering it. If exceeded, CI fails.

<!-- lint-prose on -->

After:

> `budget.mjs` reads the committed budget from `budget.json` and counts the
> files that import protos. If the count exceeds the budget, CI fails. Run
> `budget.mjs --write` only to lower the budget.

The rewrite names the real files and gives the sentence an actor. It moves the
condition first and puts "only" next to the purpose that it limits. The filler
and the metaphor are gone. More pairs, one for each layer and mode, are in
`references/examples.md`.

## Find the details in the reference files

- `references/modes.md`: a skeleton and the leak signs for each mode, plus a map
  from common doc types to modes. Read it before you draft or restructure a doc.
- `references/word-list.md`: plain-word swaps, words with two meanings,
  inclusive terms, and formats for dates and units. Read it when you revise
  words.
- `references/slop-patterns.md`: the catalog of machine-writing tells. Read it
  before the final pass.
- `references/commits-and-prs.md`: commit messages, PR descriptions, changelog
  entries, and release notes, with templates. Read it before you write any of
  them.
- `references/examples.md`: before-and-after rewrites for each layer and each
  mode.
- `scripts/lint_prose.py`: the checker. It flags only the rules that a pattern
  can catch. Run it with `--list-rules` to see them.

## Sources

- [Diátaxis](https://diataxis.fr/) by Daniele Procida: the four modes and the
  compass.
- [Google developer documentation style guide](https://developers.google.com/style):
  the sentence, procedure, heading, list, and word rules.
- [ASD-STE100 Simplified Technical English](https://www.asd-ste100.org/), Issue
  9, January 2025: the sentence and paragraph limits, one meaning per word, and
  the place of warnings.
- John R. Kohl, _The Global English Style Guide_ (SAS Institute, 2008): the
  syntactic cues that keep a sentence to one reading.
