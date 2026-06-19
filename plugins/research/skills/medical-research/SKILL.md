---
name: medical-research
description: >-
  Citation-grounded biomedical literature research and responsible hypothesis
  generation for contested chronic diseases. Retrieves before generating
  against PubMed / Europe PMC / ClinicalTrials.gov, tethers every claim to a
  resolvable PMID/DOI with a verbatim quote, grades evidence (OCEBM + GRADE),
  and theorizes beyond textbooks ONLY in a fenced, falsifiable hypothesis
  space. Never gives individualized medical advice.
when_to_use: >-
  Trigger for medical/biomedical literature research, evidence synthesis,
  "what does the research say about", mechanism questions, contested or
  emerging conditions (long COVID, ME/CFS, POTS, fibromyalgia, MCAS),
  novel-hypothesis generation grounded in literature, GRADE / evidence
  grading, systematic-style searches, or citation verification of medical
  claims. NOT for individual diagnosis, treatment, or dosing advice.
disable-model-invocation: false
user-invocable: false
model: inherit
---

# Medical Research — Grounded Evidence + Responsible Theorizing

A research method for diseases the textbooks get wrong. For contested,
fast-moving, under-characterized conditions — long COVID, ME/CFS, POTS,
fibromyalgia, MCAS — textbooks are stale and sometimes harmful (many still
present graded exercise therapy as treatment, contraindicated for ME/CFS since
NICE NG206 in 2021). The leading evidence lives in preprints, large cohorts
and GWAS (RECOVER, DecodeME), named labs, and rigorous patient-led research.
This skill reaches that evidence, verifies it claim-by-claim, and — on request
— theorizes past it without fabricating.

The whole method rests on **one hard wall**: a *grounded channel* where every
claim is tethered to a resolvable source and graded, and a *fenced hypothesis
channel* where novelty comes only from connecting cited facts. Hallucination
is the two blurring; the wall is what keeps it honest.

## What this does — and does not — do

**Does:** retrieve-before-generate over structured biomedical APIs; tether
every claim to a resolvable identifier with a quote-and-locate snippet; grade
evidence (OCEBM per-citation + GRADE per-body); run a two-gate verification
(existence, then entailment); generate literature-based-discovery hypotheses
with named bridging mechanisms and discriminating tests; emit a tiered,
audited report.

**Does NOT:** give individualized medical advice, diagnose, dose, or judge
whether a symptom is an emergency; recommend a treatment "you should try";
present graded exercise therapy as recommended; neutrally relay apheresis /
"blood-washing", stem-cell/exosome, ozone, or brain-retraining offerings; cite
from model memory or the open web; let a speculative claim read as actionable.
Every run reasserts: *for research and education; not medical advice; not a
substitute for a licensed clinician.*

## Two modes

- **grounded** (default) — only claims tethered to retrieved sources, graded
  and tiered. No hypotheses.
- **hypothesis** — grounded claims *plus* a fenced theorizing channel. Enable
  when the user asks to "theorize", "hypothesize", "what could explain", or
  explore mechanisms. Hypotheses are built only by combining cited facts and
  always ship with a falsification test.

## Pipeline

Orchestrated by the `/medical-research` command, which dispatches the
`retriever`, `citation-verifier`, `evidence-adjudicator`, and (in hypothesis
mode) `hypothesis-critic` agents and persists every artifact under
`.research/<timestamp>/`. The contract and schema are defined in the
`research-contract` skill (preloaded into every agent).

0. **Clarify / triage.** If underspecified, ask 2–3 scoping questions
   (condition, population/subtype, intervention-vs-mechanism-vs-prognosis,
   whether theorizing is wanted). Detect contested-disease mode → load the
   inverted heuristics in `references/contested-diseases.md`. Detect theorize
   intent → enable hypothesis mode.
1. **Plan / decompose.** Break the question into 3–8 orthogonal sub-questions,
   classify each by OCEBM question-type, write `plan.md`.
2. **Fan-out retrieval.** One `retriever` per sub-question, each with a fresh
   context window, retrieving only from structured biomedical sources.
3. **Iterative search.** Inside each retriever: search broad → read → reflect →
   narrow, until ≥2 independent sources per claim (or 1 if authoritative) or a
   search cap is hit. Every fact stored as identifier + verbatim quote +
   locator.
4. **Source tiering & normalization.** Classify and down-tier abstract-only /
   paywalled / preprint / retracted sources; dedupe by DOI + statement.
5. **Synthesize (draft).** Reconcile retriever notes into claims — conflicts
   reconciled, not averaged.
6. **Verify — two gates.** `citation-verifier` resolves every identifier
   (Gate 1: existence); `evidence-adjudicator` re-fetches each source and
   checks the quote entails the claim with the draft out of context (Gate 2:
   support), confirming / down-tiering / dropping each.
7. **Report.** Render the tiered, audited `report.md`.

## References (read on demand)

- `references/biomedical-apis.md` — the source matrix: which MCP tools / APIs
  to call for what, auth, rate limits, identifier-resolution gotchas.
- `references/evidence-grading.md` — OCEBM 2011 grid, GRADE up/down domains,
  Guideline-26 informative verbs, tier mapping.
- `references/contested-diseases.md` — source-priority ladder, inverted
  heuristics, the five-mechanism menu, PACE / microclot / predatory traps,
  named cohorts and labs.
- `references/theorizing.md` — literature-based discovery (ABC), Strong
  Inference, the abduction scaffold, the novelty check, falsification format.
- `references/safety-rails.md` — disclaimers, the harm-flag list, anti-false-
  hope, and the mandatory six-step pre-output self-critique.
- `references/report-template.md` — the report layout and a worked example.

## The Iron Law

> NO SOURCE = NO CLAIM. EXISTENCE IS NOT SUPPORT. EVERY GROUNDED CLAIM CARRIES
> A RESOLVABLE IDENTIFIER, A VERBATIM QUOTE, AND AN EVIDENCE GRADE.

Abstention beats fabrication. A short report of verified claims outperforms a
long one of plausible claims. Before any conclusion shows, run the six-step
self-critique in `references/safety-rails.md` — steelman, red-team, bias
check, calibration check, harm check, rail check.

## How to run

Use the `/medical-research` command: `/medical-research <question or
condition>` (append a theorizing request to enable hypothesis mode). It
requires the plugin's two MCP servers (`pubmed`, `biomcp`) — see the plugin
README for setup and API keys.
