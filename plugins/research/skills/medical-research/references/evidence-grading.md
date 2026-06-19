# Evidence Grading — OCEBM + GRADE → Tier

Every grounded claim carries two grades and one tier. Grade from **study
design and replication**, never from how confident the prose feels.

## Step 1 — OCEBM 2011 level (per citation, fast)

A study-design tag for the strongest source behind the claim. For
treatment-benefit questions:

| Level | Design |
| --- | --- |
| **1** | Systematic review of RCTs (or n-of-1 trials) |
| **2** | Individual RCT (or observational study with a dramatic effect) |
| **3** | Non-randomized controlled cohort / follow-up study |
| **4** | Case-series, case-control, or historically-controlled study |
| **5** | Mechanism-based reasoning |

Downgrade a level for poor quality, imprecision, or **indirectness** (the
study's PICO does not match the question). Upgrade an observational study for a
large effect. The level maps to the `ocebm_level` field (`"1"`–`"5"`).

## Step 2 — GRADE certainty (per body of evidence)

The certainty rating across all sources for a claim → the `grade` field.

- **Start**: RCT evidence = High; observational = Low.
- **Rate DOWN** one level (serious) or two (very serious) for any of five
  domains: **risk of bias**, **inconsistency** (results disagree),
  **indirectness** (population/intervention/outcome mismatch), **imprecision**
  (wide CIs, few events), **publication bias**.
- **Rate UP** (observational only): **large effect**, **dose-response
  gradient**, **all plausible confounders would reduce** the observed effect.
- Result: `HIGH | MODERATE | LOW | VERY_LOW`.

Keep certainty-of-evidence separate from strength-of-conclusion. A consistent
finding from weak designs is still Low certainty.

## Step 3 — Informative-statement verb (GRADE Guideline 26)

Phrase the claim's `statement` with the verb that matches its certainty, so the
hedging is machine-checkable and a reader cannot misread strength:

| Certainty | Verb template |
| --- | --- |
| High | "X **results in / reduces** …" |
| Moderate | "X **likely / probably results in** …" |
| Low | "X **may result in** …" |
| Very Low | "the evidence is **very uncertain** about whether X …" |

## Step 4 — Tier

Map certainty + disagreement to the contract tier:

- **ESTABLISHED** (≈ High): multiple low-bias RCTs / strong reviews,
  guideline-endorsed.
- **EMERGING** (≈ Moderate): consistent but limited; some bias or few studies.
- **SPECULATIVE** (≈ Low / Very Low): single small study, preclinical, or
  mechanism-based — still cited, but flagged weak.
- **CONTESTED**: genuine expert disagreement / competing paradigms. Present
  **all** positions, each with its own grade; do not adjudicate beyond the
  evidence. Common in long COVID, ME/CFS, chronic Lyme.

## Contested-disease addendum — inverted heuristics

In this space a glossy RCT can be the *least* trustworthy artifact. For
unblindable behavioral interventions (graded exercise therapy, CBT-as-cure,
brain-retraining), **demand**:

- objective endpoints (not just self-report on an unblinded trial),
- pre-registration with no post-hoc outcome switching,
- no mid-trial redefinition of "recovery",
- auditable data.

**PACE is the worked example**: reported recovery (~60%) collapsed to ~20% on
patient-obtained reanalysis after outcome-switching; NICE GRADE-downgraded the
behavioral-intervention evidence to low/very-low. Downgrade hard when these
fail.

Each contested-disease claim additionally records:

- **`case_definition`** — which definition the cohort used, and whether it
  requires **post-exertional malaise** (CCC / ICC / IOM 2015 > Fukuda 1994 >
  Oxford). An "ME/CFS" cohort defined by Oxford (fatigue only, no PEM) may not
  generalize to a PEM-defined population — note it.
- **replication status** — independent lab? standardized assay? (the microclot
  literature is the cautionary tale: striking early findings, uneven
  replication.)
- **`commercial_conflict`** — does anyone sell the therapy being evaluated?
