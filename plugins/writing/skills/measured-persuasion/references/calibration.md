# Voice Calibration

The 8 traits in `../SKILL.md` describe a voice at full intensity. In practice, the voice is a dial, not a switch. This guide covers when to dial traits up, dial them down, or stop using the voice entirely.

The general principle: this voice earns trust through _visible deliberation_. That deliberation is a service to the reader when they need to be persuaded, and an imposition when they need to be informed, unblocked, or instructed. Match the voice to what the reader is there to do.

## Intensity by document type

| Document type                      | Intensity                | What to emphasize                                                                   | What to drop                                                  |
| ---------------------------------- | ------------------------ | ----------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Strategy memo / proposal           | Full                     | All 8 traits; scaffold load-bearing; hedging on the hypothesis                      | —                                                             |
| Experiment design / RFC            | Full, with extra hedging | Scaffold; deliberate hedging; contrastive framing on methodology choices            | —                                                             |
| Technical brief / design doc       | Medium                   | Contrastive framing, concrete anchoring, parenthetical precision                    | Scaffold as proposal structure; fewer inversions              |
| ADR (architecture decision record) | Low                      | One contrastive framing of the decision; parenthetical precision on technical terms | Scaffold, varied rhythm — ADRs want terse                     |
| Postmortem / incident report       | Not this voice           | —                                                                                   | Full voice; the reader wants timeline clarity, not persuasion |
| Release notes                      | Not this voice           | —                                                                                   | Full voice; the reader wants the change list                  |
| How-to / runbook / tutorial        | Not this voice           | —                                                                                   | Full voice; bullets and imperatives are the right shape       |
| API reference                      | Not this voice           | —                                                                                   | Full voice; precision without persuasion is the job           |

The cut-off between "full" and "medium" is about whether the document is _arguing_ or _describing_. Strategy memos argue. Design docs describe, and occasionally argue a decision or two. The argumentative sections within a design doc can deploy the voice; the descriptive sections should not.

## Intensity by section within a document

Even in a document where the voice is appropriate, intensity should vary:

- **Dial up** on: novel claims, methodology choices, counterintuitive positions, the thesis, the bit where you are asking the reader to change their mind. This is where deliberation is load-bearing.
- **Dial down** on: background context the reader already accepts, definitions of terms everyone knows, step-by-step procedures, transitional summaries. Here deliberation reads as padding.

A rough test: if you can remove a passage without changing the reader's decision, that passage should be written in a lighter voice. Save the full voice for the passages that do the persuading.

A more concrete rule: at most one inversion per section. Inversions are expensive — they force the reader to hold two framings in their head at once — so use them where the new framing actually earns the cost.

## Negative space: when this voice is wrong

The voice is wrong when the reader's situation makes visible deliberation a cost rather than a benefit.

- **Crisis communication / incident response.** During an outage, the on-call reader wants "here is what is broken, here is what we're doing, here is when the next update will be." Hedging reads as evasion; contrastive framing reads as wordiness. Use the voice for the postmortem's _lessons-learned_ section, not the timeline.
- **Instructional documentation.** How-to guides and tutorials want imperatives ("Run `make install`", not "It may be useful to begin by running `make install`"). The voice adds friction to the one task the reader is actually trying to accomplish.
- **Reference material.** API docs, configuration reference, glossaries. The reader wants precision without commentary. Parenthetical precision is fine; the rest of the voice is overhead.
- **Short internal messages.** Slack, PR descriptions, chat. The voice is calibrated for documents the reader will sit down with. If the message is a two-liner, write a two-liner.
- **Status updates.** Weekly updates, standups, progress reports. These want "done / doing / blocked," not persuasion.

A useful heuristic: if you cannot identify a _decision the reader needs to make_, they probably do not need to be persuaded, and this voice is probably overkill.

## Audience adaptation

The current SKILL.md describes the audience as "smart, skeptical, busy." That is a reasonable floor, but the audience actually varies along three axes. Calibrate as follows.

### Engineer-reader (peer or near-peer)

Can handle jargon. Expects precision. Will notice overexplanation and read it as condescension.

- Use technical terms directly; translate only the ones that cross subfield boundaries (e.g. "W3C Trace Context" is fine; "eventual consistency" may want a gloss for a frontend audience).
- Lean on concrete anchoring with real systems, file paths, API names.
- Hedging should be calibrated — engineers distinguish honest uncertainty from padded certainty.

### Cross-functional decision-maker (PM, staff engineer in another org, director)

Has context on the business problem but not the technical details. Needs the argument to survive translation.

- Translate every technical term inline the first time, per parenthetical precision.
- Lean heavier on concrete anchoring — the story beats the system diagram here.
- Structural scaffold matters more: state the context, state the hypothesis, state the test. Let them skim by section.

### Executive reader (VP, C-suite)

Wants the thesis first, the reasoning second, and the details third, if at all. Will bail halfway.

- Lead with the inversion or the thesis in the first two sentences. Do not bury it under context.
- Push methodology and caveats into a dedicated "How we would validate this" section or appendix.
- Hedging still matters — executives have radar for overconfidence — but the hedges should be compact, not recursive.

## Calibration checklist

Before shipping a draft in this voice, run through these questions:

1. **Is this the right document type?** If it's a runbook or release notes, stop and rewrite in the appropriate voice.
2. **Is the intensity varying across sections?** If every paragraph reads at the same density, the novel claims are not landing distinctively. Thin out the background.
3. **Does each inversion earn its cost?** Read every "is not X; is Y" sentence and ask whether removing it would weaken the argument. If not, cut it.
4. **Are the hedges hedging certainty, not the claim?** "It could potentially be argued that there might be some effect" is evasive. "The trajectory is plausible. The timeline is uncertain." is honest.
5. **Is the audience axis right?** Engineer-reader vs. executive-reader changes where the thesis lives in the document. If the first page does not tell an executive why to care, the document is miscalibrated for that reader.

The goal is a document where the density of the voice matches the density of the argument. Full voice where the persuasion happens; lighter voice everywhere else; no voice at all in the places where the reader just needs the answer.
