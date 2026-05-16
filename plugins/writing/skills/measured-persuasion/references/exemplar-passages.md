# Exemplar Passages by Trait

A compact reference for each of the 8 traits in `../SKILL.md`, drawn from `observability.md`. Use this as a pattern bank — a small set of "here is what this trait looks like in real prose" examples — not as a template to imitate. Each passage carries a line reference so you can return to the surrounding paragraph if you want to see how the trait fits into a larger argument.

The point of this file is to decouple the _trait_ from the _document_. The full exemplar (`observability.md`) commits to one subject, one structure, one audience. These passages are extracted from that structure so the voice can travel to any technical document.

## How to use this file

Read the trait name you want to deploy, scan its 2–3 passages, then write your own sentence in the same shape. Do not copy phrasing. The gloss above each passage names the _move_ the sentence makes; that move is what generalizes.

---

## 1. Contrastive framing

_Define by negation first, then by affirmation, at the sentence level. "not X, but Y."_

**Move: locate the true failure by naming a plausible-but-wrong explanation first.**

> The dashboard says the system is healthy. It is lying, not because the data is wrong, but because the questions the dashboard was built to answer are not the questions that matter right now.
>
> — `observability.md` line 9

**Move: deny the casual interpretation, then name the load-bearing one.**

> It is a property of the system itself (that is, a quality intrinsic to the system's architecture and instrumentation) that determines the degree to which an engineer can understand internal state by examining external outputs. […] Purchasing an observability platform does not make a system observable any more than purchasing a stethoscope makes a patient healthy.
>
> — `observability.md` line 29

**Move: collapse a quantitative difference into a qualitative one.**

> Without the trace, the engineer would start debugging the gateway. With it, they skip directly to the span that actually failed. This is not a minor efficiency gain; it is the difference between investigating the right service and investigating the wrong one.
>
> — `observability.md` line 218

---

## 2. Parenthetical precision

_Refine meaning mid-sentence with `(that is, …)` or `(not X, but Y)`. Also: translate jargon inline — precise term, then plain-English restatement in parentheses._

**Move: define a load-bearing term the first time it appears, then keep moving.**

> This document makes the case that observability (that is, the property of a system that enables engineers to answer novel diagnostic questions from its telemetry without deploying new code) is a prerequisite for operating distributed systems reliably.
>
> — `observability.md` line 13

**Move: qualify the claim mid-flight without starting a new sentence.**

> It is a property of the system itself (that is, a quality intrinsic to the system's architecture and instrumentation) that determines the degree to which an engineer can understand internal state by examining external outputs.
>
> — `observability.md` line 29

**Move: name the thing and gloss it in the same breath, for readers who may not share the jargon.**

> AI agents (that is, LLM-based tools with access to observability APIs) can automate the retrieval portion of this workflow.
>
> — `observability.md` line 332

---

## 3. Deliberate hedging

_Hedge the certainty, not the claim. State what you believe; qualify how sure you are._

**Move: state the result cleanly, then mark what it does and does not establish.**

> These results are encouraging, but they come with caveats: the evaluation benchmarks are heterogeneous, the sample sizes are small relative to the diversity of production incidents, and the comparison baselines vary across studies.
>
> — `observability.md` line 381

**Move: name the vendor claim, acknowledge it, then locate what is still missing.**

> The vendor claims are impressive, but they are vendor claims. Independent replication of these numbers in peer-reviewed settings remains sparse.
>
> — `observability.md` line 363

**Move: separate what is directionally true from what is unknown in one sentence each.**

> The trajectory is plausible. The timeline is uncertain.
>
> — `observability.md` line 405

---

## 4. Inversion for insight

_Flip the expected direction of the argument. Operates at the level of methodology or framing, not a single sentence._

**Move: redefine the object in terms of a property, not an activity.**

> Observability is not the act of watching a system; it is the quality of a system that makes watching it useful.
>
> — `observability.md` line 33

**Move: reframe two positions as opposite _kinds_ of question rather than opposite _intensities_ of the same question.**

> Monitoring asks a closed question: "is this metric above its threshold?" Distributed systems generate open questions: "why did this specific request, from this specific user, at this specific time, behave differently from the millions of requests that preceded it?"
>
> — `observability.md` line 23

**Distinction from contrastive framing:** contrastive framing is a sentence shape ("not X, but Y"). Inversion is an argumentative move — it changes which direction the reasoning runs. A passage can use both. The question is which lever you are pulling deliberately.

---

## 5. Concrete anchoring

_One well-chosen example per abstract claim. The example serves the abstraction; do not linger on it._

**Move: open with the scene, collapse to the abstract claim, then move on.**

> Imagine it is 3 a.m. and transcreation's on-call engineer is paged for a latency spike on `POST /arena/battle`. She opens the dashboard. The latency graph, which reports a five-minute rolling average, shows a gentle upward trend but nothing alarming. […] The dashboard says the system is healthy. It is lying.
>
> — `observability.md` line 9 (opening of the document)

**Move: make the cost of the old way visceral by listing the specific chores.**

> Without distributed tracing, triage means an engineer opens terminal windows to four services, greps their logs for timestamps near the alert, attempts to correlate entries by eye, and hopes that the relevant log lines were emitted at a verbosity level that was enabled in production. This process can take hours for a non-trivial cross-service failure. With tracing and exemplars, the same engineer follows a single trace ID from the alert to the root-cause span in minutes.
>
> — `observability.md` line 271

**Move: illustrate by walking through a single worked instance, then return immediately to the generalization.**

> It queries the metrics API for error rate and latency by route over the last 30 minutes […] It requests exemplar trace IDs from the latency histogram, fetches the full trace for the worst offender, and finds that the `anthropic.chat.completion` span consumed 14.2 seconds with two retries. […] The entire sequence follows the same narrowing funnel a human would use, but executes in seconds rather than minutes.
>
> — `observability.md` line 338

---

## 6. Varied rhythm

_Long sentences carry the reasoning; short sentences land the conclusion. Contrast is the mechanism — a short sentence only reads as a punch because the preceding sentence was long._

**Move: a compact, declarative reversal after a fuller explanatory one.**

> This is not theoretical. The infrastructure for AI-assisted debugging exists today in production-ready form. Its adoption is a function of trust calibration and instrumentation quality rather than technical feasibility. The tooling is ahead of the organizational readiness, which is the normal sequence for infrastructure shifts of this kind.
>
> — `observability.md` line 373

**Move: two short sentences close a long paragraph's hedging with a clean beat.**

> Their integration into a coherent, self-improving observability system remains an active area of development rather than a deployed reality. The trajectory is plausible. The timeline is uncertain.
>
> — `observability.md` line 405

**Move: a subordinate-clause sentence does the work; a four-word sentence pockets the result.**

> When an engineer opens a trace waterfall and sees that the `anthropic.chat.completion` span consumed 14 of the request's 16 seconds, the diagnosis is immediate. No grep required.
>
> — `observability.md` line 108

---

## 7. Logical signposting

_Small structural markers: "Concretely,", "In other words,", "That is,", "The workflow is concrete." Tell the reader where you are in the argument._

**Move: signal a pivot from statement to grounding.**

> The workflow is concrete. When a metric fires an alert (say, p95 latency on `POST /arena/battle` exceeds the 10-second SLO threshold), the engineer's first move is to pivot from the aggregate to the specific.
>
> — `observability.md` line 124

**Move: name the nature of what you just said before restating it more precisely.**

> This limitation is structural, not incidental. Metrics achieve their efficiency precisely because they discard per-event identity in favor of dimensional aggregation.
>
> — `observability.md` line 212

**Move: a one-sentence signpost that tells the reader which pillar answers which question.**

> Logs answer the "why" that traces structurally cannot.
>
> — `observability.md` line 224

Use signposts sparingly — one or two per section. More than that and they start narrating every step rather than marking inflection points.

---

## 8. Structural scaffold

_Three-part structure for proposals and strategy documents: Context → Hypothesis → Experiment. Within each section: abstract claim first, then concrete grounding, then implications._

Scaffold is a document-level trait, not a sentence-level one. Rather than extract passages, the reference here is to how `observability.md` uses the scaffold:

- **Context / current state** (roughly lines 9–34): grounds the problem in a concrete on-call scenario, then generalizes to the distributed-systems trend that breaks traditional monitoring.
- **Hypothesis** (roughly lines 27–118): observability is a property of the system, defined via control theory and instantiated through three composable pillars. Hedged (e.g., "the analogy breaks in another [direction]" at line 52) to signal what the framing does and does not claim.
- **Experiment / methodology** (roughly lines 180+): the debugging workflow — alert → metric → exemplar → trace → log — as the operational test of whether the hypothesis holds. Each pillar gets its own subsection, grounded in transcreation's actual API surface.

If you are writing a strategy memo or proposal, the scaffold is: what is true now, what we believe to be true but cannot yet prove, and how we would test it. The scaffold is the structural cousin of deliberate hedging — both separate "what we know" from "what we suspect" so the reader can calibrate trust.

---

## Cross-trait observations

Two patterns worth naming because they recur across the passages above:

1. **Traits compose; they rarely appear alone.** The triage passage (line 271) deploys hedging ("can take hours", "in minutes"), concrete anchoring (the tedious grep sequence), and varied rhythm (long → short → long) in eight lines. When revising, do not try to layer traits one pass at a time — write the paragraph, then check which traits earned their place.

2. **Contrastive framing and inversion often appear together.** "Observability is not the act of watching a system; it is the quality of a system that makes watching it useful" (line 33) is a contrastive-framing sentence doing the work of an inversion. Do not feel obligated to classify; feel obligated to notice which lever is load-bearing and lean on it.
