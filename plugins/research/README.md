# omniagents-research

Citation-grounded biomedical literature research with responsible hypothesis
generation — built for the diseases textbooks get wrong (long COVID, ME/CFS,
POTS/dysautonomia, fibromyalgia, MCAS).

It works by holding a **hard wall** between two channels:

- a **grounded channel** where every claim is retrieved-before-generated,
  tethered to a resolvable PMID/DOI with a verbatim quote, graded (OCEBM +
  GRADE), and passed through two independent verification gates (existence,
  then entailment); and
- a **fenced hypothesis channel** (opt-in) where novelty comes only from
  connecting *cited* facts (literature-based discovery), and every hypothesis
  ships with a discriminating test and a falsification criterion.

> **For research and education only. Not medical advice, not a diagnosis, and
> not a substitute for a licensed clinician.** The plugin never gives
> individualized treatment, dosing, or emergency guidance, and it flags
> harmful/predatory interventions rather than relaying them.

## What it is

| Piece | Path |
| --- | --- |
| Entry command | `/medical-research <question> [theorize]` |
| Methodology skill | `skills/medical-research/` (+ 6 references) |
| Contract + renderer | `skills/research-contract/` (`SKILL.md` + `schema.py`) |
| Retrieval specialist | `agents/retriever.md` (one per sub-question) |
| Gate 1 — existence | `agents/citation-verifier.md` |
| Gate 2 — entailment | `agents/evidence-adjudicator.md` |
| Hypothesis critic | `agents/hypothesis-critic.md` (hypothesis mode) |
| Wiring lint | `scripts/doctor.py` |

## Setup

The plugin declares two MCP servers in `.mcp.json`; they start automatically
when the plugin is installed, but each needs a runtime and (optionally) API
keys for usable rate limits.

### Runtimes

- **`pubmed`** (`@cyanheads/pubmed-mcp-server`) — needs **Node.js 18+** (runs
  via `npx`). This is the workhorse: PubMed + Europe PMC + Unpaywall full-text,
  citation formatting, ID conversion.
- **`biomcp`** (`biomcp-python`) — needs **`uv`** (runs via `uvx`). Secondary:
  trials, variants, genomics.

### API keys (set in your shell environment)

All optional — the servers run without them, just at lower rate limits — except
where noted by the workflow at runtime.

| Variable | Used by | Why |
| --- | --- | --- |
| `NCBI_API_KEY` | pubmed, biomcp | PubMed 3→10 req/s ([get one free](https://www.ncbi.nlm.nih.gov/account/)) |
| `NCBI_ADMIN_EMAIL` | pubmed | NCBI/Europe PMC polite-pool identification |
| `UNPAYWALL_EMAIL` | pubmed | **mandatory** for Unpaywall open-access full-text resolution |

Note: **OpenAlex now requires an API key** (since 2026-02-13; the `mailto`
polite pool was removed). The pipeline prefers PubMed/Europe PMC, which do not
need it; OpenAlex is only a fallback enrichment path.

## Usage

```
/medical-research what does the evidence say about viral persistence in long COVID
/medical-research theorize about mitochondrial mechanisms in ME/CFS
```

If the question is underspecified, the command asks 2–3 scoping questions
first. Append "theorize" / "hypothesize" / "what could explain" to enable
hypothesis mode.

### What you get

Every run writes a git-ignored folder:

```
.research/<timestamp>/
  plan.md              # sub-questions + mode
  NN_<slug>.json/.md   # one retriever report per sub-question
  merged.json          # after Gate 1 (existence)
  report.json          # canonical final report (after Gate 2)
  report.md            # the headline, tiered, cited report
  claim-ledger.json    # per-claim audit trail
.research/latest -> <timestamp>
```

The report tiers every claim **ESTABLISHED / EMERGING / CONTESTED /
SPECULATIVE**, phrases each with its GRADE verb, links every source, and (in
hypothesis mode) lists competing mechanisms with their falsification tests.

## How the rigor is enforced

- **The Iron Law**, in code: `schema.py` refuses to render a claim without a
  resolvable identifier *and* a verbatim quote — "no source = no claim" is
  validated, not trusted.
- **Existence ≠ support**: a real citation routinely fails to back its claim,
  so Gate 1 (the citation-verifier resolves identifiers) and Gate 2 (the
  evidence-adjudicator re-fetches and checks entailment with the draft out of
  context) are *separate* passes. Expect claims to be dropped or down-tiered
  every run.
- **Theorizing stays honest**: hypotheses never render as grounded claims; the
  hypothesis-critic rejects any chain edge that does not resolve to a source
  asserting it.

## Health check

```
/research-doctor                   # wiring lint + offline contract guard (+ --deep canary)
python3 scripts/doctor.py          # the lint alone (or --json)
bash evals/check_schema.sh         # the deterministic contract guard alone
```

`doctor.py` verifies the agent `skills:` preloads resolve, the four agents are
wired to the command, `schema.py` runs, and both MCP servers are declared.
`check_schema.sh` proves — offline, no MCP — that `schema.py` rejects a
sourceless or unquoted claim, a malformed identifier, a leaked hypothesis, and
a disclaimer-less report. `/research-doctor --deep` additionally canary-tests
that the `retriever`'s skills actually preloaded.

## Evals

`evals/` measures **recall** (right evidence + right safety flags) and
**precision** (no fabricated citation, no harmful recommendation):

- `evals/check_schema.sh` — deterministic structural guard (runs now, no MCP).
- `evals/fixtures/fabricated-pmid/` — Gate 1: a plausibly-formatted but
  non-existent `PMID:99999999` must be dropped by resolution, the resolvable
  control kept.
- `evals/fixtures/pace-get-safety/` — safety rails: GET is flagged as harm
  (PEM; NICE NG206, 2021), never recommended, and no individualized advice is
  given.

Behavioral fixtures need the plugin installed with MCP up; see
`evals/README.md`.

## Known limitations

- **biomcp tool names are version-dependent.** The agents allow-list biomcp's
  unified `search`/`fetch` entry points; if your installed biomcp exposes
  different tool names, those calls fall back to the public ClinicalTrials.gov /
  variant APIs via `WebFetch` (documented in
  `skills/medical-research/references/biomedical-apis.md`). PubMed retrieval is
  unaffected.
- **Open-access only for full text.** Paywalled papers are used at
  abstract-level and explicitly down-tiered ("abstract only — full text not
  verified").
- **Not a clinician.** By design — see the disclaimer above.
