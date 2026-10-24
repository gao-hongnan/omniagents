# Machine-writing tells

Read this file before the final pass. This file lists the patterns that mark
text as machine-written. Each one costs the reader trust, and most cost words
too. One tell is a lead. A cluster is a verdict.

A word on these lists is not wrong in every context. "Robust" has a meaning in
statistics, and "landscape" has one in printing. The test: can you replace the
word with a specific fact? If you can, do it. Keep a word that is a term of art
in the codebase or the field.

## Contents

- AI vocabulary
- Filler
- Hedges
- Assistant talk
- Structural tells
- Format and layout tells
- Abstract metaphors and invented jargon
- Vague claims
- Tells in commits and PRs
- Add an offender

## AI vocabulary

| Tell                                                                                                  | Write instead                                                                 |
| ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| "delve into", "dive into", "explore" meaning discuss                                                  | "cover", "describe", or the specific action                                   |
| "leverage", "harness", "utilize"                                                                      | "use"                                                                         |
| "robust", "seamless", "powerful", "comprehensive"                                                     | The property and its number: "retries three times", "covers all 14 endpoints" |
| "crucial", "vital", "pivotal", "essential" as emphasis                                                | What breaks without it                                                        |
| "landscape", "realm", "tapestry", "ecosystem" as a figure                                             | The actual set: "the three Python type checkers"                              |
| "streamline", "enhance", "elevate", "empower", "unlock", "supercharge"                                | The change and its size: "cuts the build from 9 minutes to 4"                 |
| "foster", "bolster", "underscore", "showcase" as verbs of emphasis                                    | "show", or cut                                                                |
| "a testament to", "plays a key role in", "serves as", "stands as"                                     | "is", or the specific relation                                                |
| "myriad", "plethora", "a wide range of", "various"                                                    | The number, or "several"                                                      |
| "cutting-edge", "state-of-the-art", "best-in-class", "next-generation", "world-class", "blazing fast" | The measurement, or nothing                                                   |
| "ever-evolving", "fast-paced", "in today's world"                                                     | Cut                                                                           |
| "Moreover", "Furthermore", "Additionally" at the start of sentence after sentence                     | Cut them, or join the sentences                                               |

## Filler

| Tell                                                                   | Fix                                                                     |
| ---------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| "It's worth noting that", "It's important to note that", "Note that"   | Cut. State the fact.                                                    |
| "In order to"                                                          | "To"                                                                    |
| "As mentioned earlier", "As we saw above"                              | Cut, or link the section by name.                                       |
| "In this section, we will discuss", "This guide will walk you through" | Start with the content. An opener that names the reader's task is fine. |
| "Let's dive in", "Without further ado", "Here's the thing"             | Cut                                                                     |
| "The fact that"                                                        | Rewrite: "because", "that"                                              |
| "When it comes to", "In terms of", "At the end of the day"             | Cut, or name the subject directly.                                      |
| "basically", "actually", "really", "very", "quite", "simply", "just"   | Cut                                                                     |

## Hedges

- Stacks: "may potentially", "could possibly", "might perhaps", "it seems that
  it may". Use one hedge or none.
- Unscoped qualifiers: "in some cases", "often", "typically", "generally", with
  no case named. Name the case: "on tables over 10 GB".
- Reference states facts with no hedge. Explanation hedges the certainty once
  and says what you haven't measured: "This holds for tables under 10 GB. We
  haven't measured larger ones."

## Assistant talk

None of these belong in a doc, a commit, or a PR:

- Openers: "Great question!", "Certainly!", "Sure!", "Absolutely!"
- Closers: "I hope this helps", "Let me know if you have any questions", "Happy
  coding!", "Feel free to reach out"
- Self-reference: "As an AI", "I've updated the file to", "Here's the updated
  version"
- Announcements: "This PR aims to", "This commit introduces a comprehensive"

## Structural tells

- A rule of three: three adjectives or three parallel clauses where one is true.
  Keep the true one.
- "Not only X but also Y", "It's not X, it's Y", or "X isn't just Y", framed
  around a single point. State the point.
- An opener that restates the title or the question.
- The "whether you're a beginner or an expert" opener, and the "from startups to
  enterprises" range.
- A summary that repeats the body: "In summary", "Key takeaways", "In
  conclusion". A how-to guide ends with a check that the task worked. A
  reference page has no summary.
- Symmetric paragraphs: every paragraph the same length and shape, each one
  ending in a one-line moral.
- Rhetorical questions as headings or openers: "What if there were a better
  way?"
- Two-part headings joined by a colon: "Performance: Why It Matters".

## Format and layout tells

- Em dashes, worst in pairs around an aside.
- Bold scattered through sentences for emphasis. Keep bold for UI elements and
  run-in labels.
- Emoji in headings and bullets, and check marks or crosses as bullets.
- A heading over every one or two paragraphs.
- Bullets of fragments where the reader needs a connected argument. Explanation
  is prose.
- A table with two rows, and a list with one item.
- Title Case Headings.
- A horizontal rule between every section.
- Exclamation marks.
- Quotation marks for emphasis.

## Abstract metaphors and invented jargon

| Offender                     | Plain replacement                                               |
| ---------------------------- | --------------------------------------------------------------- |
| "ratchet"                    | "a budget that only decreases"                                  |
| "evacuate"                   | "move", "migrate"                                               |
| "endgame"                    | "the final state", "the goal"                                   |
| "north star"                 | "the goal"                                                      |
| "lever", "knob", as a figure | "the setting", by its name                                      |
| "load-bearing"               | "required", "other code depends on it"                          |
| "unlock"                     | "lets you", "makes it possible to"                              |
| "guardrails"                 | "checks", "limits", by their names                              |
| "paper cuts"                 | "small problems", then name them                                |
| "boil the ocean"             | "cover everything at once"                                      |
| "low-hanging fruit"          | "the easiest fixes"                                             |
| "move the needle"            | The metric and the change                                       |
| "first-class citizen"        | "fully supported"                                               |
| "secret sauce"               | The mechanism, by name                                          |
| "battle-tested"              | "used in production since `<date>`", "tested against `<cases>`" |
| "deep dive"                  | "detailed guide", "close look"                                  |
| "bake in"                    | "build in", "include by default"                                |

Terms of art are not on this list: "cache", "thread", "fork", "heap",
"handshake", "garbage collection", and "race condition" stay. The test is
whether developers in the field use the word with this meaning.

## Vague claims

- "Significantly faster", "much better", "highly scalable": give the number and
  its conditions. "p95 latency drops from 180 ms to 40 ms at 1,000 requests per
  second."
- "40+ integrations", "dozens of": give the exact count, true at the commit,
  with the command that counts it.
- "Fully", "completely", "100%": say what you checked.
- "Production-ready", "enterprise-grade": say what makes it so, such as the
  tests it passes, the load it handled, or the guarantees it makes.

## Tells in commits and PRs

- A story of the process: "I started by exploring the codebase, then...". State
  the change.
- A file-by-file list that repeats the diff.
- "All tests pass ✅". Name the command and the result.
- "Comprehensive", "robust", or "significant improvements" in a commit subject.
- A bullet for every small change in a commit body. Give the why, in prose.

## Add an offender

When you meet a new tell, propose it in your reply as one table row: the
offender and its plain replacement. Don't edit this file during a writing task.
