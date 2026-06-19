# Report Layout

The report is **rendered from JSON** by `research-contract/schema.py` — never
hand-write the Markdown. This is what belongs in each section so the JSON you
emit renders well.

## Sections (rendered in this order)

1. **Disclaimer** (`disclaimer`) — the standard framing line. Required.
2. **Executive Summary** (`executive_summary`) — 200–300 words. Each headline
   finding names its tier inline. Lead with what is ESTABLISHED, then EMERGING,
   then what is genuinely CONTESTED, then (if any) the strongest hypotheses
   clearly marked speculative.
3. **Findings** (`claims`, grouped by `sub_question`) — every claim phrased with
   its GRADE informative verb, tagged `[TIER]`, with OCEBM level, support
   verdict, confidence, one-line note, and ≥1 citation (resolver link + verbatim
   quote + locator). Contested-disease claims add case-definition/PEM and
   commercial-conflict.
4. **Mechanistic Hypotheses** (`hypotheses`, hypothesis mode only) — 2–4
   competing mechanisms, each an A→B→C chain with named bridge, cited edges,
   confidence, assumptions, discriminating test, falsification, novelty badge.
5. **Contested / Conflicting Evidence** (`contested`) — present all sides with
   each side's grade. Do not average.
6. **Safety Flags** (`safety_flags`) — harmful/predatory interventions with harm
   profile + commercial context.
7. **Open Questions** (`open_questions`) — what could not be resolved and why
   (paywalled-abstract-only items, freshness limits, missing replication).
8. **Sources** — auto-collected from every citation (resolver links; retractions
   and preprints marked).
9. **Method / Audit** (`audit`) — sub-question count, search/fetch counts,
   `claims_dropped` (mirrors the reviewer's "adjudication dropped N"),
   refusal rate, API/version caveats.

## Field discipline

- **Lead with strength, end with uncertainty.** A reader should know in the
  first paragraph what is solid and what is a guess.
- **Every claim opens-and-checks.** The resolver link opens the source; the
  quote is what they check the claim against. If you cannot supply both, the
  claim does not belong in `claims` — abstain or move to `open_questions`.
- **`claims_dropped` is a feature.** Report how many claims the gates dropped or
  down-tiered; a run that drops nothing is suspicious.

## Worked fragment (one claim, as JSON)

```json
{
  "statement": "Low-dose naltrexone may reduce fatigue in some long COVID patients.",
  "tier": "SPECULATIVE",
  "grade": "VERY_LOW",
  "ocebm_level": "4",
  "sub_question": "What pharmacological options have any evidence?",
  "citations": [
    {
      "identifier": "PMID:37000000",
      "url": "https://pubmed.ncbi.nlm.nih.gov/37000000/",
      "quote": "In this open-label case series, 38% reported reduced fatigue at 8 weeks.",
      "locator": "Results, Table 2",
      "source_type": "case-series",
      "peer_reviewed": true,
      "retracted": false
    }
  ],
  "support": "ENTAILED",
  "confidence": 62,
  "commercial_conflict": "none",
  "note": "Open-label, no control arm, n=40; hypothesis-generating only."
}
```

Note the Very-Low GRADE, the "may" verb, the explicit no-control limitation,
and confidence below the grounded-claim comfort line — all consistent. A
reader cannot mistake this for an ESTABLISHED treatment.
