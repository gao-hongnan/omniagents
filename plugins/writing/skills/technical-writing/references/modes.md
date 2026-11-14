# Modes in depth

Read this file when you draft a doc, restructure one, or can't place a passage
in a mode. The hub has the rules. This file has the shapes. The four modes and
the compass come from Diátaxis by Daniele Procida. The skeletons and wording
here are this skill's own.

## Contents

- Tell the modes apart
- Tutorial
- How-to guide
- Reference
- Explanation
- Map common docs to modes
- Split a mixed doc

## Tell the modes apart

| Mode        | The reader is                    | The reader wants          | The doc succeeds when                             |
| ----------- | -------------------------------- | ------------------------- | ------------------------------------------------- |
| Tutorial    | new, and learning                | a first success to repeat | the learner finishes and sees the output it shows |
| How-to      | competent, and working           | one task done             | the task works, and a check proves it             |
| Reference   | working, and missing one fact    | that exact fact           | the fact is there, correct, and found in seconds  |
| Explanation | studying, away from the keyboard | to understand why         | the reader can predict how the system behaves     |

When a passage fits two rows, ask the two compass questions about that passage
alone. First: does it tell the reader what to do, or what is true? Second: does
it serve someone who is learning, or someone who is working?

## Tutorial

Write a tutorial for the reader's first contact with the product, when the goal
is a skill that they keep.

```text
# <Build the result>                  Title names what we build.

<One paragraph: what we build, and what the learner has at the end.>

## Before you start                    Exact versions, accounts, and a clean directory.

## <Bare verb phrase for step 1>
<One action.>
<Expected output, pasted from a real run.>
<At most one clause of why, with a link to the explanation.>

## <Bare verb phrase for step 2>        One heading per visible result.

## What we built                       What exists now. Links to how-to guides and explanation.
```

Write it this way:

- Promise the result, not the lesson: "In this tutorial, we build a CLI that
  tails a log file." Never "you will learn".
- After each step, say what the learner sees, and check it with them: "The
  prompt now starts with `(venv)`."
- Offer one path. Options and alternatives belong in how-to guides.
- Test the whole tutorial from a clean environment, at the versions it names,
  before it ships. A tutorial that fails at step 4 loses the reader for good.

| Leak sign                                 | Fix                                                |
| ----------------------------------------- | -------------------------------------------------- |
| A table of every option                   | Link the reference page.                           |
| A paragraph on why the design is this way | Keep one clause. Link the explanation.             |
| "Alternatively, you can..."               | Cut the fork. A how-to guide can carry it.         |
| A step with no visible result             | Merge it into the next step, or show what changed. |

## How-to guide

Write a how-to guide when a competent reader has a goal and needs the steps.

```text
# How to <do the task>                 Or "<Do the task>". Use one form across the doc set.

<One sentence: the problem this guide solves and when a reader meets it.>

## Before you begin                    Only the prerequisites that the steps need.

## <Bare verb phrase for the first part>
1. <Goal, condition, or location.> <Action.> <Result.>
2. ...

## Check that it worked                A command, and the output that proves success.

## Troubleshoot                        Optional. Key each entry by the exact error text.

## See also                            Links to reference and explanation.
```

Write it this way:

- Start from the reader's goal, in the reader's words: "How to rotate a leaked
  API key", not "Using the key manager".
- Assume the reader knows the basics. Link the tutorial instead of teaching.
- Branch where readers differ: "If you use Postgres, run...". Keep each branch
  short, or split the guide.
- End with a check that proves success.

| Leak sign                                  | Fix                                                   |
| ------------------------------------------ | ----------------------------------------------------- |
| A step that teaches a concept              | Link the tutorial or the explanation.                 |
| Background on how the feature came to be   | Move it to an explanation page. Link it.              |
| Every option for a command                 | Show the options this task needs. Link the reference. |
| A step that only describes, with no action | Fold the fact into the step that needs it.            |

## Reference

Write reference for facts that a reader looks up while working: APIs, CLI flags,
config keys, error codes, and limits.

```text
## `<name>`

<One sentence: what it is or what it does.>

Type: <type>. Default: <default>. Allowed: <values or range>. Since: <version>.

<Constraint or warning, if any: "Must be less than `max_connections`.">

<The smallest example that shows the entry in use.>
```

Write it this way:

- Mirror the structure of the code: one page for each module, command, or
  resource, in the code's order or in alphabetical order.
- Use the same entry pattern every time, so that a reader learns the page once.
- State limits and errors as facts: "Returns `429` after 100 requests in one
  minute." Never "usually" or "should".
- Generate the entries from the code or the schema when you can. Write only the
  descriptions by hand.

| Leak sign                        | Fix                                                       |
| -------------------------------- | --------------------------------------------------------- |
| Numbered steps                   | Move them to a how-to guide. Link it.                     |
| "We recommend..."                | Move the advice to a how-to guide or an explanation page. |
| History of the design            | Move it to an explanation page.                           |
| "Usually", "typically", "should" | State the actual condition and the actual behavior.       |

## Explanation

Write explanation when a reader asks why the system works the way it does.

```text
# <Noun phrase that takes "About">     "Retry budgets", "Why we shard by tenant"

<The why question that this page answers, in one or two sentences.>

## <The problem and its constraints>
## <How the design answers them>
## <The alternatives, and why we didn't pick them>
## <What the design costs, and where it stops working>
```

Write it this way:

- Anchor the page on one real question that someone asked.
- Take a position. "We chose X because Y, and it costs us Z" teaches more than a
  balanced list of pros and cons.
- Connect the topic to what the reader already knows: an earlier version, a
  familiar system, or a constraint that they have met.
- Keep it bounded. When the page starts to give steps or to list options, link
  the how-to guide or the reference instead.

| Leak sign                         | Fix                                   |
| --------------------------------- | ------------------------------------- |
| Numbered steps                    | Move them to a how-to guide. Link it. |
| A table of options and defaults   | Move it to the reference. Link it.    |
| Pros and cons with no conclusion  | Say which option wins here, and why.  |
| A second topic in the second half | Split the page.                       |

## Map common docs to modes

Each entry gives the doc type, its mode, and what the mode asks of it.

- **README:** a landing page that routes. Give one paragraph on what the project
  is and who it is for, a quickstart, and links. Keep each part in its mode, and
  keep the page short.
- **Quickstart:** a tutorial for a new reader, or a how-to guide for an expert
  one. Decide which reader you serve before you write.
- **Runbook:** a how-to guide. Give the preconditions, numbered steps with a
  check after each, a rollback, and who to escalate to. Write for a tired reader
  under pressure.
- **Troubleshooting guide:** a how-to guide. Key each entry by the exact error
  text or symptom. Then give the cause, then the fix.
- **Migration or upgrade guide:** a how-to guide with a reference table. Write
  the steps as a how-to guide, and list the breaking changes in a table.
- **API, CLI, or config reference:** reference. Generate it from code, and use
  one entry pattern.
- **Architecture overview:** explanation. Pair each diagram with text that says
  what each part does and why it exists.
- **Design doc or RFC:** explanation with a decision. `measured-persuasion` owns
  the argument. This skill owns the background, design detail, and rollout.
- **ADR:** explanation. The repo's ADR template owns the sections. If the repo
  has none and `documentation-and-adrs` is present, that skill owns them.
- **Changelog or release notes:** a reference record. See `commits-and-prs.md`.
- **Onboarding guide:** a tutorial. Give one path to a first contribution.
- **FAQ:** no mode. An FAQ collects answers that have no mode. Move each answer
  into the doc where a reader would look for it.
- **Docstring:** reference. The `docstrings` skills own the sections. This skill
  governs the sentences.
- **Code comment:** explanation, at the scale of a line. Say why, not what.

## Split a mixed doc

To split a doc that mixes modes, follow these steps:

1. Tag each section with its mode. Then tag each paragraph. Use the two compass
   questions.
2. Keep the majority mode in place.
3. Move each minority block to a doc of its own mode, or to an existing doc of
   that mode.
4. Leave one sentence and a link where each block was.
5. Retitle each doc for its mode. A how-to guide takes a verb phrase. An
   explanation takes a noun phrase that fits after "About". A reference page
   takes the name of the thing.
