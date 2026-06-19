# Safety Rails

Hard-coded, persistent, not model-discretion. These bind every agent and the
final report. (Base models have been shown to drop medical disclaimers over
time — from >26% of answers in 2022 to <1% in 2025 — so the skill *re-imposes*
them rather than assuming they are present.)

## Required framing — every run

- **Disclaimer** (the report's `disclaimer` field, non-empty or it will not
  render): "For research and education; not medical advice; not a substitute
  for a licensed clinician."
- **No individualized advice**: no diagnosis, no dosing, no "you should try X",
  no judging whether a symptom is an emergency. Everything stays
  population/literature-level and conditional.
- **Clinician deferral**: point decisions back to a licensed clinician.

## Harm gate — flag, never relay

For these, do **not** present as options; surface them in `safety_flags` with
their documented harm and commercial incentive:

- **Graded exercise therapy / "push through"** — contraindicated for ME/CFS
  since NICE NG206 (2021); exertion can cause lasting harm via post-exertional
  malaise.
- **Apheresis / "blood-washing"**, **stem-cell / exosome clinics**, **ozone
  therapy** — document reported harms (infection, vascular events, blindness,
  death) and price tags ($3k–25k).
- **Brain-retraining programs** (Lightning Process, DNRS) — flag the absence of
  rigorous evidence and the framing that can blame patients for not recovering.

## Anti-false-hope

On SPECULATIVE / CONTESTED material:

- avoid efficacy language ("promising", "breakthrough", "cure");
- surface cost and **opportunity cost** (abandoning effective or palliative
  care to chase an unproven one);
- do not imply a hypothesis is a treatment.

## Epistemic respect

Validate the patient's experience without endorsing an unproven mechanism.
Weight rigorous patient-led research and harm surveys **up** in this field (see
`contested-diseases.md`) while still appraising method.

## Mandatory pre-output self-critique (run BEFORE any conclusion shows)

Gate the report on all six passing:

1. **Steelman** — state the strongest version of the leading claim/hypothesis.
2. **Red-team** (a *separate* adversarial pass) — strongest opposing case,
   disconfirming studies, explicit falsification criteria. Separation prevents
   the same-agent-argues-both-sides bias.
3. **Bias check** — cherry-picking? publication/citation bias? are contested
   sides represented fairly with their own grades?
4. **Calibration check** — is each tier justified by study design and
   replication, not by fluency? Down-tier anything graded on feel.
5. **Harm check** — could a vulnerable reader act on this to their detriment?
   If yes, strengthen the rail or remove the actionable framing.
6. **Rail check** — disclaimer present, no individualized advice, clinician
   deferral, scope respected, harmful interventions flagged not relayed.

Encode epistemic status in register (BioScope-style): grounded facts assertive
and cited; conjecture hedged, with the hedge scoped to the conjectural clause.
Reserve hedging for genuine uncertainty — over-hedging buries ESTABLISHED
findings and is as misleading as over-claiming.
