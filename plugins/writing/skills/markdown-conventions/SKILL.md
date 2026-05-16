---
name: markdown-conventions
description: >-
  Use when authoring or reviewing Markdown, CommonMark, GitHub-Flavored
  Markdown, MyST, README files, docs pages, Markdown tables, fenced code
  examples, links, images, citations, or markdownlint / Prettier output.
when_to_use: >-
  Trigger for `.md` / `.markdown` files, generated docs, READMEs, markdownlint
  warnings, Prettier markdown formatting, CommonMark syntax choices, MyST
  citations, table cleanup, heading hierarchy, code-fence language tags,
  bare URLs, missing image alt text, noisy line wrapping, or citation hygiene
  in Markdown documents.
disable-model-invocation: false
user-invocable: true
allowed-tools: []
model: inherit
paths:
  - "**/*.md"
  - "**/*.markdown"
shell: bash
---

# Markdown Conventions

This skill defines project Markdown policy. It is not a Markdown tutorial.
When a local formatter or linter config exists, follow it first; this skill
fills the gaps that formatters cannot infer from intent.

The baseline syntax target is CommonMark-compatible Markdown, with
GitHub-Flavored Markdown tables where the renderer supports them. The linting
model follows `markdownlint` rule names, and formatting assumes Prettier only
when the consuming project has enabled it for Markdown.

## Non-negotiables

- Use ATX headings (`#`) only. Do not use Setext headings.
- Do not skip heading levels.
- Use fenced code blocks with a language tag. Use backtick fences unless the
  project already standardizes on tildes.
- Use inline Markdown links for prose links. Do not leave bare URLs in prose.
- Add meaningful alt text for images, diagrams, screenshots, and charts.
- Keep one blank line around headings, lists, code fences, tables, and
  horizontal rules unless a renderer-specific construct requires otherwise.
- Do not add citation-looking markup without a resolvable source. If a document
  uses `{cite}` roles or Pandoc-style `[@key]` citations, the bibliography must
  be part of the same document set.

## Fenced Code Blocks

Always use fenced code blocks with a language identifier. This maps to
`markdownlint` MD040 (`fenced-code-language`) and MD046 (`code-block-style`).
Prefer fences over indented code blocks because fences preserve intent under
copy, review, and formatter rewrites.

````text
Good:
  ```python
  x = 1
  ```

Bad - no language tag:
  ```
  x = 1
  ```

Bad - indented code block:
      x = 1
````

## Language Tags

Use the shortest unambiguous Pygments lexer name:

| Language   | Tag          |
| ---------- | ------------ |
| Python     | `python`     |
| TypeScript | `typescript` |
| JavaScript | `javascript` |
| Bash/Shell | `bash`       |
| SQL        | `sql`        |
| JSON       | `json`       |
| YAML       | `yaml`       |
| TOML       | `toml`       |
| Markdown   | `markdown`   |
| Plain text | `text`       |
| Diff       | `diff`       |
| Dockerfile | `dockerfile` |

If no syntax highlighting applies, use `text`; never leave the tag empty.

## ASCII Tables and Boxes

Align all columns precisely. Every row must have identical column widths.

```text
# Good - columns aligned, consistent padding
| Name   | Type   | Default |
| ------ | ------ | ------- |
| host   | string | -       |
| port   | int    | 8080    |

# Bad - ragged columns
| Name | Type | Default |
| --- | --- | --- |
| host | string | - |
| port | int | 8080 |
```

## Table Formatting Rules

- Header separator row uses dashes matching the column width: `------` not `---`
- Single space padding on both sides of every cell
- Use `-` for empty/not-applicable cells unless the project already uses a
  different sentinel
- Right-align numeric columns when it improves readability

## Headings

- ATX style only (`#`), never Setext (underlines). This maps to
  `markdownlint` MD003 (`heading-style`).
- One blank line before and after every heading
- No skipping levels: `##` must follow `#`, `###` must follow `##`. This maps
  to MD001 (`heading-increment`).
- No trailing punctuation on headings unless the punctuation is part of a
  product name or quoted string

## Lists

- Unordered lists use `-`, not `*` or `+`
- Ordered lists use `1.` for every item (auto-numbering)
- Indent nested lists by 4 spaces
- One blank line before and after a list block

## Links and References

- Prefer inline links `[text](url)` for one-off references
- Use reference-style links `[text][ref]` when the same URL appears more than
  once
- No bare URLs in prose. Use a named link, or wrap literal URLs in angle
  brackets when the URL itself is the content.
- Use descriptive link text. Avoid "click here", "this", and raw domain names
  unless the domain is the subject.

## Citations

Use citations when a claim depends on an external source, a current tool
behavior, an empirical result, or a quoted definition. Do not cite common
project conventions or obvious syntax choices.

- For normal Markdown, use inline links near the claim:
  `Prettier's prose wrapping depends on the proseWrap option ([Prettier](...)).`
- For MyST documents, use `{cite:p}` / `{cite:t}` or Pandoc-style `[@key]`
  citations only when the document set includes a BibTeX file configured in
  `myst.yml`.
- Prefer primary sources: specifications, official docs, standards, papers,
  or upstream repositories.
- If a citation key cannot be resolved, replace it with an inline source link
  or add the bibliography entry before shipping the document.

## Emphasis

- Bold: `**text**`, not `__text__`
- Italic: `_text_`, not `*text*`
- No emphasis on code; use backticks instead

## Inline Code

- Wrap identifiers, file paths, CLI commands, and values in single backticks
- Use fenced blocks for anything longer than one line

## Line Length and Wrapping

- Prose wraps at the project's configured Prettier `printWidth` when Prettier
  is enabled with `proseWrap: "always"`. If no formatter is configured, wrap
  prose around 80 characters by convention.
- Tables, code blocks, and URLs are exempt from line-length limits
- No trailing whitespace

## Horizontal Rules

- Use `---` on its own line, with blank lines above and below
- Never use `***` or `___`

## Images

- Always include alt text: `![description](path)`. This maps to `markdownlint`
  MD045 (`no-alt-text`).
- Never leave alt text empty
- For diagrams and screenshots, describe the information conveyed, not the file
  format: `![Latency chart showing p95 spike after deploy](latency.png)`.

## Linting

When markdownlint is configured, fix violations before committing. Run
manually:

```bash
npx markdownlint "path/to/file.md"
```

Common rule IDs this skill intentionally aligns with:

| Rule  | Meaning                              |
| ----- | ------------------------------------ |
| MD001 | Heading levels increment by one      |
| MD003 | Heading style                        |
| MD009 | No trailing spaces                   |
| MD012 | No multiple consecutive blank lines  |
| MD013 | Line length                          |
| MD022 | Blank lines around headings          |
| MD031 | Blank lines around fenced code       |
| MD034 | No bare URLs                         |
| MD040 | Fenced code blocks specify language  |
| MD045 | Images have alternate text           |
| MD046 | Code block style                     |
| MD048 | Code fence style                     |

## References

- [CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/) - baseline
  Markdown parsing model for headings, fenced code blocks, links, emphasis,
  and block structure.
- [markdownlint rules](https://github.com/DavidAnson/markdownlint/tree/main/doc)
  - source for MD001, MD003, MD009, MD012, MD013, MD022, MD031, MD034, MD040,
  MD045, MD046, and MD048.
- [Prettier options](https://prettier.io/docs/options#prose-wrap) - source for
  Markdown prose wrapping behavior.
- [MyST citations](https://mystmd.org/guide/citations) - source for `{cite}`
  roles, Pandoc-style citations, DOI citations, and bibliography config.

## Freshness

This skill is project policy over Markdown conventions, not a complete
upstream reference. When a renderer, formatter, linter, or publishing system
changes behavior, verify against primary docs. Prefer Context7 MCP for
CommonMark, markdownlint, Prettier, and MyST when available; otherwise use the
official documentation sites above.
