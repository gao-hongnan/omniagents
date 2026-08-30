# Skill Quality Audit — omniagents (2026-07-31)

Three parallel Fable 5 research agents (official docs · GitHub ecosystem · practitioner
lessons) plus a local structural audit of all repo skills. This dossier records the
distilled rulebook, the audit verdict, actions taken in-session, and the prioritized
backlog. Citations inline; full source index at the end.

## 1. The rulebook (distilled, with load-bearing sources)

### Delivery mechanics before prose

- Claude Code appends `when_to_use` to `description` in the skill listing and truncates
  the pair at **1,536 chars per skill**; the whole listing shares a budget of **~1% of
  context (~15,000 chars default)** — overflow silently drops descriptions,
  least-invoked first. Knobs: `skillListingBudgetFraction`,
  `SLASH_COMMAND_TOOL_CHAR_BUDGET`, per-entry `skillListingMaxDescChars`
  ([Claude Code skills docs](https://code.claude.com/docs/en/skills)).
- Portable spec limits: `name` 1–64 chars (lowercase-hyphen, must equal directory name),
  `description` 1–1024 chars, no XML tags, no "anthropic"/"claude" in names
  ([agentskills.io spec](https://agentskills.io/specification)).
- `allowed-tools` is now a per-turn permission **grant**, not a restriction — the 2025
  mental model is obsolete; `disallowed-tools` restricts. `paths`, `shell`,
  `when_to_use`, `context: fork`, `agent`, `background`, `hooks`, `effort` are all real
  Claude-Code-only fields; portable skills should stick to spec fields.
- Practitioner rule #1 ([Jesse Vincent, Superpowers v4.3.0](https://blog.fsck.com/2026/02/12/superpowers-v4-3-0/)):
  verify the skill is *delivered* (budget, YAML parse, hooks firing) before rewording
  prose. His system once ran "installed, configured, full of carefully written skills,
  and completely inert" because a SessionStart hook ran `async: true`.

### Descriptions are the product

- Baseline autonomous activation measured at **~50%** across four independent studies
  (Vercel Jan 2026; Seleznov Feb 2026, 650 trials; Zecheng Mar 2026; Sogl May 2026).
  "Spend 70% of your SKILL.md iteration time on the description field."
- What works: trigger-direction ("Use when…", concrete symptoms, error messages, file
  types, tool names) **without summarizing the workflow** — workflow-summarizing
  descriptions let strong models "wing it" instead of reading the skill (obra
  writing-skills; observed as an Opus 4.5 regression). Directive phrasing with a
  negative constraint ("do not X directly — use this skill first") measured 20× odds of
  activation (Seleznov, p < 0.0001).
- Official shape: third-person capability sentence + "Use when …" trigger sentence
  ([platform best-practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)).
- For side-effectful workflows: `disable-model-invocation: true` and let the user type it.

### Bodies

- < 500 lines / < 5k tokens; split the rest into `references/` (one level deep,
  descriptively named, TOC on any file > 100 lines, per-domain partitioning so only the
  relevant file loads). Body persists in context all session in Claude Code; on
  compaction only the first 5k tokens per skill re-attach (25k shared) — long monoliths
  get truncated exactly when the session is longest.
- "Claude is already smart": cut anything the model already knows; challenge every
  paragraph's token cost. ETH Zurich (Feb 2026): unvetted context files averaged +4%
  quality for +20% cost; auto-generated ones were net-negative.
- Match prose form to observed failure type (obra writing-skills): rule violations →
  prohibition + rationalization table + red flags; wrong output shape → recipe;
  omissions → REQUIRED template slots; conditional behavior → observable predicates.
  Prohibitions backfire on shaping problems; recipes backfire on rule violations.
- Scripts are deterministic anchors: bundle what agents keep reinventing; scripts solve
  errors rather than defer; no voodoo constants; never interactive.

### Evals

- Official method is eval-first: ≥3 scenarios, baseline without the skill, minimal
  instructions to close observed gaps, iterate
  ([best-practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices);
  [agentskills evaluating-skills](https://agentskills.io/skill-creation/evaluating-skills)).
- Superpowers RED/GREEN: no skill (or skill edit) without first watching an agent fail
  without it; capture rationalizations verbatim; pressure-test with 3+ stacked
  pressures; fresh subagent per sample + control + 5 reps.
- Kill zero-uplift sections: Sogl's per-assertion A/B found a section "paying tokens
  for nothing"; skills regress on model bumps — re-benchmark then.

## 2. Audit verdict

**Overall: prose quality is well above ecosystem norms** — imperative, why-explaining,
cross-referencing without duplication, provenance sections, dossier-driven authoring
(`docs/superpowers/specs/`). `codebase-design` is an exemplar (vocabulary → decision
flow → NOT-covered → rejected framings → provenance). The gaps are **structural and
mechanical**, not prose.

### Findings (prioritized)

| # | Severity | Finding | Evidence |
| --- | --- | --- | --- |
| F1 | HIGH | **Global listing budget overflow risk**: repo-wide effective listing (desc + `when_to_use`) is **22,421 chars vs ~15,000 default budget** — with the full suite installed, least-invoked skills silently lose their descriptions | Top entries: `python/testing` 1,626 (fixed in-session → ~1,465), `writing/blueprint` 1,109, `ts/testing` 1,024, `ts/typings` 991, `grill` 906 |
| F2 | HIGH | **Per-skill cap exceeded**: `python/testing` was over the 1,536-char per-skill truncation cap — tail keywords (deepeval, pytest config) were invisible | Fixed in-session by de-duplicating `when_to_use` against `description` |
| F3 | MED | **Monolith bodies over/near the 500-line bar, no progressive disclosure**: `python/library-patterns` 614L, `ts/library-patterns` 580L (over); `python/performance` 464L, `python/pydantic` 400L, `reviewer/review-contract` 405L, `drawio` 374L (near) | Compaction re-attach truncates at 5k tokens; mutually-exclusive contexts (sync/async/streaming/pagination) load together |
| F4 | MED | **No trigger or output evals anywhere except `reviewer/`**: authoring is dossier-driven but nothing measures activation or uplift | Only `plugins/reviewer/evals/evals.json` exists; no `evals/` in any skill |
| F5 | MED (partial 2026-08-30) | **Giant reference files without TOCs**: `system/reliability.md` 2,128L, `system/communication.md` 2,081L, `software/anti-patterns.md` 1,734L, `software/functional.md` 1,403L, `software/architectural.md` 1,322L, `software/concurrency.md` 1,252L, `system/cloud.md` 1,726L, terraform refs 375–572L, typings canonical-examples 426–458L | Official: TOC above 100 lines so `head -100` partial reads reveal scope. TOCs added 2026-08-30 to `software/anti-patterns.md` and `typings/canonical-examples.md` (see `specs/2026-08-30-python-production-bar.md`) |
| F6 | LOW | **Frontmatter inconsistency (4 families)** + explicit-default noise: `disable-model-invocation: false`, `user-invocable: true`, `model: inherit`, `shell: bash`, `allowed-tools: []` restate defaults; `allowed-tools: []` grants nothing under 2026 semantics | ts/docstrings and design-patterns skills carry none of the house set; ts/testing + ts/typings carry only `paths` |
| F7 | LOW | `ts/docstrings` description is thin (238 chars, no `when_to_use`) vs sibling `python/docstrings` (743 effective) — likely under-triggers | Description-length asymmetry between the two docstrings skills |
| F8 | FIXED | `tech-lead` plugin absent from `marketplace.json` → never shipped | Entry added in-session; `claude plugin validate` passes |
| F9 | NOTE | No CI step validates per-skill spec compliance (name/desc limits, name==dirname) | `make validate` covers marketplace manifest only |

### What is deliberately fine

- Reviewer skills stay monolithic and model-invocable: they are **preloaded whole** into
  specialist subagents via `skills:` frontmatter — splitting saves nothing and
  `disable-model-invocation: true` would break preloading (docs confirm: preload is
  blocked for disable-model-invocation skills).
- `when_to_use` house convention is a real, supported field and matches the best-evidenced
  practitioner pattern (trigger-direction). Keep it — but put it on a budget (F1).
- `grill` stays project-local by design; house metadata cost (~5.6k tokens listing-wide)
  is a conscious spend, mitigated by per-plugin installation.

## 3. Actions taken in-session

1. **Imported 7 exceptionally-written skills** (byte-exact, each skill dir ships upstream
   `LICENSE` + `ATTRIBUTION.md` with repo/commit/changes):
   - `plugins/workflow` (**new**, omniagents-workflow): `systematic-debugging`,
     `test-driven-development`, `verification-before-completion` (MIT,
     [obra/superpowers](https://github.com/obra/superpowers) @44c9b2d);
     `git-workflow-and-versioning` (MIT,
     [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) @7829ffd)
   - `plugins/sre` (**new**, omniagents-sre): `observability-and-instrumentation` (MIT,
     addyosmani @7829ffd; repo-root checklist relocated into skill-local `references/`
     so the existing link resolves)
   - `plugins/data` (**new**, omniagents-data): `supabase-postgres-best-practices`
     (MIT, [supabase/agent-skills](https://github.com/supabase/agent-skills) @1207767;
     full 34-file rule set)
   - `plugins/writing`: `documentation-and-adrs` (MIT, addyosmani @7829ffd)
2. **Registered** the 3 new plugins + the stranded `omniagents-tech-lead` in
   `marketplace.json`; `claude plugin validate` passes.
3. **Fixed F2**: trimmed `python/testing` `when_to_use` by deleting only items duplicated
   verbatim in `description` (snapshot, coverage, OTel-span, hypothesis-stateful,
   type-level phrasing); effective entry now ~1,465 < 1,536.
4. Not released: everything above is invisible to installed marketplaces until
   `make release VERSION=… ` + push (cache keys on version).

## 4. Backlog (recommended, not applied)

| Priority | Work | Notes |
| --- | --- | --- |
| P1 | **Metadata diet**: trim `when_to_use` on the top ~10 chattiest skills toward ≤ 800 effective chars each; target full-suite total ≤ 15k | Semantic edits — consult each skill's dossier; front-load the key use case (truncation is tail-first) |
| P2 | **Split the two library-patterns monoliths** into hub + `references/{sync,async,streaming,errors,pagination}.md` per the domain-partition pattern | Mirrors testing-skill hub+references restructure shipped in v0.10.0 |
| P3 | **Add TOCs** to every reference file > 100 lines (14 files, mostly design-patterns) | Mechanical; script-able |
| P4 | **Adopt skill-creator eval loop** for the 5 most-invoked skills: 3 scenarios + baseline, then 20-query trigger eval (60/40 split, 3 runs/query) | `/plugin install skill-creator@claude-plugins-official`; wire `quick_validate.py`/`skills-ref validate` into `make validate` (F9) |
| P5 | **Normalize frontmatter**: drop explicit-default keys (`disable-model-invocation: false`, `user-invocable: true`, `model: inherit`, `shell: bash`, `allowed-tools: []`); bring `ts/docstrings` up to house description shape (F7) | Also decide per skill whether `paths` is doing real work |
| P6 | **Steal the compliance devices** from the imported superpowers skills (rationalization tables, red-flags lists, hard gates) into the skills that enforce discipline under pressure — candidates: parcae `poiesis`, `review` pipeline entry points | Form-matches-failure-type: gates for discipline failures only |
| P7 | Consider next imports: sentry `gha-security-review` (Apache-2.0; placement decision reviewer-vs-iac + contract adaptation), anthropics `incident-response` (Apache-2.0; needs CONNECTORS.md adaptation) into `sre`, `hallmark` (MIT) / vercel `react-best-practices` (Apache-2.0) if a frontend plugin materializes | Trail of Bits security skills are CC-BY-SA — **do not import**; author any PBT skill from primary sources instead |

## 5. Ecosystem notes (from the survey)

- Best collections by quality: obra/superpowers (MIT), addyosmani/agent-skills (MIT),
  anthropics/skills (Apache-2.0 except proprietary docx/pdf/pptx/xlsx),
  anthropics/knowledge-work-plugins (Apache-2.0), getsentry/skills (Apache-2.0),
  supabase/agent-skills (MIT), cloudflare/skills (Apache-2.0),
  trailofbits/skills (CC-BY-SA — read, don't copy). openai/skills has **no license** —
  unusable. Community mega-collections show farmed-star/bulk-generation red flags; a
  Snyk audit (Feb 2026) found 36% of sampled community skills had security flaws — import
  only from named authors/orgs, read every file.
- Our remaining gaps after this import round: CI/CD authoring, incident response,
  security *engineering* (proactive), property-based testing, frontend/react.
- Remember the counter-signal: "skills are context you build from repeated needs, not
  capabilities you download" (Lisa Ross). Imports above were selected because they
  encode process disciplines we repeatedly needed and match the house bar; resist bulk
  importing beyond that.

## 6. Source index

Official: [platform best-practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) ·
[agentskills.io spec](https://agentskills.io/specification) ·
[optimizing-descriptions](https://agentskills.io/skill-creation/optimizing-descriptions) ·
[evaluating-skills](https://agentskills.io/skill-creation/evaluating-skills) ·
[Claude Code skills](https://code.claude.com/docs/en/skills) ·
[engineering blog](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) ·
[anthropics/skills](https://github.com/anthropics/skills).
Practitioners: [Simon Willison skills tag](https://simonwillison.net/tags/skills/) ·
[Jesse Vincent Superpowers series](https://blog.fsck.com/2025/10/09/superpowers/) ·
[Superpowers v4.3.0 postmortem](https://blog.fsck.com/2026/02/12/superpowers-v4-3-0/) ·
[Vercel eval study](https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals) ·
Seleznov (Medium, Feb 2026) · Zecheng (dev.to, Mar 2026) · Sogl (dev.to, May 2026) ·
Fernandez (tessl.io, Mar 2026) · HN threads 45607117 / 45619537 / 46809708 / 48289950.
