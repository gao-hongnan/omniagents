# omniagents-pedagogy

Incremental teaching skill for deep code understanding via structured Socratic
dialogue. Invoke `/coding-teacher [topic]` and Claude becomes your teacher — not
just solving the problem, but verifying that you understand it.

## Skills

| Skill                                | Invocation                               |
| ------------------------------------ | ---------------------------------------- |
| `omniagents-pedagogy:coding-teacher` | `/coding-teacher [topic, file, PR, bug]` |

## What it does

`/coding-teacher` opens a session-scoped learning document at
`.claude/learning/deep-teach-<session-id>.md` and works through a structured
checklist:

- What problem are we solving and why did it exist?
- What are the relevant code paths and design decisions?
- What is the proposed solution and why not the alternatives?
- What edge cases, failure modes, and downstream impacts matter?
- What tests or checks prove this works?

Claude teaches **incrementally** — it pauses after each concept, asks you to
restate your understanding, corrects misunderstandings, and only advances when
you can answer a verification question. It will not summarize at the end until
you have completed a full teach-back of every checklist item.

## Teaching levels

Claude selects the explanation depth based on context:

| Level           | Audience                             |
| --------------- | ------------------------------------ |
| ELI5            | Pure intuition, no assumed knowledge |
| ELI14           | Simplified but technically honest    |
| ELI-intern      | Practical engineering explanation    |
| Senior engineer | Design tradeoffs and architecture    |

## Modes

**Default** — general code understanding from topic, file path, or description.

**Debugging mode** — triggered when the topic is a bug or unexpected behavior.
Walks through symptom → root cause → fix → regression test.

**Code review mode** — triggered when the topic is a PR or diff. Covers what
changed, what behavior changed, what contracts are affected, and what tests are
missing.

## Layout

```
skills/
  coding-teacher/
    SKILL.md    # skill definition loaded by /coding-teacher
```

## Installation

```bash
claude plugin install omniagents-pedagogy@omniagents
```

## Usage

```text
/coding-teacher the authentication middleware refactor
/coding-teacher plugins/reviewer/commands/review.md
/coding-teacher PR #42
/coding-teacher the ECONNRESET bug in the websocket handler
```
