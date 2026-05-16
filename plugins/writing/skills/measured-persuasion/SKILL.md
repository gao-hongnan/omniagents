---
name: measured-persuasion
description: >-
  Use when writing technical strategy memos, proposals, experiment designs,
  RFCs, investment justifications, executive narratives, or persuasive
  documents where skeptical decision-makers need evidence, caveats, tradeoffs,
  and a measured, intellectually honest tone.
when_to_use: >-
  Trigger for "write a proposal", "draft a memo", "strategy document",
  "make the case for", "persuade leadership", "justify investment",
  "experiment design", "executive narrative", "technical brief", or any draft
  where the reader must decide whether to approve, fund, prioritize, or change
  direction based on evidence.
argument-hint: "<TARGET>"
disable-model-invocation: false
user-invocable: true
allowed-tools: []
model: inherit
paths:
  - "**/*.md"
  - "**/*.markdown"
  - "**/*.rst"
  - "**/*.txt"
shell: bash
---

# Measured Persuasion

A prose style that persuades through precision, not assertion. It earns trust by
demonstrating that the writer has thought carefully, acknowledged complexity,
and chosen their words deliberately. The voice is formal but not stiff, hedged
but not evasive, abstract but anchored in concrete detail.

This skill is a revision and review guide, not a general-purpose "make it
sound smarter" filter. Use it when the document is trying to move a decision.
Do not apply the voice to operational writing where the reader needs speed,
sequence, or an exact answer more than deliberation.

## Non-negotiables

- Identify the decision the reader needs to make before revising the prose.
  If there is no decision, use a plainer writing style.
- Preserve truth over polish. Do not make claims stronger, broader, or more
  certain than the evidence supports.
- Separate facts, interpretation, and recommendation. Readers should be able
  to tell which parts are observed, which are inferred, and which are argued.
- Ground load-bearing claims with evidence. Cite external sources when a claim
  depends on research, benchmarks, current vendor behavior, standards, or
  quoted definitions.
- Keep the document useful for the intended audience. A dense executive memo
  is a failure even if every sentence is elegant.

## The 8 Traits

### 1. Contrastive Framing

Make points by defining what something is NOT, then what it IS. This forces
precision and signals nuance.

**Weak:**

> AI tooling improves developer productivity.

**This voice:**

> The productivity gains from AI-assisted development derive not solely from the
> capabilities of the agent itself, but from the quality of the environment it
> operates in.

Use on: Key claims, thesis statements, any point where the reader might assume a
simpler version of your argument.

Contrastive framing is a _sentence-level_ move — the shape "not X, but Y". It is
easily confused with inversion (§4), which operates at the level of the
argument, not the sentence. A single passage can use both. The distinction is
which lever you are pulling deliberately: the sentence shape, or the direction
of the reasoning.

### 2. Parenthetical Precision

Tighten meaning mid-sentence with `(that is, ...)`, `(or, at least, ...)`,
`(not X, but Y)`. This shows the writer refining their own thought in real time.

This trait also serves a second purpose: **translating jargon inline**. Use the
precise academic or technical term, then immediately follow it with a
plain-English restatement in parentheses. The jargon earns precision; the
parenthetical earns accessibility.

**Weak:**

> We wanted to prevent the codebase from degrading.

**This voice:**

> I sought to avoid (or, at least, delay) the process of this "greenfield"
> turning into a "brownfield".

**Jargon translation:**

> It may be useful to distinguish between latency (how quickly a given piece of
> work is delivered) and throughput (how much is delivered overall).

Use on: Claims that need qualification, terms that could be misread, technical
vocabulary that not all readers will share, moments where you want to show you
considered the edge case.

### 3. Deliberate Hedging

Use "may be", "rather than", "not solely", "can be" — not as weakness, but as
intellectual honesty. The reader should feel that the writer is being precise
about what they know versus what they believe.

**Weak (overconfident):**

> Documentation investment pays off in the long run.

**Weak (evasive):**

> It could potentially possibly be argued that documentation might have some
> effect.

**This voice:**

> The impact from this kind of foundation investment is indirect and deferred,
> making it difficult to attribute and easy to deprioritise.

The line between honest hedging and evasive hedging: hedge the _certainty_, not
the _claim_. State what you believe, then qualify how sure you are.

### 4. Inversion for Insight

Flip the expected direction of an argument to reveal something non-obvious. This
is the signature move of this voice.

**Conventional direction:**

> Take a poorly-documented codebase and improve it, then measure the difference.

**Inverted:**

> Degrading from a known good state inverts this problem. It is easier to
> rigorously destroy documentation than to rigorously create it. Documentation
> can be missing or wrong in many ways, but is complete and correct in
> essentially one way.

Use on: Methodology choices, counterintuitive positions, anywhere the reader's
default assumption needs redirecting.

_Why it works._ Expectation violation forces the reader to hold both the default
framing and your framing in mind at the same time. That simultaneous comparison
is how nuance actually transmits — a claim written in the conventional direction
can be agreed with and immediately forgotten, because it did not require the
reader to reshuffle anything. An inverted claim cannot be absorbed without some
reshuffling, which is precisely when thinking happens.

Inversion is expensive for the reader, so use it where a new framing actually
earns the cost — methodology choices, thesis-level claims, counterintuitive
positions. At most one inversion per section; more and they stop landing.

### 5. Concrete Anchoring

Ground one abstract argument per section with a single, well-chosen concrete
example. Then zoom back out. Do not linger on the example; it serves the
abstraction, not the other way around.

**Abstract only:**

> Small documentation errors can disrupt automated workflows.

**This voice:**

> Even at this early stage, a brief code snippet added to the project-level
> CLAUDE.md nudged the agent to run unit tests with `pytest` rather than
> `uv run pytest`, losing the required dependencies from the virtual
> environment. This is a minor interruption, but results in breaking the agentic
> loop, becoming a potential blocker on the agent's ability to operate
> autonomously.

One example per abstract claim. Choose the most illustrative one, not the most
dramatic.

### 6. Varied Rhythm

Alternate between complex subordinate-clause sentences and short declarative
punches. The complex sentences do the analytical work; the short ones land the
point.

**Monotonous:**

> The bottleneck shifts elsewhere. The equilibrium changes. The configuration
> becomes suboptimal.

**This voice:**

> If AI tooling substantially relaxes that constraint (that is, if developers
> are now potentially more productive individually), the current configuration
> may no longer be optimal, not because anything is broken, but because the
> equilibrium it was designed for has shifted.

Follow a long sentence with a short one. Follow a qualified claim with an
unqualified one.

_Why it works._ The contrast is the mechanism. A short declarative sentence
lands as a punch only because the preceding sentence made the reader hold
several clauses in mind; after that cognitive load, a short sentence gives them
a place to rest and marks its content as load-bearing. Without the long sentence
before it, the short one reads as a fragment; without the short sentence after,
the long one reads as sprawl. Varied rhythm is not an aesthetic preference but a
way of telling the reader which claims to remember.

### 7. Logical Signposting

Use explicit connectors to show the reader where you are in the argument:
"Concretely,", "In other words,", "That is,", "Rather than", "This reflects a
concern with a longer horizon,".

These are not filler. They are structural markers that tell the reader: "I am
about to restate this more precisely" or "I am about to ground this in
practice".

Use sparingly — one or two per section. They should feel like a hand on the
reader's shoulder, not a tour guide narrating every step.

### 8. Structural Scaffold

For proposals and strategy documents, use this three-part structure:

**Context / Pain Points / Current State** — What is true now. What is
insufficient about it. Ground this in specific observations, not generic
complaints.

**Hypothesis** — What you believe to be true, stated as a testable claim. Use
hedging here. Distinguish between what you know and what you suspect.

**Experiment / Test Methodology** — How to validate the hypothesis. Be concrete
about steps. Explain design choices (why this approach rather than an
alternative).

Within each section: abstract claim first, then concrete grounding, then
implications.

## Anti-Patterns

This voice is NOT:

- **Unexplained jargon.** Academic and technical terms are encouraged, but
  always followed by a plain-English restatement in parentheses. The jargon
  earns precision; the restatement earns accessibility. Never assume the reader
  knows the term.
- **Corporate buzzwords.** "Leverage synergies", "drive alignment" — this
  voice earns authority through precision, not vocabulary.
- **Hedging into nothing.** "It could potentially be argued that there might be
  some effect" — hedge the certainty, not the claim.
- **AI-balanced writing.** Rule of three, em dash decoration, "not only X but
  also Y" as filler.
- **Bullet-point thinking.** This voice uses prose paragraphs. Reserve bullets
  for methodology steps only.
- **Assertion without grounding.** "This is important." — says who? Ground it
  or qualify it.

## When NOT to use this voice

This voice earns trust through _visible deliberation_. That deliberation is a
service to the reader when they need to be persuaded, and an imposition when
they need to be informed, unblocked, or instructed. Match the voice to what the
reader is there to do.

Do not use this voice for:

- **Incident postmortems and crisis communication.** The on-call reader wants
  timeline clarity, not persuasion; hedging reads as evasion.
- **Release notes and changelogs.** The reader wants the change list, not a
  thesis.
- **How-to guides, tutorials, runbooks.** Imperatives ("run `make install`") are
  the right shape; parenthetical qualifications get in the way of the task.
- **API reference and configuration documentation.** Precision without
  persuasion is the job.
- **Short internal messages** (Slack, PR descriptions, status updates). If the
  message is a two-liner, write a two-liner.

A useful heuristic: if you cannot identify a _decision the reader needs to
make_, they probably do not need to be persuaded, and this voice is probably
overkill. For details on document-type calibration, see
`references/calibration.md`.

## Calibration

The 8 traits describe the voice at full intensity. In practice, the voice is a
dial, not a switch. Strategy memos and proposals warrant the full voice. Design
documents and ADRs want it only in the sections where a decision is being
argued. Most technical writing — reference, tutorial, status — wants little or
none of it.

Within a document where the voice is appropriate, intensity should still vary.
Dial up on novel claims, methodology choices, and the thesis. Dial down on
background context, agreed-upon definitions, and step-by-step procedures. A
rough test: if removing a passage would not change the reader's decision, that
passage should be written in a lighter voice.

Audience matters too. An engineer-reader can absorb jargon directly; a
cross-functional decision-maker needs every technical term translated inline; an
executive reader wants the thesis in the first two sentences and the methodology
in an appendix.

For the full calibration guide, including document-type mappings and audience
variants, see `references/calibration.md`.

## Evidence and Citations

Persuasion in this voice depends on visible judgment. Citations are part of
that judgment, but only when they carry weight.

Use citations for:

- Empirical claims: benchmark results, market size, productivity data, incident
  statistics, survey findings.
- Current external behavior: vendor features, standards, model or tool
  capabilities, pricing, policy, or compatibility.
- Quoted definitions and named frameworks.
- Claims a skeptical reader would reasonably challenge.

Do not cite:

- The writer's own recommendation when it follows from already-cited evidence.
- Common project context that the intended audience already knows.
- Every sentence in a paragraph. Citation density can obscure the argument.

Prefer primary sources: standards, official docs, upstream repositories, papers,
or original reports. Use secondary sources only when the source is itself the
subject of the claim.

Citation format depends on the document:

- Normal Markdown: cite with inline links close to the claim.
- MyST / Sphinx documents: use `{cite:p}` / `{cite:t}` only when the document
  set includes a configured BibTeX file.
- Pandoc-style documents: use `[@key]` only when the bibliography is present.

Before shipping a cited draft, run a citation pass:

1. Every quote has a source.
2. Every `{cite}` / `[@key]` key resolves.
3. Every current external claim has been checked against a primary source.
4. Vendor claims are labeled as vendor claims unless independently verified.
5. The sources support the sentence they are attached to, not just the topic.

## Process

1. **Draft the content** in plain language. Get the argument right first.
2. **Apply contrastive framing** to the 2-3 most important claims. Rewrite them
   as "not X, but Y".
3. **Add parenthetical precision** where a term could be misread or a claim
   needs qualification.
4. **Ground at least one abstract argument per section** with a concrete
   anecdote or example. Choose the most illustrative, not the most dramatic.
5. **Vary sentence rhythm.** Find clusters of same-length sentences and break
   them up.
6. **Add logical signposts** at transitions: "Concretely,", "In other words,",
   "That is,".
7. **Check hedging balance.** Every hedge should qualify certainty, not dilute
   the claim.
8. **Final pass:** Remove residual AI-shaped patterns: ornamental em dashes,
   rule-of-three padding, "not only X but also Y" filler, and symmetrical
   paragraphs that add no new claim.

## Audience

This voice is calibrated for decision-makers who:

- Need to be persuaded, not instructed
- Respect intellectual honesty over confidence
- Will notice if you overstate your case
- Value concrete evidence over abstract claims

Write as if the reader is smart, skeptical, and busy. That baseline covers most
cases; see `references/calibration.md` for how to adjust emphasis for
engineer-peer, cross-functional, and executive readers specifically.

## References

- `references/exemplar-passages.md` — short passages demonstrating each trait,
  with one-line glosses and line attributions. Read this when you want to see
  what a trait looks like in real prose without committing to a full exemplar
  document.
- `references/calibration.md` — guidance on voice intensity by document type and
  section, audience adaptation, and when not to use the voice at all.
- `references/observability.md` — optional extended exemplar. A full document
  written in this voice, useful mainly when drafting a multi-section strategy
  document where seeing the Context → Hypothesis → Experiment scaffold operate
  at length would help. Do not treat it as a template to imitate structurally;
  every document has its own structure.
- [MyST citations](https://mystmd.org/guide/citations) — source for `{cite:p}`
  / `{cite:t}`, DOI citations, and bibliography configuration when the draft is
  a MyST document.
- [CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/) — baseline Markdown
  syntax reference when the output format is Markdown.

## Freshness

This skill defines a project voice and review policy. It is not a permanent
source of truth for external claims. Before using current vendor features,
market data, standards, model capabilities, tool behavior, or benchmark results
as evidence, verify against primary sources. Prefer Context7 MCP for official
documentation when available; otherwise use official docs, standards, papers,
or upstream repositories.
