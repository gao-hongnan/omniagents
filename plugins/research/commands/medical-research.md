---
description:
    Run a citation-grounded medical literature study: triage and decompose the
    question, fan out retrievers over biomedical sources, verify every citation
    through two gates (existence + entailment), optionally generate and critique
    hypotheses, and persist every artifact under .research/<timestamp>/
argument-hint:
    <research question or condition> [theorize|hypothesis to enable hypothesis mode]
allowed-tools:
    Bash(git rev-parse:*), Bash(git config:*), Bash(mkdir:*), Bash(date:*),
    Bash(python3:*), Bash(ln:*), Bash(grep:*), Bash(printf:*), Bash(basename:*),
    Glob, Read, Write, Agent, AskUserQuestion
model: inherit
---

## Context

- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Author: !`git config user.name 2>/dev/null || echo 'unknown'`
- Today: !`date +%Y-%m-%d`

## Task

Run the medical-research pipeline for `$ARGUMENTS`. JSON is canonical; Markdown
is rendered by `${CLAUDE_PLUGIN_ROOT}/skills/research-contract/schema.py`
(stdlib only). The contract, tiers, Iron Law, and safety rails live in the
`omniagents-research:research-contract` and `omniagents-research:medical-research`
skills — apply them.

**This is research, not medical advice.** No diagnosis, dosing, individualized
recommendation, or emergency triage ever appears in the output. Harmful or
predatory interventions are flagged in `safety_flags`, never relayed as
options.

1. **Parse `$ARGUMENTS`** into a research question and a mode. Mode is
   `hypothesis` if the user asked to theorize / hypothesize / explore
   mechanisms / "what could explain", else `grounded`.

2. **Clarify / triage (Stage 0).** If the question is underspecified (no
   condition, population, or angle), ask 2–3 scoping questions with
   `AskUserQuestion` — condition, population/subtype, whether they want
   intervention vs mechanism vs prognosis, and whether to theorize — then stop
   for the answer. If a contested condition is named (long COVID, ME/CFS, POTS,
   fibromyalgia, MCAS), note that contested-disease heuristics and harm rails
   apply.

3. **Plan / decompose (Stage 1).** Break the question into 3–8 orthogonal
   sub-questions, each classified by OCEBM question-type. Create the run
   directory and write `plan.md`:

    `D="$(git rev-parse --show-toplevel 2>/dev/null || pwd)/.research/$(date +%Y-%m-%dT%H-%M-%S)"; mkdir -p "$D"; echo "$D"`

   Write the question, mode, and numbered sub-questions to `<DIR>/plan.md`.

4. **Fan-out retrieval (Stage 2).** Dispatch one `retriever` per sub-question
   with the `Agent` tool **in parallel**, before reading any result. Number
   them `01`, `02`, … Each prompt is self-contained:
    - **Overall question** and **this retriever's one sub-question**.
    - **Mode** and the run directory.
    - **Report path**: `<DIR>/NN_<slug>.json` — the retriever `Write`s its
      `RetrieverReport` JSON there and returns a one-line summary.
    - Reminder: structured biomedical sources only; verbatim quote + resolver
      URL + locator per citation; grade and tier per the contract; abstain
      rather than fabricate.

5. **Validate + render each retriever report** as it returns:
    - `python3 "${CLAUDE_PLUGIN_ROOT}/skills/research-contract/schema.py" notes "<DIR>/NN_<slug>.json"`
    - On a validation error it names the offending field — fix that field (or
      drop the offending claim; never invent data) and re-run. Re-dispatch a
      retriever once if it failed to write its file.

6. **Gate 1 — existence (Stage 6a).** Dispatch `citation-verifier` with the
   overall question, mode, author, date, disclaimer, and the contents of every
   `<DIR>/NN_<slug>.json` verbatim. It resolves every identifier, dedupes,
   filters, and returns one merged report JSON object. `Write` it verbatim to
   `<DIR>/merged.json`.

7. **Hypothesis generation + critique (Stage 6b — hypothesis mode only).**
   Before Gate 2: from the merged grounded claims, draft 2–4 candidate
   literature-based-discovery hypotheses (ABC chains with cited edges, per the
   `theorizing` reference). Dispatch `hypothesis-critic` with the candidates and
   the grounded claims; it verifies every edge, red-teams, runs the novelty
   check, and returns the survivors. Fold survivors into the merged report's
   `hypotheses[]`; demote the rest to `open_questions`. In grounded mode,
   `hypotheses` stays `[]`.

8. **Gate 2 — support / final report (Stage 6c).** Dispatch
   `evidence-adjudicator` with the run context and the contents of
   `<DIR>/merged.json` verbatim. It re-fetches each source, checks entailment,
   confirms / down-tiers / drops each claim, enforces the safety rails and the
   six-step self-critique, and returns the final research report JSON object.
   `Write` it verbatim to `<DIR>/report.json`.

9. **Render the report:**
    - `python3 "${CLAUDE_PLUGIN_ROOT}/skills/research-contract/schema.py" report "<DIR>/report.json"`
    - Fix-and-rerun on validation errors as in step 5. (A report with no
      `disclaimer` will not render — that is the rail working.)

10. **Persist a claim ledger and finalize.** Write `<DIR>/claim-ledger.json`
    (each claim: statement, identifier, quote, support verdict, tier, grade).
    Point `latest` at the run and keep `.research/` out of git:

    `R="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"; ln -sfn "$(basename "<DIR>")" "$R/.research/latest"; grep -qxF '.research/' "$R/.gitignore" 2>/dev/null || printf '.research/\n' >> "$R/.gitignore"`

    Then `Read` `<DIR>/report.md` and relay it verbatim. You may prepend one
    sentence (how many claims the gates dropped). End with one line pointing to
    the artifacts, e.g.
    `Saved: .research/<timestamp>/ — report.md plus per-sub-question notes, merged.json, report.json, and claim-ledger.json.`

Question: $ARGUMENTS
