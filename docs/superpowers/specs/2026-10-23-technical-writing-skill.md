# Technical-writing skill: source dossier

- **Date:** 2026-10-23
- **Status:** applied and verified (section 5). Ships in v1.4.0.
- **Trigger:** The maintainer pasted a draft skill, `SKILL (1).md`, and asked
  for it to join the writing plugin, enhanced. The draft layers four standards:
  Diátaxis, the Google developer documentation style guide, ASD-STE100, and
  Kohl's Global English. This dossier is the source of truth for the skill's
  stances. Change a stance here before you change the skill.

The draft is not the Omniverse-specific `technical-writing` skill in
`omniverse/.claude/skills/`. That skill serves one Jupyter Book. Its 2026-08-01
eval showed that a strong model already makes generic quality moves. A skill
earns its tokens through rules that a model can't guess. This skill follows that
lesson: its hub holds specific, checkable rules, not general advice.

## 1. Source audit

The audit checked each layer against its primary source on 2026-10-23.

### Diátaxis

Source: [diataxis.fr](https://diataxis.fr/), by Daniele Procida. The content is
CC BY-SA 4.0.

- Confirmed: tutorials say "we", promise the result, and avoid "you will learn".
  Every step shows a visible result, and explanation shrinks to a link. How-to
  guides take task titles and conditional imperatives. Explanation offers
  opinion, passes the "about" test, and anchors on a why question.
- Corrected: the draft said reference has "no instruction". Diátaxis lists "You
  must not apply b unless c" as reference language, with "Provide warnings where
  appropriate", and calls examples valuable. The skill now puts constraints,
  warnings, and a usage example in reference, and keeps procedures out.
- Corrected: the draft used "the compass" without saying what it is. The compass
  is the pair of questions, and Diátaxis applies it to whole documents and to
  single sentences.

### Google developer documentation style guide

Source: [developers.google.com/style](https://developers.google.com/style). The
content is CC BY 4.0.

- Collision: Google says "Use second person: 'you' rather than 'we'". Diátaxis
  tutorials say "we". Precedence resolves it (stance S4).
- Added from the procedures page: the location before the action, the result
  after it, and "Optional:" before an optional step.
- Added from the word list: "because", not "since" or "as". "After", not "once".
  "Although", not "while", for a contrast. Avoid "currently", "new", "now", and
  "latest". Use inclusive terms such as "allowlist" and "placeholder".
- Added from the headings and lists pages: no links in headings, and no list of
  one item.
- Added from the global-audience page: at most two nouns in front of a noun, and
  phrasal verbs kept whole or replaced.
- House rules, not Google rules: Google allows em dashes without spaces, and it
  says only "If possible, avoid using semicolons". The skill bans both. The ban
  follows Global English, and em dashes are also a machine-writing tell. The
  skill keeps the bans and names them as house rules.
- Not adopted: Google's "avoid code items in headings". Reference pages name
  code in their headings.

### ASD-STE100

Source: Issue 9, released 2025-01-15, with 53 writing rules. The specification
is free from ASD. The asd-ste100.org site returned 403 to the fetch, so the
audit confirmed the rules through the Wikipedia summary and the STEMG release
notes. The skill cites no rule numbers for that reason.

- Confirmed: 20 words for an instruction, 25 for other sentences, and one
  instruction per sentence. Also confirmed: the active voice, no omitted words,
  and "-ing" forms only in technical names. The draft softens the last rule to
  "where you can", and the skill keeps that.
- Added: one topic and at most six sentences per paragraph, and a vertical list
  for complex text.
- Corrected: the draft's warning example ("If hot oil touches your skin,
  injuries can occur") showed a condition but no step that it guards. The new
  example is a software warning placed before its step.

### Global English

Source: John R. Kohl, _The Global English Style Guide_ (SAS Institute, 2008).
The book is not online. A review confirms its chapters on syntactic cues and its
rule that keeps phrasal verbs whole. Google's global-audience, slashes, and
optional-plurals pages corroborate the rules for "only", relative pronouns,
antecedents, one term per concept, slashes, and "(s)". The rest stay as the
draft stated them.

### Commits, PRs, and changelogs

Sources: the Git project's SubmittingPatches ("Describe your changes well"),
Google engineering practices ("Writing good CL descriptions"), Chris Beams ("How
to Write a Git Commit Message", 2014), and Keep a Changelog 1.1.0. Git
lowercases the word after an "area: " prefix, and Beams capitalizes the subject.
The skill follows the repo's convention first.

## 2. Diagnosis of the draft

1. **No automatic trigger.** `disable-model-invocation: true` hides the skill
   from the model, yet the description says to use it "when writing or reviewing
   docs". Only `/technical-writing` could run it.
2. **A missing dependency.** "Apply the unslop skill" points at a skill that
   exists neither in this marketplace nor on this machine.
3. **Another codebase's rules.** "Indent code snippets with tabs" contradicts
   this repo's Prettier config. "Swarm logs" and the proto budget come from
   somewhere else.
4. **Rules that collide with no tiebreak.** Tutorial "we" against "you". "Keep
   the long sentence" against the 25-word limit. "Cut every word" against "keep
   'that'".
5. **An undefined term:** "the compass".
6. **A reference rule that was too strict** (section 1).
7. **Breaks of its own rules.** "A long word has to buy its length" is a
   metaphor. "Opinion is allowed" is passive. "Each title should tolerate" uses
   "should". Two mode paragraphs ran to eight and nine sentences.
8. **Missing practice.** Nothing said to verify a documented command, the
   costliest doc failure for an agent. The draft had no review procedure, no
   output shape for findings, and no commit or PR template. Nothing limited how
   much of a doc an edit may touch.
9. **No mechanical check,** although a pattern can catch most of the rules in
   its last three layers.

## 3. Stances

- **S1. Model-invocable.** `disable-model-invocation: false`, with a
  trigger-first description and a directive constraint: "Do not draft or review
  documentation without loading this skill first." The 2026-07-31 skill-quality
  audit measured that shape as the strongest for activation. The description and
  `when_to_use` total 751 characters.
- **S2. The skill owns its tells catalog** in `references/slop-patterns.md`. A
  writer proposes a new offender in the reply and never edits the skill during a
  task.
- **S3. Precedence:** the repo's style guide, then exact strings, then mode
  rules, then clarity over brevity. An existing file's format counts as the
  repo's convention. This repo's CHANGELOG keeps its em-dash separator for that
  reason.
- **S4. Tutorials say "we",** as Diátaxis prescribes, despite Google's "you".
- **S5. "Long" means up to about 25 words,** so the rhythm rule and the STE
  limit agree.
- **S6. How-to titles** take `How to <task>` or the bare `<Task>`, with one form
  per doc set.
- **S7. Reference carries** constraints, warnings, and a usage example, and
  never procedures.
- **S8. Prove facts, within a safety bound.** Run read-only, local, or scratch
  commands. For a destructive or production command, check the syntax, and say
  that it wasn't run.
- **S9. Licensing.** Diátaxis is CC BY-SA 4.0, and this plugin is MIT, so the
  skill states Diátaxis concepts in its own words. It quotes only the short
  phrases that the draft already used. The skeletons and leak tables are
  original. Google's guide is CC BY 4.0, and the hub's Sources section credits
  it.
- **S10. Checker scope.** `lint_prose.py` checks patterns only. Errors are rules
  with few false positives, and warnings need a person. Code, URLs, and quoted
  text are mentions, so the checker skips them. It exits 1 on errors, or on
  warnings with `--strict`.
- **S11. No `paths` frontmatter.** The api-design dossier records that `paths`
  is inert for plugin skills, and that it hides a skill-directory install until
  the user touches a matching file.
- **S12. A hub and references.** The hub stays under 500 lines and about 5,000
  tokens. Skeletons, word lists, the tells catalog, templates, and examples load
  on demand.
- **S13. Routing.** `measured-persuasion` owns arguments, `markdown-conventions`
  owns syntax, and the `docstrings` skills own the structure of API docs. The
  repo's ADR template owns ADR sections. The skill routes to
  `documentation-and-adrs` only when it is present, because v1.4.0 doesn't ship
  that byte-exact import, which stays unedited. Both editable siblings now point
  back to this skill.

## 4. File map

```text
plugins/writing/skills/technical-writing/
  SKILL.md                      hub: layers, precedence, workflow, review template
  references/modes.md           skeletons, leak signs, a map from doc type to mode
  references/word-list.md       swaps, words with two meanings, inclusive terms
  references/slop-patterns.md   the catalog of machine-writing tells
  references/commits-and-prs.md commit, PR, and changelog templates
  references/examples.md        before-and-after pairs for each layer and mode
  scripts/lint_prose.py         the pattern checker, with --self-test
plugins/writing/evals/
  README.md
  technical-writing/evals.json      six behavior scenarios, 41 assertions
  technical-writing/triggers.json   20 trigger queries
```

## 5. Verification

Run on 2026-10-23:

- `lint_prose.py --self-test`: 52 of 52 pass on Python 3.14.0 and on the macOS
  system Python, 3.9.6.
- The checker reports 0 errors and 0 warnings on the hub and the five
  references. Prettier (`--tab-width 2 --prose-wrap always --print-width 80`)
  and markdownlint, with the repo config, both pass.
- A precision sample on `README.md`, `plugins/unknowns/README.md`, and
  `markdown-conventions/SKILL.md` found no false positives. Every sampled hit
  breaks a rule that the skill states.
- `claude plugin validate .` and `claude plugin validate plugins/writing` pass.
  The two plugin warnings predate this change: no icon, and a gitignored
  `.DS_Store`.
- `make sync-codex` changed only `plugins/writing/.codex-plugin/plugin.json` and
  `.agents/plugins/marketplace.json`.

## 6. Open items

- Run the evals. The behavior scenarios and the trigger queries exist, but
  nobody has run them yet. Use the skill-creator eval loop with a no-skill
  baseline.
- Consider a Vale package that mirrors the house rules, for repos that run Vale
  in CI.
- Keep three checks as judgment calls: noun stacks, mixed modes, and one thing
  under several names. No pattern catches them, so the evals' judgment
  assertions cover them.
