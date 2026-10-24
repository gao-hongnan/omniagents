# Word list

Read this file when you revise words. Swap a word only when the swap keeps the
meaning. The real name of a symbol, command, flag, or branch always wins. Write
`kill` when the command is `kill`, and "the `master` branch" when the branch has
that name. Entries marked (G) follow the Google developer documentation style
guide's word list.

## Contents

- Use the plain word
- Pick the word with one meaning
- Keep these words out of procedures
- Replace Latin abbreviations
- Use inclusive, literal terms
- Write timeless text
- Write dates, times, and units that read one way
- Keep one name for each thing

## Use the plain word

| Instead of                                               | Write                                  |
| -------------------------------------------------------- | -------------------------------------- |
| "utilize", "make use of" (G)                             | "use"                                  |
| "leverage", meaning use (G)                              | "use"                                  |
| "facilitate"                                             | "help", or the specific verb           |
| "perform" (a task)                                       | "do", "run"                            |
| "in order to" (G)                                        | "to"                                   |
| "allows you to", "enables you to" (G)                    | "lets you"                             |
| "commence", "initiate"                                   | "start", "begin"                       |
| "terminate", "abort", "kill", outside a command name (G) | "stop", "end", "exit", "cancel"        |
| "prior to"                                               | "before"                               |
| "subsequent to"                                          | "after"                                |
| "in the event that"                                      | "if"                                   |
| "due to the fact that"                                   | "because"                              |
| "has the ability to", "is able to"                       | "can"                                  |
| "a number of"                                            | "several", or the number               |
| "comprise" (G)                                           | "consist of", "contain", "include"     |
| "via" (G)                                                | "through", "by", "with", "using"       |
| "aka" (G)                                                | "also known as"                        |
| "functionality" (G, use with caution)                    | "feature", "function", or what it does |
| "with regard to", "with respect to"                      | "about", "for"                         |
| "wish" (G)                                               | "want", "need"                         |
| "hit" a key (G)                                          | "press"                                |
| "check" a checkbox (G)                                   | "select"                               |

## Pick the word with one meaning

| Word                  | Problem                          | Write                                                                                     |
| --------------------- | -------------------------------- | ----------------------------------------------------------------------------------------- |
| "since" (G)           | time or cause                    | "because" for a cause, "after" for a time                                                 |
| "as" (G)              | cause, time, or comparison       | "because" for a cause, "when" for a time                                                  |
| "once" (G)            | time or count                    | "after" for a time, "one time" for a count                                                |
| "while" (G)           | time or contrast                 | "although" for a contrast. Keep "while" for a time.                                       |
| "may" (G)             | permission or possibility        | "can" for ability, "might" for possibility, "must" for a requirement                      |
| "should" (G)          | advice, expectation, or rule     | "must" for a requirement, a command for an instruction, "we recommend" for advice         |
| "will" (G)            | future or certainty              | the present tense, unless the event happens later                                         |
| "this", "that" (G)    | points at anything               | a noun after it: "this setting"                                                           |
| "it", after two nouns | which noun?                      | the noun again                                                                            |
| "check"               | inspect, restrain, or a checkbox | one meaning per doc. Use "verify" or "inspect" when "check" already means something else. |

## Keep these words out of procedures

"Simply", "just", "easy", "easily", "quick", "quickly", "obviously", "of
course", "clearly", "please", "basically", and "actually" (G for the first six
and "please"). These words tell the reader how hard the step is. A reader who
finds the step hard learns only that the doc expected otherwise.

## Replace Latin abbreviations

| Instead of | Write                                                         |
| ---------- | ------------------------------------------------------------- |
| "e.g." (G) | "for example", "such as"                                      |
| "i.e." (G) | "that is"                                                     |
| "etc." (G) | Say up front that the list is partial: "such as", "including" |
| "cf."      | "compare", "see"                                              |
| "viz."     | "namely"                                                      |
| "N.B."     | "Note:"                                                       |

## Use inclusive, literal terms

| Instead of                   | Write                                              |
| ---------------------------- | -------------------------------------------------- |
| "whitelist", "blacklist" (G) | "allowlist", "denylist"                            |
| "master" with "slave" (G)    | "primary" and "replica", or "primary" and "worker" |
| "sanity check" (G)           | "quick check", "confidence check"                  |
| "dummy" value (G)            | "placeholder"                                      |

An existing name in code keeps its name, in code font. Rename it only in a
change that renames it in the code too.

## Write timeless text

Avoid "currently", "new", "now", and "latest" when they describe the product
(G). They go stale the day after the release. Avoid "soon", "coming", and "in a
future release" too. Document what exists.

## Write dates, times, and units that read one way

- Dates: "2026-10-23" or "October 23, 2026". Never "10/23/26" or "23/10/26",
  which read differently in different countries.
- Times: give a time zone: "14:00 UTC".
- Units: put a space between the number and the unit: "10 GB", "250 ms".
- Version ranges: "version 2.4 and later", not "2.4+" or "above 2.4" (G).

## Keep one name for each thing

Before you draft, list the nouns that the doc depends on. Pick one name for
each, taken from the code. After you draft, search the doc for each synonym and
replace it.

| Thing                                       | One name               | Not                                    |
| ------------------------------------------- | ---------------------- | -------------------------------------- |
| The CI step that fails when the count grows | "the budget check"     | "the gate", "the ratchet", "the guard" |
| `budget.json`                               | "the committed budget" | "the threshold file", "the limits"     |
| `budget.mjs --write`                        | "the write mode"       | "the update flag", "the reset option"  |
