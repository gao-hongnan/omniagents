# Biomedical Sources & Tools

Retrieve **only** from these structured sources. Never cite from model memory
or a general web page — if you did not retrieve it from a resolvable source,
you cannot claim it (the Iron Law). The plugin ships two MCP servers; prefer
their tools, and fall back to `WebFetch` against the public APIs when a tool is
unavailable.

## Primary: the `pubmed` MCP server (`@cyanheads/pubmed-mcp-server`)

The workhorse. It chains PubMed → Europe PMC → Unpaywall for full-text, plus
ID conversion and formatted citations. Ten tools (prefix
`mcp__plugin_omniagents-research_pubmed__`):

| Tool | Use it for |
| --- | --- |
| `pubmed_search_articles` | PubMed term search → PMIDs (the existence-of-record source of truth) |
| `pubmed_europepmc_search` | Europe PMC search incl. **preprints (medRxiv/bioRxiv)** and full-text/section hits |
| `pubmed_fetch_articles` | PMID → title, abstract, metadata (note: abstract, **not** full text) |
| `pubmed_fetch_fulltext` | Open-access full text via PMC / Europe PMC / Unpaywall (where legally available) |
| `pubmed_format_citations` | Render APA/MLA/Vancouver/BibTeX — never hand-format a reference |
| `pubmed_find_related` | Citation-graph neighbours of a key paper |
| `pubmed_lookup_citation` | Resolve a loose reference to a PMID (existence check) |
| `pubmed_convert_ids` | PMID ↔ DOI ↔ PMCID conversion (build resolver URLs) |
| `pubmed_lookup_mesh` | MeSH terms to sharpen a search |
| `pubmed_spell_check` | Fix a query that returns nothing |

**Quote-and-locate**: prefer `pubmed_fetch_fulltext` so the `quote` field is a
real sentence with a `locator` (section/paragraph). When only the abstract is
available, you may quote the abstract but **down-tier and note "abstract only —
full text not verified"**.

## Secondary: the `biomcp` MCP server (`biomcp-python`)

For trials, genomics, variants, and drug/disease records — the genomics-heavy
sub-questions PubMed does not serve well. Tools are prefixed
`mcp__plugin_omniagents-research_biomcp__`. BioMCP exposes a unified grammar;
the public MCP entry points are typically `search` and `fetch` (plus
entity helpers). Use it for ClinicalTrials.gov queries (trial status/phase),
variant/gene lookups, and disease records. If a biomcp tool name does not
resolve in your tool list, fall back to the public APIs below via `WebFetch`.

## Fallback public APIs (via `WebFetch` / `Bash` curl)

| Role | Endpoint | Access notes |
| --- | --- | --- |
| Existence of record | NCBI E-utilities `esearch`/`efetch`/`esummary` | free; 3 rps, 10 with `NCBI_API_KEY`; ESearch caps at 10k IDs |
| Full text + sections + preprints | Europe PMC REST `/search`, `/{PMCID}/fullTextXML` | no auth, ~10 rps; JATS XML for the PMC OA subset |
| Citation graph + quote snippets | Semantic Scholar Graph `/paper/search`, `/snippet/search` | keyless is throttled; `S2_API_KEY` gives a dedicated quota |
| Cross-publisher metadata + OA status | OpenAlex `/works` | **API key REQUIRED since 2026-02-13** (the `mailto` polite pool was removed) — fail loudly if missing |
| DOI metadata + retraction status | Crossref `/works` | free polite pool via `mailto`; rate-limit headers changed 2025-12-01 — read them, don't hardcode |
| Legal OA full text | Unpaywall `/v2/{DOI}` | email **mandatory** (`UNPAYWALL_EMAIL`); returns `url_for_pdf` only when OA exists |
| Trials | ClinicalTrials.gov v2 `/api/v2/studies` | no key; set `pageSize` explicitly (≤1000); record status/phase |
| Preprints | medRxiv/bioRxiv `/details/...` | no key; **always flag as not-yet-peer-reviewed** |

## Resolver URLs (deterministic — build these for every citation)

- DOI → `https://doi.org/<doi>`
- PMID → `https://pubmed.ncbi.nlm.nih.gov/<pmid>/`
- PMCID → `https://www.ncbi.nlm.nih.gov/pmc/articles/<pmcid>/`
- NCT → `https://clinicaltrials.gov/study/<nct>`

## Retrieval discipline

- **Search broad, then narrow.** Start with MeSH-sharpened terms; widen on zero
  hits (`pubmed_spell_check`), narrow on flooding.
- **≥2 independent sources** per non-authoritative claim; 1 is acceptable only
  for a systematic review or guideline.
- **Stop** when novelty is exhausted or you hit the search cap (~30–60 searches
  per sub-question). Record the count in the audit.
- **Down-tier** preprints, abstract-only, and retracted sources; never silently
  drop a retraction — surface it.
- **Dedupe** by casefolded DOI + lowercased statement before reporting.
